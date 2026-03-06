"""
Protocol Manager für RigBridge.

Zentraler Manager für Protokoll-Instanzen (Singleton-Pattern).
Verwaltet aktives Protokoll und dispatcht Commands.
"""

from typing import Any, Dict, Optional, List, Callable
from pathlib import Path

from .base_protocol import BaseProtocol, CommandResult
from ..config.logger import RigBridgeLogger

logger = RigBridgeLogger.get_logger(__name__)


class ProtocolManager:
    """
    Singleton-Manager für Funkgerät-Protokolle.

    Verantwortlichkeiten:
    - Verwaltet aktive Protokoll-Instanz (z.B. CIVProtocol)
    - Dispatcht API-Commands an aktives Protokoll
    - Empfängt unsolicited frames vom Transport Layer
    - Validiert Radio-IDs und verwirft ungültige Frames
    - Koordiniert Wavelog-Integration (zukünftig)

    Ähnlich dem TransportManager, aber eine Schicht höher in der Architektur:

    API Layer
        ↓
    ProtocolManager (diese Klasse)
        ↓
    Protocol Implementation (CIVProtocol, etc.)
        ↓
    TransportManager
        ↓
    Transport Layer (USB, LAN, SIM)
    """

    _instance: Optional['ProtocolManager'] = None

    def __new__(cls) -> 'ProtocolManager':
        """Singleton-Pattern: Nur eine Instanz erlaubt."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialisiert den ProtocolManager (nur beim ersten Aufruf)."""
        if self._initialized:
            return

        self._protocol: Optional[BaseProtocol] = None
        self._initialized = True
        logger.debug('ProtocolManager singleton initialized')

    # ========================================================================
    # Protokoll-Verwaltung
    # ========================================================================

    def set_protocol(self, protocol: BaseProtocol) -> None:
        """
        Setzt das aktive Protokoll.

        Args:
            protocol: Aktive Protokoll-Instanz (z.B. CIVProtocol)
        """
        self._protocol = protocol
        logger.info(f'Protocol set: {protocol.__class__.__name__}')

    def get_protocol(self) -> Optional[BaseProtocol]:
        """
        Gibt das aktive Protokoll zurück.

        Returns:
            Aktive Protokoll-Instanz oder None
        """
        return self._protocol

    def has_protocol(self) -> bool:
        """
        Prüft ob ein Protokoll aktiv ist.

        Returns:
            True wenn Protokoll gesetzt
        """
        return self._protocol is not None

    # ========================================================================
    # Command-Dispatch (API → Protocol)
    # ========================================================================

    async def execute_command(
        self,
        command_name: str,
        data: Optional[Dict[str, Any]] = None,
        is_health_check: bool = False,
    ) -> CommandResult:
        """
        Führt einen generischen Befehl über das aktive Protokoll aus.

        Args:
            command_name: Name des Befehls aus YAML
            data: Optionale Befehlsdaten
            is_health_check: True für Health-Check-Befehle

        Returns:
            CommandResult mit Erfolg/Fehler und Daten

        Raises:
            RuntimeError: Wenn kein Protokoll aktiv ist
        """
        if not self._protocol:
            error_msg = 'No protocol set in ProtocolManager'
            logger.error(error_msg)
            return CommandResult(
                success=False,
                error=error_msg
            )

        try:
            result = await self._protocol.execute_command(
                command_name=command_name,
                data=data,
                is_health_check=is_health_check
            )
            return result
        except Exception as e:
            error_msg = f'Command execution failed: {e}'
            logger.error(error_msg)
            return CommandResult(
                success=False,
                error=error_msg
            )

    def list_commands(self) -> List[str]:
        """
        Gibt Liste aller verfügbaren Befehle zurück.

        Returns:
            Liste der Befehlsnamen aus YAML-Protokoll
        """
        if not self._protocol:
            logger.warning('No protocol set - returning empty command list')
            return []

        return self._protocol.list_commands()

    # ========================================================================
    # Convenience-Methoden (häufig verwendete Operationen)
    # ========================================================================

    async def get_frequency(self) -> Optional[int]:
        """
        Liest die aktuelle Betriebsfrequenz.

        Returns:
            Frequenz in Hz oder None bei Fehler
        """
        if not self._protocol:
            logger.error('No protocol set')
            return None

        return await self._protocol.get_frequency()

    async def get_mode(self) -> Optional[str]:
        """
        Liest den aktuellen Betriebsmodus.

        Returns:
            Modus (z.B. 'USB') oder None bei Fehler
        """
        if not self._protocol:
            logger.error('No protocol set')
            return None

        return await self._protocol.get_mode()

    async def get_power(self) -> Optional[float]:
        """
        Liest die aktuelle Sendeleistung (VORBEREITET).

        Returns:
            Leistung in Watt oder None
        """
        if not self._protocol:
            logger.error('No protocol set')
            return None

        return await self._protocol.get_power()

    def supports_power(self) -> bool:
        """
        Prüft ob Power-Befehle unterstützt werden.

        Returns:
            True wenn Power read/write verfügbar
        """
        if not self._protocol:
            return False

        return self._protocol.supports_power()

    # ========================================================================
    # Unsolicited Frame Handling (Transport → Protocol)
    # ========================================================================

    async def handle_unsolicited_frame(self, frame: bytes) -> None:
        """
        Verarbeitet einen unsolicited Frame vom Transport Layer.

        Workflow:
        1. Prüft ob Frame von gültiger Radio-ID stammt
        2. Verwirft Frame wenn Radio-ID unbekannt
        3. Leitet valide Frames an Protokoll-Handler weiter
        4. Protokoll parst Frame und ruft registrierte Callbacks auf

        Diese Methode wird vom Transport Background-Reader aufgerufen
        wenn unaufgeforderte Daten empfangen werden.

        Args:
            frame: Empfangener Frame (raw bytes)
        """
        if not self._protocol:
            logger.warning('No protocol set - discarding unsolicited frame')
            return

        # Radio-ID validieren
        if not self._protocol.is_valid_radio_id(frame):
            logger.debug(
                f'Unsolicited frame discarded: Invalid Radio-ID '
                f'(hex: {frame.hex(" ").upper()})'
            )
            return

        # An Protokoll-spezifischen Handler weiterleiten
        try:
            await self._protocol.handle_unsolicited_frame(frame)
        except Exception as e:
            logger.error(f'Error handling unsolicited frame: {e}')

    # ========================================================================
    # Wavelog-Integration (Vorbereitung)
    # ========================================================================

    def register_unsolicited_handler(
        self,
        handler: Callable[[Dict[str, Any]], None]
    ) -> None:
        """
        Registriert einen Handler für unsolicited data.

        Verwendung für Wavelog-Auto-Forward (zukünftig):
        ```python
        def wavelog_handler(data: Dict[str, Any]):
            if 'frequency' in data and 'mode' in data:
                # Automatische Weiterleitung an Wavelog
                pass

        protocol_manager.register_unsolicited_handler(wavelog_handler)
        ```

        Args:
            handler: Callback-Funktion für geparste Daten
        """
        if not self._protocol:
            logger.warning('No protocol set - cannot register handler')
            return

        self._protocol.register_unsolicited_handler(handler)

    def unregister_unsolicited_handler(
        self,
        handler: Callable[[Dict[str, Any]], None]
    ) -> None:
        """
        Entfernt einen registrierten Unsolicited-Handler.

        Args:
            handler: Zu entfernender Handler
        """
        if self._protocol:
            self._protocol.unregister_unsolicited_handler(handler)

    # ========================================================================
    # Debugging & Inspection
    # ========================================================================

    def get_protocol_info(self) -> Dict[str, Any]:
        """
        Gibt Informationen über das aktive Protokoll zurück.

        Returns:
            Dict mit Protokoll-Details
        """
        if not self._protocol:
            return {
                'active': False,
                'protocol_type': None,
                'supported_commands': []
            }

        return {
            'active': True,
            'protocol_type': self._protocol.__class__.__name__,
            'protocol_file': str(self._protocol.protocol_file),
            'manufacturer_file': str(self._protocol.manufacturer_file) if self._protocol.manufacturer_file else None,
            'supported_commands': self._protocol.list_commands(),
            'supports_power': self._protocol.supports_power(),
        }
