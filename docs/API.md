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
- **Audio-API**: Bidirektionales Audio-Streaming via REST + WebSocket (IC-905 USB-Audio)

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
    "enable_https": true,           // HTTPS standardmäßig aktiv
    "cert_file": null,              // null = automatisches selbst-signiertes Zertifikat
    "key_file": null
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
- HTTPS ist standardmäßig aktiv (`enable_https: true`)

### HTTPS

HTTPS ist **standardmäßig aktiv**. Beim Start wird automatisch ein selbst-signiertes Zertifikat erzeugt (via `cryptography`-Paket), falls kein eigenes angegeben ist.

**Standard (selbst-signiertes Zertifikat):**
```json
{
  "api": {
    "enable_https": true,
    "cert_file": null,
    "key_file": null
  }
}
```

**Eigenes Zertifikat (empfohlen für Netzwerk-Betrieb):**
```json
{
  "api": {
    "enable_https": true,
    "cert_file": "/pfad/zu/rigbridge.crt",
    "key_file":  "/pfad/zu/rigbridge.key"
  }
}
```

> **Empfehlung für lokales Netzwerk:** [`mkcert`](https://github.com/FiloSottile/mkcert) erzeugt lokal vertrauenswürdige Zertifikate ohne Browser-Warnungen.  
> Ideal in Kombination mit einem lokalen DNS-Resolver (z.B. Pi-hole):
> ```bash
> mkcert -install
> mkcert rigbridge.local
> ```
> Die erzeugten Dateien `rigbridge.local.pem` und `rigbridge.local-key.pem` dann als `cert_file`/`key_file` eintragen.

### Secrets

Secrets (z.B. API-Keys) werden **nicht** in `config.json` gespeichert.
Stattdessen wird in `config.json` eine API-Key-Angabe (`api_key_or_secret_ref`) hinterlegt,
die zur Laufzeit über den konfigurierten Secret-Provider (z.B. Vault) aufgelöst wird.

```json
{
  "wavelog": {
    "api_key_or_secret_ref": "rigbridge/wavelog#api_key"
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
**Zuletzt aktualisiert:** 21. Juni 2026

---

## 🎙 Audio-Streaming API (IC-905 USB-Audio)

Das IC-905 stellt über USB zwei ALSA-Geräte bereit:

| Richtung | ALSA-Gerät | Bedeutung |
|---|---|---|
| **Capture** (`pcmC0D0c`) | Host-Mikrofon | **RX** – Empfangsaudio des IC-905 |
| **Playback** (`pcmC0D0p`) | Host-Lautsprecher | **TX** – Eingang IC-905-Mikrofon |

### REST-Endpunkte

#### `GET /api/audio/devices`

Listet alle via PortAudio/ALSA sichtbaren Audio-Geräte.

**Response:**
```json
{
  "devices": [
    {
      "index": 0,
      "name": "USB Audio CODEC: USB Audio (hw:0,0)",
      "max_input_channels": 1,
      "max_output_channels": 1,
      "default_samplerate": 48000.0,
      "supports_capture": true,
      "supports_playback": true
    }
  ],
  "sounddevice_available": true
}
```

#### `GET /api/audio/config`

Liefert die gespeicherte Audio-Konfiguration.

**Response:**
```json
{
  "enabled": true,
  "capture_device": "0",
  "playback_device": "0",
  "sample_rate": 48000,
  "format": "S16_LE",
  "codec": "pcm"
}
```

#### `PUT /api/config` (Audio-Abschnitt)

Speichert die Audio-Konfiguration persistent in `config.json`.

**Request:**
```json
{
  "audio": {
    "enabled": true,
    "capture_device": "0",
    "playback_device": "0",
    "sample_rate": 48000,
    "format": "S16_LE",
    "codec": "pcm"
  }
}
```

| Feld | Typ | Werte | Beschreibung |
|---|---|---|---|
| `enabled` | bool | `true`/`false` | Audio-Streaming beim Start aktivieren |
| `capture_device` | string | Gerät-Index (z.B. `"0"`) oder Name | RX-Gerät (IC-905 → Host) |
| `playback_device` | string | Gerät-Index oder Name | TX-Gerät (Host → IC-905) |
| `sample_rate` | int | `8000`, `16000`, `48000` | Abtastrate in Hz |
| `format` | string | `S16_LE`, `S32_LE`, `F32_LE` | PCM-Format |
| `codec` | string | `pcm` | Codec (Opus: geplant) |

#### `GET /api/audio/status`

Gibt den aktuellen Betriebszustand der Streams zurück.

**Response:**
```json
{
  "enabled": true,
  "sounddevice_available": true,
  "rx_active": true,
  "tx_active": false,
  "rx_clients_connected": 2,
  "capture_device": "0",
  "playback_device": "0",
  "sample_rate": 48000,
  "format": "S16_LE",
  "codec": "pcm",
  "last_error": null
}
```

#### `POST /api/audio/start`

Startet RX-Capture-Stream gemäß gespeicherter Konfiguration.

#### `POST /api/audio/stop`

Stoppt alle laufenden Audio-Streams.

---

### WebSocket-Endpunkte

#### `WS /api/audio/rx` — IC-905 RX → Client

Sendet kontinuierlich PCM-Audio-Chunks als Binärdaten an den Client.

- **Auto-Start beim Connect**: Der Server-seitige RX-Stream startet automatisch beim ersten Client-Connect — kein vorheriges `POST /api/audio/start` nötig
- Nach `accept()` sendet der Server zuerst eine **JSON-Status-Nachricht** (Text-Frame), danach folgen kontinuierliche Binär-Frames:
  ```json
  {"status": "connected", "rx_active": true, "sample_rate": 48000, "format": "S16_LE"}
  ```
- Mehrere Clients gleichzeitig werden unterstützt (**Broadcast**)
- Verbindungsabbruch eines Clients stoppt den Stream nicht für andere
- Client kann `"ping"` (Text) senden, Server antwortet mit `"pong"`
- Bei Fehler (z.B. `sounddevice` nicht verfügbar): JSON `{"error": "..."}` + WebSocket-Close mit Code `1011`

**Beispiel (Python):**
```python
import asyncio, websockets

async def receive_rx():
    uri = "ws://localhost:8081/api/audio/rx"
    async with websockets.connect(uri) as ws:
        while True:
            pcm_chunk = await ws.recv()   # bytes: S16_LE PCM
            # → in ffmpeg, sounddevice.play() etc. weiterverarbeiten

asyncio.run(receive_rx())
```

**Beispiel – YouTube-Stream einspeisen:**
```python
import asyncio, subprocess, websockets

async def stream_youtube_to_rig(youtube_url: str):
    # ffmpeg: YouTube-Audio → PCM S16_LE 48 kHz Mono
    proc = subprocess.Popen([
        "ffmpeg", "-i", youtube_url,
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "48000", "-ac", "1",
        "-f", "s16le", "pipe:1"
    ], stdout=subprocess.PIPE)

    uri = "ws://localhost:8081/api/audio/tx"
    async with websockets.connect(uri) as ws:
        while chunk := proc.stdout.read(4096):
            await ws.send(chunk)

asyncio.run(stream_youtube_to_rig("https://youtube.com/watch?v=..."))
```

#### `WS /api/audio/tx` — Client → IC-905 TX (Mikrofon)

Empfängt PCM-Audio-Chunks als Binärdaten und gibt sie auf den TX-Eingang des IC-905 aus.

- **Exklusiver Zugriff**: Nur ein TX-Client gleichzeitig
- Ist TX bereits belegt, wird die Verbindung mit Code `1008` abgelehnt
- Client sendet rohe PCM-Bytes (Format/Samplerate gemäß Konfiguration)

---

### PTT — Sendetaste via CI-V

Der Browser-TX-Sender und externe Clients können die Sendetaste (PTT) über CI-V steuern:

#### `PUT /api/rig/command` — PTT EIN

```bash
curl -X PUT https://localhost:8080/api/rig/command \
  -H "Content-Type: application/json" \
  -d '{"command": "send_transceiver_status", "data": {"status": true}}'
```

**Response:**
```json
{"success": true, "data": {"status": true}}
```

#### `PUT /api/rig/command` — PTT AUS

```bash
curl -X PUT https://localhost:8080/api/rig/command \
  -H "Content-Type: application/json" \
  -d '{"command": "send_transceiver_status", "data": {"status": false}}'
```

**Response:**
```json
{"success": true, "data": {"status": true}}
```

> **Hinweis:** Der `send_transceiver_status`-Befehl muss in der gerätespezifischen YAML-Datei definiert sein.  
> Der Browser-TX-Sender setzt PTT automatisch beim Aktivieren/Deaktivieren des PTT-Buttons.

---

### Docker: Audio-Gerät-Passthrough

Damit der Container auf die IC-905 USB-Audio-Geräte zugreifen kann, müssen in `docker-compose.yml` folgende Einträge gesetzt sein:

```yaml
devices:
  - /dev/snd/pcmC0D0c:/dev/snd/pcmC0D0c   # RX (Capture)
  - /dev/snd/pcmC0D0p:/dev/snd/pcmC0D0p   # TX (Playback)
  - /dev/snd/controlC0:/dev/snd/controlC0  # ALSA Control

group_add:
  - "29"   # audio-Gruppe (GID 29 auf Jetson/Debian)
```

> **Hinweis:** Die Gerät-IDs (`pcmC0D0c`, `pcmC0D0p`) können je nach Reihenfolge der angeschlossenen USB-Geräte variieren.  
> Mit `arecord -l` und `aplay -l` lässt sich das korrekte Gerät auf dem Host ermitteln.

### Python-Abhängigkeiten (Audio)

Das Audio-Modul benötigt `sounddevice` und `numpy` (PCM-Konvertierung). Beide sind in `requirements.txt` enthalten:

```bash
pip install -r requirements.txt
```

| Paket | Zweck |
|---|---|
| `sounddevice` | ALSA/PortAudio-Zugriff für RX-Capture und TX-Playback |
| `numpy` | PCM-Puffer-Konvertierung in `audio_manager.py` |
| `cryptography` | Automatische Generierung selbst-signierter Zertifikate (HTTPS) |
