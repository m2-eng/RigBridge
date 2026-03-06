"""
Connection State Management fuer CAT/WaveLog.

Haltet den CAT-Verbindungszustand getrennt vom USB-Transportzustand.
"""

from enum import Enum
from typing import Optional

from ..config.logger import RigBridgeLogger

logger = RigBridgeLogger.get_logger(__name__)


class CatConnectionStatus(str, Enum):
    """Zustaende fuer CAT/WaveLog-Verbindung."""

    DISCONNECTED = "disconnected"
    WARNING = "warning"
    CONNECTED = "connected"


class CatConnectionState:
    """Einfache Zustandsmaschine fuer CAT-Verbindung."""

    def __init__(self):
        self.status = CatConnectionStatus.DISCONNECTED
        self.last_error: Optional[str] = None

    def update_status(self, new_status: CatConnectionStatus, error: Optional[str] = None) -> None:
        """Aktualisiert den Status und loggt Statuswechsel."""
        if new_status != self.status:
            old_status = self.status
            self.status = new_status
            logger.info(f"CAT-Statusaenderung: {old_status.value} -> {new_status.value}")

        if new_status == CatConnectionStatus.CONNECTED:
            self.last_error = None
        elif error:
            self.last_error = error

    def is_connected(self) -> bool:
        """True wenn CAT verbunden ist."""
        return self.status == CatConnectionStatus.CONNECTED

    def is_warning(self) -> bool:
        """True wenn CAT im Warnungszustand ist."""
        return self.status == CatConnectionStatus.WARNING
