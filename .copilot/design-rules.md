# RigBridge – Design-Regeln

> Diese Datei definiert verbindliche Design-Prinzipien für das gesamte Projekt.
> Als AI-Assistent (GitHub Copilot) musst du diese Regeln bei **jeder** Änderung
> am Projekt berücksichtigen und einhalten.

---

## 1. Architekturprinzipien

- **Trennung von Verantwortlichkeiten (Separation of Concerns):** Backend-Logik (USB, CI-V, CAT) ist strikt vom Frontend (UI) getrennt. Kein direkter Hardware-Zugriff aus dem Frontend.
- **API-First:** Alle Funktionen werden primär über eine definierte REST-API bereitgestellt. Das Frontend ist ein reiner Consumer dieser API.
- **Protokoll-agnostisch:** Die API-Schicht kennt keine gerätespezifischen Details. Diese werden ausschließlich über YAML-Protokolldateien injiziert.

---

## 2. UI / Frontend

- Die Browser-Oberfläche dient ausschließlich der **Konfiguration** (USB-Einstellungen, CAT-Einstellungen, usw.).
- Keine gerätespezifische Steuerungslogik im Frontend.
- Das UI muss **responsiv** und ohne externe CSS-Frameworks auskommen (eigene, schlanke Styles), sofern kein Framework explizit gewählt wurde.
- Einstellungsformulare bieten clientseitige Validierung vor dem Absenden.

---

## 3. Backend

- **USB-Kommunikation** läuft in einem eigenen Modul (`src/backend/usb/`) und ist über ein definiertes Interface abstrahiert.
- **CI-V-Befehle** werden ausschließlich im Modul `src/backend/civ/` zusammengestellt und interpretiert.
- **CAT-Schnittstelle** (`src/backend/cat/`) ist ein eigenständiger Service, der die API nach außen (Wavelog) exponiert.
- Konfigurationen (Baud Rate, Port, API Key, ...) werden persistent gespeichert und beim Start geladen.
- Der USB/Serial-Port-Name wird **ausschließlich über Konfiguration / Umgebungsvariable** übergeben – nie hardcoded. Format ist OS-abhängig (`/dev/ttyUSB0` auf Linux, `COM3` auf Windows).

---

## 4. Fehlerbehandlung

- Alle API-Endpunkte geben strukturierte Fehlermeldungen zurück (JSON mit `error`, `message`, `code`).
- Hardware-Fehler (USB, Serial) werden abgefangen und als sinnvolle API-Fehler weitergeleitet.
- Keine unbehandelten Ausnahmen (`unhandled exceptions`) in der Produktion.

---

## 5. Sicherheit

### 5.1 Allgemein

- Der CAT-API-Key wird niemals im Frontend-Code oder in versionierten Configs gespeichert.
- Konfigurationsdateien mit Secrets werden ausschließlich über `.env`-Dateien verwaltet (sind in `.gitignore` aufgeführt).
- Secrets dürfen nicht in Log-Ausgaben erscheinen.
- API-Endpunkte, die Konfiguration zurückliefern (`GET /api/config`), dürfen **niemals** Secrets (API-Keys, Passwörter) im Response-Body enthalten. Felder werden durch `***` oder komplett weggelassen.

### 5.2 Docker-Container (Linux/Produktion)

| Maßnahme | Umsetzung |
|---|---|
| Kein Root-Prozess | `USER appuser` (UID 1001) im Dockerfile |
| Gepinnte Base-Image-Version | `python:3.11.12-slim` statt `:latest` oder `:slim` |
| Privilege-Eskalation verboten | `security_opt: no-new-privileges:true` |
| Alle Capabilities gedroppt | `cap_drop: [ALL]` – nur bei Bedarf einzeln zurückgeben |
| Read-only Filesystem | `read_only: true` + `tmpfs` für `/tmp` |
| Port nur lokal binden | `127.0.0.1:<port>:8080` (kein offenes `0.0.0.0`) |
| Ressourcen-Limits | `deploy.resources.limits` (CPU + RAM) |
| Netzwerk-Isolation | Dediziertes Docker-Netzwerk `rigbridge_net` |
| Keine Secrets im Image | Nur über `.env` zur Laufzeit übergeben |

- Bei jeder Aktualisierung der Base-Image-Version die Patch-Notes auf CVEs prüfen.
- Das Image regelmäßig mit einem Scanner (z.B. `docker scout`, `trivy`) auf bekannte Schwachstellen prüfen.

### 5.3 Verschlüsselung

#### Transport (TLS/HTTPS)

| Verbindung | Anforderung | Begründung |
|---|---|---|
| Browser → RigBridge-API | HTTPS **empfohlen**, wenn Zugriff über Netzwerk (nicht nur `localhost`) | API-Key-Übertragung beim Speichern der Konfiguration |
| Browser → RigBridge-API | HTTP akzeptabel, wenn **ausschließlich** `127.0.0.1` (lokaler Zugriff auf demselben Gerät) | Transport bleibt im Loopback |
| RigBridge → Wavelog | **HTTPS erzwingen** (TLS-Zertifikat validieren, kein `verify=False`) | API-Key wird im Header übertragen |

- Wird die App in einem lokalen Heimnetz über eine IP-Adresse (nicht `localhost`) aufgerufen, muss HTTPS aktivierbar sein.
- Für selbstsignierte Zertifikate (`mkcert` o.Ä.) ist die Konfiguration zu dokumentieren.
- Ein optionaler TLS-Modus (HTTPS) mit konfigurierbarem Zertifikatspfad ist vorzubereiten und per Konfiguration aktivierbar umzusetzen.

#### Speicherung von Secrets (API-Key)

- Der Wavelog API-Key wird verschlüsselt gespeichert (kein Klartext im persistenten Speicher).
- Die `.env`-Datei muss restriktive Dateiberechtigungen haben: `chmod 600 .env` (nur Eigentuemer lesbar).
- Im Docker-Container wird die `.env`-Datei über `env_file` eingebunden und ist nicht im Image enthalten.
- Für die Verschlüsselung sind plattformgeeignete Mechanismen zu verwenden (z.B. OS-Keychain / Windows Credential Manager oder ein dokumentiertes, sicheres Verschlüsselungsverfahren).
- Unverschlüsselte Fallbacks dürfen nur als explizite, dokumentierte Ausnahme für lokale Entwicklungsumgebungen zulässig sein.

---

## 6. Plattformunterstützung

| Umgebung | Plattform | Ausführung |
|---|---|---|
| Produktion | Linux | Docker Container |
| Entwicklung | Windows | **Nativ** (Python + pyserial, **kein Docker**) |
| Entwicklung | Linux | Nativ oder Docker |

- Der Code **muss auf beiden Plattformen ohne Änderungen lauffähig sein**.
- Auf **Windows wird die Anwendung ausschließlich nativ** ausgeführt. Docker ist auf Windows nicht vorgesehen.
- Dateipfade immer mit `pathlib.Path` konstruieren, nie mit String-Konkatenation oder `os.path.join`.
- Zeilenenden: intern immer `\n` verwenden; in Dateien über `.editorconfig` geregelt (LF).
- USB-Serial-Portnamen sind plattformabhängig und kommen ausschließlich aus der Konfiguration:
  - Linux: `/dev/ttyUSB0`, `/dev/ttyACM0`
  - Windows: `COM3`, `COM4`, ...
- Plattformspezifischer Code wird in eigene Hilfsfunktionen ausgelagert und nicht verstreut.
