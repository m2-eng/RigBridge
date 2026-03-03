# RigBridge Test Suite

Gut organisierte, hierarchisch aufgebaute Test-Suite für RigBridge.

## 📋 Test-Hierarchie

Tests sind in 4 Stufen organisiert, die aufeinander aufbauen:

### Stufe 1: Protokoll-Parser Tests
**Verzeichnis:** `tests/backend/test_1_protocol/`  
**Zweck:** YAML-Protokoll laden und Structure validieren  
**Abhängigkeiten:** Keine  
**Ausführung:**
```bash
pytest tests/backend/test_1_protocol/ -m protocol
# oder
python run_tests.py -l protocol
```

✅ Prüft:
- YAML-Datei kann geladen werden
- Befehle sind korrekt definiert
- Frame-Konfiguration (Preamble, Terminator, Adressen) ist richtig

---

### Stufe 2: Befehlsaufbau Tests
**Verzeichnis:** `tests/backend/test_2_commands/`  
**Zweck:** CI-V Frame-Aufbau (Request-Format)  
**Abhängigkeiten:** Stufe 1 ✓  
**Ausführung:**
```bash
pytest tests/backend/test_2_commands/ -m commands
# oder
python run_tests.py -l commands
```

✅ Prüft:
- Frame wird korrekt gebaut
- Adressen in TX-Richtung richtig geordnet ([Radio, Controller])
- Preamble [FE FE] und Terminator [FD] vorhanden
- CMD-Bytes sind gesetzt

---

### Stufe 3: USB-Simulation Tests
**Verzeichnis:** `tests/backend/test_3_usb_simulation/`  
**Zweck:** Befehlsausführung OHNE echte Hardware  
**Abhängigkeiten:** Stufe 1 + 2 ✓  
**Ausführung:**
```bash
pytest tests/backend/test_3_usb_simulation/ -m usb_sim
# oder
python run_tests.py -l simulation
```

✅ Prüft:
- Befehle können ausgeführt werden (Fallback-Modus)
- CommandResult hat richtige Struktur
- Mehrere Befehle nacheinander funktionieren
- Keine echte Hardware nötig

---

### Stufe 4: USB Real-Hardware Tests
**Verzeichnis:** `tests/backend/test_4_usb_real_hardware/`  
**Zweck:** Echte Kommunikation mit IC-905  
**Abhängigkeiten:** Stufe 1, 2, 3 ✓ + **IC-905 angeschlossen**  
**Ausführung:**
```bash
# Nur mit Hardware!
pytest tests/backend/test_4_usb_real_hardware/ -m usb_real
# oder
python run_tests.py -l real
```

⚠️ **ACHTUNG:** Diese Tests erfordern:
- Icom IC-905 Transceiver angeschlossen
- USB-Verbindung aktiv
- Korrekter COM-Port in `config.json`
- CI-V auf dem Funkgerät aktiviert

---

## 🚀 Schnellstart

### Alle Tests ausführen (inkl. Real Hardware)
```bash
python run_tests.py
```

### PR-Tests ausführen (ohne Real Hardware)
```bash
python run_tests.py -l pr
```

### Hierarchische Test-Ausführung (mit Zwischenergebnissen)
```bash
python run_tests.py -l full-hierarchy
```

### Nur eine Stufe testen
```bash
# Nur Protokoll-Parser
python run_tests.py -l protocol

# Nur Befehle + Protokoll
python run_tests.py -l commands

# Nur Simulation
python run_tests.py -l simulation
```

### Real-Hardware Tests ausführen (IC-905)
```bash
# Nur mit angeschlossener Hardware
python run_tests.py -l real

# Optional direkt per pytest
pytest tests/backend/test_4_usb_real_hardware/ -m "usb_real and manual" -v
```

### Mit Verbose Output
```bash
python run_tests.py -l protocol -v
python run_tests.py -l pr -v
```

### Mit Coverage Report
```bash
python run_tests.py -l pr -c
# HTML Report dann in: htmlcov/index.html
```

---

## 📂 Dateistruktur

```
tests/
├── conftest.py                          # Shared Fixtures und Logging Setup
├── backend/
│   ├── __init__.py
│   ├── test_integration.py              # Komponenten-Integration
│   │
│   ├── test_1_protocol/
│   │   ├── __init__.py
│   │   └── test_yaml_parser.py         # YAML laden + Structure
│   │
│   ├── test_2_commands/
│   │   ├── __init__.py
│   │   └── test_command_builder.py     # Frame-Aufbau
│   │
│   ├── test_3_usb_simulation/
│   │   ├── __init__.py
│   │   └── test_usb_mock.py            # Ohne Hardware (Fallback)
│   │
│   └── test_4_usb_real_hardware/
│       ├── __init__.py
│       └── test_usb_real.py            # Mit IC-905 (MANUAL)
│
└── frontend/                            # (später)
```

---

## ✅ Was wird getestet?

| Stufe | Test | Prüfpunkte |
|-------|------|-----------|
| 1 | YAML-Parser | Datei geladen, Struktur OK, Befehle vorhanden |
| 2 | Frame-Aufbau | Preamble, Adressen (TX), CMD, Terminator |
| 3 | Simulation | Kommando-Exec, Result-Struktur, Mehrfach-Befehle |
| 4 | Real HW | USB-Verbindung, Frequenz-Read, Modus, S-Meter |

---

## 🔄 CI/CD Integration

### GitHub Actions Beispiel
```yaml
name: Tests
on: [push, pull_request]
jobs:
  tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - run: pip install -r requirements.txt
      - run: python run_tests.py -l pr
```

---

## 📝 Test-Marker

Alle Tests sind mit pytest-Markern versehen:

```bash
# Nur Protokoll-Tests
pytest tests/ -m protocol

# Nur Befehls-Tests
pytest tests/ -m commands

# Nur USB-Simulation
pytest tests/ -m usb_sim

# Nur echte Hardware
pytest tests/ -m usb_real

# Alles außer Real Hardware
pytest tests/ -m "not usb_real"

# Integration Tests
pytest tests/ -m integration

# Manuelle Tests (erfordern Intervention)
pytest tests/ -m manual
```

---

## 🛠️ Pytest Konfiguration

Siehe `pytest.ini` für vollständige Konfiguration:
- Testpfade: `tests/`
- Logging: `tests/pytest.log`
- Markers: protocol, commands, usb_sim, usb_real, manual, slow, integration

---

## 📌 Wichtige Hinweise

### Alte Test-Dateien
❌ Diese Dateien sind **nicht mehr in Verwendung:**
- `test_integration.py` (root) → `tests/backend/test_integration.py`
- `test_real_hardware.py` (root) → `tests/backend/test_4_usb_real_hardware/test_usb_real.py`
- `test_real_hardware_debug.py` (root) → ENTFERNT (redundant)
- `tests/backend/test_usb_integration.py` → deprecated, konsolidiert in Stufe 3 + 4

Diese sollten gelöscht werden, um Doppelungen zu vermeiden.

### Real Hardware Tests
⚠️  Tests in `test_4_usb_real_hardware` sind **optional** und **manuell**:
- Werden in der Standard-CI-Pipeline **übersprungen**
- Können lokal mit `python run_tests.py -l real` ausgeführt werden
- Erfordern `@pytest.mark.usb_real` und `@pytest.mark.manual`

### Performance
- Stufen 1-3 dauern ~5-10 Sekunden
- Stufe 4 kann 30+ Sekunden dauern (Hardware-Kommunikation)
- Use `-k` for specific tests: `pytest tests/ -k "frequency"`

---

## 🐛 Debugging

### Einzelnen Test ausführen
```bash
pytest tests/backend/test_1_protocol/test_yaml_parser.py::TestProtocolParser::test_parser_initialization -vv
```

### Mit Debug-Output
```bash
pytest tests/backend/test_2_commands/test_command_builder.py -vv --tb=long --capture=no
```

### Nur fehlgeschlagene Tests
```bash
pytest tests/ --lf -v
```

### Mit x-Flag (stoppt bei erstem Fehler)
```bash
pytest tests/backend/test_1_protocol/ -x -v
```

---

## 📚 Weitere Ressourcen

- pytest docs: https://docs.pytest.org/
- pytest markers: https://docs.pytest.org/en/how-to/mark.html
- pytest fixtures: https://docs.pytest.org/en/how-to/fixture.html
