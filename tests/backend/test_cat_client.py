"""
Unit-Tests für WavelogCatClient.

Testet:
- Korrekte Payload-Erzeugung für WaveLog API
- Korrekte URL-Erzeugung für WaveLogGate HTTP Endpoint
- WebSocket-Handling (gemockt)
"""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, Mock

import pytest
import httpx

from src.backend.cat.cat_client import WavelogCatClient
from src.backend.config.settings import WavelogConfig


@pytest.fixture
def wavelog_config():
    """Standard WaveLog-Konfiguration für Tests."""
    return WavelogConfig(
        enabled=True,
        api_url='https://wavelog.test/',
        api_key_or_secret_ref='test_key_ref',
        polling_interval=5,
        radio_name='ICOM IC-7300',
        station_id='STATION1',
        wavelog_gate_http_base='http://localhost:54321',
        wavelog_gate_ws_url='ws://localhost:54322',
    )


@pytest.fixture
async def client(wavelog_config):
    """Erstellt einen WavelogCatClient für Tests."""
    async with WavelogCatClient(wavelog_config, api_key='test_api_key_123') as client:
        yield client


class TestWavelogCatClientInit:
    """Tests für Client-Initialisierung."""

    def test_init_with_config(self, wavelog_config):
        """Test: Client-Initialisierung mit Config."""
        client = WavelogCatClient(wavelog_config)
        assert client.config == wavelog_config
        assert client._api_key == ''

    def test_init_with_api_key(self, wavelog_config):
        """Test: Client-Initialisierung mit API-Key."""
        client = WavelogCatClient(wavelog_config, api_key='my_key')
        assert client._api_key == 'my_key'

    def test_set_api_key(self, wavelog_config):
        """Test: API-Key setzen."""
        client = WavelogCatClient(wavelog_config)
        client.set_api_key('new_key')
        assert client._api_key == 'new_key'


class TestSendRadioStatus:
    """Tests für send_radio_status()."""

    @pytest.mark.asyncio
    async def test_send_status_success(self, client, wavelog_config):
        """Test: Erfolgreicher Status-Versand."""
        # Mock HTTP Response
        mock_response = httpx.Response(
            status_code=200,
            text='OK',
            request=httpx.Request('POST', 'https://wavelog.test/index.php/api/radio'),
        )

        with patch.object(client._http_client, 'post', return_value=mock_response) as mock_post:
            result = await client.send_radio_status(
                frequency_hz=7100000,
                mode='USB',
                power_w=50.0,
            )

            assert result is True
            mock_post.assert_called_once()

            # Prüfe aufgerufene URL
            call_args = mock_post.call_args
            assert 'index.php/api/radio' in str(call_args.args[0])

            # Prüfe Payload
            payload = call_args.kwargs['json']
            assert payload['key'] == 'test_api_key_123'
            assert payload['radio'] == 'ICOM IC-7300'
            assert payload['frequency'] == '7100000'
            assert payload['mode'] == 'USB'
            assert payload['power'] == '50.0'
            assert payload['station_id'] == 'STATION1'
            assert 'timestamp' in payload

            # Prüfe Timestamp-Format: YYYY/MM/DD  HH:MM (zwei Leerzeichen!)
            timestamp = payload['timestamp']
            assert '/' in timestamp
            assert '  ' in timestamp  # Zwei Leerzeichen zwischen Datum und Zeit

    @pytest.mark.asyncio
    async def test_send_status_without_power(self, client):
        """Test: Status-Versand ohne Power-Angabe."""
        mock_response = httpx.Response(
            status_code=200,
            text='OK',
            request=httpx.Request('POST', 'https://test.com'),
        )

        with patch.object(client._http_client, 'post', return_value=mock_response) as mock_post:
            result = await client.send_radio_status(
                frequency_hz=14200000,
                mode='CW',
            )

            assert result is True

            # Power darf nicht im Payload sein
            payload = mock_post.call_args.kwargs['json']
            assert 'power' not in payload

    @pytest.mark.asyncio
    async def test_send_status_mode_uppercase(self, client):
        """Test: Modus wird automatisch zu Großbuchstaben konvertiert."""
        mock_response = httpx.Response(
            status_code=200,
            text='OK',
            request=httpx.Request('POST', 'https://test.com'),
        )

        with patch.object(client._http_client, 'post', return_value=mock_response) as mock_post:
            await client.send_radio_status(
                frequency_hz=14200000,
                mode='lsb',  # Kleinbuchstaben
            )

            payload = mock_post.call_args.kwargs['json']
            assert payload['mode'] == 'LSB'  # Großbuchstaben

    @pytest.mark.asyncio
    async def test_send_status_no_api_key(self, wavelog_config):
        """Test: Fehler wenn kein API-Key gesetzt ist."""
        async with WavelogCatClient(wavelog_config) as client_no_key:
            result = await client_no_key.send_radio_status(
                frequency_hz=7100000,
                mode='USB',
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_send_status_http_error(self, client):
        """Test: HTTP-Fehler (Status != 200)."""
        mock_response = httpx.Response(
            status_code=401,
            text='Unauthorized',
            request=httpx.Request('POST', 'https://test.com'),
        )

        with patch.object(client._http_client, 'post', return_value=mock_response):
            result = await client.send_radio_status(
                frequency_hz=7100000,
                mode='USB',
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_send_status_request_exception(self, client):
        """Test: Netzwerkfehler (RequestError)."""
        with patch.object(
            client._http_client,
            'post',
            side_effect=httpx.RequestError('Network error'),
        ):
            result = await client.send_radio_status(
                frequency_hz=7100000,
                mode='USB',
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_send_status_without_station_id(self, wavelog_config):
        """Test: Payload ohne station_id wenn nicht konfiguriert."""
        config_no_station = WavelogConfig(
            enabled=True,
            api_url='https://wavelog.test/',
            radio_name='Test Radio',
            station_id=None,  # Explizit None
        )

        async with WavelogCatClient(config_no_station, api_key='key') as client:
            mock_response = httpx.Response(
                status_code=200,
                text='OK',
                request=httpx.Request('POST', 'https://test.com'),
            )

            with patch.object(client._http_client, 'post', return_value=mock_response) as mock_post:
                await client.send_radio_status(
                    frequency_hz=7100000,
                    mode='USB',
                )

                payload = mock_post.call_args.kwargs['json']
                assert 'station_id' not in payload


class TestSetRadioViaGate:
    """Tests für set_radio_via_gate()."""

    @pytest.mark.asyncio
    async def test_set_radio_success(self, client):
        """Test: Erfolgreicher QSY über Gate."""
        mock_response = httpx.Response(
            status_code=200,
            text='OK',
            request=httpx.Request('GET', 'http://localhost:54321/7155000/LSB'),
        )

        with patch.object(client._http_client, 'get', return_value=mock_response) as mock_get:
            result = await client.set_radio_via_gate(
                frequency_hz=7155000,
                mode='LSB',
            )

            assert result is True
            mock_get.assert_called_once()

            # Prüfe URL-Format: {base}/{frequency}/{mode}
            url = mock_get.call_args.args[0]
            assert url == 'http://localhost:54321/7155000/LSB'

    @pytest.mark.asyncio
    async def test_set_radio_mode_uppercase(self, client):
        """Test: Modus wird zu Großbuchstaben konvertiert."""
        mock_response = httpx.Response(
            status_code=200,
            text='OK',
            request=httpx.Request('GET', 'http://test.com'),
        )

        with patch.object(client._http_client, 'get', return_value=mock_response) as mock_get:
            await client.set_radio_via_gate(
                frequency_hz=14200000,
                mode='cw',  # Kleinbuchstaben
            )

            url = mock_get.call_args.args[0]
            assert 'CW' in url  # Großbuchstaben

    @pytest.mark.asyncio
    async def test_set_radio_http_error(self, client):
        """Test: HTTP-Fehler."""
        mock_response = httpx.Response(
            status_code=500,
            text='Internal Server Error',
            request=httpx.Request('GET', 'http://test.com'),
        )

        with patch.object(client._http_client, 'get', return_value=mock_response):
            result = await client.set_radio_via_gate(7100000, 'USB')
            assert result is False

    @pytest.mark.asyncio
    async def test_set_radio_request_exception(self, client):
        """Test: Netzwerkfehler."""
        with patch.object(
            client._http_client,
            'get',
            side_effect=httpx.RequestError('Network error'),
        ):
            result = await client.set_radio_via_gate(7100000, 'USB')
            assert result is False


class TestWebSocketSubscription:
    """Tests für WebSocket-Funktionalität."""

    @pytest.mark.asyncio
    async def test_subscribe_gate_status(self, client):
        """Test: WebSocket-Subscription startet Task."""
        callback = MagicMock()

        # Mock WebSocket-Loop, damit er sofort beendet
        with patch.object(client, '_ws_listen_loop', new_callable=AsyncMock):
            await client.subscribe_gate_status(callback)

            assert client._ws_task is not None
            assert not client._ws_task.done() or client._ws_task.cancelled()

            # Cleanup
            client._running = False
            if not client._ws_task.done():
                client._ws_task.cancel()
                try:
                    await client._ws_task
                except asyncio.CancelledError:
                    pass

    @pytest.mark.asyncio
    async def test_subscribe_twice_raises_error(self, client):
        """Test: Zweite Subscription wirft Fehler."""
        callback = MagicMock()

        with patch.object(client, '_ws_listen_loop', new_callable=AsyncMock):
            await client.subscribe_gate_status(callback)

            with pytest.raises(RuntimeError, match='already active'):
                await client.subscribe_gate_status(callback)

            # Cleanup
            client._running = False
            if client._ws_task and not client._ws_task.done():
                client._ws_task.cancel()
                try:
                    await client._ws_task
                except asyncio.CancelledError:
                    pass

    def test_is_ws_connected_false_initially(self, wavelog_config):
        """Test: WebSocket initial nicht verbunden."""
        client = WavelogCatClient(wavelog_config)
        assert client.is_ws_connected() is False

    def test_is_ws_connected_true_when_connected(self, wavelog_config):
        """Test: WebSocket-Status wenn verbunden."""
        client = WavelogCatClient(wavelog_config)

        # Mock verbundenen WebSocket
        mock_ws = MagicMock()
        mock_ws.closed = False
        client._ws_connection = mock_ws

        assert client.is_ws_connected() is True

    def test_is_ws_connected_false_when_closed(self, wavelog_config):
        """Test: WebSocket-Status wenn geschlossen."""
        client = WavelogCatClient(wavelog_config)

        mock_ws = MagicMock()
        mock_ws.closed = True
        client._ws_connection = mock_ws

        assert client.is_ws_connected() is False


class TestContextManager:
    """Tests für Context Manager."""

    @pytest.mark.asyncio
    async def test_context_manager_initializes_http_client(self, wavelog_config):
        """Test: Context Manager initialisiert HTTP Client."""
        client = WavelogCatClient(wavelog_config)
        assert client._http_client is None

        async with client:
            assert client._http_client is not None
            assert isinstance(client._http_client, httpx.AsyncClient)

        # Nach Exit sollte Client geschlossen sein
        assert client._http_client is None

    @pytest.mark.asyncio
    async def test_close_cancels_websocket_task(self, wavelog_config):
        """Test: close() beendet WebSocket-Task."""
        async with WavelogCatClient(wavelog_config) as client:
            # Starte Mock-Task
            client._ws_task = asyncio.create_task(asyncio.sleep(10))
            client._running = True

            await client.close()

            assert client._ws_task.cancelled()
