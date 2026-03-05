"""
Connection State Management für Transport-Layer.

Verwaltet den Verbindungsstatus generisch für alle Transport-Typen
(USB, LAN, etc.) mit State Machine Pattern.
"""

from enum import Enum
from typing import Optional, Dict

from ..config.logger import RigBridgeLogger

logger = RigBridgeLogger.get_logger(__name__)


class TransportStatus(str, Enum):
    """Generischer Transport-Verbindungsstatus."""
    DISCONNECTED = "disconnected"
    """Keine Verbindung verfügbar / kann nicht geöffnet werden"""

    COMMUNICATION_ERROR = "communication_error"
    """Fehler bei Kommunikation (z.B. I/O Fehler, Timeout)"""

    CONNECTED = "connected"
    """Gerät verbunden und antwortet auf Befehle"""


class ConnectionState:
    """
    Zustandsmaschine für Transport-Verbindungsstatus.

    Verwaltet Statusübergänge und loggt Änderungen.
    Generisch verwendbar für USB, LAN, etc.
    """

    def __init__(self, transport_type: str = "Transport"):
        """
        Initialisiert ConnectionState.

        Args:
            transport_type: Typ des Transports (z.B. "USB", "LAN") für Logging
        """
        self.status = TransportStatus.DISCONNECTED
        self.transport_type = transport_type
        self.status_names: Dict[TransportStatus, str] = {
            TransportStatus.DISCONNECTED: 'GETRENNT',
            TransportStatus.COMMUNICATION_ERROR: 'KOMMUNIKATIONSFEHLER',
            TransportStatus.CONNECTED: 'VERBUNDEN'
        }
        self.last_error: Optional[str] = None

    def update_status(
        self,
        new_status: TransportStatus,
        connection_info: str = "",
        error: Optional[str] = None
    ) -> None:
        """
        Aktualisiert den Verbindungsstatus und loggt Änderungen.

        Args:
            new_status: Neuer Status
            connection_info: Zusatzinformationen zur Verbindung (z.B. "COM4 @ 19200 baud")
            error: Optional: Fehlermeldung bei Fehler-Status
        """
        if new_status != self.status:
            old_status = self.status
            self.status = new_status

            # Logge statusspezifische Meldungen
            if new_status == TransportStatus.DISCONNECTED:
                if error:
                    logger.error(f"{self.transport_type} Kommunikation verloren: {error}")
                else:
                    logger.warning(f"{self.transport_type} Kommunikation getrennt: {connection_info}")
                self.last_error = error

            elif new_status == TransportStatus.COMMUNICATION_ERROR:
                if error:
                    logger.warning(f"{self.transport_type} Kommunikationsfehler: {error}")
                else:
                    logger.warning(f"{self.transport_type} Kommunikationsfehler aufgetreten")
                self.last_error = error

            elif new_status == TransportStatus.CONNECTED:
                logger.info(f"{self.transport_type} Gerät erkannt und verbunden")
                if old_status == TransportStatus.DISCONNECTED and connection_info:
                    logger.info(f"{self.transport_type} verbunden: {connection_info}")
                self.last_error = None

            # Logge den Statuswechsel
            old_name = self.status_names[old_status]
            new_name = self.status_names[new_status]
            logger.info(f"{self.transport_type}-Statusänderung: {old_name} -> {new_name}")

    def is_connected(self) -> bool:
        """
        Prüft, ob eine Verbindung besteht (nicht DISCONNECTED).

        Returns:
            True wenn Status nicht DISCONNECTED ist
        """
        return self.status != TransportStatus.DISCONNECTED

    def is_fully_operational(self) -> bool:
        """
        Prüft, ob Verbindung voll funktionsfähig ist (CONNECTED ohne Fehler).

        Returns:
            True wenn Status CONNECTED ist
        """
        return self.status == TransportStatus.CONNECTED

    def get_error(self) -> Optional[str]:
        """
        Gibt den letzten Fehler zurück.

        Returns:
            Letzte Fehlermeldung oder None
        """
        return self.last_error

    def __repr__(self) -> str:
        """String-Repräsentation des Status."""
        return f"ConnectionState({self.transport_type}, {self.status.value})"
