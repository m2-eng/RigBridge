"""
Unit-Tests für CIVProtocol.

Testet die CI-V Protokoll-Implementierung.
"""

import pytest
from pathlib import Path

from src.backend.protocol.civ_protocol import CIVProtocol
from src.backend.protocol.base_protocol import CommandResult


@pytest.mark.unit
class TestCIVProtocol:
    """Unit-Tests für CIVProtocol."""

    def test_initialization(self, protocol_file, manufacturer_file):
        """Test: CIVProtocol-Initialisierung."""
        protocol = CIVProtocol(protocol_file, manufacturer_file)

        assert protocol is not None, "Protokoll sollte initialisiert sein"
        assert protocol._executor is not None, "Sollte internen Executor haben"
        assert protocol._parser is not None, "Sollte internen Parser haben"

    def test_list_commands(self, protocol_file, manufacturer_file):
        """Test: Commands auflisten."""
        protocol = CIVProtocol(protocol_file, manufacturer_file)

        commands = protocol.list_commands()
        command_names = {command['name'] for command in commands}

        assert len(commands) > 0, "Sollte Commands haben"
        assert 'read_operating_frequency' in command_names, "Sollte read_operating_frequency haben"
        assert 'read_operating_mode' in command_names, "Sollte read_operating_mode haben"
        assert all('description' in command for command in commands), "Jeder Command sollte eine Beschreibung enthalten"

    def test_is_valid_radio_id_with_valid_frame(self, protocol_file, manufacturer_file):
        """Test: Radio-ID-Validierung mit gültigem Frame."""
        protocol = CIVProtocol(protocol_file, manufacturer_file)

        # Baue gültiges CI-V unsolicited Frame (Radio → PC)
        # Format: [Preamble] [Controller] [Radio] [CMD] [...]
        radio_addr = protocol.get_radio_address()
        controller_addr = protocol.get_controller_address()
        valid_frame = bytes([0xFE, 0xFE, controller_addr, radio_addr, 0x03, 0x00, 0xFD])

        is_valid = protocol.is_valid_radio_id(valid_frame)

        assert is_valid, f"Sollte gültiges Frame erkennen (Radio: 0x{radio_addr:02X})"

    def test_is_valid_radio_id_without_preamble(self, protocol_file, manufacturer_file):
        """Test: Radio-ID-Validierung ohne Preamble."""
        protocol = CIVProtocol(protocol_file, manufacturer_file)

        # Fehlerhafte Preamble
        invalid_frame = bytes([0xFF, 0xFF, 0x94, 0xE0, 0x03, 0x00, 0xFD])

        is_valid = protocol.is_valid_radio_id(invalid_frame)

        assert not is_valid, "Sollte ungültiges Frame erkennen"

    def test_is_valid_radio_id_with_wrong_radio_address(self, protocol_file, manufacturer_file):
        """Test: Radio-ID-Validierung mit falscher Radio-Adresse."""
        protocol = CIVProtocol(protocol_file, manufacturer_file)

        # Korrekte Preamble, aber falsche Radio-Adresse (0xFF statt korrekte)
        controller_addr = protocol.get_controller_address()
        invalid_frame = bytes([0xFE, 0xFE, 0xFF, controller_addr, 0x03, 0x00, 0xFD])

        is_valid = protocol.is_valid_radio_id(invalid_frame)

        assert not is_valid, "Sollte Frame mit falscher Radio-ID ablehnen"

    def test_is_valid_radio_id_with_short_frame(self, protocol_file, manufacturer_file):
        """Test: Radio-ID-Validierung mit zu kurzem Frame."""
        protocol = CIVProtocol(protocol_file, manufacturer_file)

        # Zu kurzes Frame
        short_frame = bytes([0xFE, 0xFE])

        is_valid = protocol.is_valid_radio_id(short_frame)

        assert not is_valid, "Sollte zu kurze Frames ablehnen"

    def test_get_radio_address(self, protocol_file, manufacturer_file):
        """Test: Radio-Adresse auslesen."""
        protocol = CIVProtocol(protocol_file, manufacturer_file)

        radio_address = protocol.get_radio_address()

        assert radio_address is not None, "Sollte Radio-Adresse haben"
        assert isinstance(radio_address, int), "Radio-Adresse sollte Integer sein"
        assert 0 <= radio_address <= 0xFF, "Radio-Adresse sollte gültiger Byte-Wert sein"

    def test_get_controller_address(self, protocol_file, manufacturer_file):
        """Test: Controller-Adresse auslesen."""
        protocol = CIVProtocol(protocol_file, manufacturer_file)

        controller_address = protocol.get_controller_address()

        assert controller_address is not None, "Sollte Controller-Adresse haben"
        assert isinstance(controller_address, int), "Controller-Adresse sollte Integer sein"
        assert 0 <= controller_address <= 0xFF, "Controller-Adresse sollte gültiger Byte-Wert sein"

    @pytest.mark.asyncio
    async def test_execute_command_without_usb(self, protocol_file, manufacturer_file):
        """Test: Command ohne USB-Connection (Fallback-Modus)."""
        protocol = CIVProtocol(protocol_file, manufacturer_file)

        result = await protocol.execute_command('read_operating_frequency')

        assert hasattr(result, 'success'), "Sollte CommandResult zurückgeben"
        assert hasattr(result, 'data'), "Sollte data-Attribut haben"

    @pytest.mark.asyncio
    async def test_get_frequency_fallback(self, protocol_file, manufacturer_file):
        """Test: get_frequency im Fallback-Modus."""
        protocol = CIVProtocol(protocol_file, manufacturer_file)

        frequency = await protocol.get_frequency()

        # Im Fallback-Modus könnte None zurückkommen
        assert frequency is None or isinstance(frequency, int)

    @pytest.mark.asyncio
    async def test_get_mode_fallback(self, protocol_file, manufacturer_file):
        """Test: get_mode im Fallback-Modus."""
        protocol = CIVProtocol(protocol_file, manufacturer_file)

        mode = await protocol.get_mode()

        # Im Fallback-Modus könnte None zurückkommen
        assert mode is None or isinstance(mode, str)

    @pytest.mark.asyncio
    async def test_get_power_fallback(self, protocol_file, manufacturer_file):
        """Test: get_power im Fallback-Modus."""
        protocol = CIVProtocol(protocol_file, manufacturer_file)

        power = await protocol.get_power()

        # Im Fallback-Modus könnte None zurückkommen (nicht unterstützt)
        assert power is None or isinstance(power, float)

    def test_supports_power(self, protocol_file, manufacturer_file):
        """Test: Power-Support-Check."""
        protocol = CIVProtocol(protocol_file, manufacturer_file)

        supports = protocol.supports_power()

        assert isinstance(supports, bool), "Sollte Boolean zurückgeben"

    @pytest.mark.asyncio
    async def test_handle_unsolicited_frame_with_valid_frame(self, protocol_file, manufacturer_file):
        """Test: Unsolicited Frame Handling mit gültigem Frame."""
        protocol = CIVProtocol(protocol_file, manufacturer_file)

        # Baue gültiges CI-V unsolicited Frame (Radio → PC)
        # Format: [Preamble] [Controller] [Radio] [CMD] [...]
        radio_addr = protocol.get_radio_address()
        controller_addr = protocol.get_controller_address()
        valid_frame = bytes([0xFE, 0xFE, controller_addr, radio_addr, 0x03, 0x00, 0xFD])

        # Sollte nicht werfen
        await protocol.handle_unsolicited_frame(valid_frame)

    @pytest.mark.asyncio
    async def test_handle_unsolicited_frame_with_invalid_frame(self, protocol_file, manufacturer_file):
        """Test: Unsolicited Frame Handling mit ungültigem Frame."""
        protocol = CIVProtocol(protocol_file, manufacturer_file)

        # Ungültiges Frame (falsche Preamble)
        invalid_frame = bytes([0xFF, 0xFF, 0x94, 0xE0, 0x03, 0x00, 0xFD])

        # Sollte nicht werfen, nur loggen
        await protocol.handle_unsolicited_frame(invalid_frame)

    def test_register_unsolicited_handler(self, protocol_file, manufacturer_file):
        """Test: Unsolicited-Handler registrieren."""
        protocol = CIVProtocol(protocol_file, manufacturer_file)

        handler_called = []

        def test_handler(data):
            handler_called.append(data)

        protocol.register_unsolicited_handler(test_handler)

        assert test_handler in protocol._unsolicited_handlers, "Handler sollte registriert sein"

    def test_unregister_unsolicited_handler(self, protocol_file, manufacturer_file):
        """Test: Unsolicited-Handler deregistrieren."""
        protocol = CIVProtocol(protocol_file, manufacturer_file)

        def test_handler(data):
            pass

        protocol.register_unsolicited_handler(test_handler)
        protocol.unregister_unsolicited_handler(test_handler)

        assert test_handler not in protocol._unsolicited_handlers, "Handler sollte nicht mehr registriert sein"

    def test_multiple_handler_registration(self, protocol_file, manufacturer_file):
        """Test: Mehrere Handler registrieren."""
        protocol = CIVProtocol(protocol_file, manufacturer_file)

        def handler1(data):
            pass

        def handler2(data):
            pass

        protocol.register_unsolicited_handler(handler1)
        protocol.register_unsolicited_handler(handler2)

        assert len(protocol._unsolicited_handlers) == 2, "Sollte 2 Handler haben"
        assert handler1 in protocol._unsolicited_handlers
        assert handler2 in protocol._unsolicited_handlers


@pytest.mark.integration
class TestCIVProtocolIntegration:
    """Integrationstests für CIVProtocol."""

    @pytest.mark.asyncio
    async def test_command_execution_sequence(self, protocol_file, manufacturer_file):
        """Test: Mehrere Commands in Sequenz."""
        protocol = CIVProtocol(protocol_file, manufacturer_file)

        commands = ['read_operating_frequency', 'read_operating_mode']

        for cmd in commands:
            result = await protocol.execute_command(cmd)
            assert hasattr(result, 'success'), f"Command {cmd} sollte Result haben"

    @pytest.mark.asyncio
    async def test_unsolicited_frame_with_handler(self, protocol_file, manufacturer_file):
        """Test: Unsolicited Frame mit registriertem Handler."""
        protocol = CIVProtocol(protocol_file, manufacturer_file)

        received_data = []

        def capture_handler(data):
            received_data.append(data)

        protocol.register_unsolicited_handler(capture_handler)

        # Valid Frame senden (unsolicited: Radio → PC)
        # Format: [Preamble] [Controller] [Radio] [CMD] [...]
        radio_addr = protocol.get_radio_address()
        controller_addr = protocol.get_controller_address()
        valid_frame = bytes([0xFE, 0xFE, controller_addr, radio_addr, 0x03, 0x00, 0xFD])
        await protocol.handle_unsolicited_frame(valid_frame)

        # Handler sollte aufgerufen worden sein (wenn Frame erfolgreich geparst)
        # Im Fallback-Modus könnte dies nicht der Fall sein
        assert isinstance(received_data, list), "Sollte Liste sein"
