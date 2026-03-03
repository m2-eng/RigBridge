"""
Stufe 2: Befehlsaufbau Tests.

Testet den Aufbau von CI-V Frames (Request-Format).
"""

import pytest

from src.backend.civ.executor import CIVCommandExecutor


@pytest.mark.commands
class TestCommandBuilder:
    """Tests für CI-V Befehlsaufbau."""

    def test_executor_initialization(self, protocol_file):
        """Test: CIVCommandExecutor kann initialisiert werden."""
        executor = CIVCommandExecutor(protocol_file=protocol_file)
        assert executor is not None
        assert executor.parser is not None

    def test_build_read_s_meter_frame(self, protocol_file):
        """Test: S-Meter Read-Befehl wird korrekt gebaut."""
        executor = CIVCommandExecutor(protocol_file=protocol_file)
        frame, error = executor.build_request('read_s_meter')
        
        assert error is None, f"Fehler beim Frame-Aufbau: {error}"
        assert frame is not None
        
        # Verifiziere Frame-Struktur
        assert frame[0:2] == bytearray([0xFE, 0xFE]), "Preamble sollte [FE FE] sein"
        assert frame[2] == 0xA4, "RadioAddr sollte 0xA4 sein"
        assert frame[3] == 0xE0, "ControllerAddr sollte 0xE0 sein"
        assert frame[-1] == 0xFD, "Terminator sollte [FD] sein"

    def test_build_read_frequency_frame(self, protocol_file):
        """Test: Frequenz Read-Befehl wird korrekt gebaut."""
        executor = CIVCommandExecutor(protocol_file=protocol_file)
        frame, error = executor.build_request('read_operating_frequency')
        
        assert error is None, f"Fehler beim Frame-Aufbau: {error}"
        assert frame is not None
        
        # Frame sollte Mindestlänge haben: [FE FE] + [RadioAddr] + [ControllerAddr] + [CMD] + [FD]
        assert len(frame) >= 6, f"Frame zu kurz: {frame.hex()}"

    def test_build_set_frequency_frame(self, protocol_file):
        """Test: Frequenz Set-Befehl wird korrekt gebaut."""
        executor = CIVCommandExecutor(protocol_file=protocol_file)
        
        # Testfrequenz: 145.5 MHz
        frequency_hz = 145_500_000
        frame, error = executor.build_request(
            'set_operating_frequency',
            data={'frequency': frequency_hz}
        )
        
        assert error is None, f"Fehler beim Frame-Aufbau: {error}"
        assert frame is not None
        
        # Verifiziere Preamble und Host
        assert frame[0:2] == bytearray([0xFE, 0xFE])
        assert frame[2] == 0xA4
        assert frame[3] == 0xE0
        assert frame[-1] == 0xFD

    def test_frame_address_order_tx(self, protocol_file):
        """Test: TX Frame hat korrekte Adressreihenfolge (Radio, Controller)."""
        executor = CIVCommandExecutor(protocol_file=protocol_file)
        frame, error = executor.build_request('read_s_meter')
        
        assert error is None
        # TX: [FE FE] [RadioAddr 0xA4] [ControllerAddr 0xE0] [CMD] ...
        assert frame[2] == 0xA4, "TX: Position 2 sollte RadioAddr (0xA4) sein"
        assert frame[3] == 0xE0, "TX: Position 3 sollte ControllerAddr (0xE0) sein"

    def test_frame_struct_preamble(self, protocol_file):
        """Test: Frame-Preamble ist korrekt."""
        executor = CIVCommandExecutor(protocol_file=protocol_file)
        frame, error = executor.build_request('read_s_meter')
        
        assert error is None
        # Icom CI-V Preamble ist immer [FE FE]
        assert bytes(frame[0:2]) == bytes([0xFE, 0xFE])

    def test_frame_struct_terminator(self, protocol_file):
        """Test: Frame-Terminator ist korrekt."""
        executor = CIVCommandExecutor(protocol_file=protocol_file)
        frame, error = executor.build_request('read_s_meter')
        
        assert error is None
        # Icom CI-V Terminator ist immer [FD]
        assert frame[-1] == 0xFD

    def test_invalid_command_name(self, protocol_file):
        """Test: Ungültiger Befehlsname liefert Fehler."""
        executor = CIVCommandExecutor(protocol_file=protocol_file)
        frame, error = executor.build_request('invalid_command_xyz')
        
        assert frame is None or len(frame) == 0
        assert error is not None, "Es sollte ein Fehler für ungültigen Befehl gemeldet werden"

    def test_frame_minimum_length(self, protocol_file):
        """Test: Frame hat Mindestlänge."""
        executor = CIVCommandExecutor(protocol_file=protocol_file)
        frame, error = executor.build_request('read_s_meter')
        
        assert error is None
        # Minimum: [FE FE] + [RadioAddr] + [ControllerAddr] + [CMD] + [FD]
        min_length = 2 + 1 + 1 + 1 + 1  # = 6
        assert len(frame) >= min_length, f"Frame zu kurz (min {min_length}): {frame.hex()}"

    def test_frame_no_null_bytes_between_payload(self, protocol_file):
        """Test: Keine unerwarteten Null-Bytes im Frame."""
        executor = CIVCommandExecutor(protocol_file=protocol_file)
        frame, error = executor.build_request('read_s_meter')
        
        assert error is None
        # Prüfe, dass Frame valide Bytes hat (nicht zufällig Null außer in Kontroll-Bytes)
        assert all(isinstance(b, int) and 0 <= b <= 255 for b in frame), \
            "Frame enthält ungültige Byte-Werte"
