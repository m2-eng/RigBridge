"""
API-Routen für RigBridge.

Definiert REST-Endpunkte für Funk-Geräte-Steuerung und Konfiguration.

WICHTIG: Alle USB-Zugriffe werden durch TransportManager synchronisiert.
Keine Race Conditions zwischen Health-Check und API-Befehlen.
"""

import asyncio
import httpx
import logging
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
from ..transport import USBConnection, TransportStatus
from ..cat.cat_client import WavelogCatClient
from src import __version__

logger = RigBridgeLogger.get_logger(__name__)

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


def _resolve_wavelog_api_key(config) -> str:
    """
    Löst den Wavelog API-Key auf.

    Unterstützte Varianten für `wavelog.api_key_or_secret_ref`:
    - Direkter API-Key im Klartext (z.B. `abcd1234ef567890`)
    - Secret-Referenz via Vault (Format: `path#key`)

    Hinweis: Direkter Klartext-API-Key wird gespeichert (CFG-03).
    """
    api_key_ref = (config.wavelog.api_key_or_secret_ref or '').strip()
    if not api_key_ref:
        raise SecretProviderError('Wavelog API-Key nicht konfiguriert')

    # Wenn # enthalten → Secret-Referenz via Vault
    if '#' in api_key_ref:
        provider = create_secret_provider(config)
        return provider.get_secret(api_key_ref)

    # Ansonsten: direkter API-Key im Klartext
    return api_key_ref


async def _fetch_wavelog_station_info(config, api_key: str) -> List[Dict[str, Any]]:
    """Lädt Stationen aus WaveLog über den station_info API-Endpunkt."""
    endpoint = f'index.php/api/station_info/{api_key}'
    url = f"{config.wavelog.api_url.rstrip('/')}/{endpoint}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, headers={'Accept': 'application/json'})
        response.raise_for_status()
        payload = response.json()

    if isinstance(payload, dict) and payload.get('status') == 'failed':
        reason = payload.get('reason', 'unknown reason')
        raise ValueError(f'WaveLog station_info failed: {reason}')

    if not isinstance(payload, list):
        raise ValueError('WaveLog station_info returned unexpected payload format')

    return payload


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
    usb_status: TransportStatus = Field(
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
    cat_status: Optional[Dict[str, Any]] = Field(
        default=None,
        description='CAT-Client-Status (WaveLog-Integration)'
    )


class ConfigResponse(BaseModel):
    """Response mit aktueller Konfiguration (Secrets maskiert)."""
    usb: Dict[str, Any] = Field(description='USB-Konfiguration')
    api: Dict[str, Any] = Field(description='API-Konfiguration')
    wavelog: Dict[str, Any] = Field(description='Wavelog-Konfiguration')
    secret_provider: Dict[str, Any] = Field(description='Secret-Provider-Konfiguration')
    device: Dict[str, Any] = Field(description='Geräte-Konfiguration')


class ConfigUpdateResponse(BaseModel):
    """Response nach Config-Update."""
    success: bool = Field(description='Update erfolgreich')
    message: str = Field(description='Bestätigungmeldung')


class CommandListResponse(BaseModel):
    """Response mit Liste verfügbarer Befehle."""
    commands: List[str] = Field(
        description='Liste der verfügbaren Befehlsnamen aus YAML'
    )


class DeviceListResponse(BaseModel):
    """Response mit Liste verfügbarer Geräte."""
    devices: List[DeviceInfo] = Field(
        description='Liste der verfügbaren Funkgeräte'
    )


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
    api_key_or_secret_ref: Optional[str] = None
    polling_interval: Optional[int] = None
    radio_name: Optional[str] = None
    station_id: Optional[str] = None
    wavelog_gate_http_base: Optional[str] = None
    wavelog_gate_ws_url: Optional[str] = None


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
    'usb_status': TransportStatus.DISCONNECTED,
    'last_check': None,
}

# Globaler State für CAT-Client und Background-Task
_cat_client_state = {
    'client': None,
    'task': None,
    'running': False,
    'last_update': None,
}


async def _perform_usb_health_check() -> TransportStatus:
    """
    Führt einen USB-Verbindungstest durch.

    Sendet den 'read_transceiver_id' Befehl und evaluiert die Antwort.
    Bei Fehler wird automatisch ein Reconnect-Versuch unternommen.

    WICHTIG: Nutzt TransportManager automatisch via executor.execute_command()
    für Synchronisierung.

    Returns:
        TransportStatus: disconnected, attached oder connected
    """
    try:
        executor = _get_or_create_executor()

        # Port ist offen - teste ob Gerät antwortet
        # execute_command ist ASYNC und nutzt TransportManager automatisch
        result = await executor.execute_command(
            'read_transceiver_id',
            is_health_check=True,
        )

        if result.success:
            logger.debug('Device responded to health check')
            return TransportStatus.CONNECTED
        else:
            logger.debug(f'Health check failed: {result.error}')
            return TransportStatus.COMMUNICATION_ERROR

    except Exception as e:
        logger.debug(f'USB health check error: {e}')
        return TransportStatus.DISCONNECTED


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
                previous_status = get_usb_status()
                current_status = await _perform_usb_health_check()

                # Logging bei Statusänderung
                if current_status != previous_status:
                    consecutive_failures = 0
                elif current_status == TransportStatus.COMMUNICATION_ERROR:
                    consecutive_failures += 1
                    if consecutive_failures % 6 == 1:
                        logger.warning(f'Health check failed {consecutive_failures} times')

                _health_check_state['usb_status'] = get_usb_status()
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


def get_usb_status() -> TransportStatus:
    """Gibt aktuellen, zyklisch geprüften USB-Status zurück."""
    executor = _get_or_create_executor()
    return executor.usb_connection.state.status if executor and executor.usb_connection else TransportStatus.DISCONNECTED


# ============================================================================
# CAT Client - WaveLog Integration
# ============================================================================


async def _get_radio_status() -> Dict[str, Any]:
    """
    Liest aktuellen Radio-Status (Frequenz, Mode, Power).

    Nutzt verfügbare USB-Befehle. Für fehlende Befehle werden Dummy-Werte verwendet.

    Returns:
        Dict mit frequency_hz, mode, power_w (oder None wenn nicht verfügbar)
    """
    try:
        executor = _get_or_create_executor()

        # Frequenz auslesen
        frequency_hz = None
        freq_result = await executor.execute_command('read_operating_frequency')
        if freq_result.success and freq_result.data:
            frequency_hz = freq_result.data.get('frequency')

        # Modus auslesen
        mode = None
        mode_result = await executor.execute_command('read_operating_mode')
        if mode_result.success and mode_result.data:
            mode = mode_result.data.get('mode')

        # Power auslesen (wenn Befehl verfügbar)
        # Hinweis: Viele Geräte haben keinen Befehl zum Auslesen der aktuellen Sendeleistung
        # Verwende Dummy-Wert oder lasse None
        power_w = None
        # TODO: Implementiere read_tx_power wenn verfügbar in YAML
        # Für jetzt: Dummy-Wert basierend auf Config oder None

        return {
            'frequency_hz': frequency_hz,
            'mode': mode,
            'power_w': power_w,
        }

    except Exception as e:
        logger.debug(f'Fehler beim Auslesen des Radio-Status: {e}')
        return {
            'frequency_hz': None,
            'mode': None,
            'power_w': None,
        }


async def _get_or_create_cat_client() -> Optional[WavelogCatClient]:
    """
    Erstellt oder gibt existierenden CAT-Client zurück.

    Returns:
        WavelogCatClient oder None wenn nicht aktiviert
    """
    config = ConfigManager.get()

    # Prüfe ob WaveLog aktiviert ist
    if not config.wavelog.enabled:
        return None

    # Erstelle Client wenn noch nicht vorhanden
    if _cat_client_state['client'] is None:
        try:
            # Prüfe ob API-Key konfiguriert ist
            if not config.wavelog.api_key_or_secret_ref:
                logger.warning('Wavelog API-Key ist nicht konfiguriert')
                return None

            # API-Key auflösen (Secret-Ref oder direkter Key)
            try:
                api_key = _resolve_wavelog_api_key(config)
            except SecretProviderError as e:
                logger.warning(f'Konnte API-Key nicht laden: {e}')
                return None

            # Client erstellen (Context Manager wird NICHT verwendet im Background-Task)
            client = WavelogCatClient(config.wavelog, api_key=api_key)

            # HTTP Client manuell initialisieren
            await client.__aenter__()

            _cat_client_state['client'] = client
            logger.info('WaveLog CAT Client erstellt')

        except Exception as e:
            logger.error(f'Fehler beim Erstellen des CAT-Clients: {e}')
            return None

    return _cat_client_state['client']


async def start_cat_update_task(update_interval: Optional[int] = None):
    """
    Startet zyklische Radio-Status-Updates zu WaveLog im Hintergrund.

    Args:
        update_interval: Update-Intervall in Sekunden (aus Config wenn None)
    """
    config = ConfigManager.get()

    # Prüfe ob aktiviert
    if not config.wavelog.enabled:
        logger.info('WaveLog CAT-Integration ist deaktiviert')
        return

    if _cat_client_state['running']:
        logger.warning('CAT update task already running')
        return

    interval = update_interval or config.wavelog.polling_interval
    _cat_client_state['running'] = True
    logger.info(f'WaveLog CAT update task gestartet (Intervall: {interval}s)')

    async def cat_update_loop():
        """Endlosschleife für zyklische Status-Updates."""
        consecutive_failures = 0

        while _cat_client_state['running']:
            try:
                # Client initialisieren wenn nötig
                client = await _get_or_create_cat_client()

                if client:
                    # Radio-Status auslesen
                    status = await _get_radio_status()

                    # An WaveLog senden wenn Daten vorhanden
                    if status['frequency_hz'] and status['mode']:
                        success = await client.send_radio_status(
                            frequency_hz=status['frequency_hz'],
                            mode=status['mode'],
                            power_w=status['power_w'],
                        )

                        if success:
                            consecutive_failures = 0
                            logger.debug(
                                f'Radio-Status an WaveLog gesendet: '
                                f'{status["frequency_hz"]} Hz, {status["mode"]}'
                            )
                            _cat_client_state['last_update'] = asyncio.get_event_loop().time()
                        else:
                            consecutive_failures += 1
                            if consecutive_failures % 6 == 1:
                                logger.warning(
                                    f'WaveLog-Update fehlgeschlagen '
                                    f'({consecutive_failures}x)'
                                )
                    else:
                        logger.debug('Radio-Status unvollständig, überspringe Update')

            except Exception as e:
                logger.error(f'Fehler im CAT-Update-Loop: {e}')
                consecutive_failures += 1

            # Warte bis zum nächsten Update
            await asyncio.sleep(interval)

    # Starte Task
    task = asyncio.create_task(cat_update_loop())
    _cat_client_state['task'] = task


async def stop_cat_update_task():
    """Stoppt zyklische CAT-Updates zu WaveLog."""
    _cat_client_state['running'] = False

    # Task beenden
    if _cat_client_state['task']:
        try:
            _cat_client_state['task'].cancel()
            await _cat_client_state['task']
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f'Fehler beim Stoppen des CAT-Tasks: {e}')
        finally:
            _cat_client_state['task'] = None

    # Client schließen
    if _cat_client_state['client']:
        try:
            await _cat_client_state['client'].close()
        except Exception as e:
            logger.error(f'Fehler beim Schließen des CAT-Clients: {e}')
        finally:
            _cat_client_state['client'] = None

    logger.info('WaveLog CAT update task gestoppt')


def get_cat_status() -> Dict[str, Any]:
    """
    Gibt aktuellen CAT-Client-Status zurück.

    Returns:
        Dict mit enabled, running, last_update
    """
    config = ConfigManager.get()
    return {
        'enabled': config.wavelog.enabled,
        'running': _cat_client_state['running'],
        'last_update': _cat_client_state['last_update'],
        'client_connected': _cat_client_state['client'] is not None,
    }


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

        if config.wavelog.enabled and config.wavelog.api_key_or_secret_ref:
            try:
                _resolve_wavelog_api_key(config)
            except SecretProviderError as exc:
                degraded_mode = True
                secret_provider_available = False
                logger.warning(f'Secret provider unavailable, running degraded: {exc}')

        return StatusResponse(
            usb_status=usb_status,
            usb_connected=(usb_status in [TransportStatus.CONNECTED, TransportStatus.COMMUNICATION_ERROR]),
            degraded_mode=degraded_mode,
            secret_provider_available=secret_provider_available,
            device_name=config.device.name,
            api_version=__version__,
            features=['set_frequency', 'set_mode', 'read_s_meter'],
            cat_status=get_cat_status(),
        )

    @router.get(
        '/logs',
        tags=['Logs'],
        summary='System-Logs abrufen',
    )
    async def get_logs(
        limit: int = Query(20, description='Max. Anzahl der Logs'),
        level: Optional[str] = Query(None, description='Optionaler Level-Filter (DEBUG/INFO/WARNING/ERROR/CRITICAL)'),
        newest_first: bool = Query(True, description='Neueste Eintraege zuerst ausgeben'),
    ) -> Dict[str, Any]:
        """
        Gibt die letzten System-Logs zurück (max. 1000 Zeilen im Buffer).

        Args:
            limit: Max. Anzahl der neuesten Logs (Standard: 20)
            level: Optionales Log-Level fuer serverseitiges Filtern
            newest_first: Reihenfolge der Ausgabe (neueste zuerst bei True)

        Returns:
            Dict mit 'logs' (Liste) und 'total' (Gesamtanzahl)
        """
        try:
            logs = RigBridgeLogger.get_logs(
                limit=limit,
                level=level,
                newest_first=newest_first,
            )
            return {
                'logs': logs,
                'total': len(logs),
                'limit': limit,
                'level': level,
                'newest_first': newest_first,
            }
        except Exception as e:
            logger.error(f'Failed to retrieve logs: {e}')
            raise HTTPException(status_code=500, detail=f'Failed to retrieve logs: {str(e)}')

    @router.get(
        '/config',
        response_model=ConfigResponse,
        tags=['Config'],
        summary='Aktuelle Konfiguration abrufen',
    )
    async def get_config() -> ConfigResponse:
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

        if response['wavelog'].get('api_key_or_secret_ref'):
            response['wavelog']['api_key_or_secret_ref'] = '***'

        return response

    @router.put(
        '/config',
        response_model=ConfigUpdateResponse,
        tags=['Config'],
        summary='Konfiguration aktualisieren',
    )
    async def update_config(request: ConfigUpdateRequest) -> ConfigUpdateResponse:
        """Aktualisiert Konfiguration und speichert sie persistent in config.json."""
        config = ConfigManager.get()
        payload = request.model_dump(exclude_none=True)

        if 'usb' in payload:
            for key, value in payload['usb'].items():
                setattr(config.usb, key, value)
            # Invalidiere gecachten Executor damit er mit neuen USB-Settings neu erstellt wird
            _global_executor_cache.clear()
            logger.debug('CIV Executor Cache invalidiert (USB-Config aktualisiert)')

        if 'api' in payload:
            api_values = payload['api']
            log_level_changed = False

            if 'log_level' in api_values:
                try:
                    old_level = config.api.log_level
                    config.api.log_level = LogLevel(api_values['log_level'])

                    # Logger neu konfigurieren wenn Log-Level sich geändert hat
                    if old_level != config.api.log_level:
                        log_level_changed = True
                        level_map = {
                            LogLevel.DEBUG: logging.DEBUG,
                            LogLevel.INFO: logging.INFO,
                            LogLevel.WARNING: logging.WARNING,
                            LogLevel.ERROR: logging.ERROR,
                        }
                        RigBridgeLogger.configure(level=level_map[config.api.log_level])
                        logger.info(f"Log-Level geändert: {old_level.value} → {config.api.log_level.value}")

                except ValueError as exc:
                    raise HTTPException(status_code=422, detail=f'Invalid log_level: {exc}')

            for key, value in api_values.items():
                if key != 'log_level':
                    setattr(config.api, key, value)

        if 'wavelog' in payload:
            for key, value in payload['wavelog'].items():
                setattr(config.wavelog, key, value)
            # Invalidiere gecachten CAT-Client damit er mit neuen Settings neu erstellt wird
            _cat_client_state['client'] = None
            logger.debug('WaveLog CAT-Client Cache invalidiert (Config aktualisiert)')

            # Starte CAT-Task mit neuer Konfiguration neu
            await stop_cat_update_task()
            if config.wavelog.enabled:
                logger.info('Starte CAT-Update-Task mit aktualisierter Konfiguration neu...')
                await start_cat_update_task()

        if 'secret_provider' in payload:
            for key, value in payload['secret_provider'].items():
                setattr(config.secret_provider, key, value)

        if 'device' in payload:
            for key, value in payload['device'].items():
                setattr(config.device, key, value)

        ConfigManager.save()

        return ConfigUpdateResponse(
            success=True,
            message='Configuration updated',
        )

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
                logger.debug(f'Frequency read: {frequency} Hz')
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
                logger.debug(f'Frequency set to {request.frequency_hz} Hz')
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
                logger.debug(f'Mode read: {mode}')
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
                logger.debug(f'Mode set to {request.mode}')
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
                logger.debug(f'S-Meter read: {raw_value} (raw) = {db_value} dB')
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
        response_model=CommandListResponse,
        tags=['Info'],
        summary='Verfügbare Befehle auflisten',
    )
    async def list_commands() -> CommandListResponse:
        """Gibt eine Liste aller verfügbaren Befehle zurück."""
        try:
            executor = get_executor()
            commands = executor.parser.list_commands()
            logger.debug(f'Listed {len(commands)} available commands')
            return CommandListResponse(commands=sorted(commands))
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

            # Prüfe ob API-Key-Referenz/Fallback vorhanden ist
            if not config.wavelog.api_key_or_secret_ref:
                return WavelogTestResponse(
                    success=False,
                    message='Wavelog API key reference not configured',
                )

            # Versuche API-Key aufzulösen (Secret-Ref oder Direktwert)
            try:
                api_key = _resolve_wavelog_api_key(config)
            except SecretProviderError as e:
                return WavelogTestResponse(
                    success=False,
                    message=f'Secret provider error: {str(e)}',
                )

            try:
                stations_raw = await _fetch_wavelog_station_info(config, api_key)
                logger.info(f'Wavelog connection test successful ({len(stations_raw)} stations)')
                return WavelogTestResponse(
                    success=True,
                    message='Wavelog is reachable and authenticated',
                    station_count=len(stations_raw),
                )
            except (httpx.HTTPError, ValueError) as e:
                logger.warning(f'Wavelog connection test failed: {e}')
                return WavelogTestResponse(
                    success=False,
                    message=f'Wavelog request failed: {str(e)}',
                    station_count=0,
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

            api_key = _resolve_wavelog_api_key(config)
            stations_raw = await _fetch_wavelog_station_info(config, api_key)

            stations: List[WavelogStation] = []
            for entry in stations_raw:
                try:
                    station_id = int(entry.get('station_id'))
                    name = str(entry.get('station_profile_name') or entry.get('name') or '').strip()
                    callsign = str(entry.get('station_callsign') or entry.get('callsign') or '').strip()
                    if station_id and name and callsign:
                        stations.append(
                            WavelogStation(id=station_id, name=name, callsign=callsign)
                        )
                except (TypeError, ValueError):
                    continue

            logger.info(f'Retrieved {len(stations)} stations from Wavelog')
            return WavelogStationsResponse(stations=stations)

        except Exception as e:
            logger.error(f'Get Wavelog stations failed: {e}')
            return WavelogStationsResponse(stations=[])

    # ========================================================================
    # DEVICE DISCOVERY ENDPOINTS
    # ========================================================================

    @router.get(
        '/devices',
        response_model=DeviceListResponse,
        tags=['Info'],
        summary='Verfügbare Funkgeräte auflisten',
    )
    async def list_devices() -> DeviceListResponse:
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
            return DeviceListResponse(devices=sorted(devices, key=lambda d: d.name))

        except Exception as e:
            logger.error(f'Device list failed: {e}')
            return DeviceListResponse(devices=[])

    # ========================================================================
    # CAT CLIENT CONTROL ENDPOINTS
    # ========================================================================

    @router.post(
        '/cat/start',
        tags=['CAT'],
        summary='Startet CAT-Status-Updates zu WaveLog',
    )
    async def start_cat():
        """Startet den CAT-Background-Task für automatische Radio-Status-Updates."""
        try:
            await start_cat_update_task()
            return {'success': True, 'message': 'CAT update task started'}
        except Exception as e:
            logger.error(f'Failed to start CAT task: {e}')
            raise HTTPException(status_code=500, detail=str(e))

    @router.post(
        '/cat/stop',
        tags=['CAT'],
        summary='Stoppt CAT-Status-Updates zu WaveLog',
    )
    async def stop_cat():
        """Stoppt den CAT-Background-Task."""
        try:
            await stop_cat_update_task()
            return {'success': True, 'message': 'CAT update task stopped'}
        except Exception as e:
            logger.error(f'Failed to stop CAT task: {e}')
            raise HTTPException(status_code=500, detail=str(e))

    @router.get(
        '/cat/status',
        tags=['CAT'],
        summary='CAT-Client-Status abrufen',
    )
    async def get_cat_client_status():
        """Gibt den aktuellen Status des CAT-Clients zurück."""
        return get_cat_status()

    @router.post(
        '/cat/send-now',
        tags=['CAT'],
        summary='Sendet sofort aktuellen Radio-Status an WaveLog',
    )
    async def send_cat_now():
        """Sendet einmalig den aktuellen Radio-Status, unabhängig vom Background-Task."""
        try:
            config = ConfigManager.get()

            if not config.wavelog.enabled:
                return {'success': False, 'message': 'WaveLog is not enabled'}

            # Client holen/erstellen
            client = await _get_or_create_cat_client()
            if not client:
                return {'success': False, 'message': 'Failed to create CAT client'}

            # Status auslesen
            status = await _get_radio_status()

            if not status['frequency_hz'] or not status['mode']:
                return {
                    'success': False,
                    'message': 'Radio status incomplete',
                    'status': status,
                }

            # An WaveLog senden
            success = await client.send_radio_status(
                frequency_hz=status['frequency_hz'],
                mode=status['mode'],
                power_w=status['power_w'],
            )

            return {
                'success': success,
                'message': 'Status sent' if success else 'Failed to send status',
                'status': status,
            }

        except Exception as e:
            logger.error(f'Failed to send status: {e}')
            raise HTTPException(status_code=500, detail=str(e))

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
