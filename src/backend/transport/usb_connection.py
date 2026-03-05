"""
USB/Serial Transport-Implementierung für RigBridge.

Implementiert BaseTransport für serielle USB-Verbindungen
mit CI-V Protokoll-Support.
"""

import serial
import time
from typing import Optional

from ..config.logger import RigBridgeLogger
from ..config.settings import USBConfig
from .base_transport import BaseTransport, FrameData
from .connection_state import TransportStatus

logger = RigBridgeLogger.get_logger(__name__)


class USBConnection(BaseTransport):
    """
    USB/Serial Transport-Implementierung.

    Verwaltet serielle Verbindung zu Funkgerät über USB
    mit automatischem Reconnect und Fehlerbehandlung.
    """

    def __init__(self, config: USBConfig, simulate: bool = False):
        """
        Initialisiert USB-Verbindung.

        Args:
            config: USBConfig mit Port-Einstellungen
            simulate: Wenn True, simulierter Modus (ohne echte Hardware)
        """
        super().__init__(transport_type="USB")

        self.config = config
        self.simulate = simulate
        self.serial_port: Optional[serial.Serial] = None

        # Verbinde automatisch im nicht-simulierten Modus
        if not simulate:
            if self.connect():
                # Starte unsolicited frame handling nur wenn Handler registriert sind
                # (wird automatisch von register_unsolicited_handler() gestartet)
                self.register_unsolicited_handler(lambda frame: None)  # Dummy-Handler, damit Task gestartet wird
                pass

    def connect(self) -> bool:
        """
        Stellt USB-Verbindung her.

        Returns:
            True wenn erfolgreich, False bei Fehler
        """
        if self.simulate:
            self.state.update_status(
                TransportStatus.CONNECTED,
                connection_info="Simulation Mode"
            )
            return True

        if self.state.is_connected() and self.serial_port and self.serial_port.is_open:
            return True

        return self._connect_serial()

    def _connect_serial(self) -> bool:
        """
        Interne Methode: Stellt echte serielle Verbindung her.

        Returns:
            True wenn erfolgreich, False bei Fehler
        """
        try:
            # Schließe alte Verbindung falls noch offen
            if self.serial_port and self.serial_port.is_open:
                try:
                    self.serial_port.close()
                    logger.debug(f"Alte Verbindung zu {self.config.port} geschlossen")
                except Exception:
                    pass

            # Öffne neue Verbindung
            self.serial_port = serial.Serial(
                port=self.config.port,
                baudrate=self.config.baud_rate,
                bytesize=self.config.data_bits,
                stopbits=self.config.stop_bits,
                parity=self.config.parity,
                timeout=self.config.timeout,
                write_timeout=self.config.timeout,
            )

            connection_info = f"{self.config.port} @ {self.config.baud_rate} baud"
            self.state.update_status(TransportStatus.CONNECTED, connection_info=connection_info)
            self.last_error = None

            return True

        except serial.SerialException as e:
            self.last_error = str(e)
            self.state.update_status(
                TransportStatus.DISCONNECTED,
                connection_info=self.config.port,
                error=str(e)
            )
            logger.error(f"USB-Verbindungsfehler: {e}")
            return False

    def disconnect(self) -> None:
        """
        Trennt USB-Verbindung.

        Stoppt auch Background-Tasks für unsolicited frames.
        """
        # Stoppe Background-Task (von BaseTransport)
        self._stop_listening_for_unsolicited_frames()

        # Schließe serielle Verbindung
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
                self.state.update_status(
                    TransportStatus.DISCONNECTED,
                    connection_info=self.config.port
                )
            except Exception as e:
                logger.error(f"Fehler beim Trennen der USB-Verbindung: {e}")

    def send_frame(self, frame: FrameData) -> bool:
        """
        Sendet Frame über USB.

        Args:
            frame: Zu sendende Frame-Daten

        Returns:
            True wenn erfolgreich, False bei Fehler
        """
        if not self.state.is_fully_operational() and not self.simulate:
            # Versuche automatisch zu reconnecten
            if not self.reconnect_if_needed():
                logger.error("Reconnect fehlgeschlagen, kann Frame nicht senden")
                return False

        try:
            # Formatiere für Debug-Output
            hex_str = " ".join(f"{b:02X}" for b in frame.raw_bytes)

            if self.simulate:
                logger.debug(f"[SIMULATION] Frame gesendet: {hex_str}")
                self.state.update_status(TransportStatus.CONNECTED, "Simulation")
                return True

            # Sende über echte Verbindung
            bytes_sent = self.serial_port.write(frame.raw_bytes)

            if bytes_sent == len(frame.raw_bytes):
                logger.debug(f"[TX] Frame gesendet ({bytes_sent} bytes): {hex_str}")
                self.state.update_status(
                    TransportStatus.CONNECTED,
                    f"{self.config.port} @ {self.config.baud_rate} baud"
                )
                return True
            else:
                error_msg = f"Unvollständiger Frame-Versand: {bytes_sent}/{len(frame.raw_bytes)} bytes"
                self.state.update_status(
                    TransportStatus.COMMUNICATION_ERROR,
                    self.config.port,
                    error=error_msg
                )
                return False

        except serial.SerialException as e:
            self.last_error = str(e)
            self.state.update_status(
                TransportStatus.COMMUNICATION_ERROR,
                self.config.port,
                error=str(e)
            )

            # Versuche einmalig reconnect
            logger.info("Versuche automatischen Reconnect nach Fehler...")
            if self.reconnect_if_needed():
                logger.info("Reconnect erfolgreich, wiederhole Frame-Versand...")
                try:
                    bytes_sent = self.serial_port.write(frame.raw_bytes)
                    if bytes_sent == len(frame.raw_bytes):
                        logger.info(f"[TX] Frame nach Reconnect gesendet ({bytes_sent} bytes)")
                        return True
                except Exception as retry_error:
                    logger.error(f"Retry nach Reconnect fehlgeschlagen: {retry_error}")

            return False

    def read_response(self, timeout: Optional[float] = None) -> Optional[FrameData]:
        """
        Liest Response vom Funkgerät.

        Erwartet CI-V Format: 0xFE 0xFE ... 0xFD

        Args:
            timeout: Optional: Timeout in Sekunden

        Returns:
            FrameData mit Antwort oder None bei Fehler/Timeout
        """
        if not self.state.is_connected() and not self.simulate:
            logger.error("USB nicht verbunden, kann Response nicht lesen")
            return None

        try:
            if self.simulate:
                # Simulation: keine Daten
                return None

            # Setze temporären Timeout
            old_timeout = self.serial_port.timeout
            if timeout:
                self.serial_port.timeout = timeout

            # Lese CI-V Frame (0xFE...0xFD)
            frame_data = bytearray()
            in_frame = False

            while True:
                byte = self.serial_port.read(1)

                if not byte:
                    # Timeout
                    if frame_data:
                        hex_str = " ".join(f"{b:02X}" for b in frame_data)
                        logger.debug(f"[RX] Unvollständiges Frame auf Timeout: {hex_str}")
                    break

                byte_val = byte[0]

                if byte_val == 0xFE and not in_frame:
                    # Frame-Start
                    frame_data.append(byte_val)
                    in_frame = True
                elif in_frame:
                    frame_data.append(byte_val)

                    if byte_val == 0xFD:
                        # Frame-Ende gefunden
                        hex_str = " ".join(f"{b:02X}" for b in frame_data)
                        logger.debug(f"[RX] Frame empfangen ({len(frame_data)} bytes): {hex_str}")

                        # Timeout zurücksetzen
                        if timeout:
                            self.serial_port.timeout = old_timeout

                        return FrameData(bytes(frame_data))

            # Timeout ohne 0xFD
            if timeout:
                self.serial_port.timeout = old_timeout

            if frame_data:
                hex_str = " ".join(f"{b:02X}" for b in frame_data)
                logger.warning(f"[RX] Unvollständiges Frame: {hex_str}")

            return None

        except serial.SerialException as e:
            self.last_error = str(e)
            self.state.update_status(
                TransportStatus.COMMUNICATION_ERROR,
                self.config.port,
                error=str(e)
            )

            # Versuche automatischen Reconnect
            logger.info("Versuche automatischen Reconnect nach Lesefehler...")
            if self.reconnect_if_needed():
                logger.info("Reconnect erfolgreich nach Lesefehler")

            return None

    def reconnect_if_needed(self) -> bool:
        """
        Fehlertoleranz: Reconnect bei Fehlern.

        Returns:
            True wenn verbunden, False bei anhaltendem Fehler
        """
        if self.state.is_fully_operational():
            return True

        logger.warning(
            f"USB nicht verbunden, versuche Reconnect in "
            f"{self.config.reconnect_interval}s..."
        )
        time.sleep(self.config.reconnect_interval)

        return self.reconnect()

    def __repr__(self) -> str:
        """String-Repräsentation."""
        status = "verbunden" if self.state.is_connected() else "getrennt"
        return f"USBConnection({self.config.port}, {status})"


# =============================================================================
# Mock-Serial für Testing
# =============================================================================

class MockSerial:
    """Mock-Serial für Testing ohne echte Hardware."""

    def __init__(self, port: str = None, **kwargs):
        """Initialisiert MockSerial mit Dummy-Werten."""
        self.port = port
        self.is_open = True
        self.timeout = kwargs.get('timeout', 1.0)
        self.write_buffer = bytearray()
        self.read_buffer = bytearray()
        self.response_factory = None

    def write(self, data: bytes) -> int:
        """Schreibt in den internen Buffer."""
        self.write_buffer.extend(data)
        return len(data)

    def read(self, size: int = 1) -> bytes:
        """Liest aus dem Response-Buffer."""
        if not self.read_buffer:
            # Erstelle Response basierend auf letztem Request
            if self.response_factory:
                response = self.response_factory(bytes(self.write_buffer))
                if response:
                    self.read_buffer.extend(response)
                    self.write_buffer.clear()

        if size > len(self.read_buffer):
            size = len(self.read_buffer)

        result = bytes(self.read_buffer[:size])
        del self.read_buffer[:size]
        return result

    def close(self) -> None:
        """Schließt die Mock-Verbindung."""
        self.is_open = False

    def flush(self) -> None:
        """Dummy flush."""
        pass

    def set_response_factory(self, factory):
        """Setzt eine Funktion zur Erzeugung von Mock-Responses."""
        self.response_factory = factory


def create_mock_response_factory(frequency_hz: int = 145500000, mode: str = 'CW'):
    """
    Erstellt eine Mock-Response-Factory für Simulator.

    Args:
        frequency_hz: Zu simulierende Frequenz
        mode: Zu simulierender Modus

    Returns:
        Factory-Funktion(request_bytes) -> response_bytes
    """
    def factory(request: bytes) -> Optional[bytes]:
        """Generiert eine simulierte CI-V-Antwort."""
        if len(request) < 6:
            return None

        # Erkenne Befehl: [0xFE, 0xFE, cmd, subcmd, ...]
        cmd = request[2] if len(request) > 2 else 0
        subcmd = request[3] if len(request) > 3 else 0

        # Read Operating Frequency: cmd=0x03, subcmd=0x00
        if cmd == 0x03 and subcmd == 0x00:
            freq_bcd = _frequency_to_bcd(frequency_hz)
            return bytes([0xFE, 0xFE, 0xE0, 0x94, 0x03, 0x00]) + freq_bcd + bytes([0xFD])

        # Read Operating Mode: cmd=0x04, subcmd=0x00
        if cmd == 0x04 and subcmd == 0x00:
            mode_codes = {'CW': 0x05, 'SSB': 0x01, 'AM': 0x02, 'FM': 0x03}
            mode_code = mode_codes.get(mode, 0x05)
            return bytes([0xFE, 0xFE, 0xE0, 0x94, 0x04, 0x00, mode_code, 0x00, 0xFD])

        # Read S-Meter: cmd=0x15, subcmd=0x02
        if cmd == 0x15 and subcmd == 0x02:
            s_meter_value = 0x78  # S8
            return bytes([0xFE, 0xFE, 0xE0, 0x94, 0x15, 0x02, s_meter_value, 0xFD])

        # Default: Echo mit OK
        return bytes([0xFE, 0xFE, 0xE0, 0x94, 0xFB, 0xFD])

    return factory


def _frequency_to_bcd(frequency_hz: int) -> bytes:
    """
    Konvertiert Frequenz (Hz) in BCD-Format für CI-V.

    Format: [byte0, byte1, byte2, byte3, byte4]
    - byte4 = Gigahertz
    - byte3 = Megahertz
    - byte2 = Kilohertz
    - byte1 = Hertz HO
    - byte0 = Hertz LO

    Beispiel 145.500.000 Hz:
    - GHz: 0
    - MHz: 145 = 0x45
    - kHz: 500 = 0x00 + 5 (reversed)
    - Hz: 0 (reversed)
    """
    freq = frequency_hz

    byte0 = ((freq % 100) % 10) << 4 | ((freq % 100) // 10)
    freq //= 100
    byte1 = ((freq % 100) % 10) << 4 | ((freq % 100) // 10)
    freq //= 100
    byte2 = ((freq % 100) % 10) << 4 | ((freq % 100) // 10)
    freq //= 100
    byte3 = ((freq % 100) % 10) << 4 | ((freq % 100) // 10)
    freq //= 100
    byte4 = ((freq % 100) % 10) << 4 | ((freq % 100) // 10)

    return bytes([byte0, byte1, byte2, byte3, byte4])
