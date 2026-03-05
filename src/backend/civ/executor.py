"""
CI-V Befehlsausführung und -verarbeitung.

Parsed YAML-Protokolldefinitionen und führt CI-V-Befehle aus.
"""

from typing import Any, Dict, Optional, List, Tuple
from dataclasses import dataclass
from pathlib import Path
import yaml
from enum import Enum

from ..config.logger import RigBridgeLogger
from ..transport.transport_manager import TransportManager

logger = RigBridgeLogger.get_logger(__name__)


class DataType(str, Enum):
    """Unterstützte Datentypen in Protokollen."""
    UINT8 = 'uint8'
    UINT16 = 'uint16'
    UINT32 = 'uint32'
    BOOLEAN = 'boolean'


@dataclass
class CIVCommand:
    """
    Ein einzelner CI-V Befehl.

    Attributes:
        name: Befehlsname (z.B. 'set_operating_frequency')
        cmd: Haupt-Befehlsbyte (z.B. 0x05)
        subcmd: Unterbefehls-Bytes (optional, z.B. [0x01] oder [0x05, 0x00, 0x01])
        description: Kurzbeschreibung
        request_structure: Strutur der Request-Daten
        response_structure: Struktur der Response-Daten
    """
    name: str
    cmd: int
    subcmd: Optional[List[int]]
    description: str
    request_structure: List[Dict[str, Any]] = None
    response_structure: List[Dict[str, Any]] = None


@dataclass
class CommandResult:
    """Ergebnis der Befehlsausführung."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    raw_response: Optional[bytes] = None


class ProtocolParser:
    """Parser für YAML-Protokolldefinitionen."""

    def __init__(self, protocol_file: Path, manufacturer_file: Path) -> None:
        """
        Initialisiert den Protocol-Parser.

        Args:
            protocol_file: Pfad zur YAML-Protokolldatei (z.B. ic905.yaml)
            manufacturer_file: Pfad zur Herstellerdatei (z.B. ic905_manufacturer.yaml)
        """
        self.protocol_file = Path(protocol_file)
        self.manufacturer_file = Path(manufacturer_file)
        self.commands: Dict[str, CIVCommand] = {}
        self.preamble: bytes = b'\xFE\xFE'
        self.terminator: int = 0xFD
        self.controller_addr: int = 0xE0
        self.radio_addr: int = 0xA4
        self._parse_protocol()

    @staticmethod
    def _parse_int(value: Any, default: int) -> int:
        """Parst Integer-Werte aus int/hex-string robust."""
        if value is None:
            return default
        if isinstance(value, str):
            return int(value, 0)
        return int(value)

    def _parse_protocol(self) -> None:
        """Parst die YAML-Protokolldatei."""
        protocol = self._read_protocol_file()

        # Versuche zuerst nested 'protocol' key (neue Struktur)
        root = protocol.get('protocol', protocol)

        # Frame-/Adress-Konfiguration laden
        frame_cfg = root.get('config', {}).get('frame', {})
        addresses = root.get('addresses', {})
        preamble = frame_cfg.get('preamble', [0xFE, 0xFE])
        if isinstance(preamble, list) and len(preamble) >= 2:
            self.preamble = bytes([
                self._parse_int(preamble[0], 0xFE),
                self._parse_int(preamble[1], 0xFE),
            ])
        self.terminator = self._parse_int(frame_cfg.get('terminator', 0xFD), 0xFD)
        self.controller_addr = self._parse_int(
            addresses.get('controller', frame_cfg.get('default_controller', 0xE0)),
            0xE0,
        )
        self.radio_addr = self._parse_int(
            addresses.get('radio', frame_cfg.get('default_radio', 0xA4)),
            0xA4,
        )

        commands_dict = None
        if 'protocol' in protocol and isinstance(protocol['protocol'], dict):
            commands_dict = protocol['protocol'].get('commands')

        # Fallback auf top-level 'commands' (alte Struktur)
        if not commands_dict and 'commands' in protocol:
            commands_dict = protocol['commands']

        if not commands_dict:
            logger.warning(
                f'No commands found in {self.protocol_file}'
            )
            return

        for cmd_name, cmd_data in commands_dict.items():
            try:
                cmd = self._parse_command(cmd_name, cmd_data)
                self.commands[cmd_name] = cmd
                logger.debug(f'Loaded command: {cmd_name}')
            except Exception as e:
                logger.error(
                    f'Failed to parse command {cmd_name}: {e}'
                )

    def _parse_command(self, name: str, data: Dict[str, Any]) -> CIVCommand:
        """Parst einen einzelnen Befehlseintrag."""
        # Verarbeite cmd - kann Integer oder hex-String sein
        cmd_val = data.get('cmd', 0)
        if isinstance(cmd_val, str):
            cmd = int(cmd_val, 0)  # 0x03 -> 3
        else:
            cmd = int(cmd_val)  # 3 -> 3

        # Verarbeite subcmd als Unterbefehl (optional, 1..n Bytes)
        subcmd_val = data.get('subcmd')
        subcmd: Optional[List[int]] = None
        if subcmd_val is not None:
            if isinstance(subcmd_val, list):
                subcmd = [self._parse_int(value, 0) & 0xFF for value in subcmd_val]
            else:
                subcmd = [self._parse_int(subcmd_val, 0) & 0xFF]

        return CIVCommand(
            name=name,
            cmd=cmd,
            subcmd=subcmd,
            description=data.get('description', ''),
            request_structure=data.get('request', {}),
            response_structure=data.get('response', {}),
        )

    def get_command(self, name: str) -> Optional[CIVCommand]:
        """Gibt einen Befehl nach Name zurück."""
        return self.commands.get(name)

    def get_command_by_code(
        self,
        cmd: int,
        subcmd: Optional[List[int]] = None,
    ) -> Optional[CIVCommand]:
        """Gibt einen Befehl nach cmd/subcmd-Codes zurück."""
        expected_subcmd = subcmd or []
        for command in self.commands.values():
            if command.cmd == cmd and (command.subcmd or []) == expected_subcmd:
                return command
        return None

    def list_commands(self) -> List[str]:
        """Gibt Liste aller verfügbaren Befehle zurück."""
        return list(self.commands.keys())

    def _read_protocol_file(self) -> Optional[Dict[str, Any]]:
        """Liest die YAML-Protokolldatei und gibt den Inhalt zurück."""
        if not self.protocol_file.exists():
            logger.error(f'protocol_file not found: {self.protocol_file}')
            return

        with open(self.protocol_file, 'r', encoding='utf-8') as f:
            protocol = yaml.safe_load(f)

        if not protocol:
            logger.warning(f'Protocol file is empty: {self.protocol_file}')
            return

        if not self.manufacturer_file.exists():
            logger.warning(f'manufacturer_file not found: {self.manufacturer_file} (file is optional; can contain shared datatypes)')
            return

        with open(self.manufacturer_file, 'r', encoding='utf-8') as f:
            manufacturer = yaml.safe_load(f)

        # Merge manufacturer data into protocol (manufacturer data types are appended to protocol's data_types if not already defined)
        if manufacturer:
            protocol['protocol'] = protocol.get('protocol', {})

            # Merge data types (manufacturer data types haben Vorrang, wenn Schlüssel gleich)
            data_types_p = protocol.get('protocol', {}).get('data_types')
            data_types_m = manufacturer.get('data_types')
            data_types = data_types_p or {}
            if data_types_m:
                for key, value in data_types_m.items():
                    if key not in data_types:
                        data_types[key] = value
            protocol['protocol']['data_types'] = data_types

        return protocol


    def _read_protocol_command(self, command_name: str) -> str:
        """Liest einen Befehl aus der YAML-Datei."""
        # Lesen der YAML-Datei und Suche nach dem Befehl
        protocol = self._read_protocol_file().get('protocol', {})
        cmd_data = protocol.get('commands', {}).get(command_name)

        for key in ['request', 'response']:
            items = cmd_data.get(key, [])
            if items:
                for index in range(len(items)):
                    item = items[index]
                    if 'type' in item:
                        # Replace type reference with actual structure from data_types
                        data_type_name = item['type']
                        data_types = protocol.get('data_types', {})
                        if data_type_name in data_types:
                            cmd_data[key][index] = data_types[data_type_name]

        if cmd_data:
            return cmd_data
        else:
            logger.warning(f'Command "{command_name}" not found in protocol file')
            return None


class CIVCommandExecutor:
    """
    Executor für CI-V Befehle mit USB-Unterstützung.

    Verwaltet Protokoll-Parsing und echte Befehlsausführung über USB/Serial.
    """

    def __init__(self, protocol_file: Path, manufacturer_file: Path, usb_connection=None) -> None:
        """
        Initialisiert den Command Executor.

        Args:
            protocol_file: Pfad zur Protokolldatei
            manufacturer_file: Pfad zur Herstellerdatei
            usb_connection: USBConnection-Instanz (optional, wird bei Bedarf erstellt)
        """
        self.parser = ProtocolParser(protocol_file, manufacturer_file)
        self.usb_connection = usb_connection
        self.transport_manager = TransportManager(usb_connection=usb_connection)
        logger.info(
            f'CIV Command Executor initialized with '
            f'{len(self.parser.commands)} commands'
        )

    def set_usb_connection(self, usb_connection) -> None:
        """Setzt die USB-Verbindung für Befehlsausführung."""
        self.usb_connection = usb_connection
        self.transport_manager.set_usb_connection(usb_connection)
        logger.debug('USB connection set for CIV executor')

    async def execute_command(
        self,
        command_name: str,
        data: Optional[Dict[str, Any]] = None,
        is_health_check: bool = False,
    ) -> CommandResult:
        """
        Führt einen CI-V Befehl aus (mit TransportManager-Synchronisierung).

        Args:
            command_name: Name des Befehls (aus YAML)
            data: Optional: Daten für gebundene Befehle (PUT)
            is_health_check: True für Health-Check Operationen (kürzere Timeouts)

        Returns:
            CommandResult mit Ergebnis und Daten
        """
        cmd = self.parser.get_command(command_name)
        if not cmd:
            logger.warning(f'Unknown command: {command_name}')
            return CommandResult(
                success=False,
                error=f'Unknown command: {command_name}'
            )

        logger.debug(
            f'Executing command: {command_name} '
            f'(0x{cmd.cmd:02X}{"".join(f"/{value:02X}" for value in (cmd.subcmd or []))})'
        )

        try:
            # Baue Request
            frame_bytes, error = self.build_request(command_name, data)
            if error:
                return CommandResult(success=False, error=error)

            # Sende über Transport Manager mit Synchronisierung
            response_data = await self.transport_manager.execute_command_on_device(
                frame_bytes=frame_bytes,
                command_name=command_name,
                is_health_check=is_health_check,
            )

            # Falls keine echte Hardware, simuliere Antwort
            if response_data is None:
                result_data = self._simulate_command_response(command_name, data)
                return CommandResult(success=True, data=result_data)

            # Parse echte Antwort von Gerät
            return self.parse_response(response_data.raw_bytes, command_name)

        except Exception as e:
            logger.error(f'Command execution failed: {e}')
            return CommandResult(success=False, error=str(e))

    def _simulate_command_response(self, command_name: str, data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Simuliert eine Antwort für Tests ohne USB."""
        if command_name == 'read_operating_frequency':
            return {'frequency': 145500000, 'vfo': 'A'}
        elif command_name == 'read_operating_mode':
            return {'mode': 'CW', 'filter': None}
        elif command_name == 'read_s_meter':
            return {'level_high': 0x78, 'level_low': 0x00}
        else:
            return data or {}

    def build_request(
        self,
        command_name: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bytes, Optional[str]]:
        """
        Baut eine CI-V Request-Nachricht.

        Returns:
            Tuple aus (bytes, error_message)
        """
        cmd = self.parser.get_command(command_name)
        if not cmd:
            return b'', f'Unknown command: {command_name}'

        # CI-V Request (PC -> Radio):
        # [Preamble] [Radio] [Controller] [CMD] [SUBCMD?] [DATA...] [Terminator]
        frame = bytearray([
            self.parser.preamble[0],
            self.parser.preamble[1],
            self.parser.radio_addr,
            self.parser.controller_addr,
            cmd.cmd,
        ])

        if cmd.subcmd:
            frame.extend(cmd.subcmd)

        # Encode data based on command
        encoded_data, error = self._encode_data(command_name, data)
        if error:
            return b'', error

        if encoded_data:
            frame.extend(encoded_data)
            logger.debug(f'Added {len(encoded_data)} bytes of encoded data to frame')

        frame.append(self.parser.terminator)  # End marker

        # Debug: Ausgabe des vollständigen Frames
        hex_str = " ".join(f"{b:02X}" for b in frame)
        logger.debug(f'[BUILD] CI-V Frame für "{command_name}": {hex_str}')

        return bytes(frame), None

    def _encode_data(self, command_name: str, data: Optional[Dict[str, Any]]) -> Tuple[bytes, Optional[str]]:
        """
        Codiert Befehls-Daten für CI-V Format.

        Returns:
            Tuple aus (encoded_bytes, error_message)
        """
        if not data:
            return b'', None

        # Spezielle Codierung für bekannte Befehle
        if command_name == 'set_operating_frequency':
            frequency_hz = data.get('frequency')
            if not frequency_hz:
                return b'', 'Missing frequency in data'
            return self._frequency_to_bcd(frequency_hz), None

        elif command_name == 'set_operating_mode':
            mode = data.get('mode', 'CW')
            mode_codes = {'CW': 0x05, 'SSB': 0x01, 'AM': 0x02, 'FM': 0x03}
            mode_code = mode_codes.get(mode, 0x05)
            return bytes([mode_code, 0x00]), None  # mode + filter

        # Fallback: Serialize dict as-is (für generische Befehle)
        return b'', None

    def parse_response(
        self,
        raw_response: bytes,
        expected_command: str,
    ) -> CommandResult:
        """
        Parst eine CI-V Response-Nachricht.

        Args:
            raw_response: Rohe Bytes aus dem Gerät
            expected_command: Name des erwarteten Befehls
        """
        # Debug: Ausgabe der rohen Response
        hex_str = " ".join(f"{b:02X}" for b in raw_response)
        logger.debug(f'[PARSE] Response für "{expected_command}": {hex_str}')

        expected_cmd = self.parser.get_command(expected_command)
        if not expected_cmd:
            return CommandResult(
                success=False,
                error=f'Unknown expected command: {expected_command}',
                raw_response=raw_response,
            )

        # Validierung
        if len(raw_response) < 6:
            return CommandResult(
                success=False,
                error='Response too short',
                raw_response=raw_response,
            )

        if raw_response[0:2] != self.parser.preamble:
            return CommandResult(
                success=False,
                error='Invalid CI-V frame start',
                raw_response=raw_response,
            )

        if raw_response[-1] != self.parser.terminator:
            return CommandResult(
                success=False,
                error='Invalid CI-V frame end',
                raw_response=raw_response,
            )

        # CI-V Response (Radio -> PC):
        # [Preamble] [Controller] [Radio] [CMD] [SUBCMD?] [DATA...] [Terminator]
        if raw_response[2] != self.parser.controller_addr or raw_response[3] != self.parser.radio_addr:
            return CommandResult(
                success=False,
                error=(
                    f'Unexpected address order in response: '
                    f'{raw_response[2]:02X} {raw_response[3]:02X} '
                    f'(expected {self.parser.controller_addr:02X} {self.parser.radio_addr:02X})'
                ),
                raw_response=raw_response,
            )

        if raw_response[4] != expected_cmd.cmd:
            return CommandResult(
                success=False,
                error=(
                    f'Unexpected response command byte: {raw_response[4]:02X} '
                    f'(expected {expected_cmd.cmd:02X})'
                ),
                raw_response=raw_response,
            )

        payload_start = 5
        expected_subcmd = expected_cmd.subcmd or []
        if expected_subcmd:
            if len(raw_response) < (6 + len(expected_subcmd)):
                return CommandResult(
                    success=False,
                    error='Response too short for subcommand validation',
                    raw_response=raw_response,
                )
            actual_subcmd = list(raw_response[5:5 + len(expected_subcmd)])
            if actual_subcmd != expected_subcmd:
                return CommandResult(
                    success=False,
                    error=(
                        f'Unexpected response subcmd bytes: '
                        f'{" ".join(f"{value:02X}" for value in actual_subcmd)} '
                        f'(expected {" ".join(f"{value:02X}" for value in expected_subcmd)})'
                    ),
                    raw_response=raw_response,
                )
            payload_start = 5 + len(expected_subcmd)

        payload = raw_response[payload_start:-1]

        decoded_data, error = self._decode_response(expected_command, payload)
        if error:
            return CommandResult(
                success=False,
                error=error,
                raw_response=raw_response,
            )

        return CommandResult(
            success=True,
            data=decoded_data,
            raw_response=raw_response,
        )

    def _decode_response(self, command_name: str, payload: bytes) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Dekodiert die Response-Daten für ein Kommando.

        Returns:
            Tuple aus (decoded_dict, error_message)
        """
        if not payload:
            return {}, None

        command = self.parser._read_protocol_command(command_name)

        response = command.get('response', {})
        if not response:
            logger.error(f'No response structure defined for command: {command_name}')
            return {'raw_data': payload.hex()}, None

        # Spezielle Dekodierung für bekannte Befehle
        if not command:
            return {'raw_data': payload.hex()}, None

        elif command_name == 'read_operating_frequency':
            if len(payload) < 5:
                return None, f'Response too short for frequency: {len(payload)} bytes'

            bcd_bytes = payload[:5]
            frequency = self._bcd_to_frequency(bcd_bytes)
            return {'frequency': frequency, 'vfo': 'A'}, None

        elif command_name == 'read_s_meter':
            if len(payload) < 1:
                return None, f'Response too short for S-meter: {len(payload)} bytes'

            level = payload[0]
            return {'level_high': level, 'level_low': 0}, None

        elif command_name == 'read_transceiver_id':
            if len(payload) < 1:
                return None, f'Response too short for transceiver ID: {len(payload)} bytes'
            return {'id': payload.hex()}, None

        else:
            # Check data length against response structure
            payload_length = len(payload)
            for item in response:
                if 'size' in item and payload_length == item['size']:
                    break
                else:
                    item = None

            if not item:
                logger.error(f'No matching response structure found for command: {command_name}')
                return {'raw_data': payload.hex()}, None

            # Select decoding method based on item definition
            if not 'encoding' in item:
                logger.error('No encoding method defined for command, returning raw data')
                return {'raw_data': payload.hex()}, None

            encoding = item['encoding']

            if encoding == 'bytes':
                bytes_def = item.get('bytes', [])
                if not bytes_def:
                    logger.error('No byte definitions found for bytes encoding, returning raw data')
                    return {'raw_data': payload.hex()}, None

                return_data = {}
                for byte_def in bytes_def:
                    index = byte_def.get('index')
                    length = byte_def.get('length', 1)
                    name = byte_def.get('name', f'byte_{index}')
                    encoding_method = byte_def.get('encoding', 'direct')

                    if index is  None and index + length > len(payload):
                        logger.error(f'Byte definition index/length out of bounds for payload: {index}+{length} > {len(payload)}')
                        return {'raw_data': payload.hex()}, None

                    if encoding_method == 'enum':
                        values = byte_def.get('values', {})
                        raw_value = payload[index] if length == 1 else payload[index:index+length]
                        if length == 1:
                            decoded_value = values.get(raw_value, f'UNKNOWN(0x{raw_value:02X})')
                        else:
                            decoded_value = values.get(raw_value.hex(), f'UNKNOWN(0x{raw_value.hex()})')
                        return_data[name] = decoded_value
                    else:
                        return_data[name] = payload[index:index + length].hex()

                return return_data, None

            return {'raw_data': payload.hex()}, None

    # @staticmethod
    # def _decode_bytes(payload: bytes, command: Dict[str, Any]):
    #     """Dekodiert Payload-Bytes basierend auf der Befehlsdefinition."""
    #     bytes = command['encoding'].get('bytes', [])
    #     print(f'Decoding bytes for command: {command["name"]}')



# finding: These functions do not use the YAML-files of the CI-V protocol. (see #9 GitHub issue for details)
    @staticmethod
    def _frequency_to_bcd(frequency_hz: int) -> bytes:
        """Konvertiert Frequenz (Hz) in BCD-Format für CI-V."""
        # Icom CI-V: 5 BCD-Bytes, niederwertige Dezimalstellen zuerst.
        # Pro Byte: low nibble = 10^n, high nibble = 10^(n+1).
        value = int(frequency_hz)
        bcd = bytearray()

        for _ in range(5):
            d0 = value % 10
            value //= 10
            d1 = value % 10
            value //= 10
            bcd.append((d1 << 4) | d0)

        return bytes(bcd)

    @staticmethod
    def _bcd_to_frequency(bcd_bytes: bytes) -> int:
        """Konvertiert BCD CI-V Frequenz zurück in Hz."""
        if len(bcd_bytes) < 5:
            return 0

        frequency = 0
        factor = 1
        for byte in bcd_bytes[:5]:
            low_digit = byte & 0x0F
            high_digit = (byte >> 4) & 0x0F
            frequency += low_digit * factor
            factor *= 10
            frequency += high_digit * factor
            factor *= 10

        return frequency
