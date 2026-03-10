"""
API-Routen für RigBridge.

Definiert REST-Endpunkte für Funk-Geräte-Steuerung und Konfiguration.

WICHTIG: Alle USB-Zugriffe werden durch TransportManager synchronisiert.
Keine Race Conditions zwischen Health-Check und API-Befehlen.
"""

import asyncio
import httpx
import logging
import yaml
from fastapi import APIRouter, HTTPException, Query, Path as PathParam
from pydantic import BaseModel, Field
from typing import Any, Optional, Dict, List
from pathlib import Path
from dataclasses import asdict
from enum import Enum

from ..config.logger import RigBridgeLogger
from ..config.settings import ConfigManager, LogLevel
from ..config.secret_provider import create_secret_provider, SecretProviderError
from ..protocol import ProtocolManager
from ..protocol.civ_protocol import CIVProtocol
from ..protocol.base_protocol import CommandResult
from ..transport import USBConnection, TransportStatus
from ..cat.cat_client import WavelogCatClient
from ..cat.connection_state import CatConnectionState, CatConnectionStatus
from src import __version__

logger = RigBridgeLogger.get_logger(__name__)

# ============================================================================
# Globaler Protocol Manager (Singleton)
# ============================================================================
_global_protocol_manager: Optional[ProtocolManager] = None


def _get_or_create_protocol_manager() -> ProtocolManager:
    """
    Globale ProtocolManager-Instanz (Singleton).
    Wird von Health-Check und API-Endpunkten gemeinsam genutzt.
    """
    global _global_protocol_manager

    if _global_protocol_manager is None:
        try:
            config = ConfigManager.get()
            protocol_file = config.device.get_protocol_path()
            manufacturer_file = config.device.get_manufacturer_path()

            # CIVProtocol-Instanz erstellen
            protocol = CIVProtocol(
                protocol_file=protocol_file,
                manufacturer_file=manufacturer_file
            )
            # Konfigurierte Adressen aus config.json haben Vorrang vor YAML-Defaults.
            protocol.set_addresses(
                config.device.controller_address,
                config.device.radio_address,
            )
            logger.debug(f'CIVProtocol initialized for {protocol_file}')

            # USB-Connection initialisieren
            try:
                usb_conn = USBConnection(config.usb)
                protocol.set_usb_connection(usb_conn)
                logger.info(f'USB Connection configured for {config.usb.port} @ {config.usb.baud_rate} baud')

                # Registriere ProtocolManager als Unsolicited-Frame-Handler am Transport
                # Wrapper-Funktion, um FrameData in bytes zu konvertieren
                def unsolicited_frame_handler(frame_data):
                    """Handler für unsolicited frames vom Transport → ProtocolManager."""
                    try:
                        # Extrahiere raw bytes aus FrameData
                        raw_bytes = frame_data.raw_bytes if hasattr(frame_data, 'raw_bytes') else bytes(frame_data)
                        # Leite an ProtocolManager weiter (dieser prüft Radio-ID)
                        # Verwende create_task, da handle_unsolicited_frame async ist
                        asyncio.create_task(_global_protocol_manager.handle_unsolicited_frame(raw_bytes))
                    except Exception as e:
                        logger.error(f'Error in unsolicited frame handler: {e}')

                usb_conn.register_unsolicited_handler(unsolicited_frame_handler)
                logger.debug('ProtocolManager registered as unsolicited frame handler')

            except Exception as e:
                logger.warning(f'Failed to initialize USB connection: {e} - Using mock data')

            # ProtocolManager erstellen und Protokoll setzen
            _global_protocol_manager = ProtocolManager()
            _global_protocol_manager.set_protocol(protocol)
            logger.info('ProtocolManager initialized with CIVProtocol')

        except Exception as e:
            logger.error(f'Failed to create ProtocolManager: {e}')
            raise

    return _global_protocol_manager


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


def _is_auth_related_error(error_text: str) -> bool:
    """Heuristik: Erkennt API-Key/Auth-bezogene Fehlertexte."""
    text = (error_text or '').lower()
    patterns = [
        '401',
        '403',
        'unauthorized',
        'forbidden',
        'api key',
        'apikey',
        'auth',
        'token',
        'authentication',
    ]
    return any(p in text for p in patterns)


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


class PowerResponse(BaseModel):
    """Response für Sendeleistungs-Lesungen (VORBEREITET)."""
    power_w: float = Field(
        description='Sendeleistung in Watt [W]'
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
    default_controller: int = Field(description='Standard Controller-Adresse aus frame.default_controller')
    default_radio: int = Field(description='Standard Funkgerät-Adresse aus frame.default_radio')


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


class LicenseResponse(BaseModel):
    """Response mit Lizenzinhalten."""
    content: str = Field(
        description='Inhalt der LICENSE-Datei'
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
    health_check_enabled: Optional[bool] = None
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
    controller_address: Optional[int] = None
    radio_address: Optional[int] = None


class ConfigUpdateRequest(BaseModel):
    usb: Optional[USBConfigUpdate] = None
    api: Optional[APIConfigUpdate] = None
    wavelog: Optional[WavelogConfigUpdate] = None
    secret_provider: Optional[SecretProviderConfigUpdate] = None
    device: Optional[DeviceConfigUpdate] = None


def _parse_yaml_int(value: Any, fallback: int) -> int:
    """Parst int oder Hex-String robust."""
    if value is None:
        return fallback
    if isinstance(value, str):
        return int(value, 0)
    return int(value)


def _read_device_defaults(protocol_path: Path) -> tuple[int, int]:
    """Liest frame.default_controller/default_radio aus einer Geräte-YAML."""
    default_controller = 0xE0
    default_radio = 0xA4

    with open(protocol_path, 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f) or {}

    root = raw.get('protocol', raw)
    frame = root.get('frame', {}) if isinstance(root, dict) else {}

    return (
        _parse_yaml_int(frame.get('default_controller'), default_controller),
        _parse_yaml_int(frame.get('default_radio'), default_radio),
    )


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
    'last_send_success': None,
    'last_test_success': None,
    'last_error': None,
    'connection_state': CatConnectionState(),
}


async def _perform_usb_health_check() -> TransportStatus:
    """
    Führt einen USB-Verbindungstest durch.

    Sendet den 'read_transceiver_id' Befehl und evaluiert die Antwort.
    Bei Fehler wird automatisch ein Reconnect-Versuch unternommen.

    WICHTIG: Nutzt TransportManager automatisch via protocol_manager.execute_command()
    für Synchronisierung.

    Returns:
        TransportStatus: disconnected, attached oder connected
    """
    try:
        protocol_manager = _get_or_create_protocol_manager()

        # Port ist offen - teste ob Gerät antwortet
        # execute_command ist ASYNC und nutzt TransportManager automatisch
        result = await protocol_manager.execute_command(
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
    protocol_manager = _get_or_create_protocol_manager()
    protocol = protocol_manager.get_protocol()

    if protocol and hasattr(protocol, '_executor') and protocol._executor.usb_connection:
        return protocol._executor.usb_connection.state.status

    return TransportStatus.DISCONNECTED


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
        protocol_manager = _get_or_create_protocol_manager()

        # Frequenz auslesen
        frequency_hz = await protocol_manager.get_frequency()

        # Modus auslesen
        mode = await protocol_manager.get_mode()

        # Power auslesen (wenn Befehl verfügbar) - VORBEREITET
        power_w = await protocol_manager.get_power()

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
        _cat_client_state['last_error'] = 'WaveLog disabled'
        _cat_client_state['connection_state'].update_status(
            CatConnectionStatus.DISCONNECTED,
            error='WaveLog disabled',
        )
        return None

    # Erstelle Client wenn noch nicht vorhanden
    if _cat_client_state['client'] is None:
        try:
            # Prüfe ob API-Key konfiguriert ist
            if not config.wavelog.api_key_or_secret_ref:
                logger.warning('Wavelog API-Key ist nicht konfiguriert')
                _cat_client_state['last_error'] = 'Wavelog API-Key ist nicht konfiguriert'
                _cat_client_state['connection_state'].update_status(
                    CatConnectionStatus.WARNING,
                    error='Wavelog API-Key ist nicht konfiguriert',
                )
                return None

            # API-Key auflösen (Secret-Ref oder direkter Key)
            try:
                api_key = _resolve_wavelog_api_key(config)
            except SecretProviderError as e:
                logger.warning(f'Konnte API-Key nicht laden: {e}')
                _cat_client_state['last_error'] = f'Konnte API-Key nicht laden: {e}'
                _cat_client_state['connection_state'].update_status(
                    CatConnectionStatus.WARNING,
                    error=f'Konnte API-Key nicht laden: {e}',
                )
                return None

            # Client erstellen (Context Manager wird NICHT verwendet im Background-Task)
            client = WavelogCatClient(config.wavelog, api_key=api_key)

            # HTTP Client manuell initialisieren
            await client.__aenter__()

            _cat_client_state['client'] = client
            _cat_client_state['last_error'] = None
            # Client erstellt: noch kein verifizierter End-to-End Test, Status bleibt wie bisher
            logger.info('WaveLog CAT Client erstellt')

        except Exception as e:
            logger.error(f'Fehler beim Erstellen des CAT-Clients: {e}')
            _cat_client_state['last_error'] = f'Fehler beim Erstellen des CAT-Clients: {e}'
            _cat_client_state['connection_state'].update_status(
                CatConnectionStatus.DISCONNECTED,
                error=f'Fehler beim Erstellen des CAT-Clients: {e}',
            )
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
        _cat_client_state['last_error'] = 'WaveLog CAT-Integration ist deaktiviert'
        _cat_client_state['connection_state'].update_status(
            CatConnectionStatus.DISCONNECTED,
            error='WaveLog CAT-Integration ist deaktiviert',
        )
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
                            _cat_client_state['last_send_success'] = True
                            _cat_client_state['last_error'] = None
                            _cat_client_state['connection_state'].update_status(
                                CatConnectionStatus.CONNECTED
                            )
                            logger.debug(
                                f'Radio-Status an WaveLog gesendet: '
                                f'{status["frequency_hz"]} Hz, {status["mode"]}'
                            )
                            _cat_client_state['last_update'] = asyncio.get_event_loop().time()
                        else:
                            consecutive_failures += 1
                            _cat_client_state['last_send_success'] = False
                            _cat_client_state['last_error'] = 'WaveLog-Update fehlgeschlagen'
                            if getattr(client, 'last_error_kind', None) == 'auth':
                                _cat_client_state['connection_state'].update_status(
                                    CatConnectionStatus.WARNING,
                                    error='WaveLog API-Key/Authentifizierung fehlgeschlagen',
                                )
                            else:
                                _cat_client_state['connection_state'].update_status(
                                    CatConnectionStatus.DISCONNECTED,
                                    error='WaveLog-Update fehlgeschlagen',
                                )
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
                _cat_client_state['last_send_success'] = False
                _cat_client_state['last_error'] = f'Fehler im CAT-Update-Loop: {e}'
                _cat_client_state['connection_state'].update_status(
                    CatConnectionStatus.DISCONNECTED,
                    error=f'Fehler im CAT-Update-Loop: {e}',
                )

            # Warte bis zum nächsten Update
            await asyncio.sleep(interval)

    # Starte Task
    task = asyncio.create_task(cat_update_loop())
    _cat_client_state['task'] = task


async def stop_cat_update_task():
    """Stoppt zyklische CAT-Updates zu WaveLog."""
    _cat_client_state['running'] = False
    _cat_client_state['connection_state'].update_status(CatConnectionStatus.DISCONNECTED)

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
        'connection_status': _cat_client_state['connection_state'].status.value,
        'connected': _cat_client_state['connection_state'].is_connected(),
        'last_send_success': _cat_client_state['last_send_success'],
        'last_test_success': _cat_client_state['last_test_success'],
        'last_error_kind': getattr(_cat_client_state['client'], 'last_error_kind', None) if _cat_client_state['client'] else None,
        'last_error': _cat_client_state['last_error'] or _cat_client_state['connection_state'].last_error,
    }


# ============================================================================
# Router und Endpunkte
# ============================================================================


def create_router() -> APIRouter:
    """Erstellt und konfiguriert den API-Router."""
    router = APIRouter()

    def get_protocol_manager() -> ProtocolManager:
        """Gibt die globale ProtocolManager-Instanz zurück."""
        return _get_or_create_protocol_manager()

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
            features=['read_s_meter'],
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
            # Invalidiere ProtocolManager damit er mit neuen USB-Settings neu erstellt wird
            global _global_protocol_manager
            _global_protocol_manager = None
            logger.debug('ProtocolManager invalidiert (USB-Config aktualisiert)')

        if 'api' in payload:
            api_values = payload['api']
            log_level_changed = False
            health_check_changed = False
            new_health_check_enabled = config.api.health_check_enabled

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
                    if key == 'health_check_enabled':
                        health_check_changed = (config.api.health_check_enabled != value)
                        new_health_check_enabled = value
                    setattr(config.api, key, value)

            if health_check_changed:
                if new_health_check_enabled:
                    logger.info('Health check aktiviert - starte Background-Task')
                    await start_usb_health_check_task()
                else:
                    logger.info('Health check deaktiviert - stoppe Background-Task')
                    await stop_usb_health_check_task()

        if 'wavelog' in payload:
            for key, value in payload['wavelog'].items():
                setattr(config.wavelog, key, value)

            # Starte CAT-Task mit neuer Konfiguration neu
            await stop_cat_update_task()
            if config.wavelog.enabled:
                logger.info('Starte CAT-Update-Task mit aktualisierter Konfiguration neu...')
                await start_cat_update_task()

        if 'secret_provider' in payload:
            for key, value in payload['secret_provider'].items():
                setattr(config.secret_provider, key, value)

        if 'device' in payload:
            device_values = payload['device']
            device_selection_changed = any(
                k in device_values for k in ('manufacturer', 'protocol_file')
            )

            for key, value in device_values.items():
                setattr(config.device, key, value)

            # Bei Gerätewechsel Standard-Adressen aus der gewählten YAML verwenden,
            # falls keine expliziten Adressen im Request übergeben wurden.
            if device_selection_changed:
                try:
                    default_controller, default_radio = _read_device_defaults(
                        config.device.get_protocol_path()
                    )

                    if 'controller_address' not in device_values:
                        config.device.controller_address = default_controller
                    if 'radio_address' not in device_values:
                        config.device.radio_address = default_radio
                except Exception as e:
                    logger.warning(f'Could not read device defaults from YAML: {e}')

            # ProtocolManager muss nach Geräte-/Adressänderung neu aufgebaut werden.
            _global_protocol_manager = None
            logger.debug('ProtocolManager invalidiert (Device-Config aktualisiert)')

        ConfigManager.save()

        return ConfigUpdateResponse(
            success=True,
            message='Configuration updated',
        )

    # ========================================================================
    # ALLGEMEINE COMMAND ENDPOINTS (Generische API)
    # ========================================================================

    @router.get(
        '/rig/command',
        response_model=CommandResponse,
        tags=['Commands'],
        summary='Generischer Befehl ausführen (GET - lesend)',
    )
    async def execute_generic_command_get(
        name: str = Query(
            description='Name des Befehls aus YAML (z.B. "read_s_meter")'
        ),
    ) -> CommandResponse:
        """
        Führt einen read-only Befehl aus der YAML-Protokolldefinition aus.

        Diese generische API unterstützt alle in der YAML definierten Lesebefehle.
        ProtocolManager kümmert sich automatisch um Synchronisierung.

        Beispiel: `GET /api/rig/command?name=read_s_meter`
        """
        try:
            protocol_manager = get_protocol_manager()
            result = await protocol_manager.execute_command(name)

            if result.success:
                logger.info(f'Command executed: {name}')
                return CommandResponse(
                    success=True,
                    command=name,
                    data=result.data,
                )
            else:
                logger.warning(f'Command failed: {name} - {result.error}')
                raise HTTPException(status_code=400, detail=result.error)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'Command execution error: {e}')
            raise HTTPException(status_code=500, detail=str(e))

    @router.put(
        '/rig/command',
        response_model=CommandResponse,
        tags=['Commands'],
        summary='Generischer Befehl ausführen (PUT - schreibend)',
    )
    async def execute_generic_command_put(
        request: CommandRequest,
    ) -> CommandResponse:
        """
        Führt einen schreibenden Befehl aus der YAML-Protokolldefinition aus.

        Diese generische API unterstützt alle in der YAML definierten Schreibbefehle.
        ProtocolManager kümmert sich automatisch um Synchronisierung.

        Request Body Beispiel:
        ```json
        {
            "command": "set_operating_frequency",
            "data": {"frequency": 145500000}
        }
        ```
        """
        try:
            protocol_manager = get_protocol_manager()
            result = await protocol_manager.execute_command(
                command_name=request.command,
                data=request.data
            )

            if result.success:
                logger.info(f'Command executed: {request.command}')
                return CommandResponse(
                    success=True,
                    command=request.command,
                    data=result.data,
                )
            else:
                logger.warning(f'Command failed: {request.command} - {result.error}')
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
            protocol_manager = get_protocol_manager()
            frequency = await protocol_manager.get_frequency()

            if frequency is not None:
                logger.debug(f'Frequency read: {frequency} Hz')
                return FrequencyResponse(frequency_hz=frequency)
            else:
                raise HTTPException(
                    status_code=400,
                    detail='Failed to read frequency'
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'Frequency read failed: {e}')
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
            protocol_manager = get_protocol_manager()
            mode = await protocol_manager.get_mode()

            if mode is not None:
                logger.debug(f'Mode read: {mode}')
                return ModeResponse(mode=mode)
            else:
                raise HTTPException(
                    status_code=400,
                    detail='Failed to read mode'
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'Mode read failed: {e}')
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
            protocol_manager = get_protocol_manager()
            result = await protocol_manager.execute_command('read_s_meter')

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
    # SPECIFIC POWER ENDPOINTS (VORBEREITET)
    # ========================================================================

    @router.get(
        '/rig/power',
        response_model=PowerResponse,
        tags=['Power'],
        summary='Aktuelle Sendeleistung auslesen (VORBEREITET)',
    )
    async def get_power() -> PowerResponse:
        """
        Liest die aktuelle Sendeleistung des Geräts (VORBEREITET).

        Hinweis: Noch nicht vollständig implementiert.
        Abhängig von YAML-Protokolldefinitionen und Geräteunterstützung.
        """
        try:
            protocol_manager = get_protocol_manager()
            power = await protocol_manager.get_power()

            if power is not None:
                logger.debug(f'Power read: {power} W')
                return PowerResponse(power_w=power)
            else:
                raise HTTPException(
                    status_code=501,  # Not Implemented
                    detail='Power read not yet fully implemented or not supported by device'
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'Power read failed: {e}')
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
            protocol_manager = get_protocol_manager()
            commands = protocol_manager.list_commands()
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
                _cat_client_state['last_test_success'] = False
                _cat_client_state['last_error'] = 'Wavelog is not enabled in configuration'
                _cat_client_state['connection_state'].update_status(
                    CatConnectionStatus.DISCONNECTED,
                    error='Wavelog is not enabled in configuration',
                )
                return WavelogTestResponse(
                    success=False,
                    message='Wavelog is not enabled in configuration',
                )

            # Prüfe ob API-Key-Referenz/Fallback vorhanden ist
            if not config.wavelog.api_key_or_secret_ref:
                _cat_client_state['last_test_success'] = False
                _cat_client_state['last_error'] = 'Wavelog API key reference not configured'
                _cat_client_state['connection_state'].update_status(
                    CatConnectionStatus.WARNING,
                    error='Wavelog API key reference not configured',
                )
                return WavelogTestResponse(
                    success=False,
                    message='Wavelog API key reference not configured',
                )

            # Versuche API-Key aufzulösen (Secret-Ref oder Direktwert)
            try:
                api_key = _resolve_wavelog_api_key(config)
            except SecretProviderError as e:
                _cat_client_state['last_test_success'] = False
                _cat_client_state['last_error'] = f'Secret provider error: {str(e)}'
                _cat_client_state['connection_state'].update_status(
                    CatConnectionStatus.WARNING,
                    error=f'Secret provider error: {str(e)}',
                )
                return WavelogTestResponse(
                    success=False,
                    message=f'Secret provider error: {str(e)}',
                )

            try:
                stations_raw = await _fetch_wavelog_station_info(config, api_key)
                logger.info(f'Wavelog connection test successful ({len(stations_raw)} stations)')
                _cat_client_state['last_test_success'] = True
                _cat_client_state['last_error'] = None
                # Auch 0 Stationen sind ein valider Verbindungs-/Auth-Erfolg
                _cat_client_state['connection_state'].update_status(CatConnectionStatus.CONNECTED)
                return WavelogTestResponse(
                    success=True,
                    message='Wavelog is reachable and authenticated',
                    station_count=len(stations_raw),
                )
            except (httpx.HTTPError, ValueError) as e:
                logger.warning(f'Wavelog connection test failed: {e}')
                _cat_client_state['last_test_success'] = False
                _cat_client_state['last_error'] = f'Wavelog request failed: {str(e)}'
                if isinstance(e, httpx.HTTPStatusError) and e.response is not None and e.response.status_code in (401, 403):
                    _cat_client_state['connection_state'].update_status(
                        CatConnectionStatus.WARNING,
                        error=f'Wavelog request failed: {str(e)}',
                    )
                elif _is_auth_related_error(str(e)):
                    _cat_client_state['connection_state'].update_status(
                        CatConnectionStatus.WARNING,
                        error=f'Wavelog request failed: {str(e)}',
                    )
                else:
                    _cat_client_state['connection_state'].update_status(
                        CatConnectionStatus.DISCONNECTED,
                        error=f'Wavelog request failed: {str(e)}',
                    )
                return WavelogTestResponse(
                    success=False,
                    message=f'Wavelog request failed: {str(e)}',
                    station_count=0,
                )

        except Exception as e:
            logger.error(f'Wavelog test failed: {e}')
            _cat_client_state['last_test_success'] = False
            _cat_client_state['last_error'] = f'Test failed: {str(e)}'
            _cat_client_state['connection_state'].update_status(
                CatConnectionStatus.DISCONNECTED,
                error=f'Test failed: {str(e)}',
            )
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
                                try:
                                    default_controller, default_radio = _read_device_defaults(protocol_file)
                                except Exception as e:
                                    logger.warning(f'Could not read defaults for {protocol_file}: {e}')
                                    default_controller, default_radio = 0xE0, 0xA4
                                devices.append(DeviceInfo(
                                    name=f'{manufacturer.upper()} {device_name.upper()}',
                                    manufacturer=manufacturer,
                                    protocol_file=device_name,
                                    default_controller=default_controller,
                                    default_radio=default_radio,
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
                _cat_client_state['connection_state'].update_status(
                    CatConnectionStatus.DISCONNECTED,
                    error='WaveLog is not enabled',
                )
                _cat_client_state['last_send_success'] = False
                _cat_client_state['last_error'] = 'WaveLog is not enabled'
                return {'success': False, 'message': 'WaveLog is not enabled'}

            # Client holen/erstellen
            client = await _get_or_create_cat_client()
            if not client:
                _cat_client_state['last_send_success'] = False
                return {'success': False, 'message': 'Failed to create CAT client'}

            # Status auslesen
            status = await _get_radio_status()

            if not status['frequency_hz'] or not status['mode']:
                _cat_client_state['last_send_success'] = False
                _cat_client_state['last_error'] = 'Radio status incomplete'
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

            _cat_client_state['last_send_success'] = success
            if success:
                _cat_client_state['last_error'] = None
                _cat_client_state['connection_state'].update_status(CatConnectionStatus.CONNECTED)
                _cat_client_state['last_update'] = asyncio.get_event_loop().time()
            else:
                if getattr(client, 'last_error_kind', None) == 'auth':
                    _cat_client_state['last_error'] = 'WaveLog API-Key/Authentifizierung fehlgeschlagen'
                    _cat_client_state['connection_state'].update_status(
                        CatConnectionStatus.WARNING,
                        error='WaveLog API-Key/Authentifizierung fehlgeschlagen',
                    )
                else:
                    _cat_client_state['last_error'] = 'WaveLog Verbindung fehlgeschlagen'
                    _cat_client_state['connection_state'].update_status(
                        CatConnectionStatus.DISCONNECTED,
                        error='WaveLog Verbindung fehlgeschlagen',
                    )

            return {
                'success': success,
                'message': 'Status sent' if success else 'Failed to send status',
                'status': status,
            }

        except Exception as e:
            logger.error(f'Failed to send status: {e}')
            raise HTTPException(status_code=500, detail=str(e))

    # ========================================================================
    # LICENSE ENDPOINT
    # ========================================================================

    @router.get(
        '/license',
        response_model=LicenseResponse,
        tags=['Info'],
        summary='Lizenzinformation abrufen',
    )
    async def get_license() -> LicenseResponse:
        """Gibt den Inhalt der LICENSE-Datei zurück."""
        try:
            # LICENSE-Datei aus Repo-Root lesen
            license_path = Path(__file__).parent.parent.parent.parent / 'LICENSE'

            if not license_path.exists():
                logger.warning(f'LICENSE file not found at {license_path}')
                raise HTTPException(
                    status_code=404,
                    detail='LICENSE file not found'
                )

            # Datei mit UTF-8 Encoding lesen
            content = license_path.read_text(encoding='utf-8')
            logger.debug(f'LICENSE file served ({len(content)} bytes)')

            return LicenseResponse(content=content)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'Failed to read LICENSE file: {e}')
            raise HTTPException(
                status_code=500,
                detail=f'Failed to read LICENSE file: {str(e)}'
            )

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
