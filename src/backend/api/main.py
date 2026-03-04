"""
FastAPI Hauptanwendung für RigBridge.

Definiert die REST-API und initialisiert alle Services.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging
import asyncio

from ..config.logger import RigBridgeLogger, StructuredFormatter
from ..config.settings import ConfigManager, LogLevel
from .routes import create_router, start_usb_health_check_task, stop_usb_health_check_task

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
    redaction_filter = RigBridgeLogger.get_redaction_filter()

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
        stdout_handler.addFilter(redaction_filter)
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
    access_handler.addFilter(redaction_filter)
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

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException):
        code = f'HTTP_{exc.status_code}'
        message = exc.detail if isinstance(exc.detail, str) else 'Request failed'
        return JSONResponse(
            status_code=exc.status_code,
            content={
                'error': True,
                'code': code,
                'message': message,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                'error': True,
                'code': 'VALIDATION_ERROR',
                'message': str(exc),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, _exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                'error': True,
                'code': 'INTERNAL_SERVER_ERROR',
                'message': 'Internal server error',
            },
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

    # Startup-Event: Starte USB-Health-Check Background-Task
    @app.on_event('startup')
    async def startup_usb_health_check():
        """Starte zyklische USB-Verbindungsprüfung beim Start."""
        try:
            asyncio.create_task(start_usb_health_check_task())
            logger.info('USB health check task started')
        except Exception as e:
            logger.error(f'Failed to start USB health check task: {e}')

    # Shutdown-Event: Stoppe USB-Health-Check
    @app.on_event('shutdown')
    async def shutdown_usb_health_check():
        """Stoppe zyklische Prüfung beim Shutdown."""
        try:
            await stop_usb_health_check_task()
            logger.info('USB health check task stopped')
        except Exception as e:
            logger.error(f'Failed to stop USB health check task: {e}')

    # Statische Dateien: Frontend (nur wenn vorhanden)
    frontend_path = Path(__file__).parent.parent.parent / 'frontend'
    if frontend_path.exists():
        # Mount static files aus src/frontend/assets und src/frontend/pages
        assets_path = frontend_path / 'assets'
        if assets_path.exists():
            app.mount('/assets', StaticFiles(directory=assets_path), name='assets')

        # Fallback: Alle unbekannten Routes geben index.html zurück (SPA-Navigation)
        @app.get('/{full_path:path}')
        async def serve_frontend(full_path: str):
            """Serve index.html für SPA-Navigation, oder spezifische Datei."""
            index_file = frontend_path / 'index.html'
            if index_file.exists():
                return FileResponse(index_file, media_type='text/html')
            # Fallback: 404 wenn index.html nicht existiert
            return JSONResponse(
                status_code=404,
                content={'error': True, 'code': 'NOT_FOUND', 'message': 'Frontend not configured'},
            )

    logger.info('FastAPI application created and configured')
    return app


if __name__ == '__main__':
    logger.error('Direkter Start von src.backend.api.main ist nicht unterstützt.')
    logger.error('Bitte starte RigBridge mit: python run_api.py')
    raise SystemExit(2)
