"""
WaveLog CAT Client für RigBridge.

Sendet Radio-Status (Frequenz/Mode/Power) an WaveLog und kann optional
QSY-Requests (Bandmap-Klicks) über WaveLogGate verarbeiten.

Dokumentation:
- WaveLog Radio API: https://docs.wavelog.org/en/latest/api/radio/
- WaveLogGate: https://github.com/Wavelog/WaveLogGate
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Callable, Dict, Any
from urllib.parse import urljoin

import httpx
import websockets

from ..config.logger import RigBridgeLogger
from ..config.settings import WavelogConfig


logger = RigBridgeLogger.get_logger(__name__)


class WavelogCatClient:
    """
    CAT-Client für WaveLog-Integration.

    Sendet Radio-Status an WaveLog und kann QSY-Befehle über WaveLogGate empfangen.
    """

    def __init__(self, config: WavelogConfig, api_key: Optional[str] = None):
        """
        Initialisiert den WaveLog CAT Client.

        Args:
            config: WaveLog-Konfiguration
            api_key: WaveLog API-Key (überschreibt config.api_key_or_secret_ref)
        """
        self.config = config
        self._api_key = api_key or ''
        self._http_client: Optional[httpx.AsyncClient] = None
        self._ws_connection = None
        self._ws_task: Optional[asyncio.Task] = None
        self._running = False

    async def __aenter__(self) -> 'WavelogCatClient':
        """Context Manager Entry: Initialisiert HTTP Client."""
        self._http_client = httpx.AsyncClient(
            timeout=10.0,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context Manager Exit: Schließt alle Verbindungen."""
        await self.close()

    async def close(self) -> None:
        """Schließt alle offenen Verbindungen."""
        # WebSocket schließen
        if self._ws_task and not self._ws_task.done():
            self._running = False
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass

        if self._ws_connection and not self._ws_connection.closed:
            await self._ws_connection.close()

        # HTTP Client schließen
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    def set_api_key(self, api_key: str) -> None:
        """
        Setzt den API-Key für WaveLog-Anfragen.

        Args:
            api_key: WaveLog API-Key
        """
        self._api_key = api_key

    async def send_radio_status(
        self,
        frequency_hz: int,
        mode: str,
        power_w: Optional[float] = None,
    ) -> bool:
        """
        Sendet Radio-Status an WaveLog.

        Args:
            frequency_hz: Frequenz in Hz
            mode: Betriebsmodus (z.B. 'USB', 'LSB', 'CW', 'FM')
            power_w: Optionale Sendeleistung in Watt

        Returns:
            True bei Erfolg, False bei Fehler

        Raises:
            RuntimeError: Wenn HTTP Client nicht initialisiert ist
        """
        if not self._http_client:
            raise RuntimeError('HTTP Client not initialized. Use async context manager.')

        if not self._api_key:
            logger.error('WaveLog API-Key nicht gesetzt')
            return False

        # Timestamp im Format YYYY/MM/DD  HH:MM (zwei Leerzeichen zwischen Datum und Zeit!)
        timestamp = datetime.utcnow().strftime('%Y/%m/%d  %H:%M')

        # Payload gemäß WaveLog-Dokumentation
        payload = {
            'key': self._api_key,
            'radio': self.config.radio_name,
            'frequency': str(frequency_hz),
            'mode': mode.upper(),
            'timestamp': timestamp,
        }

        # Power nur hinzufügen wenn gesetzt
        if power_w is not None:
            payload['power'] = str(power_w)

        # Station-ID hinzufügen wenn konfiguriert
        if self.config.station_id:
            payload['station_id'] = self.config.station_id

        # Konstruiere vollständige URL
        api_endpoint = urljoin(self.config.api_url, 'index.php/api/radio')

        try:
            logger.debug(
                f'Sende Radio-Status an WaveLog: {frequency_hz} Hz, {mode}, '
                f'Power: {power_w}W'
            )

            response = await self._http_client.post(
                api_endpoint,
                json=payload,
            )

            if response.status_code == 200:
                logger.debug(f'WaveLog Antwort: {response.text}')
                return True
            else:
                logger.error(
                    f'WaveLog API Error: Status {response.status_code}, '
                    f'Response: {response.text}'
                )
                return False

        except httpx.RequestError as e:
            logger.error(f'Fehler beim Senden an WaveLog: {e}')
            return False

    async def set_radio_via_gate(
        self,
        frequency_hz: int,
        mode: str,
    ) -> bool:
        """
        Setzt Radio-Frequenz und Modus über WaveLogGate HTTP-Endpoint.

        Args:
            frequency_hz: Frequenz in Hz
            mode: Betriebsmodus (z.B. 'USB', 'LSB', 'CW', 'FM')

        Returns:
            True bei Erfolg, False bei Fehler

        Raises:
            RuntimeError: Wenn HTTP Client nicht initialisiert ist
        """
        if not self._http_client:
            raise RuntimeError('HTTP Client not initialized. Use async context manager.')

        # URL: http://localhost:54321/{frequency}/{mode}
        url = f'{self.config.wavelog_gate_http_base}/{frequency_hz}/{mode.upper()}'

        try:
            logger.debug(f'Setze Radio über Gate: {url}')

            response = await self._http_client.get(url)

            if response.status_code == 200:
                logger.debug(f'Gate Antwort: {response.text}')
                return True
            else:
                logger.error(
                    f'WaveLogGate Error: Status {response.status_code}, '
                    f'Response: {response.text}'
                )
                return False

        except httpx.RequestError as e:
            logger.error(f'Fehler beim Aufruf von WaveLogGate: {e}')
            return False

    async def subscribe_gate_status(
        self,
        on_status: Callable[[int, str, Dict[str, Any]], None],
    ) -> None:
        """
        Abonniert Radio-Status-Updates über WaveLogGate WebSocket.

        Args:
            on_status: Callback-Funktion, die bei Status-Updates aufgerufen wird
                       Parameter: (frequency_hz: int, mode: str, full_data: dict)

        Raises:
            RuntimeError: Wenn bereits eine WebSocket-Verbindung aktiv ist
        """
        if self._ws_task and not self._ws_task.done():
            raise RuntimeError('WebSocket subscription already active')

        self._running = True
        self._ws_task = asyncio.create_task(
            self._ws_listen_loop(on_status)
        )

    async def _ws_listen_loop(
        self,
        on_status: Callable[[int, str, Dict[str, Any]], None],
    ) -> None:
        """
        Interne WebSocket-Listen-Schleife.

        Args:
            on_status: Callback-Funktion für Status-Updates
        """
        retry_delay = 5
        max_retry_delay = 60

        while self._running:
            try:
                logger.info(f'Verbinde zu WaveLogGate WebSocket: {self.config.wavelog_gate_ws_url}')

                async with websockets.connect(
                    self.config.wavelog_gate_ws_url,
                    ping_interval=20,
                    ping_timeout=10,
                ) as websocket:
                    self._ws_connection = websocket
                    logger.info('WaveLogGate WebSocket verbunden')

                    # Reset retry delay bei erfolgreicher Verbindung
                    retry_delay = 5

                    async for message in websocket:
                        try:
                            data = json.loads(message)

                            # Prüfe auf radio_status Event
                            if data.get('type') == 'radio_status':
                                frequency = data.get('frequency')
                                mode = data.get('mode')

                                if frequency and mode:
                                    try:
                                        frequency_hz = int(frequency)
                                        on_status(frequency_hz, mode, data)
                                        logger.debug(
                                            f'Radio-Status empfangen: {frequency_hz} Hz, {mode}'
                                        )
                                    except ValueError:
                                        logger.warning(f'Ungültige Frequenz: {frequency}')
                                else:
                                    logger.warning('radio_status ohne frequency/mode')
                            else:
                                logger.debug(f'Unbekannter Event-Typ: {data.get("type")}')

                        except json.JSONDecodeError as e:
                            logger.warning(f'Ungültige JSON-Nachricht: {e}')

            except websockets.exceptions.WebSocketException as e:
                logger.warning(f'WebSocket-Fehler: {e}. Reconnect in {retry_delay}s')

            except Exception as e:
                logger.error(f'Unerwarteter Fehler in WebSocket-Loop: {e}', exc_info=True)

            finally:
                self._ws_connection = None

            # Warte bevor Reconnect versucht wird
            if self._running:
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)

    def is_ws_connected(self) -> bool:
        """
        Prüft, ob WebSocket-Verbindung aktiv ist.

        Returns:
            True wenn verbunden, sonst False
        """
        return (
            self._ws_connection is not None
            and not self._ws_connection.closed
        )
