"""
FastAPI Hauptanwendung für RigBridge.

Definiert die REST-API und initialisiert alle Services.
"""

from fastapi import FastAPI
from pathlib import Path
import logging

from ..config.logger import RigBridgeLogger, StructuredFormatter
from ..config.settings import ConfigManager, LogLevel
from .routes import create_router

# Logger-Initialisierung
logger = RigBridgeLogger.get_logger(__name__)


def get_version() -> str:
    """Lädt die Version aus der VERSION-Datei."""
    try:
        version_file = Path(__file__).parent.parent.parent.parent / 'VERSION'
        return version_file.read_text(encoding='utf-8').strip()
    except Exception:
        return '0.1.0'


def create_app(
    config_path: Path = Path('config.json'),
    log_level: LogLevel = LogLevel.INFO,
) -> FastAPI:
    """
    Factory-Funktion zum Erstellen der FastAPI-Anwendung.

    Args:
        config_path: Pfad zur Konfigurationsdatei
        log_level: Globales Log-Level

    Returns:
        Konfigurierte FastAPI-Instanz
    """
    # Logger konfigurieren
    level_map = {
        LogLevel.DEBUG: logging.DEBUG,
        LogLevel.INFO: logging.INFO,
        LogLevel.WARNING: logging.WARNING,
        LogLevel.ERROR: logging.ERROR,
    }
    RigBridgeLogger.configure(level=level_map[log_level])

    # Uvicorn- und andere Logger auch mit StructuredFormatter konfigurieren
    for logger_name in ['uvicorn', 'uvicorn.error']:
        logger_obj = logging.getLogger(logger_name)
        logger_obj.setLevel(level_map[log_level])
        logger_obj.propagate = False

        # Alte Handler entfernen
        for handler in logger_obj.handlers[:]:
            logger_obj.removeHandler(handler)

        # Neue Handler mit StructuredFormatter hinzufügen
        stdout_handler = logging.StreamHandler()
        stdout_handler.setFormatter(StructuredFormatter())
        logger_obj.addHandler(stdout_handler)

    # Uvicorn Access Logger - speziell konfigurieren
    access_logger = logging.getLogger('uvicorn.access')
    access_logger.setLevel(level_map[log_level])
    access_logger.propagate = False

    # Alte Handler entfernen
    for handler in access_logger.handlers[:]:
        access_logger.removeHandler(handler)

    # Access-Handler mit StructuredFormatter hinzufügen
    access_handler = logging.StreamHandler()
    access_handler.setFormatter(StructuredFormatter())
    access_logger.addHandler(access_handler)

    # Konfiguration laden
    config = ConfigManager.initialize(config_path)
    logger.info(f'Configuration loaded from {config_path}')
    logger.info(f'Device: {config.device.name}')
    logger.info(f'USB Port: {config.usb.port} ({config.usb.baud_rate} baud)')

    # FastAPI-Anwendung
    app_version = get_version()
    app = FastAPI(
        title='RigBridge API',
        description='REST API für Amateurfunk-Geräte-Steuerung',
        version=app_version,
        docs_url='/api/docs',
        redoc_url='/api/redoc',
        openapi_url='/api/openapi.json',
    )

    # Middleware für Logging
    @app.middleware('http')
    async def log_requests(request, call_next):
        logger.debug(f'{request.method} {request.url.path}')
        response = await call_next(request)
        logger.debug(f'Response: {response.status_code}')
        return response

    # Health-Check
    @app.get('/health', tags=['Health'])
    async def health_check():
        """Health-Check Endpunkt für Monitoring/Docker."""
        return {
            'status': 'ok',
            'device': config.device.name,
            'api_version': get_version(),
        }

    # Router registrieren
    router = create_router()
    app.include_router(router, prefix='/api')

    logger.info('FastAPI application created and configured')
    return app


if __name__ == '__main__':
    logger.error('Direkter Start von src.backend.api.main ist nicht unterstützt.')
    logger.error('Bitte starte RigBridge mit: python run_api.py')
    raise SystemExit(2)
