"""
Transport Resource Manager für RigBridge.

Zentrale Verwaltung von Ressourcen-Zugriff (USB, später LAN, etc.)
mit Synchronisierung und Timeout-Handling.

Verhindert Race Conditions durch:
- Globales asyncio.Lock für Ressourcen
- Timeout-basierte Deadlock-Prevention
- Zentrale Koordination aller Transport-Operationen
"""

import asyncio
from typing import Optional, Any, Dict
from enum import Enum

from .connection import USBConnection, SerialFrameData
from ..config.logger import RigBridgeLogger

logger = RigBridgeLogger.get_logger(__name__)


class TransportType(str, Enum):
    """Unterstützte Transport-Typen."""
    USB = "usb"
    LAN = "lan"
    SIM = "sim"  # Simulation


class TransportManager:
    """
    Zentrale Ressourcen-Verwaltung für alle Transport-Operationen.

    Ensures:
    - Nur ein Befehl zur Zeit hat Zugriff auf die Ressource
    - Keine Race Conditions zwischen API und Health-Check
    - Einfach austauschbar (USB ↔ LAN später)
    - Timeout-basierte Deadlock-Prevention
    """

    def __init__(
        self,
        usb_connection: Optional[USBConnection] = None,
        health_check_timeout: float = 5.0,
        command_timeout: float = 10.0,
    ):
        """
        Initialisiert den TransportManager.

        Args:
            usb_connection: USBConnection-Instanz (optional)
            health_check_timeout: Max Wartezeit für Health-Check (Sekunden)
            command_timeout: Max Wartezeit für normale Befehle (Sekunden)
        """
        self.usb_connection = usb_connection
        self.health_check_timeout = health_check_timeout
        self.command_timeout = command_timeout

        # Global Resource Lock - verhindert simultane Zugriffe
        self._resource_lock = asyncio.Lock()

        logger.debug(
            f"TransportManager initialized: "
            f"health_check_timeout={health_check_timeout}s, "
            f"command_timeout={command_timeout}s"
        )

    def set_usb_connection(self, usb_connection: USBConnection) -> None:
        """Setzt die USB-Verbindung für Transport-Operationen."""
        self.usb_connection = usb_connection
        logger.debug("USB connection set in TransportManager")

    async def acquire_exclusive_access(
        self,
        timeout: float,
        operation_name: str = "operation",
    ) -> bool:
        """
        Versucht exklusiven Zugriff auf Ressource zu erlangen.

        Args:
            timeout: Maximale Wartezeit in Sekunden
            operation_name: Name der Operation (für Logging)

        Returns:
            True wenn Zugriff erhalten, False bei Timeout
        """
        try:
            async with asyncio.timeout(timeout):
                await self._resource_lock.acquire()
                logger.debug(f"Exclusive access acquired for: {operation_name}")
                return True
        except asyncio.TimeoutError:
            logger.warning(
                f"Could not acquire exclusive access for {operation_name} "
                f"(timeout after {timeout}s)"
            )
            return False

    def release_exclusive_access(self) -> None:
        """Gibt exklusiven Zugriff frei."""
        if self._resource_lock.locked():
            self._resource_lock.release()
            logger.debug("Exclusive access released")

    async def send_frame(
        self,
        frame_data: SerialFrameData,
        operation_name: str = "send",
    ) -> bool:
        """
        Sendet einen Frame über die Ressource mit Lock-Schutz.

        Args:
            frame_data: Zu sendende Daten
            operation_name: Name der Operation (für Logging)

        Returns:
            True bei Erfolg, False bei Fehler/Timeout
        """
        if not self.usb_connection:
            logger.error("No USB connection available for send_frame")
            return False

        timeout = self.command_timeout
        acquired = await self.acquire_exclusive_access(timeout, operation_name)

        try:
            if not acquired:
                return False

            success = self.usb_connection.send_frame(frame_data)
            logger.debug(f"Frame sent: {operation_name}, success={success}")
            return success

        finally:
            self.release_exclusive_access()

    async def read_response(
        self,
        timeout: float = 0.7,
        operation_name: str = "read",
    ) -> Optional[SerialFrameData]:
        """
        Liest eine Antwort von der Ressource mit Lock-Schutz.

        Args:
            timeout: Lesezeitraum in Sekunden
            operation_name: Name der Operation (für Logging)

        Returns:
            SerialFrameData bei Erfolg, None bei Timeout
        """
        if not self.usb_connection:
            logger.error("No USB connection available for read_response")
            return None

        acquired = await self.acquire_exclusive_access(self.command_timeout, operation_name)

        try:
            if not acquired:
                return None

            response = self.usb_connection.read_response(timeout=timeout)
            return response

        finally:
            self.release_exclusive_access()

    async def execute_command_on_device(
        self,
        frame_bytes: bytes,
        command_name: str,
        is_health_check: bool = False,
    ) -> Optional[SerialFrameData]:
        """
        Sendet Befehl und liest Antwort mit exklusivem Zugriff.

        Verhindert Race Conditions zwischen Health-Check und API Befehlen.

        Args:
            frame_bytes: Zu sendende Befehls-Bytes
            command_name: Name des Befehls (für Logging)
            is_health_check: True wenn Health-Check Operation

        Returns:
            Antwort-Daten bei Erfolg, None bei Fehler/Timeout
        """
        if not self.usb_connection or self.usb_connection.simulate:
            logger.debug(f"Simulated command execution: {command_name}")
            return None

        # Health-Check hat verkürzte Timeout, API-Befehle reguläre
        operation_timeout = self.health_check_timeout if is_health_check else self.command_timeout
        operation_name = f"{'health_check' if is_health_check else 'api_command'}:{command_name}"

        # Acquire exclusive lock
        acquired = await self.acquire_exclusive_access(operation_timeout, operation_name)

        try:
            if not acquired:
                logger.warning(
                    f"Could not acquire lock for {operation_name} "
                    f"(timeout {operation_timeout}s)"
                )
                return None

            # Send frame
            from .connection import SerialFrameData

            frame_data = SerialFrameData(frame_bytes)
            if not self.usb_connection.send_frame(frame_data):
                logger.error(f"Failed to send frame for {command_name}")
                return None

            # Read response with echo filtering
            for attempt in range(3):
                candidate = self.usb_connection.read_response(timeout=0.7)
                if not candidate:
                    continue

                # Filter echo (TX==RX)
                if candidate.raw_bytes == frame_bytes:
                    logger.debug(
                        f"Echo detected for {command_name} (attempt {attempt + 1}/3), "
                        "waiting for real response..."
                    )
                    continue

                logger.debug(f"Response received for {command_name}")
                return candidate

            logger.warning(
                f"No valid response for {command_name} "
                "(only echo or timeout)"
            )
            return None

        finally:
            self.release_exclusive_access()

    def is_connected(self) -> bool:
        """Prüft ob Transport-Ressource verbunden ist."""
        if not self.usb_connection:
            return False
        return self.usb_connection.is_connected

    def can_connect(self) -> bool:
        """Prüft ob Transport-Ressource verbindbar ist."""
        if not self.usb_connection:
            return False
        return self.usb_connection.connect()
