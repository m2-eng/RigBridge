# RigBridge Backend - Entwicklungshandbuch

Dieses Handbuch beschreibt die Backend-Architektur und wie man mit der Entwicklung beginnt.

## 📋 Übersicht

RigBridge Backend ist eine **FastAPI**-basierte REST API zum Steuern von Icom-Funkgeräten über CI-V-Protokoll.

### Kern-Komponenten

```
src/backend/
├── config/          # Konfigurationsverwaltung & Logging
│   ├── logger.py    # Zentralisiertes Logging
│   └── settings.py  # Config-Management (JSON + env-vars)
├── civ/             # CI-V Protokoll-Parser & Executor
│   └── executor.py  # Befehlsausführung
├── usb/             # USB/Serial-Kommunikation (TODO)
├── cat/             # CAT/Wavelog-Integration (TODO)
└── api/             # REST API Endpoints
    ├── main.py      # FastAPI App-Factory
    └── routes.py    # Alle API-Endpunkte
```

## 🚀 Schnelleinstieg

### 1. Abhängigkeiten installieren
```bash
pip install -r requirements.txt
```

### 2. Konfiguration vorbereiten
```bash
# config.json existiert bereits mit Defaults
# Optional: Umgebungsvariablen setzen
export RIGBRIDGE_API_HOST=0.0.0.0
export RIGBRIDGE_API_PORT=8080
export RIGBRIDGE_USB_PORT=/dev/ttyUSB0
```

### 3. Integration-Tests ausführen
```bash
python test_integration.py
```

### 4. API starten
```bash
python run_api.py
```

Server läuft dann auf: http://127.0.0.1:8080

### 5. API via Browser testen
- **Swagger UI (interaktiv)**: http://127.0.0.1:8080/api/docs
- **ReDoc (Dokumentation)**: http://127.0.0.1:8080/api/redoc

## 📦 Architektur-Muster

### Logger (Zentralisiert)
```python
from src.backend.config import RigBridgeLogger

logger = RigBridgeLogger.get_logger(__name__)
logger.info("Nachricht mit standardisiertem Format")
# Output: [2024-01-15 10:30:45,123] [INFO] [module.name] Nachricht mit standardisiertem Format
```

### Konfiguration (12-Factor)
```python
from src.backend.config import ConfigManager

ConfigManager.initialize(Path('config.json'))
config = ConfigManager.get()

print(config.device.name)        # "IC-905"
print(config.usb.port)           # "/dev/ttyUSB0"
print(config.api.host)           # "127.0.0.1"
```

**Precedence:** Env-Vars > config.json > Defaults

Umgebungsvariablen: `RIGBRIDGE_*` (z.B. `RIGBRIDGE_USB_PORT`)

### Protokoll-Parser (YAML → Python)
```python
from src.backend.civ import CIVCommandExecutor

executor = CIVCommandExecutor(Path('protocols/manufacturers/icom/ic905.yaml'))

# Befehl nach Name suchen
cmd = executor.parser.get_command('read_s_meter')
print(cmd.cmd, cmd.subcmd)  # (0x15, 0x02)

# Befehl nach Code suchen
cmd = executor.parser.get_command_by_code(0x14, 0x0A)
```

### Befehlsausführung (Stub → Real)
```python
# Aktuell: Stub mit simulierten Daten

result = executor.execute_command('read_s_meter')
print(result.success)       # True
print(result.data)          # {"level_db": 45.5, "level_raw": 0x78}
print(result.raw_response)  # None (jetzt noch) → bytes später

# Mit Parametern
result = executor.execute_command(
    'set_operating_frequency',
    data={'frequency': 145500000}
)
```

### FastAPI Routes (Typsicher)
```python
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class FrequencyRequest(BaseModel):
    frequency_hz: int

class FrequencyResponse(BaseModel):
    frequency_hz: int
    vfo: str

@router.put("/rig/frequency")
async def set_frequency(req: FrequencyRequest) -> FrequencyResponse:
    # Pydantic validiert Input automatisch
    # OpenAPI/Swagger generiert sich selbst
    ...
```

## 🔄 Workflow für neue Features

### Neue API hinzufügen (Beispiel: Uhrzeit auslesen)

1. **Befehl in YAML definieren** (`protocols/manufacturers/icom/ic905.yaml`)
   ```yaml
   read_clock:
     cmd: 0x1A
     subcmd: 0x05
     description: "Read clock"
     type: "clock"
     # ... response_structure etc
   ```

2. **Executor aktualisieren** (`src/backend/civ/executor.py`)
   ```python
   # build_request() für read_clock mit realer Codierung
   # parse_response() für Dekodieren des Uhrzeit-Formats
   ```

3. **USB-Integration** (`src/backend/usb/connection.py`)
   ```python
   # Echte serial.Serial()-Kommunikation
   ```

4. **API-Endpoint hinzufügen** (`src/backend/api/routes.py`)
   ```python
   @router.get("/api/rig/clock", response_model=ClockResponse)
   async def get_clock():
       result = executor.execute_command('read_clock')
       return ClockResponse(...)
   ```

5. **Tests** (`tests/backend/test_routes.py`)
   ```python
   def test_get_clock(client):
       response = client.get("/api/rig/clock")
       assert response.status_code == 200
       assert "time" in response.json()
   ```

## 🧪 Testing

### Integration-Tests (alle Komponenten)
```bash
python test_integration.py
```

Das testet:
- ✅ Logger (Format)
- ✅ Config-Management (JSON + env-vars)
- ✅ YAML-Parser (Protokoll laden)
- ✅ Befehlsausführung (simulator)
- ✅ Frame-Building (0xFEFE... format)
- ✅ S-Meter Interpolation (linear)
- ✅ FastAPI App-Erstellung

### Unit-Tests (einzelne Module)
```bash
# Noch zu schreiben (TODO in IMPLEMENTATION_NOTES.md)
pytest tests/backend/
```

### Manuelles Testen via Swagger UI
1. Starte API: `python run_api.py`
2. Gehe zu: http://127.0.0.1:8080/api/docs
3. Klicke "Try it out" bei Endpunkte
4. Gib Parameter ein & klicke "Execute"

### cURL-Beispiele
```bash
# Status
curl http://127.0.0.1:8080/api/status

# Frequenz lesen
curl http://127.0.0.1:8080/api/rig/frequency

# Frequenz setzen
curl -X PUT http://127.0.0.1:8080/api/rig/frequency \
  -H "Content-Type: application/json" \
  -d '{"frequency_hz": 145500000}'

# S-Meter lesen
curl http://127.0.0.1:8080/api/rig/s-meter

# Verfügbare Befehle
curl http://127.0.0.1:8080/api/commands | jq
```

## 🔧 Debugging

### Logging aktivieren
```python
from src.backend.config import RigBridgeLogger

RigBridgeLogger.configure(
    level='DEBUG',  # oder: 'INFO', 'WARNING', 'ERROR'
    log_file='rigbridge.log'
)

logger = RigBridgeLogger.get_logger(__name__)
logger.debug("Detaillierte Debug-Info")
```

### Config debuggen
```python
from src.backend.config import ConfigManager
import json

ConfigManager.initialize(Path('config.json'))
config = ConfigManager.get()

# Als JSON anzeigen
print(json.dumps(config.to_dict(), indent=2))
```

### YAML-Parser debuggen
```python
from src.backend.civ import CIVCommandExecutor

executor = CIVCommandExecutor(Path('protocols/manufacturers/icom/ic905.yaml'))

# Alle Tests auflisten
for name, cmd in executor.parser.commands.items():
    print(f"{name}: 0x{cmd.cmd:02X}/{cmd.subcmd:02X}")
```

## 🏗️ Nächste Entwicklungs-Schritte

### Phase 1: USB/Serial (🔴 BLOCKIERT)
- [ ] `src/backend/usb/connection.py` - pyserial abstraction
- [ ] Connection state management
- [ ] Reconnection logic

### Phase 2: CI-V Encode/Decode (🔴 BLOCKIERT)
- [ ] `build_request()` mit realer BCD-Codierung
- [ ] Frequenz-Format (Hz → CI-V)
- [ ] Mode/Filter-Codierung
- [ ] `parse_response()` decoder

### Phase 3: Frontend (🟢 OPTIONAL)
- [ ] HTML/CSS UI
- [ ] Real-time status polling
- [ ] Settings dialog

### Phase 4: Integration (🟡 NICE-TO-HAVE)
- [ ] Wavelog CAT-Integration
- [ ] HTTPS setup
- [ ] Secret encryption

### Phase 5: Testing & Deployment (🟡 NICE-TO-HAVE)
- [ ] Unit-Tests (pytest)
- [ ] Integration-Tests
- [ ] Docker build optimization

## 📚 Weitere Ressourcen

- **API-Docs:** [docs/API.md](../docs/API.md)
- **Implementation Notes:** [.copilot/IMPLEMENTATION_NOTES.md](../.copilot/IMPLEMENTATION_NOTES.md)
- **YAML-Protokoll-Format:** [protocols/yaml_protocol_syntax.md](../protocols/yaml_protocol_syntax.md)
- **FastAPI-Docs:** https://fastapi.tiangolo.com
- **Pydantic-Docs:** https://docs.pydantic.dev

## 💡 Best Practices

### Code-Style
- PEP 8 (4 spaces indentation)
- Type hints in allen Funktionen
- Docstrings (Google style)

### Logging
```python
# ✅ GUT
logger = RigBridgeLogger.get_logger(__name__)
logger.info("Operation erfolgreich")

# ❌ FALSCH
print("Operation erfolgreich")
logging.debug("msg")  # Falsches Logging-System
```

### Config-Access
```python
# ✅ GUT
config = ConfigManager.get()
port = config.usb.port

# ❌ FALSCH
import json
with open('config.json') as f:
    port = json.load(f)['usb']['port']
```

### Test-Daten
```python
# ✅ GUT: Verwende Mock/Fixtures
@pytest.fixture
def mock_executor(monkeypatch):
    monkeypatch.setattr(CIVCommandExecutor, 'execute_command', mock_fn)

# ❌ FALSCH: Echte Hardware-Dependencies
def test_api(live_radio_connection):
    ...
```

## 📞 Support & Zusammenarbeit

Bei Fragen zu:
- **Architektur:** Siehe .copilot/IMPLEMENTATION_NOTES.md
- **API-Endpoints:** Siehe docs/API.md
- **YAML-Format:** Siehe protocols/yaml_protocol_syntax.md
- **Code-Konventionen:** Siehe diese Datei (Best Practices)

---

**Letztes Update:** 2024-01-15  
**Status:** Backend-Infrastruktur ✅, USB/CIV-Implementierung ⏳
