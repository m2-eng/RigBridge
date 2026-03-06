"""
Stufe 1: YAML-Protokoll Parser Tests.

Testet das Laden und Parsing der YAML-Protokolldateien.
"""

import pytest
from pathlib import Path

from src.backend.protocol.civ_protocol import ProtocolParser


@pytest.mark.protocol
class TestProtocolParser:
    """Tests für YAML-Protokoll Parser."""

    def test_parser_initialization(self, protocol_file, manufacturer_file):
        """Test: Parser kann YAML-Datei laden."""
        parser = ProtocolParser(protocol_file, manufacturer_file)
        assert parser is not None
        assert len(parser.commands) > 0, "Keine Befehle geladen"

    def test_protocol_file_exists(self, protocol_file):
        """Test: Protokolldatei existiert."""
        assert protocol_file.exists(), f"Protokolldatei nicht gefunden: {protocol_file}"

    def test_commands_loaded(self, protocol_file, manufacturer_file):
        """Test: Befehle wurden geladen."""
        parser = ProtocolParser(protocol_file, manufacturer_file)

        # Erwartete Befehle (nur aktive, nicht auskommentierte)
        expected_commands = [
            'read_operating_frequency',
            'read_operating_mode',
        ]

        for cmd_name in expected_commands:
            cmd = parser.get_command(cmd_name)
            assert cmd is not None, f"Befehl nicht gefunden: {cmd_name}"
            assert cmd.cmd is not None, f"CMD-Byte nicht gesetzt für {cmd_name}"

    def test_command_structure(self, protocol_file, manufacturer_file):
        """Test: Befehle haben richtige Struktur."""
        parser = ProtocolParser(protocol_file, manufacturer_file)
        cmd = parser.get_command('read_operating_frequency')

        assert cmd is not None
        assert isinstance(cmd.cmd, int), "cmd sollte int sein"
        assert cmd.cmd > 0, "cmd sollte > 0 sein"
        # subcmd kann None sein oder int/list
        assert cmd.subcmd is None or isinstance(cmd.subcmd, (int, list)), \
            f"subcmd sollte None, int oder list sein, ist aber {type(cmd.subcmd)}"

    def test_frame_config_loaded(self, protocol_file, manufacturer_file):
        """Test: Frame-Konfiguration wurde geladen."""
        parser = ProtocolParser(protocol_file, manufacturer_file)

        assert hasattr(parser, 'preamble'), "Preamble nicht geladen"
        assert hasattr(parser, 'terminator'), "Terminator nicht geladen"
        assert hasattr(parser, 'controller_addr'), "Controller-Adresse nicht geladen"
        assert hasattr(parser, 'radio_addr'), "Radio-Adresse nicht geladen"

        # Standardwerte für Icom CI-V
        assert parser.preamble == bytearray([0xFE, 0xFE]), "Preamble sollte [FE FE] sein"
        assert parser.terminator == 0xFD, "Terminator sollte [FD] sein"
        assert parser.controller_addr == 0xE0, "Controller-Addr sollte 0xE0 sein"
        assert parser.radio_addr == 0xA4, "Radio-Addr sollte 0xA4 sein"

    def test_get_nonexistent_command(self, protocol_file, manufacturer_file):
        """Test: Nicht existierender Befehl gibt None zurück."""
        parser = ProtocolParser(protocol_file, manufacturer_file)
        cmd = parser.get_command('nonexistent_command_xyz')
        assert cmd is None, "Nicht existierender Befehl sollte None sein"

    def test_response_decoder_exists(self, protocol_file, manufacturer_file):
        """Test: Befehle mit Responses haben decoder."""
        parser = ProtocolParser(protocol_file, manufacturer_file)
        cmd = parser.get_command('read_operating_frequency')

        # Dieser Befehl sollte einen Response-Decoder haben
        if hasattr(cmd, 'response'):
            assert cmd.response is not None, "Response sollte nicht None sein"
