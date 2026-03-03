"""
API-Routen für RigBridge.

Definiert REST-Endpunkte für Funk-Geräte-Steuerung und Konfiguration.
"""

from fastapi import APIRouter, HTTPException, Query, Path as PathParam
from pydantic import BaseModel, Field
from typing import Any, Optional, Dict, List
from pathlib import Path

from ..config.logger import RigBridgeLogger
from ..config.settings import ConfigManager
from ..civ.executor import CIVCommandExecutor, CommandResult
from src import __version__

logger = RigBridgeLogger.get_logger(__name__)


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


class StatusResponse(BaseModel):
    """System-Status."""
    usb_connected: bool
    device_name: str
    api_version: str
    features: List[str]


# ============================================================================
# Router und Endpunkte
# ============================================================================


def create_router() -> APIRouter:
    """Erstellt und konfiguriert den API-Router."""
    router = APIRouter()

    # Lazy-Load: CIV-Executor wird bei erster Anfrage initialisiert
    _executor_cache: Dict[str, CIVCommandExecutor] = {}

    def get_executor() -> CIVCommandExecutor:
        """Gibt die CIV-Executor-Instanz zurück (Singleton)."""
        cache_key = 'default'
        if cache_key not in _executor_cache:
            config = ConfigManager.get()
            protocol_file = config.device.get_protocol_path()
            _executor_cache[cache_key] = CIVCommandExecutor(protocol_file)
            logger.debug(f'CIV Executor initialized for {protocol_file}')
        return _executor_cache[cache_key]

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
        return StatusResponse(
            usb_connected=True,
            device_name=config.device.name,
            api_version=__version__,
            features=['set_frequency', 'set_mode', 'read_s_meter'],
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

        Beispiel: `/api/command/read_s_meter`
        """
        try:
            executor = get_executor()
            result = executor.execute_command(command_name)

            if result.success:
                logger.info(f'Command executed: {command_name}')
                return CommandResponse(
                    success=True,
                    command=command_name,
                    data=result.data,
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=result.error or 'Command failed',
                )
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
            result = executor.execute_command(
                command_name,
                data=request.data,
            )

            if result.success:
                logger.info(f'Command executed: {command_name}')
                return CommandResponse(
                    success=True,
                    command=command_name,
                    data=result.data,
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=result.error or 'Command failed',
                )
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
            result = executor.execute_command('read_operating_frequency')

            if result.success and result.data:
                frequency_hz = result.data.get('frequency', 145500000)
                vfo = result.data.get('vfo', 'A')
                logger.debug(f'Frequency read: {frequency_hz} Hz (VFO {vfo})')
                return FrequencyResponse(
                    frequency_hz=frequency_hz,
                    vfo=vfo,
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=result.error or 'Failed to read frequency',
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
            result = executor.execute_command(
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
                return CommandResponse(
                    success=False,
                    command='set_operating_frequency',
                    data={'status': 'NG'},
                    error=result.error or 'Failed to set frequency',
                )
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
            result = executor.execute_command('read_operating_mode')

            if result.success and result.data:
                mode = result.data.get('mode', 'CW')
                filter_val = result.data.get('filter')
                logger.debug(f'Mode read: {mode}')
                return ModeResponse(
                    mode=mode,
                    filter=filter_val,
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=result.error or 'Failed to read mode',
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
            result = executor.execute_command(
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
                return CommandResponse(
                    success=False,
                    command='set_operating_mode',
                    data={'status': 'NG'},
                    error=result.error or 'Failed to set mode',
                )
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
            result = executor.execute_command('read_s_meter')

            if result.success and result.data:
                # S-Meter-Interpolation: 0x00 = 0dB, 0x78 = 54dB, 0xF1 = 114dB
                raw_value = result.data.get('level_high', 0)
                level_db = interpolate_s_meter(raw_value)
                logger.debug(f'S-Meter read: {raw_value} (0x{raw_value:02X}) -> {level_db:.1f} dB')
                return SMeterResponse(
                    level_db=level_db,
                    level_raw=raw_value,
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=result.error or 'Failed to read S-meter',
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
