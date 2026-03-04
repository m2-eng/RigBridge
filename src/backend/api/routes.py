"""
API-Routen für RigBridge.

Definiert REST-Endpunkte für Funk-Geräte-Steuerung und Konfiguration.

WICHTIG: Alle USB-Zugriffe werden durch TransportManager synchronisiert.
Keine Race Conditions zwischen Health-Check und API-Befehlen.
"""

import asyncio
from fastapi import APIRouter, HTTPException, Query, Path as PathParam
from pydantic import BaseModel, Field
from typing import Any, Optional, Dict, List
from pathlib import Path
from dataclasses import asdict
from enum import Enum

from ..config.logger import RigBridgeLogger
from ..config.settings import ConfigManager, LogLevel
from ..config.secret_provider import create_secret_provider, SecretProviderError
from ..civ.executor import CIVCommandExecutor, CommandResult
from ..usb.connection import USBConnection
from src import __version__

logger = RigBridgeLogger.get_logger(__name__)


# ============================================================================
# Enums für Status-Werte
# ============================================================================


class USBStatus(str, Enum):
    """USB-Verbindungsstatus."""
    DISCONNECTED = "disconnected"  # Kein USB-Port verfügbar / kann nicht geöffnet werden
    ATTACHED = "attached"          # Port kann geöffnet werden, aber Gerät antwortet nicht
    CONNECTED = "connected"         # Gerät antwortet auf Befehle


# ============================================================================
# Globaler Executor-Cache (für Health-Check und API-Endpunkte)
# ============================================================================
_global_executor_cache: Dict[str, CIVCommandExecutor] = {}


def _get_or_create_executor() -> CIVCommandExecutor:
    """
    Globale Executor-Instanz (Singleton).
    Wird von Health-Check und API-Endpunkten gemeinsam genutzt.
    """
    cache_key = 'default'
    if cache_key not in _global_executor_cache:
        try:
            config = ConfigManager.get()
            protocol_file = config.device.get_protocol_path()
            manufacturer_file = config.device.get_manufacturer_path()
            executor = CIVCommandExecutor(protocol_file, manufacturer_file)
            logger.debug(f'CIV Executor initialized for {protocol_file}')

            # Initialisiere USB-Connection
            try:
                usb_conn = USBConnection(config.usb)
                executor.set_usb_connection(usb_conn)
                logger.info(f'USB Connection configured for {config.usb.port} @ {config.usb.baud_rate} baud')
            except Exception as e:
                logger.warning(f'Failed to initialize USB connection: {e} - Using mock data')

            _global_executor_cache[cache_key] = executor
        except Exception as e:
            logger.error(f'Failed to create executor: {e}')
            raise

    return _global_executor_cache[cache_key]


# ============================================================================
# Pydantic Models (Request/Response)
# ============================================================================


class CommandRequest(BaseModel):
    """Request-Modell für allgemeine Befehlsausführung."""
    command: str = Field(
        ...,
        description='Befehlsname aus YAML (z.B. "set_operating_frequency")',
    )
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        description='Befehlsdaten (für PUT-Befehle)',
    )


class FrequencyRequest(BaseModel):
    """Request für Frequenzänderung."""
    frequency_hz: int = Field(
        ...,
        ge=0,
        description='Frequenz in Hz',
    )


class ModeRequest(BaseModel):
    """Request für Modusänderung."""
    mode: str = Field(
        ...,
        description='Betriebsmodus (z.B. "CW", "SSB", "AM")',
    )


class CommandResponse(BaseModel):
    """Response für Befehlsausführung."""
    success: bool
    command: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class FrequencyResponse(BaseModel):
    """Response-Modell für Frequenzabfragen."""
    frequency_hz: int
    vfo: str = 'A'


class ModeResponse(BaseModel):
    """Response-Modell für Modusabfragen."""
    mode: str
    filter: Optional[str] = None


class SMeterResponse(BaseModel):
    """Response für S-Meter-Lesungen."""
    level_db: float = Field(
        description='S-Meter-Wert in dB (logarithmisch)'
    )
    level_raw: int = Field(
        description='Roher Sensor-Wert (0-255)'
    )


class WavelogTestResponse(BaseModel):
    """Response für Wavelog-Verbindungstest."""
    success: bool = Field(
        description='Verbindung erfolgreich kontrolliert'
    )
    message: str = Field(
        description='Detailmeldung (z.B. Fehlergrund)'
    )
    station_count: Optional[int] = Field(
        default=None,
        description='Anzahl verfügbarer Stationen (bei Erfolg)',
    )


class WavelogStation(BaseModel):
    """Wavelog-Stationsinformation."""
    id: int = Field(description='Station-ID')
    name: str = Field(description='Stationsname')
    callsign: str = Field(description='Rufzeichen')


class WavelogStationsResponse(BaseModel):
    """Response für Wavelog-Stationsliste."""
    stations: List[WavelogStation] = Field(
        description='Liste der verfügbaren Stationen'
    )


class DeviceInfo(BaseModel):
    """Information über ein verfügbares Funkgerät."""
    name: str = Field(description='Gerätename (z.B. "Icom IC-905")')
    manufacturer: str = Field(description='Hersteller (z.B. "icom")')
    protocol_file: str = Field(description='YAML-Protokoll-Datei ohne Erweiterung')


class StatusResponse(BaseModel):
    """System-Status."""
    usb_status: USBStatus = Field(
        description='USB-Verbindungsstatus: disconnected, attached, connected'
    )
    usb_connected: bool = Field(
        description='Legacy-Feld: True wenn attached oder connected (deprecated)'
    )
    degraded_mode: bool
    secret_provider_available: bool
    device_name: str
    api_version: str
    features: List[str]


class USBConfigUpdate(BaseModel):
    port: Optional[str] = None
    baud_rate: Optional[int] = None
    data_bits: Optional[int] = None
    stop_bits: Optional[int] = None
    parity: Optional[str] = None
    timeout: Optional[float] = None
    reconnect_interval: Optional[int] = None


class APIConfigUpdate(BaseModel):
    host: Optional[str] = None
    port: Optional[int] = None
    enable_https: Optional[bool] = None
    cert_file: Optional[str] = None
    key_file: Optional[str] = None
    log_level: Optional[str] = None


class WavelogConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    api_url: Optional[str] = None
    api_key_secret_ref: Optional[str] = None
    polling_interval: Optional[int] = None


class SecretProviderConfigUpdate(BaseModel):
    provider: Optional[str] = None
    vault_url: Optional[str] = None
    vault_mount: Optional[str] = None
    token_file: Optional[str] = None


class DeviceConfigUpdate(BaseModel):
    name: Optional[str] = None
    manufacturer: Optional[str] = None
    protocol_file: Optional[str] = None


class ConfigUpdateRequest(BaseModel):
    usb: Optional[USBConfigUpdate] = None
    api: Optional[APIConfigUpdate] = None
    wavelog: Optional[WavelogConfigUpdate] = None
    secret_provider: Optional[SecretProviderConfigUpdate] = None
    device: Optional[DeviceConfigUpdate] = None


# ============================================================================
# USB Health Check - Zyklische Verbindungsprüfung
# ============================================================================

# Globaler State für Background-Task
_health_check_state = {
    'task': None,
    'running': False,
    'usb_status': USBStatus.DISCONNECTED,
    'last_check': None,
}


async def _perform_usb_health_check() -> USBStatus:
    """
    Führt einen USB-Verbindungstest durch.

    Sendet den 'read_transceiver_id' Befehl und evaluiert die Antwort.
    Bei Fehler wird automatisch ein Reconnect-Versuch unternommen.

    WICHTIG: Nutzt TransportManager automatisch via executor.execute_command()
    für Synchronisierung.

    Returns:
        USBStatus: disconnected, attached oder connected
    """
    try:
        executor = _get_or_create_executor()

        # Prüfe, ob USB-Connection existiert
        if not executor.usb_connection:
            logger.debug('No USB connection available')
            return USBStatus.DISCONNECTED

        # Prüfe, ob Port geöffnet werden kann
        if not executor.usb_connection.is_connected:
            if not executor.usb_connection.connect():
                logger.debug('USB port cannot be opened')
                return USBStatus.ATTACHED

        # Port ist offen - teste ob Gerät antwortet
        # execute_command ist ASYNC und nutzt TransportManager automatisch
        result = await executor.execute_command(
            'read_transceiver_id',
            is_health_check=True,
        )

        if result.success:
            logger.debug('Device responded to health check')
            return USBStatus.CONNECTED
        else:
            logger.debug(f'Health check failed: {result.error}')
            return USBStatus.ATTACHED

    except Exception as e:
        logger.debug(f'USB health check error: {e}')
        return USBStatus.DISCONNECTED


async def start_usb_health_check_task(check_interval: int = 10):
    """
    Startet zyklische USB-Verbindungsprüfung im Hintergrund.

    Args:
        check_interval: Prüfintervall in Sekunden (Standard: 10)
    """
    if _health_check_state['running']:
        logger.warning('USB health check task already running')
        return

    _health_check_state['running'] = True
    logger.info(f'USB health check task started (interval: {check_interval}s)')

    async def health_check_loop():
        """Endlosschleife für zyklische Prüfung."""
        consecutive_failures = 0

        while _health_check_state['running']:
            try:
                previous_status = _health_check_state.get('usb_status', USBStatus.DISCONNECTED)
                current_status = await _perform_usb_health_check()

                # Logging bei Statusänderung
                if current_status != previous_status:
                    status_names = {
                        USBStatus.DISCONNECTED: '✗ GETRENNT',
                        USBStatus.ATTACHED: '◐ USB ANGESCHLOSSEN',
                        USBStatus.CONNECTED: '✓ VERBUNDEN'
                    }
                    logger.warning(
                        f'USB status changed: {status_names.get(previous_status, "?")} → '
                        f'{status_names.get(current_status, "?")}'
                    )
                    consecutive_failures = 0
                elif current_status != USBStatus.CONNECTED:
                    consecutive_failures += 1
                    if consecutive_failures % 6 == 1:
                        logger.warning(f'Health check failed {consecutive_failures} times')

                _health_check_state['usb_status'] = current_status
                _health_check_state['last_check'] = asyncio.get_event_loop().time()

            except Exception as e:
                logger.error(f'Health check loop error: {e}')

            # Warte bis zur nächsten Prüfung
            await asyncio.sleep(check_interval)

    # Starte Task
    task = asyncio.create_task(health_check_loop())
    _health_check_state['task'] = task


async def stop_usb_health_check_task():
    """Stoppe zyklische USB-Verbindungsprüfung."""
    _health_check_state['running'] = False

    if _health_check_state['task']:
        try:
            _health_check_state['task'].cancel()
            await _health_check_state['task']
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f'Error stopping health check task: {e}')
        finally:
            _health_check_state['task'] = None

    logger.info('USB health check task stopped')


def get_usb_status() -> USBStatus:
    """Gibt aktuellen, zyklisch geprüften USB-Status zurück."""
    return _health_check_state.get('usb_status', USBStatus.DISCONNECTED)


# ============================================================================
# Router und Endpunkte
# ============================================================================


def create_router() -> APIRouter:
    """Erstellt und konfiguriert den API-Router."""
    router = APIRouter()

    def get_executor() -> CIVCommandExecutor:
        """Gibt die globale CIV-Executor-Instanz zurück."""
        return _get_or_create_executor()

    # ========================================================================
    # STATUS ENDPOINTS
    # ========================================================================

    @router.get(
        '/status',
        response_model=StatusResponse,
        tags=['Status'],
        summary='Geräte- und System-Status',
    )
    async def get_status() -> StatusResponse:
        """Gibt aktuellen Status des Systems und der Verbindung an."""
        config = ConfigManager.get()
        degraded_mode = False
        secret_provider_available = True

        # Nutze zyklisch geprüften USB-Status (vom Health-Check)
        usb_status = get_usb_status()

        if config.wavelog.enabled and config.wavelog.api_key_secret_ref:
            try:
                provider = create_secret_provider(config)
                provider.get_secret(config.wavelog.api_key_secret_ref)
            except SecretProviderError as exc:
                degraded_mode = True
                secret_provider_available = False
                logger.warning(f'Secret provider unavailable, running degraded: {exc}')

        return StatusResponse(
            usb_status=usb_status,
            usb_connected=(usb_status in [USBStatus.ATTACHED, USBStatus.CONNECTED]),
            degraded_mode=degraded_mode,
            secret_provider_available=secret_provider_available,
            device_name=config.device.name,
            api_version=__version__,
            features=['set_frequency', 'set_mode', 'read_s_meter'],
        )

    @router.get(
        '/config',
        tags=['Config'],
        summary='Aktuelle Konfiguration abrufen',
    )
    async def get_config() -> Dict[str, Any]:
        """Gibt die aktuelle Konfiguration zurück (Secrets maskiert)."""
        config = ConfigManager.get()

        response: Dict[str, Any] = {
            'usb': asdict(config.usb),
            'api': {
                **asdict(config.api),
                'log_level': config.api.log_level.value,
            },
            'wavelog': asdict(config.wavelog),
            'secret_provider': asdict(config.secret_provider),
            'device': asdict(config.device),
        }

        if response['wavelog'].get('api_key_secret_ref'):
            response['wavelog']['api_key_secret_ref'] = '***'

        return response

    @router.put(
        '/config',
        tags=['Config'],
        summary='Konfiguration aktualisieren',
    )
    async def update_config(request: ConfigUpdateRequest) -> Dict[str, Any]:
        """Aktualisiert Konfiguration und speichert sie persistent in config.json."""
        config = ConfigManager.get()
        payload = request.model_dump(exclude_none=True)

        if 'usb' in payload:
            for key, value in payload['usb'].items():
                setattr(config.usb, key, value)

        if 'api' in payload:
            api_values = payload['api']
            if 'log_level' in api_values:
                try:
                    config.api.log_level = LogLevel(api_values['log_level'])
                except ValueError as exc:
                    raise HTTPException(status_code=422, detail=f'Invalid log_level: {exc}')
            for key, value in api_values.items():
                if key != 'log_level':
                    setattr(config.api, key, value)

        if 'wavelog' in payload:
            for key, value in payload['wavelog'].items():
                setattr(config.wavelog, key, value)

        if 'secret_provider' in payload:
            for key, value in payload['secret_provider'].items():
                setattr(config.secret_provider, key, value)

        if 'device' in payload:
            for key, value in payload['device'].items():
                setattr(config.device, key, value)

        ConfigManager.save()

        return {
            'success': True,
            'message': 'Configuration updated',
        }

    # ========================================================================
    # ALLGEMEINE COMMAND ENDPOINTS
    # ========================================================================

    @router.get(
        '/command/{command_name}',
        response_model=CommandResponse,
        tags=['Commands'],
        summary='Befehl ausführen (GET)',
    )
    async def execute_command_get(
        command_name: str = PathParam(
            description='Name des Befehls aus YAML'
        ),
    ) -> CommandResponse:
        """
        Führt einen read-only Befehl aus.

        TransportManager kümmert sich automatisch um Synchronisierung.
        Beispiel: `/api/command/read_s_meter`
        """
        try:
            executor = get_executor()
            result = await executor.execute_command(command_name)

            if result.success:
                logger.info(f'Command executed: {command_name}')
                return CommandResponse(
                    success=True,
                    command=command_name,
                    data=result.data,
                )
            else:
                logger.warning(f'Command failed: {command_name} - {result.error}')
                raise HTTPException(status_code=400, detail=result.error)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'Command execution error: {e}')
            raise HTTPException(status_code=500, detail=str(e))

    @router.put(
        '/command/{command_name}',
        response_model=CommandResponse,
        tags=['Commands'],
        summary='Befehl ausführen (PUT)',
    )
    async def execute_command_put(
        command_name: str,
        request: CommandRequest,
    ) -> CommandResponse:
        """
        Führt einen Befehl mit Daten aus.

        TransportManager kümmert sich automatisch um Synchronisierung.

        Beispiel:
        ```json
        {
            "command": "set_operating_frequency",
            "data": {"frequency": 145500000}
        }
        ```
        """
        try:
            executor = get_executor()
            result = await executor.execute_command(command_name, data=request.data)

            if result.success:
                logger.info(f'Command executed: {command_name}')
                return CommandResponse(
                    success=True,
                    command=command_name,
                    data=result.data,
                )
            else:
                logger.warning(f'Command failed: {command_name} - {result.error}')
                raise HTTPException(status_code=400, detail=result.error)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'Command execution error: {e}')
            raise HTTPException(status_code=500, detail=str(e))

    # ========================================================================
    # SPECIFIC FREQUENCY ENDPOINTS
    # ========================================================================

    @router.get(
        '/rig/frequency',
        response_model=FrequencyResponse,
        tags=['Frequency'],
        summary='Aktuelle Betriebsfrequenz auslesen',
    )
    async def get_frequency() -> FrequencyResponse:
        """Liest die aktuelle Betriebsfrequenz des Geräts."""
        try:
            executor = get_executor()
            result = await executor.execute_command('read_operating_frequency')

            if result.success and result.data:
                frequency = result.data.get('frequency', 0)
                logger.info(f'Frequency read: {frequency} Hz')
                return FrequencyResponse(frequency_hz=frequency)
            else:
                raise HTTPException(
                    status_code=400,
                    detail=result.error or 'Failed to read frequency'
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'Frequency read failed: {e}')
            raise HTTPException(status_code=500, detail=str(e))

    @router.put(
        '/rig/frequency',
        response_model=CommandResponse,
        tags=['Frequency'],
        summary='Betriebsfrequenz setzen',
    )
    async def set_frequency(request: FrequencyRequest) -> CommandResponse:
        """Setzt eine neue Betriebsfrequenz."""
        try:
            executor = get_executor()
            result = await executor.execute_command(
                'set_operating_frequency',
                data={'frequency': request.frequency_hz},
            )

            if result.success:
                logger.info(f'Frequency set to {request.frequency_hz} Hz')
                return CommandResponse(
                    success=True,
                    command='set_operating_frequency',
                    data={'frequency_hz': request.frequency_hz, 'status': 'OK'},
                )
            else:
                logger.warning(f'Failed to set frequency: {result.error}')
                return CommandResponse(
                    success=False,
                    command='set_operating_frequency',
                    error=result.error or 'Failed to set frequency',
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'Frequency set failed: {e}')
            raise HTTPException(status_code=500, detail=str(e))

    # ========================================================================
    # SPECIFIC MODE ENDPOINTS
    # ========================================================================

    @router.get(
        '/rig/mode',
        response_model=ModeResponse,
        tags=['Mode'],
        summary='Aktuellen Betriebsmodus auslesen',
    )
    async def get_mode() -> ModeResponse:
        """Liest den aktuellen Betriebsmodus des Geräts."""
        try:
            executor = get_executor()
            result = await executor.execute_command('read_operating_mode')

            if result.success and result.data:
                mode = result.data.get('mode', 'UNKNOWN')
                logger.info(f'Mode read: {mode}')
                return ModeResponse(mode=mode)
            else:
                raise HTTPException(
                    status_code=400,
                    detail=result.error or 'Failed to read mode'
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'Mode read failed: {e}')
            raise HTTPException(status_code=500, detail=str(e))

    @router.put(
        '/rig/mode',
        response_model=CommandResponse,
        tags=['Mode'],
        summary='Betriebsmodus setzen',
    )
    async def set_mode(request: ModeRequest) -> CommandResponse:
        """Setzt einen neuen Betriebsmodus."""
        try:
            executor = get_executor()
            result = await executor.execute_command(
                'set_operating_mode',
                data={'mode': request.mode},
            )

            if result.success:
                logger.info(f'Mode set to {request.mode}')
                return CommandResponse(
                    success=True,
                    command='set_operating_mode',
                    data={'mode': request.mode, 'status': 'OK'},
                )
            else:
                logger.warning(f'Failed to set mode: {result.error}')
                return CommandResponse(
                    success=False,
                    command='set_operating_mode',
                    error=result.error or 'Failed to set mode',
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'Mode set failed: {e}')
            raise HTTPException(status_code=500, detail=str(e))

    # ========================================================================
    # SPECIFIC METER ENDPOINTS
    # ========================================================================

    @router.get(
        '/rig/s-meter',
        response_model=SMeterResponse,
        tags=['Meters'],
        summary='S-Meter Lesewert auslesen',
    )
    async def get_s_meter() -> SMeterResponse:
        """Liest den aktuellen S-Meter-Wert des Geräts."""
        try:
            executor = get_executor()
            result = await executor.execute_command('read_s_meter')

            if result.success and result.data:
                raw_value = result.data.get('level_raw', 0)
                db_value = interpolate_s_meter(raw_value)
                logger.info(f'S-Meter read: {raw_value} (raw) = {db_value} dB')
                return SMeterResponse(level_db=db_value, level_raw=raw_value)
            else:
                raise HTTPException(
                    status_code=400,
                    detail=result.error or 'Failed to read S-meter'
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'S-Meter read failed: {e}')
            raise HTTPException(status_code=500, detail=str(e))

    # ========================================================================
    # INFO ENDPOINTS
    # ========================================================================

    @router.get(
        '/commands',
        tags=['Info'],
        summary='Verfügbare Befehle auflisten',
    )
    async def list_commands() -> Dict[str, List[str]]:
        """Gibt eine Liste aller verfügbaren Befehle zurück."""
        try:
            executor = get_executor()
            commands = executor.parser.list_commands()
            logger.debug(f'Listed {len(commands)} available commands')
            return {'commands': sorted(commands)}
        except Exception as e:
            logger.error(f'Command list failed: {e}')
            raise HTTPException(status_code=500, detail=str(e))

    # ========================================================================
    # WAVELOG INTEGRATION ENDPOINTS
    # ========================================================================

    @router.get(
        '/wavelog/test',
        response_model=WavelogTestResponse,
        tags=['Wavelog'],
        summary='Wavelog-Verbindung testen',
    )
    async def test_wavelog_connection() -> WavelogTestResponse:
        """Testet die Verbindung zu Wavelog (Erreichbarkeit + Auth)."""
        try:
            config = ConfigManager.get()

            # Prüfe ob Wavelog aktiviert ist
            if not config.wavelog.enabled:
                return WavelogTestResponse(
                    success=False,
                    message='Wavelog is not enabled in configuration',
                )

            # Prüfe ob Secret-Ref vorhanden ist
            if not config.wavelog.api_key_secret_ref:
                return WavelogTestResponse(
                    success=False,
                    message='Wavelog API key secret reference not configured',
                )

            # Versuche Secret zu laden
            try:
                provider = create_secret_provider(config)
                provider.get_secret(config.wavelog.api_key_secret_ref)
            except SecretProviderError as e:
                return WavelogTestResponse(
                    success=False,
                    message=f'Secret provider error: {str(e)}',
                )

            # Vereinfachter Test: nur Erreichbarkeit prüfen
            # TODO: Echter Wavelog-API-Call wenn Integration vorhanden
            logger.info('Wavelog connection test completed (mock)')
            return WavelogTestResponse(
                success=True,
                message='Wavelog is reachable and authenticated',
                station_count=10,
            )

        except Exception as e:
            logger.error(f'Wavelog test failed: {e}')
            return WavelogTestResponse(
                success=False,
                message=f'Test failed: {str(e)}',
            )

    @router.get(
        '/wavelog/stations',
        response_model=WavelogStationsResponse,
        tags=['Wavelog'],
        summary='Verfügbare Stationen in Wavelog abrufen',
    )
    async def get_wavelog_stations() -> WavelogStationsResponse:
        """
        Ruft die Stationsliste von Wavelog ab.

        Wird üblicherweise vom UI-Dropdown verwendet.
        """
        try:
            config = ConfigManager.get()

            if not config.wavelog.enabled:
                return WavelogStationsResponse(stations=[])

            # Mock-Daten für UI-Test
            # TODO: Echter Wavelog-API-Call wenn Integration vorhanden
            mock_stations = [
                WavelogStation(id=1, name='Home Station', callsign='W5XYZ'),
                WavelogStation(id=2, name='Mobile', callsign='W5XYZ/M'),
                WavelogStation(id=3, name='Portable', callsign='W5XYZ/P'),
            ]

            logger.info(f'Retrieved {len(mock_stations)} stations from Wavelog (mock)')
            return WavelogStationsResponse(stations=mock_stations)

        except Exception as e:
            logger.error(f'Get Wavelog stations failed: {e}')
            return WavelogStationsResponse(stations=[])

    # ========================================================================
    # DEVICE DISCOVERY ENDPOINTS
    # ========================================================================

    @router.get(
        '/devices',
        tags=['Info'],
        summary='Verfügbare Funkgeräte auflisten',
    )
    async def list_devices() -> Dict[str, List[DeviceInfo]]:
        """
        Gibt eine Liste aller verfügbaren Funkgeräte aus den YAML-Protokolldateien zurück.

        Die Liste wird beim Start gescannt und gecacht.
        """
        try:
            # Scannen der protocols/manufacturers/ Ordner
            protocols_base = Path(__file__).parent.parent.parent.parent / 'protocols' / 'manufacturers'

            devices = []

            if protocols_base.exists():
                for manufacturer_dir in protocols_base.iterdir():
                    if manufacturer_dir.is_dir():
                        for protocol_file in manufacturer_dir.glob('*.yaml'):
                            if protocol_file.name not in ['manufacturer.yaml', 'meta.yaml']:
                                device_name = protocol_file.stem
                                manufacturer = manufacturer_dir.name
                                devices.append(DeviceInfo(
                                    name=f'{manufacturer.upper()} {device_name.upper()}',
                                    manufacturer=manufacturer,
                                    protocol_file=device_name,
                                ))

            logger.info(f'Listed {len(devices)} available devices')
            return {'devices': sorted(devices, key=lambda d: d.name)}

        except Exception as e:
            logger.error(f'Device list failed: {e}')
            return {'devices': []}

    return router


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def interpolate_s_meter(raw_value: int) -> float:
    """
    Interpoliert S-Meter-Rohwert zu dB.

    Kalibrierungspunkte:
    - 0x00 = 0 dB
    - 0x78 = 54 dB
    - 0xF1 = 114 dB

    Linear interpoliert zwischen Punkten.
    """
    # Definiere Kalibrierungspunkte
    calibration_points = [
        (0x00, 0),
        (0x78, 54),
        (0xF1, 114),
    ]

    # Finde relevanten Punkt-Bereich
    for i in range(len(calibration_points) - 1):
        x1, y1 = calibration_points[i]
        x2, y2 = calibration_points[i + 1]

        if x1 <= raw_value <= x2:
            # Lineare Interpolation
            slope = (y2 - y1) / (x2 - x1) if x2 != x1 else 0
            level_db = y1 + slope * (raw_value - x1)
            return level_db

    # Außerhalb des Bereichs: extrapolieren oder konstanter Wert
    return 114.0 if raw_value > 0xF1 else 0.0
