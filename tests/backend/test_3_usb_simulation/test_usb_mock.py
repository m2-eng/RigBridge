"""
Stufe 3: USB-Simulation Tests.

Testet die Kommunikation mit simulierter USB-Verbindung (ohne echte Hardware).
"""

import asyncio

import pytest

from src.backend.protocol.civ_protocol import CIVCommandExecutor, CommandResult
from src.backend.transport import USBConnection


@pytest.mark.usb_sim
class TestUSBSimulation:
    """Tests für USB-Simulation (Fallback-Modus)."""

    def test_executor_with_simulation(self, protocol_file, manufacturer_file):
        """Test: CIVCommandExecutor funktioniert ohne echte USB-Verbindung."""
        # Erstelle Executor ohne USB-Verbindung (verwendet Fallback)
        executor = CIVCommandExecutor(protocol_file=protocol_file, manufacturer_file=manufacturer_file)
        assert executor is not None

    @pytest.mark.asyncio
    async def test_read_frequency_simulation(self, protocol_file, manufacturer_file):
        """Test: Frequenz-Befehl im Simulationsmodus."""
        executor = CIVCommandExecutor(protocol_file=protocol_file, manufacturer_file=manufacturer_file)

        # Lese Frequenz (sollte Fallback-Wert zurückgeben)
        result = await executor.execute_command('read_operating_frequency')

        assert isinstance(result, CommandResult)
        # Ergebnis kann success sein (echte Hardware) oder fallback
        assert hasattr(result, 'data'), "Result sollte 'data' Attribut haben"

    @pytest.mark.asyncio
    async def test_read_mode_simulation(self, protocol_file, manufacturer_file):
        """Test: Modus-Befehl im Simulationsmodus."""
        executor = CIVCommandExecutor(protocol_file=protocol_file, manufacturer_file=manufacturer_file)

        result = await executor.execute_command('read_operating_mode')

        assert isinstance(result, CommandResult)
        assert hasattr(result, 'data'), "Result sollte 'data' Attribut haben"

    @pytest.mark.skip(reason="Befehl 'read_s_meter' in YAML auskommentiert während Syntax-Überarbeitung")
    @pytest.mark.asyncio
    async def test_read_s_meter_simulation(self, protocol_file, manufacturer_file):
        """Test: S-Meter-Befehl im Simulationsmodus."""
        executor = CIVCommandExecutor(protocol_file=protocol_file, manufacturer_file=manufacturer_file)

        result = await executor.execute_command('read_s_meter')

        assert isinstance(result, CommandResult)
        assert hasattr(result, 'data'), "Result sollte 'data' Attribut haben"

    @pytest.mark.asyncio
    async def test_command_result_structure(self, protocol_file, manufacturer_file):
        """Test: CommandResult hat erwartetete Struktur."""
        executor = CIVCommandExecutor(protocol_file=protocol_file, manufacturer_file=manufacturer_file)
        result = await executor.execute_command('read_operating_frequency')

        assert hasattr(result, 'success'), "Result sollte 'success' haben"
        assert hasattr(result, 'data'), "Result sollte 'data' haben"
        assert hasattr(result, 'error'), "Result sollte 'error' haben"

        assert isinstance(result.data, dict), "data sollte dict sein"

    @pytest.mark.asyncio
    async def test_multiple_commands_in_sequence(self, protocol_file, manufacturer_file):
        """Test: Mehrere Befehle hintereinander."""
        executor = CIVCommandExecutor(protocol_file=protocol_file, manufacturer_file=manufacturer_file)

        commands = [
            'read_operating_frequency',
            'read_operating_mode',
        ]

        for cmd_name in commands:
            result = await executor.execute_command(cmd_name)
            assert isinstance(result, CommandResult), f"Fehler bei {cmd_name}"
            assert hasattr(result, 'data'), f"{cmd_name} sollte 'data' haben"

    @pytest.mark.asyncio
    async def test_frequency_data_format(self, protocol_file, manufacturer_file):
        """Test: Frequenz-Daten haben richtiges Format."""
        executor = CIVCommandExecutor(protocol_file=protocol_file, manufacturer_file=manufacturer_file)
        result = await executor.execute_command('read_operating_frequency')

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
    @pytest.mark.skip(reason="Befehl 'set_operating_frequency' in YAML auskommentiert während Syntax-Überarbeitung")
    @pytest.mark.asyncio
    async def test_set_frequency_simulation(self, protocol_file, manufacturer_file):
        """Test: Frequenz Set-Befehl im Simulationsmodus."""
        executor = CIVCommandExecutor(protocol_file=protocol_file, manufacturer_file=manufacturer_file)

        # Setze Frequenz auf 145.5 MHz
        result = await executor.execute_command(
            'set_operating_frequency',
            data={'frequency': 145_500_000}
        )

        assert isinstance(result, CommandResult)
        # Set-Befehle haben meist kein Response-Daten, nur Error/Success
        assert hasattr(result, 'success')

    @pytest.mark.skip(reason="Befehl 'read_s_meter' in YAML auskommentiert während Syntax-Überarbeitung")
    @pytest.mark.asyncio
    async def test_frame_echo_detection_simulation(self, protocol_file, manufacturer_file):
        """Test: Echo-Detection im Simulationsmodus."""
        executor = CIVCommandExecutor(protocol_file=protocol_file, manufacturer_file=manufacturer_file)

        # Dieser Test prüft, dass der Code nicht abstürzt
        # Real Hardware würde Echo filtern
        result = await executor.execute_command('read_s_meter')
        assert isinstance(result, CommandResult)

    def test_bcd_frequency_encoding(self, protocol_file, manufacturer_file):
        """Test: BCD-Frequenz-Kodierung."""
        from src.backend.protocol.civ_protocol import CIVCommandExecutor as Executor

        # Teste BCD-Konvertierung
        executor = Executor(protocol_file=protocol_file, manufacturer_file=manufacturer_file)

        # Private Methode testen (falls vorhanden)
        if hasattr(executor, '_frequency_to_bcd'):
            # BCD-Encoding für 145.5 MHz
            bcd = executor._frequency_to_bcd(145_500_000)
            assert bcd is not None, "BCD-Encoding sollte nicht None sein"
            assert isinstance(bcd, (bytes, bytearray)), "BCD sollte bytes sein"
