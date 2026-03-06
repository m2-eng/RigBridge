# RigBridge – Struktur-Regeln

> Diese Datei definiert verbindliche Regeln zur Ordner- und Dateistruktur.
> Als AI-Assistent (GitHub Copilot) musst du diese Regeln bei **jeder** Änderung
> am Projekt berücksichtigen und einhalten.

---

## 1. Ordnerstruktur (Übersicht)

```
RigBridge/
├── .copilot/                  ← AI-Assistenten-Regeln (NICHT für Laufzeit-Code)
├── .vscode/                   ← VS Code Workspace-Einstellungen
├── docs/                      ← Projektdokumentation, ADRs, API-Beschreibungen
├── src/
│   ├── backend/               ← Python
│   │   ├── api/               ← REST-API-Routen und Handler (z.B. Flask / FastAPI)
│   │   ├── cat/               ← CAT-Schnittstelle (Wavelog-Protokoll)
│   │   ├── civ/               ← CI-V Befehlsaufbau und -verarbeitung
│   │   ├── usb/               ← USB / Serial-Kommunikation
│   │   └── config/            ← Laden, Validieren und Speichern der Konfiguration
│   └── frontend/              ← HTML / CSS / JavaScript
│       ├── components/        ← Wiederverwendbare UI-Bausteine (HTML-Fragmente + JS)
│       ├── pages/             ← Seitenspezifische Views/Templates
│       └── assets/            ← Statische Ressourcen (CSS, Bilder, Fonts)
├── protocols/
│   ├── general/               ← Generische, geräteübergreifende Datentypen (YAML)
│   └── manufacturers/
│       └── icom/              ← ICOM-spezifische Hersteller- und Geräte-YAMLs
├── tests/
│   ├── backend/               ← pytest-Tests für Backend-Module
│   └── frontend/              ← Tests für Frontend-Komponenten (JS)
├── Dockerfile                 ← Multi-Stage Docker-Build
├── docker-compose.yml         ← Lokale Entwicklungs- und Integrationsumgebung
├── .dockerignore
├── .editorconfig
├── .gitignore
└── requirements.txt           ← Python-Abhängigkeiten
```

---

## 2. Platzierungsregeln

| Inhalt | Zielordner |
|---|---|
| REST-API-Routen und Handler (Python) | `src/backend/api/` |
| CAT-Protokoll-Implementierung (Python) | `src/backend/cat/` |
| CI-V Befehlsdefinitionen / Parser (Python) | `src/backend/protocol/` |
| USB / Serial-Verbindungslogik (Python) | `src/backend/usb/` |
| Konfigurationsdateien und -schemas (Python) | `src/backend/config/` |
| Wiederverwendbare UI-Bausteine (HTML + JS) | `src/frontend/components/` |
| Seiten-Templates / Views (HTML) | `src/frontend/pages/` |
| CSS, Bilder, Fonts | `src/frontend/assets/` |
| Generische YAML-Datentypen | `protocols/general/` |
| Hersteller/Geräte-YAMLs (ICOM) | `protocols/manufacturers/icom/` |
| Tests Backend (pytest) | `tests/backend/` |
| Tests Frontend (JS) | `tests/frontend/` |
| Projektdokumentation | `docs/` |
| Python-Abhängigkeiten | `requirements.txt` (Root) |
| Docker-Build | `Dockerfile` (Root) |
| Docker-Compose (Entwicklung) | `docker-compose.yml` (Root) |

---

## 3. Dateibenennungskonventionen

**Python (Backend):**
- Moduldateien: **snake_case** → `usb_connection.py`, `civ_command_builder.py`
- Klassen: **PascalCase** → `UsbConnection`, `CivCommand`
- Konstanten: **UPPER_SNAKE_CASE** → `DEFAULT_BAUD_RATE`
- Testdateien: Präfix `test_` → `test_usb_connection.py`

**JavaScript / HTML / CSS (Frontend):**
- Dateien: **kebab-case** → `usb-settings.js`, `main-nav.html`, `base-styles.css`
- Klassen (JS): **PascalCase** → `UsbSettings`
- Konstanten (JS): **UPPER_SNAKE_CASE** → `DEFAULT_BAUD_RATE`
- Testdateien: Suffix `.test` → `usb-settings.test.js`

**YAML / Protokolldateien:**
- **kebab-case** → `icom-ic-7300.yaml`, `data-types.yaml`

---

## 4. Neue Geräte/Hersteller

- Pro Hersteller gibt es einen eigenen Unterordner in `protocols/manufacturers/<hersteller>/`.
- Pro Funkgerät gibt es eine eigene YAML-Datei in diesem Unterordner.
- Gemeinsame Hersteller-Definitionen kommen in eine Hersteller-Datei (z.B. `icom.yaml`).
- Generische, herstellerübergreifende Typen kommen in `protocols/general/`.

---

## 5. Leere Ordner

- Leere Ordner enthalten immer eine `.gitkeep`-Datei.
- Sobald der erste echte Inhalt in einem Ordner abgelegt wird, wird `.gitkeep` entfernt.
- Nicht benötigte Dateien sind zu entfrenen.
- Das root-Verzeichnis enthält nur die nötigsten Dateien.

---

## 6. Docker

- `Dockerfile` und `docker-compose.yml` liegen immer im **Projekt-Root**.
- Das `Dockerfile` nutzt Multi-Stage-Builds (`builder` + `runtime`).
- `.dockerignore` muss vor dem ersten `docker build` vorhanden sein.
- Docker-spezifische Hilfsskripte (Entrypoints, Health-Checks) kommen in `docker/`.
