# RigBridge
[![Tests](https://github.com/m2-eng/RigBridge/actions/workflows/tests.yml/badge.svg)](https://github.com/m2-eng/RigBridge/actions/workflows/tests.yml)
[![Performance](https://github.com/m2-eng/RigBridge/actions/workflows/performance.yml/badge.svg)](https://github.com/m2-eng/RigBridge/actions/workflows/performance.yml)
[![codecov](https://codecov.io/gh/m2-eng/RigBridge/branch/main/graph/badge.svg)](https://codecov.io/gh/m2-eng/RigBridge)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](LICENSE)

RigBridge ist eine offene API‑Plattform zur Steuerung von Funkgeräten über CI‑V und USB und stellt eine CAT‑Schnittstelle für Logging‑ und Steuerungssoftware wie Wavelog bereit.

## 🎯 Features

- **Moderne Browser-UI** - Admin-Panel zur Konfiguration und Überwachung
- **REST API** - Vollständige API für externe Gerätesteuerung
- **Wavelog-Integration** - Automatische Log-Einträge
- **Multi-Protokoll-Unterstützung** - Icom CI-V und weitere (via YAML)
- **Sichere Secret-Verwaltung** - HashiCorp Vault Integration
- **Echtzeitstatus** - Live-Überwachung USB, CAT, Gerätestatus

## 🚀 Quick Start

### Browser-UI starten (Native auf Windows)

```bash
# 1. Abhängigkeiten installieren
pip install -r requirements.txt

# 2. Backend starten
python run_api.py

# 3. Browser öffnen
http://127.0.0.1:8080
```

Die Browser-UI wird automatisch unter der API-URL served.

### Docker (Linux)

```bash
docker-compose up rigbridge
```

Danach: http://127.0.0.1:8080

## 📋 Browser-UI Features

Die Browser-UI bietet:

| Tab | Funktion |
|-----|----------|
| **USB-Einstellungen** | Port, Baud-Rate, Timeouts konfigurieren |
| **Gerätewahl** | Verfügbare Funk-Geräte aus YAML auswählen |
| **API-Server** | Host, Port, Log-Level konfig urieren |
| **Wavelog-Integration** | Wavelog-Verbindung testen, Stationen auswählen |
| **Informationen** | System-Status, API-Dokumentation, Swagger/ReDoc |

### Dark/Light Theme

- **Toggle-Button** im Header (🌙/☀️)
- **Automatisches Speichern** in Browser LocalStorage
- **System-Preference Fallback** - folgt Windows/macOS Dark Mode

### Echtzeitstatus

Oben links werden permanent angezeigt:
- 🟢/⚫ **USB Verbindung** - Serial-Port-Status
- 🟢/🟡/⚫ **CAT Status** - Funk-Geräte-Verbindung
- **Gerät** - Aktuell konfiguriertes Funk-Gerät

Status wird alle 5 Sekunden aktualisiert via `/api/status`.

## 🔧 Konfiguration

### config.json

Die Konfiguration wird in `config.json` gespeichert:

```json
{
  "usb": {
    "port": "COM4",
    "baud_rate": 115200,
    "data_bits": 8,
    "stop_bits": 1,
    "parity": "N"
  },
  "device": {
    "name": "Icom IC-905",
    "manufacturer": "icom",
    "protocol_file": "ic905"
  },
  "api": {
    "host": "127.0.0.1",
    "port": 8080,
    "log_level": "INFO"
  },
  "wavelog": {
    "enabled": false,
    "api_url": "https://wavelog.example.com",
    "api_key_secret_ref": "rigbridge/wavelog#api_key",
    "polling_interval": 30
  }
}
```

### theme.css (Custom Styling)

Für Anpassungen des Erscheinungsbildes:

```bash
# theme.css im Projekt-Root bearbeiten
echo ":root { --color-primary: #ff6b6b; }" >> theme.css
```

Verfügbare CSS-Variables in [docs/FRONTEND_DEVELOPMENT.md](docs/FRONTEND_DEVELOPMENT.md).

## 📖 Dokumentation

- **[docs/API.md](docs/API.md)** - Ausführliche API-Dokumentation
- **[docs/BACKEND_DEVELOPMENT.md](docs/BACKEND_DEVELOPMENT.md)** - Backend-Entwicklung
- **[docs/FRONTEND_DEVELOPMENT.md](docs/FRONTEND_DEVELOPMENT.md)** - Browser-UI Entwicklung
- **[API Swagger UI](http://127.0.0.1:8080/api/docs)** - Interaktive API-Docs (nach Backend-Start)
- **[API ReDoc](http://127.0.0.1:8080/api/redoc)** - Alternative API-Dokumentation

## 🧪 Tests

Alle Tests ausführen:

```bash
pytest tests/ -v
```

Nur Backend-API Tests:

```bash
pytest tests/backend/test_api_frontend.py -v
```

Frontend wird im Browser getestet (UI-Tests sind manuell).

## 🐳 Docker Compose

Volumes für Konfiguration:

```yaml
volumes:
  - ./config.json:/app/config.json              # Konfigurationsdatei (read-write)
  - ./theme.css:/app/src/frontend/assets/theme.css  # Custom Theme (read-write)
```

Benutzer können diese Dateien im Host bearbeiten, um RigBridge zu konfigurieren.

## 🔐 Sicherheit

- **Secrets** - Nie im Klartext speichern oder loggen
  - Password-Felder in der UI
  - Vault-Integration für API-Keys
  - Automatisches Masking (angezeigt als "***")
  
- **HTTPS** - Optional im API-Tab aktivierbar (für Production)

- **Secret-Referenzen** - Format: `provider/path#key` (z.B. `rigbridge/wavelog#api_key`)

## 💻 Systemanforderungen

- **Windows:** Python 3.9+, USB-Treiber für Funk-Gerät
- **Linux:** Python 3.9+, Zugriff auf `/dev/ttyUSB*` oder `/dev/ttyACM*`
- **Browser:** Modern (Chrome, Firefox, Safari, Edge) - kein IE11

## 📄 Lizenz

[AGPL-3.0](LICENSE) - Offene Software für Amateur-Funkgemeinschaft

## 🤝 Beiträge

Beiträge sind willkommen! Bitte:
1. Tests schreiben für neue Features
2. [BACKEND_DEVELOPMENT.md](docs/BACKEND_DEVELOPMENT.md) und [FRONTEND_DEVELOPMENT.md](docs/FRONTEND_DEVELOPMENT.md) aktualisieren
3. PR gegen `main` branch öffnen

---

**Entwickelt für Amateur-Funkgemeinschaft** 📡
