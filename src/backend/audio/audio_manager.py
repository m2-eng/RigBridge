"""
Audio-Manager für RigBridge.

Verwaltet ALSA-Audio-Streams für IC-905 USB-Audio (RX/TX) via sounddevice.
sounddevice nutzt PortAudio unter Linux direkt mit ALSA ohne PulseAudio.

IC-905 USB-Audio-Zuordnung:
  Capture  (pcmC0D0c): RX-Audio des Funkgeräts → erscheint am Host als Mikrofon
  Playback (pcmC0D0p): TX-Audio zum Funkgerät  → erscheint am Host als Lautsprecher
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

try:
    import sounddevice as sd
    import numpy as np
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False

from ..config.logger import RigBridgeLogger
from ..config.settings import ConfigManager

logger = RigBridgeLogger.get_logger(__name__)

_DTYPE_MAP: Dict[str, str] = {
    'S16_LE': 'int16',
    'S32_LE': 'int32',
    'F32_LE': 'float32',
}

_RX_BLOCKSIZE = 1024   # Frames pro Callback (~21 ms bei 48 kHz)
_RX_QUEUE_MAX = 50     # Chunks im Broadcast-Queue (Backpressure)


def _parse_device(device_str: str) -> Any:
    """Parst einen Gerät-Bezeichner: Integer-Index oder Name-String."""
    if not device_str:
        return None
    try:
        return int(device_str)
    except ValueError:
        return device_str


def _parse_dtype(fmt: str) -> str:
    return _DTYPE_MAP.get(fmt.upper(), 'int16')


class AudioManager:
    """
    Verwaltet IC-905 USB-Audio-Streams.

    RX-Stream: sounddevice.InputStream → WebSocket-Broadcast an alle Clients.
    TX-Stream: WebSocket-Empfang → sounddevice.OutputStream (exklusive Nutzung).
    """

    def __init__(self) -> None:
        self._rx_stream: Optional[Any] = None
        self._tx_stream: Optional[Any] = None
        self._rx_clients: Set[Any] = set()
        self._tx_lock: asyncio.Lock = asyncio.Lock()
        self._rx_running: bool = False
        self._tx_running: bool = False
        self._last_error: Optional[str] = None
        self._rx_queue: Optional[asyncio.Queue] = None
        self._rx_broadcast_task: Optional[asyncio.Task] = None

    # =========================================================================
    # Device Discovery
    # =========================================================================

    @staticmethod
    def is_available() -> bool:
        return SOUNDDEVICE_AVAILABLE

    @staticmethod
    def list_devices() -> List[Dict[str, Any]]:
        """Listet alle via PortAudio/ALSA sichtbaren Audio-Geräte."""
        if not SOUNDDEVICE_AVAILABLE:
            return []
        try:
            result = []
            for i, dev in enumerate(sd.query_devices()):
                result.append({
                    'index': i,
                    'name': dev['name'],
                    'max_input_channels': dev['max_input_channels'],
                    'max_output_channels': dev['max_output_channels'],
                    'default_samplerate': dev['default_samplerate'],
                    'supports_capture': dev['max_input_channels'] > 0,
                    'supports_playback': dev['max_output_channels'] > 0,
                })
            return result
        except Exception as e:
            logger.error(f'Fehler beim Auflisten der Audio-Geräte: {e}')
            return []

    # =========================================================================
    # Status
    # =========================================================================

    def get_status(self) -> Dict[str, Any]:
        config = ConfigManager.get()
        audio_cfg = config.audio
        return {
            'enabled': audio_cfg.enabled,
            'sounddevice_available': SOUNDDEVICE_AVAILABLE,
            'rx_active': self._rx_running,
            'tx_active': self._tx_running,
            'rx_clients_connected': len(self._rx_clients),
            'capture_device': audio_cfg.capture_device,
            'playback_device': audio_cfg.playback_device,
            'sample_rate': audio_cfg.sample_rate,
            'format': audio_cfg.format,
            'codec': audio_cfg.codec,
            'last_error': self._last_error,
        }

    # =========================================================================
    # RX Stream (IC-905 → Netzwerk-Clients)
    # =========================================================================

    async def start_rx(self) -> None:
        """Startet RX-Capture vom IC-905 und beginnt Broadcasting."""
        if not SOUNDDEVICE_AVAILABLE:
            raise RuntimeError('sounddevice ist nicht installiert')
        if self._rx_running:
            return

        config = ConfigManager.get()
        audio_cfg = config.audio
        device = _parse_device(audio_cfg.capture_device)
        samplerate = audio_cfg.sample_rate
        dtype = _parse_dtype(audio_cfg.format)

        self._rx_queue = asyncio.Queue(maxsize=_RX_QUEUE_MAX)
        loop = asyncio.get_event_loop()

        def _rx_callback(indata: Any, frames: int, time_info: Any, status: Any) -> None:
            if status:
                logger.debug(f'RX Audio Callback Status: {status}')
            chunk = bytes(indata)
            try:
                loop.call_soon_threadsafe(self._rx_queue.put_nowait, chunk)
            except asyncio.QueueFull:
                pass  # Verwerfen bei Überlast (Backpressure)

        try:
            self._rx_stream = sd.InputStream(
                device=device,
                samplerate=samplerate,
                channels=1,
                dtype=dtype,
                blocksize=_RX_BLOCKSIZE,
                callback=_rx_callback,
            )
            self._rx_stream.start()
            self._rx_running = True
            self._last_error = None
            logger.info(
                f'RX Audio-Stream gestartet '
                f'(Gerät={audio_cfg.capture_device!r}, {samplerate} Hz, {audio_cfg.format})'
            )
            self._rx_broadcast_task = asyncio.create_task(self._rx_broadcast_loop())
        except Exception as e:
            self._last_error = str(e)
            self._rx_running = False
            logger.error(f'RX Audio-Stream konnte nicht gestartet werden: {e}')
            raise

    async def stop_rx(self) -> None:
        """Stoppt RX-Capture-Stream und Broadcast-Task."""
        self._rx_running = False

        if self._rx_broadcast_task:
            self._rx_broadcast_task.cancel()
            try:
                await self._rx_broadcast_task
            except asyncio.CancelledError:
                pass
            self._rx_broadcast_task = None

        if self._rx_stream:
            try:
                self._rx_stream.stop()
                self._rx_stream.close()
            except Exception as e:
                logger.warning(f'Fehler beim Stoppen des RX-Streams: {e}')
            self._rx_stream = None

        logger.info('RX Audio-Stream gestoppt')

    async def _rx_broadcast_loop(self) -> None:
        """Verteilt RX-Audio-Chunks an alle verbundenen WebSocket-Clients."""
        while self._rx_running:
            try:
                chunk = await asyncio.wait_for(self._rx_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            if not self._rx_clients:
                continue

            dead: Set[Any] = set()
            for ws in self._rx_clients.copy():
                try:
                    await ws.send_bytes(chunk)
                except Exception:
                    dead.add(ws)
            self._rx_clients -= dead

    def add_rx_client(self, ws: Any) -> None:
        self._rx_clients.add(ws)
        logger.debug(f'RX-Client verbunden (gesamt: {len(self._rx_clients)})')

    def remove_rx_client(self, ws: Any) -> None:
        self._rx_clients.discard(ws)
        logger.debug(f'RX-Client getrennt (gesamt: {len(self._rx_clients)})')

    # =========================================================================
    # TX Stream (Netzwerk-Client → IC-905)
    # =========================================================================

    async def start_tx(self) -> None:
        """Startet TX-Playback-Stream zum IC-905."""
        if not SOUNDDEVICE_AVAILABLE:
            raise RuntimeError('sounddevice ist nicht installiert')
        if self._tx_running:
            return

        config = ConfigManager.get()
        audio_cfg = config.audio
        device = _parse_device(audio_cfg.playback_device)
        samplerate = audio_cfg.sample_rate
        dtype = _parse_dtype(audio_cfg.format)

        try:
            self._tx_stream = sd.OutputStream(
                device=device,
                samplerate=samplerate,
                channels=1,
                dtype=dtype,
                blocksize=_RX_BLOCKSIZE,
            )
            self._tx_stream.start()
            self._tx_running = True
            self._last_error = None
            logger.info(
                f'TX Audio-Stream gestartet '
                f'(Gerät={audio_cfg.playback_device!r}, {samplerate} Hz, {audio_cfg.format})'
            )
        except Exception as e:
            self._last_error = str(e)
            self._tx_running = False
            logger.error(f'TX Audio-Stream konnte nicht gestartet werden: {e}')
            raise

    async def stop_tx(self) -> None:
        """Stoppt TX-Playback-Stream."""
        self._tx_running = False
        if self._tx_stream:
            try:
                self._tx_stream.stop()
                self._tx_stream.close()
            except Exception as e:
                logger.warning(f'Fehler beim Stoppen des TX-Streams: {e}')
            self._tx_stream = None
        logger.info('TX Audio-Stream gestoppt')

    async def write_tx(self, data: bytes) -> None:
        """Schreibt PCM-Daten in den TX-Playback-Stream."""
        if not self._tx_running or not self._tx_stream:
            raise RuntimeError('TX-Stream ist nicht aktiv')
        config = ConfigManager.get()
        dtype = _parse_dtype(config.audio.format)
        array = np.frombuffer(data, dtype=dtype)
        await asyncio.get_event_loop().run_in_executor(None, self._tx_stream.write, array)

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def start(self) -> None:
        """Startet Audio-Streaming gemäß Konfiguration."""
        config = ConfigManager.get()
        if not config.audio.enabled:
            logger.info('Audio-Streaming ist in der Konfiguration deaktiviert')
            return
        if not SOUNDDEVICE_AVAILABLE:
            logger.warning('sounddevice nicht verfügbar – Audio-Streaming wird übersprungen')
            return
        try:
            await self.start_rx()
        except Exception as e:
            logger.error(f'RX-Stream konnte nicht gestartet werden: {e}')

    async def stop(self) -> None:
        """Stoppt alle laufenden Audio-Streams."""
        await self.stop_rx()
        await self.stop_tx()
