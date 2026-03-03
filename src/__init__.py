"""RigBridge - Amateurfunk Geräte-Steuerung über USB/CI-V."""

from pathlib import Path


def _get_version() -> str:
    """Lädt die Version aus der VERSION-Datei im Root-Verzeichnis."""
    try:
        version_file = Path(__file__).parent.parent / 'VERSION'
        return version_file.read_text(encoding='utf-8').strip()
    except Exception:
        return '0.1.0'


__version__ = _get_version()
__author__ = 'RigBridge Contributors'
