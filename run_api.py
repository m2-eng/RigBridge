#!/usr/bin/env python3
"""
RigBridge API Startup-Script.

Startet den FastAPI-Server anhand der config.json Konfiguration.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.backend.config import RigBridgeLogger, ConfigManager
from src.backend.api import create_app


def main():
    """Starte den API-Server basierend auf config.json."""
    config_file = Path('config.json')

    # Konfiguriere Logger
    logger = RigBridgeLogger.get_logger('rigbridge.startup')

    # Verifiziere Config
    if not config_file.exists():
        logger.error(f"config.json nicht gefunden: {config_file.absolute()}")
        return 1

    # Laden Sie die Konfiguration
    try:
        config = ConfigManager.initialize(config_file)
        logger.info(f"Konfiguration geladen: {config_file.absolute()}")
        logger.info(f"Device: {config.device.name}")
        logger.info(f"USB-Port: {config.usb.port} @ {config.usb.baud_rate} baud")
    except Exception as e:
        logger.error(f"Fehler beim Laden der Konfiguration: {e}")
        return 1

    # Erstelle App
    try:
        app = create_app(config_path=config_file)
        logger.info("FastAPI App erstellt")
    except Exception as e:
        logger.error(f"Fehler beim Erstellen der App: {e}")
        return 1

    # Starte uvicorn
    logger.info(f"Starte Server auf {config.api.host}:{config.api.port}")
    logger.info(f"Swagger UI: http://{config.api.host}:{config.api.port}/api/docs")
    logger.info(f"ReDoc: http://{config.api.host}:{config.api.port}/api/redoc")

    try:
        import uvicorn
        uvicorn.run(
            app,
            host=config.api.host,
            port=config.api.port,
            reload=False,
            workers=1,
            log_config=None,  # Verwende vorkonfigurierte Logger, nicht uvicorn defaults
        )
    except ImportError:
        logger.error("uvicorn nicht installiert!")
        logger.error("Installiere mit: pip install uvicorn")
        return 1
    except KeyboardInterrupt:
        logger.info("Server heruntergefahren")
        return 0
    except Exception as e:
        logger.error(f"Fehler beim Server-Start: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
