"""
Audio-API-Routen für RigBridge.

REST-Endpunkte:
  GET  /api/audio/devices  – verfügbare ALSA-Geräte auflisten
  GET  /api/audio/status   – Stream-Zustand abfragen
  GET  /api/audio/config   – Audio-Konfiguration lesen
  POST /api/audio/start    – Streams starten
  POST /api/audio/stop     – Streams stoppen

WebSocket-Endpunkte:
  WS   /api/audio/rx  – IC-905 RX → Client (Broadcast)
  WS   /api/audio/tx  – Client → IC-905 TX (exklusiv)
"""

from dataclasses import asdict
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from ..config.logger import RigBridgeLogger
from ..config.settings import ConfigManager
from .audio_manager import AudioManager, SOUNDDEVICE_AVAILABLE

logger = RigBridgeLogger.get_logger(__name__)

# Singleton – wird bei App-Start durch create_audio_router() initialisiert
_audio_manager: Optional[AudioManager] = None


def get_audio_manager() -> AudioManager:
    global _audio_manager
    if _audio_manager is None:
        _audio_manager = AudioManager()
    return _audio_manager


def create_audio_router() -> APIRouter:
    """Erstellt und konfiguriert den Audio-API-Router."""
    router = APIRouter(prefix='/audio', tags=['Audio'])

    @router.get('/devices', summary='Verfügbare Audio-Geräte auflisten')
    async def list_audio_devices() -> Dict[str, Any]:
        """
        Listet alle via PortAudio/ALSA sichtbaren Audio-Geräte.

        Gibt zu jedem Gerät zurück: Index, Name, Kanal-Anzahl (In/Out),
        Standard-Samplerate sowie Flags `supports_capture` / `supports_playback`.
        """
        devices = AudioManager.list_devices()
        return {
            'devices': devices,
            'sounddevice_available': AudioManager.is_available(),
        }

    @router.get('/status', summary='Audio-Stream-Status abrufen')
    async def get_audio_status() -> Dict[str, Any]:
        """Liefert den aktuellen Betriebszustand der Audio-Streams."""
        return get_audio_manager().get_status()

    @router.get('/config', summary='Audio-Konfiguration lesen')
    async def get_audio_config() -> Dict[str, Any]:
        """Liefert die gespeicherte Audio-Konfiguration."""
        config = ConfigManager.get()
        return asdict(config.audio)

    @router.post('/start', summary='Audio-Streams starten')
    async def start_audio() -> Dict[str, Any]:
        """Startet RX-Capture-Stream gemäß gespeicherter Konfiguration."""
        try:
            await get_audio_manager().start()
            return {'success': True, 'message': 'Audio-Streams gestartet'}
        except Exception as e:
            logger.error(f'Audio-Start fehlgeschlagen: {e}')
            raise HTTPException(status_code=500, detail=str(e))

    @router.post('/stop', summary='Audio-Streams stoppen')
    async def stop_audio() -> Dict[str, Any]:
        """Stoppt alle laufenden Audio-Streams."""
        try:
            await get_audio_manager().stop()
            return {'success': True, 'message': 'Audio-Streams gestoppt'}
        except Exception as e:
            logger.error(f'Audio-Stop fehlgeschlagen: {e}')
            raise HTTPException(status_code=500, detail=str(e))

    @router.websocket('/rx')
    async def audio_rx_ws(websocket: WebSocket) -> None:
        """
        WebSocket: IC-905 RX-Audio → Client.

        Der Server sendet kontinuierlich PCM-Chunks als Binärdaten.
        Mehrere Clients gleichzeitig werden unterstützt (Broadcast).
        Der Client kann `ping` als Text-Nachricht senden, der Server antwortet mit `pong`.

        Falls der RX-Stream noch nicht läuft, wird er beim ersten Client-Connect
        automatisch gestartet (sofern sounddevice verfügbar ist).
        """
        await websocket.accept()
        mgr = get_audio_manager()

        # sounddevice-Verfügbarkeit prüfen BEVOR Client registriert wird
        if not SOUNDDEVICE_AVAILABLE:
            await websocket.send_text(
                '{"error": "sounddevice nicht verfügbar – libportaudio2 im Container prüfen"}'
            )
            await websocket.close(code=1011)
            return

        # RX-Stream automatisch starten wenn noch nicht aktiv
        if not mgr._rx_running:
            try:
                await mgr.start_rx()
                logger.info('RX-Stream automatisch gestartet (erster WS-Client)')
            except Exception as e:
                await websocket.send_text(
                    f'{{"error": "RX-Stream konnte nicht gestartet werden: {e}"}}'
                )
                await websocket.close(code=1011)
                logger.error(f'RX-Stream Auto-Start fehlgeschlagen: {e}')
                return

        # Initiale Status-Nachricht senden (BEVOR Client in Broadcast-Liste,
        # um gleichzeitige Text+Binary-Sends aus unterschiedlichen Tasks zu vermeiden)
        config = ConfigManager.get()
        await websocket.send_text(
            f'{{"status": "connected", "rx_active": true, '
            f'"sample_rate": {config.audio.sample_rate}, '
            f'"format": "{config.audio.format}"}}'
        )

        # Jetzt Client in die Broadcast-Liste aufnehmen
        mgr.add_rx_client(websocket)
        logger.info('Audio-RX WebSocket-Client verbunden')
        try:
            while True:
                msg = await websocket.receive_text()
                if msg == 'ping':
                    await websocket.send_text('pong')
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.debug(f'RX WebSocket Fehler: {e}')
        finally:
            mgr.remove_rx_client(websocket)
            logger.info('Audio-RX WebSocket-Client getrennt')

    @router.websocket('/tx')
    async def audio_tx_ws(websocket: WebSocket) -> None:
        """
        WebSocket: Client → IC-905 TX (Mikrofon des Funkgeräts).

        Der Client sendet PCM-Audio-Chunks als Binärdaten.
        Nur ein TX-Client kann gleichzeitig senden (exklusiver Lock).
        Ist der TX-Kanal bereits belegt, wird die Verbindung sofort abgelehnt.
        """
        await websocket.accept()
        mgr = get_audio_manager()

        if mgr._tx_lock.locked():
            await websocket.send_text('{"error": "TX bereits in Verwendung"}')
            await websocket.close(code=1008)
            logger.warning('TX-WebSocket abgelehnt – Kanal bereits belegt')
            return

        async with mgr._tx_lock:
            logger.info('Audio-TX WebSocket-Client verbunden (exklusiv)')
            try:
                if not mgr._tx_running:
                    await mgr.start_tx()
                while True:
                    data = await websocket.receive_bytes()
                    await mgr.write_tx(data)
            except WebSocketDisconnect:
                pass
            except Exception as e:
                logger.error(f'TX WebSocket Fehler: {e}')
            finally:
                await mgr.stop_tx()
                logger.info('Audio-TX WebSocket-Client getrennt')

    return router
