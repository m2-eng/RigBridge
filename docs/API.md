# RigBridge API-Dokumentation

Diese Dokumentation beschreibt die REST-API und die Anwendungsstruktur von RigBridge.

## ⚡ Wichtig: Async-Ressourcenverwaltung

**Alle API-Anfragen durchlaufen den TransportManager** - eine zentrale Komponente, die alle USB-Kommunikation verwaltet.

### Warum TransportManager?

Der TransportManager bietet folgende Vorteile:

- **Sequenzielle Befehlsausführung**: Es wird immer nur ein Befehl auf einmal über USB gesendet, nicht mehrere gleichzeitig
- **Race-Condition-freie Kommunikation**: Verhindert Konflikte und Datenverschmutzung bei gleichzeitigen Anfragen
- **Garantierte Befehlsreihenfolge**: Befehle werden in der Reihenfolge ausgeführt, in der sie eingehen
- **Asynchrone Verarbeitung**: Requests werden gequeutet und asynchron verarbeitet

### HTTP 503 - USB ist beschäftigt

Falls der USB-Port momentan einen Befehl verarbeitet, kann die API mit einem **HTTP 503 Service Unavailable** antworten. Dies ist kein Fehler, sondern normales Verhalten:

- Die API ist möglicherweise momentan in der Verarbeitung eines vorherigen Befehls
- Der Client sollte den Request nach kurzer Zeit wiederholen
- Dies ist ein Sicherheitsmechanismus, um die USB-Stabilität zu wahren

Weitere technische Details zur Architektur findest du in [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 📋 Übersicht

RigBridge bietet folgende Haupt-APIs:

- **Allgemeine Befehls-API**: Flexible HTTP-Schnittstelle für beliebige CI-V-Befehle
- **Frequenz-Endpunkte**: Dedicated APIs zum Lesen/Setzen der Betriebsfrequenz
- **Modus-Endpunkte**: Dedicated APIs zum Lesen/Setzen des Betriebsmodus
- **Meter-Endpunkte**: API zum Auslesen des S-Meters
- **Info-Endpunkte**: Listings und Status-Informationen

## 🚀 Schnellstart

### Installation

```bash
# Python-Abhängigkeiten installieren
pip install -r requirements.txt

# Konfiguration anpassen (optional)
# cp config.json.example config.json
# Bearbeite: USB-Port, API-Port etc.
```

### Anwendung starten

```bash
# Windows (nativ)
python run_api.py

# Linux (nativ oder Docker)
python run_api.py
```

### API testen

Öffne im Browser: **http://localhost:8080/api/docs**

Dies öffnet die interaktive Swagger-UI-Dokumentation.

---

## 📡 API-Endpunkte

### Allgemeine Befehle

#### GET `/api/command/{command_name}`

Führt einen Read-Only-Befehl aus.

**Beispiel:**
```bash
curl http://localhost:8080/api/command/read_s_meter
```

**Response:**
```json
{
  "success": true,
  "command": "read_s_meter",
  "data": null
}
```

---

#### PUT `/api/command/{command_name}`

Führt einen Befehl mit Daten aus (READ/WRITE).

**Beispiel:**
```bash
curl -X PUT http://localhost:8080/api/command/set_operating_frequency \
  -H "Content-Type: application/json" \
  -d '{
    "command": "set_operating_frequency",
    "data": {"frequency": 145500000}
  }'
```

**Response:**
```json
{
  "success": true,
  "command": "set_operating_frequency",
  "data": {"frequency": 145500000}
}
```

---

### Betriebsfrequenz

#### GET `/api/rig/frequency`

Liest die aktuelle Betriebsfrequenz.

**Response:**
```json
{
  "frequency_hz": 145500000,
  "vfo": "A"
}
```

---

#### PUT `/api/rig/frequency`

Setzt eine neue Betriebsfrequenz.

**Request:**
```json
{
  "frequency_hz": 145500000
}
```

**Response:**
```json
{
  "success": true,
  "command": "set_operating_frequency",
  "data": {"frequency": 145500000}
}
```

---

### Betriebsmodus

#### GET `/api/rig/mode`

Liest den aktuellen Betriebsmodus.

**Response:**
```json
{
  "mode": "CW",
  "filter": "WIDE"
}
```

---

#### PUT `/api/rig/mode`

Setzt einen neuen Betriebsmodus.

**Request:**
```json
{
  "mode": "SSB"
}
```

**Response:**
```json
{
  "success": true,
  "command": "set_operating_mode",
  "data": {"mode": "SSB"}
}
```

---

### S-Meter

#### GET `/api/rig/s-meter`

Liest den aktuellen S-Meter-Wert.

**Response:**
```json
{
  "level_db": 47.5,
  "level_raw": 120
}
```

**Details:**
- `level_db`: Interpolierter Wert in Dezibel (0-114 dB)
- `level_raw`: Roher Sensor-Wert (0x00-0xFF)

**Interpolation:**
- 0x00 = 0 dB (S0)
- 0x78 = 54 dB (ungefähr S8)
- 0xF1 = 114 dB (S9+60)

---

### Status und Info

#### GET `/api/status`

Gibt System- und Geräte-Status.

**Response:**
```json
{
  "usb_connected": true,
  "device_name": "Icom IC-905",
  "api_version": "0.1.0",
  "features": ["set_frequency", "set_mode", "read_s_meter"]
}
```

---

#### GET `/api/commands`

Gibt eine Liste aller verfügbaren Befehle.

**Response:**
```json
{
  "commands": [
    "read_s_meter",
    "read_operating_frequency",
    "read_operating_mode",
    "set_operating_frequency",
    "set_operating_mode",
    ...
  ]
}
```

---

#### GET `/health`

Docker/Monitoring Health-Check.

**Response:**
```json
{
  "status": "ok",
  "device": "Icom IC-905",
  "api_version": "0.1.0"
}
```

---

## ⚙️ Konfiguration

### Datei: `config.json`

```json
{
  "usb": {
    "port": "/dev/ttyUSB0",        // Linux; Windows: "COM3"
    "baud_rate": 19200,
    "timeout": 1.0
  },
  "api": {
    "host": "127.0.0.1",            // Nur localhost per default
    "port": 8080,
    "enable_https": false
  },
  "device": {
    "name": "Icom IC-905",
    "manufacturer": "icom",
    "protocol_file": "ic905"
  }
}
```

### Konfiguration

Die Konfiguration erfolgt ausschließlich über `config.json`.
Änderungen können direkt in der Datei oder über `PUT /api/config` erfolgen.

---

## 📝 Logging

Das System verwendet strukturiertes Logging mit einheitlichem Format:

```
[2026-03-03 14:23:45] [INFO    ] [src.backend.api.main] FastAPI application created and configured
[2026-03-03 14:23:46] [DEBUG   ] [src.backend.api.routes] Frequency read successfully
[2026-03-03 14:23:47] [WARNING ] [src.backend.civ.executor] Unknown command: invalid_cmd
```

**Format:** `[TIMESTAMP] [LEVEL] [MODULE] MESSAGE`

**Log-Level konfigurieren:**

Setze `api.log_level` in `config.json` auf `DEBUG`, `INFO`, `WARNING` oder `ERROR`.

---

## 🔐 Sicherheit

### API-Port Binding

Per default bindet die API nur an `127.0.0.1` (localhost):
```json
{
  "api": {
    "host": "127.0.0.1"  // Nur lokal
  }
}
```

Für Netzwerk-Zugriff:
- Setze `host` auf `0.0.0.0` in `config.json`
- Aktiviere HTTPS mit `enable_https: true`
- Stelle TLS-Zertifikat bereit

### Secrets

Secrets (z.B. API-Keys) werden **nicht** in `config.json` gespeichert.
Stattdessen wird in `config.json` nur eine Secret-Referenz (`api_key_secret_ref`) hinterlegt,
die zur Laufzeit über den konfigurierten Secret-Provider (z.B. Vault) aufgelöst wird.

```json
{
  "wavelog": {
    "api_key_secret_ref": "rigbridge/wavelog#api_key"
  }
}
```

---

## 🧪 Entwicklung

### Tests ausführen

```bash
# Alle Tests
pytest tests/

# Nur Backend-Tests
pytest tests/backend/

# Mit Coverage
pytest --cov=src tests/
```

### Code-Qualität

```bash
# Linting
ruff check src/

# Formatierung
black src/

# Type-Checking
mypy src/
```

---

## 📚 Modulstruktur

```
src/backend/
├── config/          # Konfiguration & Logging
│   ├── logger.py    # Zentralisiertes Logger-System
│   └── settings.py  # Config-Management
├── api/             # FastAPI & REST-Endpoints
│   ├── main.py      # App-Factory
│   └── routes.py    # Endpoint-Definitionen
├── civ/             # CI-V Befehlshandling
│   └── executor.py  # Protocol-Parser & Command-Executor
├── usb/             # USB/Serial-Kommunikation (In Progress)
└── cat/             # Wavelog CAT-Integration (In Progress)
```

---

## 🔄 Workflow-Beispiel

```python
from src.backend.config import ConfigManager, RigBridgeLogger
from src.backend.api import create_app

# App starten
config = ConfigManager.initialize()
app = create_app()

# Oder mit uvicorn
# uvicorn src.backend.api:create_app --reload
```

---

## 🐛 Fehler­behebung

### Fehler: "Unknown command: read_frequency_offset"

**Ursache:** Befehl ist in der YAML-Datei auskommentiert oder nicht definiert.

**Lösung:** Checke `protocols/manufacturers/icom/ic905.yaml` und aktiviere den Befehl.

---

### Fehler: "USB Port not found"

**Ursache:** Geräte-Port ist nicht den durch `config.json` angegebene Port angeschlossen.

**Lösung:**
```bash
# Linux: Verfügbare Ports auflisten
ls -la /dev/tty*

# Windows: Geräte-Manager öffnen und Port überprüfen
```

---

## 📖 Weitere Dokumentation

- [Funktionale Anforderungen](.copilot/requirements.md)
- [Design-Richtlinien](.copilot/design-rules.md)
- [Code-Richtlinien](.copilot/coding-rules.md)
- [CI-V Protokoll-Syntax](protocols/yaml_protocol_syntax.md)

---

**Version:** 0.1.0  
**Zuletzt aktualisiert:** 3. März 2026
