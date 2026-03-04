"""
Pytest Konfiguration und Shared Fixtures für RigBridge Tests.
"""

import sys
from pathlib import Path

import pytest

# Setup Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.backend.config.logger import RigBridgeLogger
from src.backend.config.settings import ConfigManager


@pytest.fixture(scope="session", autouse=True)
def setup_logging():
    """Initialisiere Logging vor allen Tests."""
    RigBridgeLogger.configure()
    logger = RigBridgeLogger.get_logger("tests")
    logger.info("=" * 70)
    logger.info("RigBridge Test Suite - Tests starten")
    logger.info("=" * 70)
    yield
    logger.info("=" * 70)
    logger.info("RigBridge Test Suite - Tests beendet")
    logger.info("=" * 70)


@pytest.fixture(scope="session")
def project_root():
    """Gebe das Projekt-Root-Verzeichnis zurück."""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def protocol_file():
    """Protokolldatei für IC-905."""
    return PROJECT_ROOT / "protocols" / "manufacturers" / "icom" / "ic905.yaml"


@pytest.fixture(scope="session")
def manufacturer_file():
    """Herstellerdatei für Icom."""
    return PROJECT_ROOT / "protocols" / "manufacturers" / "icom" / "icom.yaml"


@pytest.fixture(scope="session")
def config_manager():
    """ConfigManager Instanz."""
    return ConfigManager.initialize()


@pytest.fixture(scope="session")
def logger():
    """Logger für Tests."""
    return RigBridgeLogger.get_logger("tests")
