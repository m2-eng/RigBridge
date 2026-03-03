"""
Stufe 3: USB-Simulation Tests.

Testet die Kommunikation mit simulierter USB-Verbindung (ohne echte Hardware).
"""

import pytest

from src.backend.civ.executor import CIVCommandExecutor, CommandResult
from src.backend.usb.connection import USBConnection


@pytest.mark.usb_sim
class TestUSBSimulation:
    """Tests für USB-Simulation (Fallback-Modus)."""

    def test_executor_with_simulation(self, protocol_file):
        """Test: CIVCommandExecutor funktioniert ohne echte USB-Verbindung."""
        # Erstelle Executor ohne USB-Verbindung (verwendet Fallback)
        executor = CIVCommandExecutor(protocol_file=protocol_file)
        assert executor is not None

    def test_read_frequency_simulation(self, protocol_file):
        """Test: Frequenz-Befehl im Simulationsmodus."""
        executor = CIVCommandExecutor(protocol_file=protocol_file)
        
        # Lese Frequenz (sollte Fallback-Wert zurückgeben)
        result = executor.execute_command('read_operating_frequency')
        
        assert isinstance(result, CommandResult)
        # Ergebnis kann success sein (echte Hardware) oder fallback
        assert hasattr(result, 'data'), "Result sollte 'data' Attribut haben"

    def test_read_mode_simulation(self, protocol_file):
        """Test: Modus-Befehl im Simulationsmodus."""
        executor = CIVCommandExecutor(protocol_file=protocol_file)
        
        result = executor.execute_command('read_operating_mode')
        
        assert isinstance(result, CommandResult)
        assert hasattr(result, 'data'), "Result sollte 'data' Attribut haben"

    def test_read_s_meter_simulation(self, protocol_file):
        """Test: S-Meter-Befehl im Simulationsmodus."""
        executor = CIVCommandExecutor(protocol_file=protocol_file)
        
        result = executor.execute_command('read_s_meter')
        
        assert isinstance(result, CommandResult)
        assert hasattr(result, 'data'), "Result sollte 'data' Attribut haben"

    def test_command_result_structure(self, protocol_file):
        """Test: CommandResult hat erwartetete Struktur."""
        executor = CIVCommandExecutor(protocol_file=protocol_file)
        result = executor.execute_command('read_s_meter')
        
        assert hasattr(result, 'success'), "Result sollte 'success' haben"
        assert hasattr(result, 'data'), "Result sollte 'data' haben"
        assert hasattr(result, 'error'), "Result sollte 'error' haben"
        
        assert isinstance(result.data, dict), "data sollte dict sein"

    def test_multiple_commands_in_sequence(self, protocol_file):
        """Test: Mehrere Befehle hintereinander."""
        executor = CIVCommandExecutor(protocol_file=protocol_file)
        
        commands = [
            'read_s_meter',
            'read_operating_frequency',
            'read_operating_mode',
        ]
        
        for cmd_name in commands:
            result = executor.execute_command(cmd_name)
            assert isinstance(result, CommandResult), f"Fehler bei {cmd_name}"
            assert hasattr(result, 'data'), f"{cmd_name} sollte 'data' haben"

    def test_frequency_data_format(self, protocol_file):
        """Test: Frequenz-Daten haben richtiges Format."""
        executor = CIVCommandExecutor(protocol_file=protocol_file)
        result = executor.execute_command('read_operating_frequency')
        
        # Wenn erfolgreich, sollte 'frequency' im Data sein
        if result.success or result.data:
            # Ergebnis kann fallback sein
            if 'frequency' in result.data:
                frequency = result.data['frequency']
                assert isinstance(frequency, int), "frequency sollte int sein"
                assert frequency > 0, "frequency sollte > 0 sein"
                # Vernünftiger Bereich für Funk (z.B. nicht negativ)
                assert frequency < 10_000_000_000, "frequency sollte < 10 GHz sein"

    @pytest.mark.slow
    def test_set_frequency_simulation(self, protocol_file):
        """Test: Frequenz Set-Befehl im Simulationsmodus."""
        executor = CIVCommandExecutor(protocol_file=protocol_file)
        
        # Setze Frequenz auf 145.5 MHz
        result = executor.execute_command(
            'set_operating_frequency',
            data={'frequency': 145_500_000}
        )
        
        assert isinstance(result, CommandResult)
        # Set-Befehle haben meist kein Response-Daten, nur Error/Success
        assert hasattr(result, 'success')

    def test_frame_echo_detection_simulation(self, protocol_file):
        """Test: Echo-Detection im Simulationsmodus."""
        executor = CIVCommandExecutor(protocol_file=protocol_file)
        
        # Dieser Test prüft, dass der Code nicht abstürzt
        # Real Hardware würde Echo filtern
        result = executor.execute_command('read_s_meter')
        assert isinstance(result, CommandResult)

    def test_bcd_frequency_encoding(self, protocol_file):
        """Test: BCD-Frequenz-Kodierung."""
        from src.backend.civ.executor import CIVCommandExecutor as Executor
        
        # Teste BCD-Konvertierung
        executor = Executor(protocol_file=protocol_file)
        
        # Private Methode testen (falls vorhanden)
        if hasattr(executor, '_frequency_to_bcd'):
            # BCD-Encoding für 145.5 MHz
            bcd = executor._frequency_to_bcd(145_500_000)
            assert bcd is not None, "BCD-Encoding sollte nicht None sein"
            assert isinstance(bcd, (bytes, bytearray)), "BCD sollte bytes sein"
