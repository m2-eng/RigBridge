"""
Unit-Tests für ProtocolManager.

Testet den zentralen Protocol Manager (Singleton-Pattern).
"""

import pytest
from pathlib import Path

from src.backend.protocol.protocol_manager import ProtocolManager
from src.backend.protocol.base_protocol import BaseProtocol, CommandResult
from src.backend.protocol.civ_protocol import CIVProtocol


@pytest.mark.unit
class TestProtocolManager:
    """Unit-Tests für ProtocolManager."""

    def test_singleton_pattern(self):
        """Test: ProtocolManager ist Singleton."""
        pm1 = ProtocolManager()
        pm2 = ProtocolManager()

        assert pm1 is pm2, "ProtocolManager sollte Singleton sein"

    def test_initial_state(self):
        """Test: Initialer Zustand ohne Protokoll."""
        pm = ProtocolManager()

        assert not pm.has_protocol(), "Sollte initial kein Protokoll haben"
        assert pm.get_protocol() is None, "get_protocol sollte None zurückgeben"
        assert pm.list_commands() == [], "Sollte leere Command-Liste zurückgeben"

    def test_set_and_get_protocol(self, protocol_file, manufacturer_file):
        """Test: Protokoll setzen und abrufen."""
        pm = ProtocolManager()
        protocol = CIVProtocol(protocol_file, manufacturer_file)

        pm.set_protocol(protocol)

        assert pm.has_protocol(), "Sollte Protokoll haben"
        assert pm.get_protocol() is protocol, "Sollte selbes Protokoll zurückgeben"

    def test_list_commands_with_protocol(self, protocol_file, manufacturer_file):
        """Test: Commands nach Protokoll-Initialisierung."""
        pm = ProtocolManager()
        protocol = CIVProtocol(protocol_file, manufacturer_file)
        pm.set_protocol(protocol)

        commands = pm.list_commands()
        command_names = {command['name'] for command in commands}

        assert len(commands) > 0, "Sollte Commands haben"
        assert 'read_operating_frequency' in command_names, "Sollte read_operating_frequency haben"
        assert 'read_operating_mode' in command_names, "Sollte read_operating_mode haben"
        assert all('description' in command for command in commands), "Jeder Command sollte eine Beschreibung enthalten"

    @pytest.mark.asyncio
    async def test_execute_command_without_protocol(self):
        """Test: Command ohne gesetztes Protokoll."""
        pm = ProtocolManager()
        # Sicherstellen dass kein Protokoll gesetzt ist
        pm._protocol = None

        result = await pm.execute_command('read_operating_frequency')

        assert not result.success, "Command sollte fehlschlagen ohne Protokoll"
        assert result.error is not None, "Sollte Fehlermeldung haben"
        assert 'No protocol set' in result.error, "Sollte spezifische Fehlermeldung haben"

    @pytest.mark.asyncio
    async def test_get_frequency_without_protocol(self):
        """Test: get_frequency ohne Protokoll."""
        pm = ProtocolManager()
        pm._protocol = None

        frequency = await pm.get_frequency()

        assert frequency is None, "Sollte None zurückgeben ohne Protokoll"

    @pytest.mark.asyncio
    async def test_get_mode_without_protocol(self):
        """Test: get_mode ohne Protokoll."""
        pm = ProtocolManager()
        pm._protocol = None

        mode = await pm.get_mode()

        assert mode is None, "Sollte None zurückgeben ohne Protokoll"

    @pytest.mark.asyncio
    async def test_get_power_without_protocol(self):
        """Test: get_power ohne Protokoll."""
        pm = ProtocolManager()
        pm._protocol = None

        power = await pm.get_power()

        assert power is None, "Sollte None zurückgeben ohne Protokoll"

    def test_supports_power_without_protocol(self):
        """Test: supports_power ohne Protokoll."""
        pm = ProtocolManager()
        pm._protocol = None

        supports = pm.supports_power()

        assert not supports, "Sollte False zurückgeben ohne Protokoll"

    def test_get_protocol_info_without_protocol(self):
        """Test: Protocol Info ohne Protokoll."""
        pm = ProtocolManager()
        pm._protocol = None

        info = pm.get_protocol_info()

        assert not info['active'], "Sollte nicht aktiv sein"
        assert info['protocol_type'] is None, "Sollte kein Protocol Type haben"
        assert info['supported_commands'] == [], "Sollte leere Commands haben"

    def test_get_protocol_info_with_protocol(self, protocol_file, manufacturer_file):
        """Test: Protocol Info mit Protokoll."""
        pm = ProtocolManager()
        protocol = CIVProtocol(protocol_file, manufacturer_file)
        pm.set_protocol(protocol)

        info = pm.get_protocol_info()

        assert info['active'], "Sollte aktiv sein"
        assert info['protocol_type'] == 'CIVProtocol', "Sollte CIVProtocol sein"
        assert len(info['supported_commands']) > 0, "Sollte Commands haben"
        assert 'protocol_file' in info, "Sollte protocol_file haben"

    @pytest.mark.asyncio
    async def test_handle_unsolicited_frame_without_protocol(self):
        """Test: Unsolicited Frame ohne Protokoll."""
        pm = ProtocolManager()
        pm._protocol = None

        # Sollte nicht werfen
        await pm.handle_unsolicited_frame(b'\xfe\xfe\x94\xe0\x03\x00\xfd')

    def test_register_handler_without_protocol(self):
        """Test: Handler-Registrierung ohne Protokoll."""
        pm = ProtocolManager()
        pm._protocol = None

        def dummy_handler(data):
            pass

        # Sollte nicht werfen, nur Warning loggen
        pm.register_unsolicited_handler(dummy_handler)

    def test_unregister_handler_without_protocol(self):
        """Test: Handler-Deregistrierung ohne Protokoll."""
        pm = ProtocolManager()
        pm._protocol = None

        def dummy_handler(data):
            pass

        # Sollte nicht werfen
        pm.unregister_unsolicited_handler(dummy_handler)


@pytest.mark.integration
class TestProtocolManagerIntegration:
    """Integrationstests für ProtocolManager mit echtem Protokoll."""

    @pytest.mark.asyncio
    async def test_execute_command_with_civ_protocol(self, protocol_file, manufacturer_file):
        """Test: Command mit CIVProtocol."""
        pm = ProtocolManager()
        protocol = CIVProtocol(protocol_file, manufacturer_file)
        pm.set_protocol(protocol)

        # Fallback-Modus ohne USB-Connection erwartet
        result = await pm.execute_command('read_operating_frequency')

        assert hasattr(result, 'success'), "Sollte success-Attribut haben"
        assert hasattr(result, 'data'), "Sollte data-Attribut haben"

    @pytest.mark.asyncio
    async def test_convenience_methods_with_protocol(self, protocol_file, manufacturer_file):
        """Test: Convenience-Methoden mit Protokoll."""
        pm = ProtocolManager()
        protocol = CIVProtocol(protocol_file, manufacturer_file)
        pm.set_protocol(protocol)

        # Diese sollten ohne Fehler durchlaufen (Fallback-Modus)
        frequency = await pm.get_frequency()
        mode = await pm.get_mode()
        power = await pm.get_power()

        # Im Fallback-Modus könnten diese None sein
        assert frequency is None or isinstance(frequency, int)
        assert mode is None or isinstance(mode, str)
        assert power is None or isinstance(power, float)

    def test_supports_power_with_protocol(self, protocol_file, manufacturer_file):
        """Test: Power-Support-Check mit Protokoll."""
        pm = ProtocolManager()
        protocol = CIVProtocol(protocol_file, manufacturer_file)
        pm.set_protocol(protocol)

        # CIVProtocol sollte Power-Befehle listen (wenn in YAML definiert)
        supports = pm.supports_power()
        assert isinstance(supports, bool)

    @pytest.mark.asyncio
    async def test_multiple_command_execution(self, protocol_file, manufacturer_file):
        """Test: Mehrere Commands nacheinander."""
        pm = ProtocolManager()
        protocol = CIVProtocol(protocol_file, manufacturer_file)
        pm.set_protocol(protocol)

        commands = ['read_operating_frequency', 'read_operating_mode']

        for cmd in commands:
            result = await pm.execute_command(cmd)
            assert hasattr(result, 'success'), f"Command {cmd} sollte Result haben"
