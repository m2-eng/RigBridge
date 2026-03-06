"""
Abstrakte Basisklasse für Funkgerät-Protokolle.

Definiert die Schnittstelle für Protokoll-Implementierungen (CI-V, CAT, etc.).
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable, List
from dataclasses import dataclass
from pathlib import Path

from ..config.logger import RigBridgeLogger

logger = RigBridgeLogger.get_logger(__name__)


@dataclass
class CommandResult:
    """Ergebnis der Befehlsausführung."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    raw_response: Optional[bytes] = None


class BaseProtocol(ABC):
    """
    Abstrakte Basisklasse für Funkgerät-Protokolle.

    Jede Protokoll-Implementierung (CIV, CAT, etc.) erweitert diese Klasse
    und implementiert die protokollspezifische Logik.

    Features:
    - Generische Command-Ausführung
    - Convenience-Methoden für häufige Operationen (Frequenz, Mode, Power)
    - Unsolicited Frame Handling mit Callback-Registrierung
    - Radio-ID-Validierung
    """

    def __init__(
        self,
        protocol_file: Path,
        manufacturer_file: Optional[Path] = None,
    ):
        """
        Initialisiert das Protokoll.

        Args:
            protocol_file: Pfad zur YAML-Protokolldefinition
            manufacturer_file: Pfad zur Hersteller-YAML (optional)
        """
        self.protocol_file = Path(protocol_file)
        self.manufacturer_file = Path(manufacturer_file) if manufacturer_file else None
        self._unsolicited_handlers: List[Callable[[bytes], None]] = []

    # ========================================================================
    # Abstrakte Methoden - MUSS von Subklassen implementiert werden
    # ========================================================================

    @abstractmethod
    async def execute_command(
        self,
        command_name: str,
        data: Optional[Dict[str, Any]] = None,
        is_health_check: bool = False,
    ) -> CommandResult:
        """
        Führt einen generischen Befehl aus.

        Args:
            command_name: Name des Befehls aus YAML (z.B. 'read_operating_frequency')
            data: Optionale Befehlsdaten für schreibende Befehle
            is_health_check: True wenn dies ein Health-Check-Befehl ist

        Returns:
            CommandResult mit Erfolg/Fehler und geparsten Daten
        """
        pass

    @abstractmethod
    def list_commands(self) -> List[str]:
        """
        Gibt Liste aller verfügbaren Befehle zurück.

        Returns:
            Liste der Befehlsnamen aus YAML
        """
        pass

    @abstractmethod
    def is_valid_radio_id(self, frame: bytes) -> bool:
        """
        Prüft ob ein Frame von der erwarteten Radio-ID stammt.

        Args:
            frame: Empfangener Frame (raw bytes)

        Returns:
            True wenn Radio-ID valide, sonst False
        """
        pass

    @abstractmethod
    async def handle_unsolicited_frame(self, frame: bytes) -> None:
        """
        Verarbeitet einen unsolicited Frame vom Funkgerät.

        Wird aufgerufen wenn das Funkgerät unaufgefordert Daten sendet
        (z.B. Frequenz-/Modus-Änderung durch manuelle Bedienung).

        Diese Methode:
        1. Validiert die Radio-ID (verwirft Frame bei Mismatch)
        2. Parst den Frame-Inhalt (Frequenz, Mode, etc.)
        3. Ruft registrierte Unsolicited-Handler auf

        Args:
            frame: Empfangener unsolicited Frame
        """
        pass

    # ========================================================================
    # Convenience-Methoden für häufige Operationen
    # ========================================================================

    async def get_frequency(self) -> Optional[int]:
        """
        Liest die aktuelle Betriebsfrequenz.

        Returns:
            Frequenz in Hz oder None bei Fehler
        """
        result = await self.execute_command('read_operating_frequency')
        if result.success and result.data:
            return result.data.get('frequency')
        return None

    async def get_mode(self) -> Optional[str]:
        """
        Liest den aktuellen Betriebsmodus.

        Returns:
            Modus (z.B. 'USB', 'CW', 'FM') oder None bei Fehler
        """
        result = await self.execute_command('read_operating_mode')
        if result.success and result.data:
            return result.data.get('mode')
        return None

    async def get_power(self) -> Optional[float]:
        """
        Liest die aktuelle Sendeleistung (VORBEREITET - noch nicht vollständig implementiert).

        Returns:
            Leistung in Watt oder None bei Fehler/nicht unterstützt
        """
        try:
            result = await self.execute_command('read_rf_power')
            if result.success and result.data:
                return result.data.get('power_w')
        except Exception as e:
            logger.debug(f'Power reading not supported or failed: {e}')
        return None

    # ========================================================================
    # Unsolicited Frame Handler-Registrierung
    # ========================================================================

    def register_unsolicited_handler(
        self,
        handler: Callable[[Dict[str, Any]], None]
    ) -> None:
        """
        Registriert einen Handler für unsolicited Frames.

        Der Handler wird aufgerufen wenn das Funkgerät unaufgefordert
        Daten sendet (z.B. Frequenz-/Modus-Änderung).

        Handler-Signatur: handler(parsed_data: Dict[str, Any])
        parsed_data kann enthalten:
        - 'frequency': int (in Hz)
        - 'mode': str (z.B. 'USB')
        - 'power': float (in Watt)
        - etc.

        Verwendung für Wavelog-Auto-Forward (zukünftig):
        ```python
        def wavelog_forwarder(data: Dict[str, Any]):
            if 'frequency' in data and 'mode' in data:
                await wavelog_client.send_radio_status(
                    frequency_hz=data['frequency'],
                    mode=data['mode']
                )

        protocol.register_unsolicited_handler(wavelog_forwarder)
        ```

        Args:
            handler: Callback-Funktion für unsolicited data
        """
        if handler not in self._unsolicited_handlers:
            self._unsolicited_handlers.append(handler)
            logger.debug(f'Unsolicited handler registered: {handler.__name__}')

    def unregister_unsolicited_handler(
        self,
        handler: Callable[[Dict[str, Any]], None]
    ) -> None:
        """
        Entfernt einen registrierten Unsolicited-Handler.

        Args:
            handler: Zu entfernender Handler
        """
        if handler in self._unsolicited_handlers:
            self._unsolicited_handlers.remove(handler)
            logger.debug(f'Unsolicited handler unregistered: {handler.__name__}')

    def _notify_unsolicited_handlers(self, parsed_data: Dict[str, Any]) -> None:
        """
        Benachrichtigt alle registrierten Handler über neue unsolicited data.

        Args:
            parsed_data: Geparste Daten aus unsolicited Frame
        """
        for handler in self._unsolicited_handlers:
            try:
                handler(parsed_data)
            except Exception as e:
                logger.error(
                    f'Error in unsolicited handler {handler.__name__}: {e}'
                )

    # ========================================================================
    # Protokoll-Informationen
    # ========================================================================

    def supports_power(self) -> bool:
        """
        Prüft ob das Protokoll Power-Befehle unterstützt.

        Returns:
            True wenn Power read/write verfügbar
        """
        commands = self.list_commands()
        return 'read_rf_power' in commands or 'set_rf_power' in commands
