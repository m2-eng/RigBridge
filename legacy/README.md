# Legacy Test Dateien

Diese Dateien sind **deprecated** und werden nicht mehr wartbar.

Sie werden hier archiviert für Rückwärts-Kompatibilität, sollten aber nicht verwendet werden.

## Neue Test-Infrastruktur

Siehe: [tests/README.md](../tests/README.md)

Verwende:
- `python run_tests.py` - zentral und plattformunabhängig
- `./run_tests.ps1` - PowerShell (Windows)
- `./run_tests.sh` - Bash (Linux/Mac)

## Dateien in diesem Verzeichnis

- `test_integration.py` - Alte Integration-Tests (archiviert)
- `test_real_hardware.py` - Alte Hardware-Tests (archiviert)
- `test_real_hardware_debug.py` - Debug-Wrapper (archiviert)

Alle Tests wurden in `tests/backend/` refaktoriert.
