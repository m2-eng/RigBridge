# RigBridge – Coding-Regeln

> Diese Datei definiert verbindliche Coding-Standards und -Konventionen.
> Als AI-Assistent (GitHub Copilot) musst du diese Regeln bei **jeder** Änderung
> am Projekt berücksichtigen und einhalten.

---

## 1. Sprache & Technologie

| Bereich | Sprache |
|---|---|
| Backend | Python 3.11+ |
| Frontend | HTML5, CSS3, JavaScript (ES2022+, kein Framework-Zwang) |
| Protokolldefinitionen | YAML |
| Container | Docker / docker-compose |

| Zielplattform | Umgebung |
|---|---|
| Produktion | Linux (Docker) |
| Entwicklung | Windows (nativ) oder Linux |

- Alle neuen Dateien erhalten einen Dateiheader-Kommentar mit kurzem Zweck-Beschrieb.
- Kommentare werden auf **Deutsch** verfasst.

---

## 2. Code-Stil

Einrückung gemäß `.vscode/settings.json` und `.editorconfig` (kein manuelles Überschreiben):

| Sprache | Einrückung | Zeilenlänge |
|---|---|---|
| Python | 4 Spaces (PEP 8) | max. 120 Zeichen |
| JavaScript | 2 Spaces | max. 120 Zeichen |
| HTML | 2 Spaces | – |
| CSS / SCSS | 2 Spaces | – |
| YAML | 2 Spaces | – |

**Python:**
- Einfache Anführungszeichen (`'`) für Strings, außer bei Docstrings (`"""`).
- PEP 8 ist verbindlich; `flake8` oder `ruff` als Linter.
- Keine ungenutzten Imports (`isort` empfohlen).

**JavaScript:**
- Semikolons immer setzen.
- Einfache Anführungszeichen (`'`) für Strings, außer in Template-Literals.
- Trailing Comma bei mehrzeiligen Arrays und Objekten.

- Kein toter Code (`dead code`) im Repository – ungenutzte Variablen, Imports und Funktionen entfernen.

---

## 3. Typisierung

**Python:**
- Alle Funktionen haben Type Hints (PEP 484): `def get_frequency(channel: int) -> float:`
- `mypy` im strict-Modus wird empfohlen.
- Dataclasses oder Pydantic für strukturierte Daten bevorzugen.

**JavaScript:**
- JSDoc-Typen für öffentliche Funktionen: `/** @param {number} channel @returns {number} */`
- Keine impliziten `undefined`-Rückgaben bei Funktionen mit definiertem Rückgabetyp.

---

## 4. Fehlerbehandlung

**Python:**
- Spezifische Ausnahmen fangen, nie blankes `except:`:
  ```python
  try:
      ...
  except serial.SerialException as e:
      logger.error('USB-Fehler: %s', e)
      raise
  ```
- Keine leeren `except`-Blöcke.
- Eigene Ausnahmen für Domänenfehler definieren (z.B. `CivCommandError`).

**JavaScript:**
- `try/catch` mit expliziter Fehlerprüfung:
  ```js
  try { ... } catch (error) {
    if (error instanceof Error) { console.error(error.message); }
  }
  ```
- Promises immer mit `.catch()` oder `await` + `try/catch` behandeln.
- Keine leeren `catch`-Blöcke.

---

## 5. Sicherheit im Code

- **Secrets nie loggen:** API-Keys und Passwörter dürfen nicht in Log-Aufrufen auftauchen, auch nicht auf `DEBUG`-Level.
- **Secrets nie in API-Responses:** Konfigurationsendpunkte maskieren Secrets (`"api_key": "***"`).
- **HTTPS erzwingen für Wavelog:**
  ```python
  # Richtig – TLS-Validierung aktiv
  requests.post(wavelog_url, headers={'X-Api-Key': key}, verify=True)
  # Verboten
  requests.post(wavelog_url, verify=False)
  ```
- **Passwort-Eingabe im UI:** Der API-Key wird im Frontend als `<input type="password">` dargestellt.
- **Dateirechte `.env`:** Bei der Inbetriebnahme auf Linux `chmod 600 .env` setzen (Dokumentation + ggf. Start-Skript).

---

## 6. YAML-Protokolldateien

- Alle YAML-Dateien folgen dem Schema, das in `protocols/general/` definiert ist.
- Neue Befehlseinträge enthalten immer: `name`, `description`, `command`, `response` (falls zutreffend).
- Hexadezimalwerte werden als Strings mit `0x`-Präfix geschrieben: `"0xFE"`.

---

## 7. Commits & Branches

- Commit-Messages folgen dem **Conventional Commits**-Format:
  `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- Feature-Branches: `feature/<kurzbeschreibung>`
- Bugfix-Branches: `fix/<kurzbeschreibung>`

---

## 8. Tests

- Jedes Backend-Modul hat eine korrespondierende Testdatei in `tests/backend/`.
- **Python:** `pytest` als Test-Framework; Dateiname `test_<modulname>.py`.
- **JavaScript:** Testdatei `<dateiname>.test.js`.
- Mindestabdeckung: alle öffentlichen Funktionen werden getestet.
- Mocks für USB/Serial-Hardware sind im Testverzeichnis zu halten, nicht im Produktionscode.

---

## 9. Dokumentation

- **Python:** Öffentliche Funktionen und Klassen erhalten Docstrings (Google-Style).
- **JavaScript:** Öffentliche Funktionen erhalten JSDoc-Kommentare.
- Komplexe Algorithmen (z.B. CI-V-Paketaufbau) werden inline kommentiert.
- Architekturentscheidungen werden als ADR-Datei in `docs/` festgehalten.

---

## 10. Docker

- Docker ist ausschließlich für **Linux** vorgesehen (Produktion + optionale Linux-Entwicklung).
- Auf **Windows** wird die Anwendung **nativ** gestartet – kein Docker.
- Das `Dockerfile` liegt im Projekt-Root und baut ein Linux-Image (Multi-Stage: `builder` + `runtime`).
- Keine Secrets in `Dockerfile` oder `docker-compose.yml` – ausschließlich über `.env`-Dateien übergeben.
- `.dockerignore` ist Pflicht und schließt mindestens `__pycache__`, `.env`, `tests/` aus.
- `docker-compose.yml` wird für Linux-Entwicklung und Produktion genutzt.
- **Sicherheit im Container** – folgende Maßnahmen sind verbindlich (siehe `docker-compose.yml`):
  - `security_opt: no-new-privileges:true`
  - `cap_drop: [ALL]`
  - `read_only: true` + `tmpfs` für `/tmp`
  - Port nur auf `127.0.0.1` binden
  - Base-Image mit expliziter Patch-Version pinnen (kein `:latest`)
  - Ressourcen-Limits (CPU + RAM) setzen
- Base-Image-Version bei jeder Aktualisierung auf CVEs prüfen (`docker scout` oder `trivy`).

---

## 11. Plattformkompatibilität (Linux & Windows)

- **Dateipfade:** Immer `pathlib.Path` verwenden. Nie `+`-Konkatenation oder `os.path.join`:
  ```python
  # Richtig
  config_path = Path('src') / 'backend' / 'config' / 'settings.yaml'
  # Falsch
  config_path = 'src/backend/config/settings.yaml'
  ```
- **Zeilenenden:** Dateien immer mit `\n` öffnen/schreiben (`open(..., newline='\n')`). `.editorconfig` sichert LF für alle Quelltext-Dateien.
- **USB-Portnamen:** Nie hardcoded. Immer aus Konfiguration / Umgebungsvariable lesen:
  - Linux: `/dev/ttyUSB0`, `/dev/ttyACM0`
  - Windows: `COM3`, `COM4`, ...
- **Prozessstart / Shell-Befehle:** `subprocess` mit Liste statt Shell-String verwenden (plattformsicher):
  ```python
  # Richtig
  subprocess.run(['python', '-m', 'pytest'], check=True)
  # Falsch
  subprocess.run('python -m pytest', shell=True)
  ```
- **Temporäre Verzeichnisse:** `tempfile.gettempdir()` oder `tempfile.TemporaryDirectory()` verwenden, nie `/tmp/` hardcoden.
- **Umgebungsabfrage** (nur wenn unumgänglich):
  ```python
  import sys
  IS_WINDOWS = sys.platform == 'win32'
  IS_LINUX   = sys.platform.startswith('linux')
  ```
  Plattformspezifischen Code in eigene Hilfsfunktionen auslagern (`src/backend/usb/platform_utils.py`).
