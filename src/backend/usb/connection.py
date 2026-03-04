"""
USB/Serial-Verbindungsverwaltung für RigBridge.

Verwaltet eine serielle Verbindung zu einem Funkgerät
mit Reconnect-Logik und Fehlerbehandlung.
"""

import serial
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from ..config.logger import RigBridgeLogger
from ..config.settings import USBConfig

logger = RigBridgeLogger.get_logger(__name__)


@dataclass
class SerialFrameData:
    """Datenkapseln für CI-V Frames."""
    raw_bytes: bytes
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

    def __repr__(self) -> str:
        hex_str = ' '.join(f'{b:02X}' for b in self.raw_bytes)
        return f"SerialFrameData(bytes={len(self.raw_bytes)}, hex={hex_str})"


class USBConnection:
    """Verwaltet die serielle USB-Verbindung zum Funkgerät."""

    def __init__(self, config: USBConfig, simulate: bool = False):
        """
        Initialisiert die USB-Verbindung.

        Args:
            config: USBConfig-Objekt mit Port-Einstellungen
            simulate: Wenn True, verwendet MockSerial statt echter Verbindung
        """
        self.config = config
        self.simulate = simulate
        self.serial_port: Optional[serial.Serial] = None
        self.last_error: Optional[str] = None
        self.is_connected = False

        if not simulate:
            self._connect()

    def _connect(self) -> bool:
        """Stellt eine echte serielle Verbindung her."""
        try:
            # Schließe alte Verbindung falls noch offen
            if self.serial_port and self.serial_port.is_open:
                try:
                    self.serial_port.close()
                    logger.debug(f"Alte Verbindung zu {self.config.port} geschlossen")
                except Exception:
                    pass

            self.serial_port = serial.Serial(
                port=self.config.port,
                baudrate=self.config.baud_rate,
                bytesize=self.config.data_bits,
                stopbits=self.config.stop_bits,
                parity=self.config.parity,
                timeout=self.config.timeout,
                write_timeout=self.config.timeout,
            )
            self.is_connected = True
            self.last_error = None
            logger.info(
                f"USB verbunden: {self.config.port} @ "
                f"{self.config.baud_rate} baud"
            )
            return True
        except serial.SerialException as e:
            self.last_error = str(e)
            self.is_connected = False
            logger.error(f"USB-Verbindungsfehler: {e}")
            return False

    def connect(self) -> bool:
        """Verbindung herstellen oder validieren."""
        if self.simulate:
            self.is_connected = True
            return True

        if self.is_connected and self.serial_port and self.serial_port.is_open:
            return True

        return self._connect()

    def disconnect(self) -> None:
        """Trennt die serielle Verbindung."""
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
                self.is_connected = False
                logger.info(f"USB getrennt: {self.config.port}")
            except Exception as e:
                logger.error(f"Fehler beim Trennen der USB-Verbindung: {e}")

    def send_frame(self, frame_data: SerialFrameData) -> bool:
        """
        Sendet ein CI-V Frame über die serielle Verbindung.

        Args:
            frame_data: SerialFrameData mit den zu sendenden Bytes

        Returns:
            True wenn erfolgreich, False bei Fehler
        """
        if not self.is_connected and not self.simulate:
            # Versuche automatisch zu reconnecten
            logger.warning("USB nicht verbunden, versuche Reconnect...")
            if not self.reconnect_if_needed():
                logger.error("Reconnect fehlgeschlagen, kann Frame nicht senden")
                return False

        try:
            # Formatiere Bytes als HEX für Debug-Output
            hex_str = " ".join(f"{b:02X}" for b in frame_data.raw_bytes)

            if self.simulate:
                logger.debug(f"[SIMULATION] Frame gesendet: {hex_str}")
                return True

            bytes_sent = self.serial_port.write(frame_data.raw_bytes)
            if bytes_sent == len(frame_data.raw_bytes):
                logger.debug(f"[TX] Frame gesendet ({bytes_sent} bytes): {hex_str}")
                return True
            else:
                logger.error(
                    f"Unvollständiger Frame-Versand: "
                    f"{bytes_sent}/{len(frame_data.raw_bytes)} bytes"
                )
                return False
        except serial.SerialException as e:
            self.last_error = str(e)
            self.is_connected = False
            logger.error(f"Fehler beim Frame-Versand: {e}")

            # Versuche einmalig zu reconnecten
            logger.info("Versuche automatischen Reconnect nach Fehler...")
            if self.reconnect_if_needed():
                # Retry nach erfolgreichem Reconnect
                logger.info("Reconnect erfolgreich, wiederhole Frame-Versand...")
                try:
                    bytes_sent = self.serial_port.write(frame_data.raw_bytes)
                    if bytes_sent == len(frame_data.raw_bytes):
                        logger.info(f"[TX] Frame nach Reconnect gesendet ({bytes_sent} bytes)")
                        return True
                except Exception as retry_error:
                    logger.error(f"Retry nach Reconnect fehlgeschlagen: {retry_error}")

            return False

    def read_response(self, timeout: Optional[float] = None) -> Optional[SerialFrameData]:
        """
        Liest die Antwort vom Funkgerät.

        Erwartet CI-V Format: 0xFE 0xFE ... 0xFD (mit Timeout nach letztem 0xFD)

        Args:
            timeout: Optionaler Timeout in Sekunden

        Returns:
            SerialFrameData mit Antwort oder None bei Fehler/Timeout
        """
        if not self.is_connected and not self.simulate:
            logger.error("USB nicht verbunden, kann Response nicht lesen")
            return None

        try:
            if self.simulate:
                # Simulation: keine Daten
                return None

            # Setze temporären Timeout falls angegeben
            old_timeout = self.serial_port.timeout
            if timeout:
                self.serial_port.timeout = timeout

            # Lese Frame-Daten (0xFE...0xFD)
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
                        if timeout:
                            self.serial_port.timeout = old_timeout
                        return SerialFrameData(bytes(frame_data))

            # Timeout ohne 0xFD
            if timeout:
                self.serial_port.timeout = old_timeout

            if frame_data:
                hex_str = " ".join(f"{b:02X}" for b in frame_data)
                logger.warning(f"[RX] Unvollständiges Frame: {hex_str}")

            return None

        except serial.SerialException as e:
            self.last_error = str(e)
            self.is_connected = False
            logger.error(f"Fehler beim Response-Lesen: {e}")

            # Versuche automatischen Reconnect
            logger.info("Versuche automatischen Reconnect nach Lesefehler...")
            if self.reconnect_if_needed():
                logger.info("Reconnect erfolgreich nach Lesefehler")

            return None

    def reconnect(self) -> bool:
        """
        Erzwingt einen Reconnect durch explizites Disconnect + Connect.

        Returns:
            True wenn erfolgreich verbunden, False bei Fehler
        """
        logger.info(f"Erzwinge Reconnect für {self.config.port}...")
        self.disconnect()
        time.sleep(0.5)  # Kurze Pause für Port-Release
        return self._connect()

    def reconnect_if_needed(self) -> bool:
        """
        Fehlertoleranz: Versucht Reconnect wenn Fehler aufgetreten sind.

        Returns:
            True wenn verbunden, False bei anhaltendem Fehler
        """
        if self.is_connected:
            return True

        logger.info(
            f"Versuche Reconnect in {self.config.reconnect_interval}s..."
        )
        time.sleep(self.config.reconnect_interval)

        return self.reconnect()

    def __enter__(self):
        """Context Manager support."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context Manager cleanup."""
        self.disconnect()

    def __repr__(self) -> str:
        status = "verbunden" if self.is_connected else "getrennt"
        return f"USBConnection({self.config.port}, {status})"


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
        Funktion(request_bytes) -> response_bytes
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
            # Antworte mit aktuelle Frequenz als BCD
            freq_bcd = _frequency_to_bcd(frequency_hz)
            # Response: [0xFE, 0xFE, 0xE0, 0x94, 0x03, 0x00, ...freq_bcd, 0xFD]
            return bytes([0xFE, 0xFE, 0xE0, 0x94, 0x03, 0x00]) + freq_bcd + bytes([0xFD])

        # Read Operating Mode: cmd=0x04, subcmd=0x00
        if cmd == 0x04 and subcmd == 0x00:
            # CW=0x05, SSB=0x01, AM=0x02, FM=0x03, DV=0x04
            mode_codes = {'CW': 0x05, 'SSB': 0x01, 'AM': 0x02, 'FM': 0x03}
            mode_code = mode_codes.get(mode, 0x05)
            # Response: [0xFE, 0xFE, 0xE0, 0x94, 0x04, 0x00, mode_code, filter, 0xFD]
            return bytes([0xFE, 0xFE, 0xE0, 0x94, 0x04, 0x00, mode_code, 0x00, 0xFD])

        # Read S-Meter: cmd=0x15, subcmd=0x02
        if cmd == 0x15 and subcmd == 0x02:
            # Response mit S-Meter Wert (0-255)
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
    # Reverse BCD format für Icom CI-V
    freq = frequency_hz

    byte0 = ((freq % 100) % 10) << 4 | ((freq % 100) // 10)  # Hz LO
    freq //= 100
    byte1 = ((freq % 100) % 10) << 4 | ((freq % 100) // 10)  # Hz HO (kHz)
    freq //= 100
    byte2 = ((freq % 100) % 10) << 4 | ((freq % 100) // 10)  # kHz (MHz)
    freq //= 100
    byte3 = ((freq % 100) % 10) << 4 | ((freq % 100) // 10)  # MHz
    freq //= 100
    byte4 = ((freq % 100) % 10) << 4 | ((freq % 100) // 10)  # GHz

    return bytes([byte0, byte1, byte2, byte3, byte4])


def _bcd_to_frequency(bcd_bytes: bytes) -> int:
    """
    Konvertiert BCD CI-V Frequenz zurück in Hz.

    Args:
        bcd_bytes: 5 Bytes in CI-V BCD-Format

    Returns:
        Frequenz in Hz
    """
    if len(bcd_bytes) < 5:
        return 0

    # Reverse BCD parsing
    byte0, byte1, byte2, byte3, byte4 = bcd_bytes[0], bcd_bytes[1], bcd_bytes[2], bcd_bytes[3], bcd_bytes[4]

    hz_lo = ((byte0 & 0xF0) >> 4) + (byte0 & 0x0F) * 10
    hz_ho = ((byte1 & 0xF0) >> 4) + (byte1 & 0x0F) * 10
    hz_kilo = ((byte2 & 0xF0) >> 4) + (byte2 & 0x0F) * 10
    hz_mega = ((byte3 & 0xF0) >> 4) + (byte3 & 0x0F) * 10
    hz_giga = ((byte4 & 0xF0) >> 4) + (byte4 & 0x0F) * 10

    return (
        hz_giga * 1_000_000_000 +
        hz_mega * 1_000_000 +
        hz_kilo * 1_000 +
        hz_ho * 100 +
        hz_lo
    )
