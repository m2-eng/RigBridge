"""
Stufe 4: USB Real-Hardware Tests.

Testet die Kommunikation mit echtem Funkgerät über USB/Serial.

⚠️  MANUAL TEST: Diese Tests erfordern echte Hardware!
    - Icom IC-905 Transceiver
    - USB-Verbindung zum Gerät
    - Korrekt konfigurierte config.json mit USB-Port

Ausführung:
    pytest tests/backend/test_4_usb_real_hardware/ -m usb_real -v --setup-show

    oder nur diesen Test:
    pytest tests/backend/test_4_usb_real_hardware/test_usb_real.py::TestRealHardware::test_read_frequency -m usb_real -v

Skip wenn keine Hardware vorhanden:
    pytest tests/backend/test_4_usb_real_hardware/ -m usb_real -v --tb=short 2>&1 | grep -E "(SKIP|PASS|FAIL)"
"""

import asyncio

import pytest
from pathlib import Path

from src.backend.config.logger import RigBridgeLogger
from src.backend.config.settings import ConfigManager
from src.backend.transport import USBConnection
from src.backend.protocol.civ_protocol import CIVCommandExecutor

logger = RigBridgeLogger.get_logger(__name__)


@pytest.mark.usb_real
@pytest.mark.manual
class TestRealHardware:
    """Tests für echte IC-905 Hardware über USB."""

    @pytest.fixture
    def usb_connection(self):
        """Stelle USB-Verbindung her (mit Fehlerbehandlung)."""
        config = ConfigManager.initialize()
        usb_config = config.usb

        conn = USBConnection(config=usb_config, simulate=False)

        if not conn.connect():
            pytest.skip(
                f"Konnte nicht zu {usb_config.port} verbinden. "
                "Bitte prüfen Sie:\n"
                "  - Funkgerät ist angeschlossen\n"
                "  - Korrekter COM-Port in config.json\n"
                "  - USB-Verbindung aktiv\n"
                "  - Keine andere Software nutzt den Port"
            )

        yield conn

        # Cleanup
        if conn.is_connected:
            conn.disconnect()

    def test_usb_connection_successfully(self, usb_connection):
        """Test: USB-Verbindung ist hergestellt."""
        assert usb_connection.is_connected, "USB sollte verbunden sein"

    @pytest.mark.asyncio
    async def test_read_frequency_from_ic905(self, usb_connection, protocol_file, manufacturer_file, request):
        """Test: Lese Frequenz vom IC-905."""
        logger.info("Lese Betriebsfrequenz vom IC-905...")

        executor = CIVCommandExecutor(
            protocol_file=protocol_file,
            manufacturer_file=manufacturer_file,
            usb_connection=usb_connection
        )

        result = await executor.execute_command('read_operating_frequency')

        # Überprüfung
        assert result.success, f"Fehler beim Auslesen: {result.error}"
        assert 'frequency' in result.data, "frequency sollte in Daten sein"

        frequency_hz = result.data['frequency']
        frequency_mhz = frequency_hz / 1_000_000

        logger.info(f"✓ Frequenz: {frequency_mhz:.6f} MHz (Raw: {frequency_hz} Hz)")
        terminal_reporter = request.config.pluginmanager.get_plugin("terminalreporter")
        if terminal_reporter is not None:
            terminal_reporter.write_line(
                f"MANUAL CHECK: IC-905 Frequenz = {frequency_mhz:.6f} MHz ({frequency_hz} Hz)",
                yellow=True,
            )

        # Sinnvolle Grenzen für Funk
        assert 0 < frequency_hz < 10_000_000_000, \
            f"Frequenz außerhalb plausiblen Bereichs: {frequency_mhz:.6f} MHz"

    @pytest.mark.asyncio
    async def test_read_mode_from_ic905(self, usb_connection, protocol_file, manufacturer_file):
        """Test: Lese Betriebsmodus vom IC-905."""
        logger.info("Lese Betriebsmodus vom IC-905...")

        executor = CIVCommandExecutor(
            protocol_file=protocol_file,
            manufacturer_file=manufacturer_file,
            usb_connection=usb_connection
        )

        result = await executor.execute_command('read_operating_mode')

        assert result.success, f"Fehler beim Auslesen: {result.error}"
        assert 'mode' in result.data, "mode sollte in Daten sein"

        mode = result.data.get('mode', 'UNKNOWN')
        logger.info(f"✓ Modus: {mode}")

    @pytest.mark.asyncio
    async def test_read_s_meter_from_ic905(self, usb_connection, protocol_file, manufacturer_file):
        """Test: Lese S-Meter Level vom IC-905."""
        logger.info("Lese S-Meter vom IC-905...")

        executor = CIVCommandExecutor(
            protocol_file=protocol_file,
            manufacturer_file=manufacturer_file,
            usb_connection=usb_connection
        )

        result = await executor.execute_command('read_s_meter')

        assert result.success, f"Fehler beim Auslesen: {result.error}"
        assert 'level_high' in result.data, "level_high sollte in Daten sein"

        level = result.data['level_high']
        logger.info(f"✓ S-Meter: 0x{level:02X} ({level})")

        # S-Meter Werte sollten im Bereich 0x00-0xF1 sein
        assert 0 <= level <= 255, f"S-Meter außerhalb Bereich: 0x{level:02X}"

    @pytest.mark.asyncio
    async def test_multiple_reads_consistency(self, usb_connection, protocol_file, manufacturer_file):
        """Test: Mehrere Reads hintereinander (Konsistenz)."""
        logger.info("Lese Frequenz mehrfach zur Konsistenzprüfung...")

        executor = CIVCommandExecutor(
            protocol_file=protocol_file,
            manufacturer_file=manufacturer_file,
            usb_connection=usb_connection
        )

        frequencies = []
        for i in range(3):
            result = await executor.execute_command('read_operating_frequency')
            assert result.success, f"Read #{i+1} fehlgeschlagen"
            frequencies.append(result.data['frequency'])

        # Frequenzen sollten gleich sein (wenn Nutzer Gerät nicht verstellt)
        logger.info(f"Frequenzen: {[f/1_000_000 for f in frequencies]}")

        # Erlauben Sie kleine Schwankungen (max ±100 Hz)
        max_diff = max(frequencies) - min(frequencies)
        assert max_diff <= 100, \
            f"Frequenzschwankung zu groß: {max_diff} Hz"

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_echo_detection_filtering(self, usb_connection, protocol_file, manufacturer_file):
        """Test: Echo-Detection und -Filterung funktioniert."""
        logger.info("Teste Echo-Detection...")

        executor = CIVCommandExecutor(
            protocol_file=protocol_file,
            manufacturer_file=manufacturer_file,
            usb_connection=usb_connection
        )

        # Führe mehrere Befehle aus - sollten kein Echo-Fehler haben
        commands = ['read_s_meter', 'read_operating_frequency', 'read_operating_mode']

        for cmd_name in commands:
            result = await executor.execute_command(cmd_name)
            # Sollten erfolgreich sein (keine Echo-Fehler)
            assert result.success or result.error is None, \
                f"Echo-Filter Fehler bei {cmd_name}: {result.error}"

    @pytest.mark.skip(reason="SET-Befehle erfordern manuelles Überprüfen des Geräts")
    @pytest.mark.asyncio
    async def test_set_frequency_on_ic905(self, usb_connection, protocol_file, manufacturer_file):
        """Test: Setze Frequenz auf dem IC-905.

        ⚠️  WARNUNG: Dieser Test ändert die Frequenz des Geräts!

        Nur aktivieren wenn:
        - Sie das Gerät vorher manuell überprüft haben
        - Sie wissen, welche Frequenz gesetzt wird
        - Sie bereit sind, es danach zurückzusetzen
        """
        logger.info("Setze Frequenz auf dem IC-905...")

        executor = CIVCommandExecutor(
            protocol_file=protocol_file,
            manufacturer_file=manufacturer_file,
            usb_connection=usb_connection
        )

        # Setze auf 145.5 MHz (IARU Region 2 2m Band)
        result = await executor.execute_command(
            'set_operating_frequency',
            data={'frequency': 145_500_000}
        )

        assert result.success, f"Fehler beim Setzen: {result.error}"
        logger.info("✓ Frequenz gesetzt - bitte manuell überprüfen!")


# Standalone-Hilfsfunktionen für manuelles Testen


def test_print_hardware_info():
    """Hilfsfunktion: Drucke Hardware-Informationen."""
    config = ConfigManager.initialize()
    print("\n")
    print("=" * 70)
    print("Hardware-Konfiguration")
    print("=" * 70)
    print(f"USB-Port: {config.usb.port}")
    print(f"Baudrate: {config.usb.baud_rate}")
    print(f"Device Name: {config.device.name}")
    print("=" * 70)


@pytest.mark.manual
def test_smoke_check(protocol_file):
    """Schnellcheck: Ist die Umgebung bereit?"""
    assert protocol_file.exists(), f"Protokolldatei nicht gefunden: {protocol_file}"
    config = ConfigManager.initialize()
    assert config is not None, "Config konnte nicht geladen werden"
    logger.info(f"✓ Umgebung OK - Port: {config.usb.port}")
