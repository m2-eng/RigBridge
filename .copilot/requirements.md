# RigBridge – Funktionale Anforderungen

> Diese Datei beschreibt **was** das System leisten muss.
> Sie dient als Referenz für Entwickler und AI-Assistenten, um:
> - den Umsetzungsstand zu prüfen
> - Inkonsistenzen zwischen Anforderung und Implementierung zu erkennen
> - neue Features gegen bestehende Anforderungen abzugleichen
>
> **Status-Legende:**
> | Symbol | Bedeutung |
> |---|---|
> | ⬜ | Nicht begonnen |
> | 🔄 | In Arbeit |
> | ✅ | Umgesetzt |
> | ❌ | Verworfen / nicht relevant |

---

## 1. Systemübersicht

RigBridge ist eine **Browser-Applikation**, die folgende Kernaufgaben erfüllt:

1. Verbindung zu einem Amateurfunkgerät über **USB / Serial** mittels **CI-V-Protokoll** (herstellerspezifisch, primär ICOM).
2. Bereitstellung einer **REST-API** für interne Nutzung (Frontend) und externe Systeme.
3. Bereitstellung einer **CAT-Schnittstelle** (Hamlib-kompatibel / Wavelog-kompatibel) für die Logbuch-Software **Wavelog**.
4. Einfache **Browser-Oberfläche** zur Konfiguration der Anwendung.

---

## 2. Akteure

| Akteur | Beschreibung |
|---|---|
| **Benutzer** | Bedient die Browser-Oberfläche zur Konfiguration |
| **Wavelog** | Externe Software, die die CAT-Schnittstelle konsumiert |
| **Funkgerät** | Hardware (z.B. ICOM IC-7300), die über USB / Serial angesteuert wird |

---

## 3. Funktionale Anforderungen

### 3.1 USB / Serial – Verbindungsverwaltung

| ID | Anforderung | Status |
|---|---|---|
| USB-01 | Das System stellt eine Verbindung zu einem Funkgerät über einen konfigurierbaren USB/Serial-Port her. | ⬜ |
| USB-02 | Der Port-Name ist konfigurierbar (Linux: `/dev/ttyUSB0`; Windows: `COM3`). | ⬜ |
| USB-03 | Die Baud-Rate ist konfigurierbar (Standardwert: 19200). | ⬜ |
| USB-04 | Weitere Serial-Parameter sind konfigurierbar: Datenbits, Stoppbits, Parität. | ⬜ |
| USB-05 | Das System erkennt, ob die USB-Verbindung aktiv oder unterbrochen ist, und meldet den Status über die API. | ⬜ |
| USB-06 | Bei Verbindungsabbruch versucht das System automatisch, die Verbindung nach konfigurierbarem Intervall wiederherzustellen. | ⬜ |
| USB-07 | Das System unterstützt sowohl Linux (`/dev/tty*`) als auch Windows (`COM*`) ohne Code-Änderung. | ⬜ |

---

### 3.2 CI-V – Protokollverarbeitung

| ID | Anforderung | Status |
|---|---|---|
| CIV-01 | Das System baut CI-V-Befehle gemäß der gerätespezifischen YAML-Protokolldatei auf. | ⬜ |
| CIV-02 | Das System interpretiert CI-V-Antworten des Funkgeräts und wandelt sie in strukturierte Daten um. | ⬜ |
| CIV-03 | Unterstützte Befehle werden aus der YAML-Datei des aktiven Geräts geladen – kein Hardcoding von Befehlen im Code. | ⬜ |
| CIV-04 | Das System unterstützt den CI-V-Befehl zum Lesen der aktuellen Frequenz. | ⬜ |
| CIV-05 | Das System unterstützt den CI-V-Befehl zum Lesen des aktuellen Betriebsmodus (z.B. SSB, CW, FM). | ⬜ |
| CIV-06 | Das System unterstützt das Setzen der Frequenz über CI-V. | ⬜ |
| CIV-07 | Das System unterstützt das Setzen des Betriebsmodus über CI-V. | ⬜ |
| CIV-08 | Unbekannte oder fehlerhafte CI-V-Antworten werden geloggt und führen nicht zu einem Absturz. | ⬜ |

---

### 3.3 Protokolldefinitionen (YAML)

| ID | Anforderung | Status |
|---|---|---|
| YAML-01 | Pro Funkgerät existiert eine eigene YAML-Datei in `protocols/manufacturers/<hersteller>/`. | 🔄 (Ordner angelegt) |
| YAML-02 | Pro Hersteller existiert eine Hersteller-YAML mit gemeinsamen Definitionen. | 🔄 (ICOM-Ordner angelegt) |
| YAML-03 | In `protocols/general/` befinden sich herstellerübergreifende, generische Datentypen. | 🔄 (Ordner angelegt) |
| YAML-04 | Das System lädt die YAML-Datei beim Start anhand des konfigurierten Gerätenamens. | ⬜ |
| YAML-05 | Das System validiert die YAML-Datei beim Laden gegen ein definiertes Schema. | ⬜ |
| YAML-06 | Ein unbekanntes oder fehlendes Gerät erzeugt eine klare Fehlermeldung beim Start. | ⬜ |
| YAML-07 | Neue Geräte können durch Ablegen einer YAML-Datei ohne Code-Änderung hinzugefügt werden. | ⬜ |

---

### 3.4 REST-API

| ID | Anforderung | Status |
|---|---|---|
| API-01 | Das System stellt eine REST-API auf einem konfigurierbaren Port bereit (Standard: 8080). | ⬜ |
| API-02 | `GET /api/status` – liefert den aktuellen Verbindungsstatus (USB, CAT). | ⬜ |
| API-03 | `GET /api/rig/frequency` – liefert die aktuelle Frequenz des Funkgeräts. | ⬜ |
| API-04 | `PUT /api/rig/frequency` – setzt die Frequenz des Funkgeräts. | ⬜ |
| API-05 | `GET /api/rig/mode` – liefert den aktuellen Betriebsmodus. | ⬜ |
| API-06 | `PUT /api/rig/mode` – setzt den Betriebsmodus. | ⬜ |
| API-07 | `GET /api/config` – liefert die aktuelle Konfiguration. Secrets (API-Keys, Passwörter) werden **niemals** zurückgeliefert (Felder werden durch `***` ersetzt oder weggelassen). | ⬜ |
| API-08 | `PUT /api/config` – speichert geänderte Konfigurationswerte persistent. | ⬜ |
| API-09 | `GET /health` – Health-Check-Endpunkt für Docker und Monitoring. | ⬜ |
| API-10 | Alle Fehlerantworten folgen dem einheitlichen Format: `{ "error": true, "code": "...", "message": "..." }`. | ⬜ |

---

### 3.5 CAT-Schnittstelle (Wavelog)

| ID | Anforderung | Status |
|---|---|---|
| CAT-01 | Das System stellt eine CAT-kompatible Schnittstelle auf einem konfigurierbaren Port bereit. | ⬜ |
| CAT-02 | Die Schnittstelle ist kompatibel mit Wavelog (Hamlib-Protokoll oder Wavelog-eigenes API). | ⬜ |
| CAT-03 | Der CAT-API-Key zur Authentifizierung gegenüber Wavelog ist konfigurierbar. | ⬜ |
| CAT-04 | Die Wavelog-API-URL ist konfigurierbar. | ⬜ |
| CAT-05 | Frequenz und Modus werden bei Änderung automatisch an Wavelog gemeldet (Push oder Poll). | ⬜ |
| CAT-06 | Die CAT-Schnittstelle kann unabhängig von der USB-Verbindung aktiviert/deaktiviert werden. | ⬜ |
| CAT-07 | Verbindungsfehler zur Wavelog-Instanz werden geloggt und führen nicht zum Absturz. | ⬜ |

---

### 3.6 Konfiguration

| ID | Anforderung | Status |
|---|---|---|
| CFG-01 | Alle Konfigurationswerte werden persistent gespeichert (Datei oder Datenbank). | ⬜ |
| CFG-02 | Die Konfiguration wird beim Start automatisch geladen. | ⬜ |
| CFG-03 | Umgebungsvariablen (`.env`) überschreiben dateibasierte Konfigurationswerte (12-Factor-Prinzip). | ⬜ |
| CFG-04 | Konfigurierbare Parameter (Mindestumfang): USB-Port, Baud-Rate, Serial-Parameter, CAT-Port, Wavelog-URL, Wavelog-API-Key, Gerätename, API-Port, Log-Level. | ⬜ |
| CFG-05 | Secrets (API-Keys) werden nicht im Klartext in Logdateien ausgegeben. | ⬜ |
| CFG-06 | Die `.env`-Datei hat auf Linux restriktive Dateiberechtigungen (`chmod 600`). | ⬜ |

---

### 3.10 Sicherheit & Verschlüsselung

| ID | Anforderung | Status |
|---|---|---|
| SEC-01 | Secrets (API-Key, Passwörter) werden niemals in API-Antworten zurückgeliefert. | ⬜ |
| SEC-02 | Secrets werden nicht in Log-Einträgen ausgegeben (auch nicht auf `DEBUG`-Level). | ⬜ |
| SEC-03 | Die Verbindung von RigBridge zu Wavelog erfolgt **ausschließlich über HTTPS** (TLS). `verify=False` ist verboten. | ⬜ |
| SEC-04 | Der API-Port (8080) wird nur auf `127.0.0.1` gebunden, solange kein Netzwerkzugriff konfiguriert ist. | ✅ (docker-compose.yml) |
| SEC-05 | HTTPS für die interne REST-API ist optional aktivierbar (konfigurierbarer Zertifikatspfad), wenn Zugriff über Netzwerk nötig ist. | ⬜ (Entscheidung offen, siehe Q-07) |
| SEC-06 | Wird HTTPS aktiviert, wird das TLS-Zertifikat validiert (kein `verify=False`). | ⬜ |
| SEC-07 | Der Wavelog API-Key wird als Passwort-Eingabefeld (`type="password"`) im UI dargestellt. | ⬜ |
| SEC-08 | Auf Linux hat die `.env`-Datei Dateiberechtigungen `600` (nur Eigentuemer lesbar). | ⬜ |

---

### 3.7 Browser-Oberfläche (Frontend)

| ID | Anforderung | Status |
|---|---|---|
| UI-01 | Die Oberfläche ist über einen Browser erreichbar (kein separates Installationspaket nötig). | ⬜ |
| UI-02 | Die Oberfläche zeigt den aktuellen Verbindungsstatus (USB, CAT) an. | ⬜ |
| UI-03 | Einstellungsseite: USB-Verbindung konfigurieren (Port, Baud-Rate, Serial-Einstellungen). | ⬜ |
| UI-04 | Einstellungsseite: Gerät auswählen (Dropdown aus verfügbaren YAML-Gerätedateien). | ⬜ |
| UI-05 | Einstellungsseite: CAT-Schnittstelle konfigurieren (Port, Wavelog-URL, API-Key). | ⬜ |
| UI-06 | Einstellungsseite: API-Server-Port konfigurieren. | ⬜ |
| UI-07 | Alle Formulare bieten clientseitige Validierung vor dem Absenden. | ⬜ |
| UI-08 | Das UI ist responsiv und auf gängigen Desktop-Browsern nutzbar (Chrome, Firefox, Edge). | ⬜ |
| UI-09 | Das UI kommt ohne externe CSS-Frameworks aus (kein Bootstrap, Tailwind o.Ä.), sofern nicht explizit anders entschieden. | ⬜ |
| UI-10 | Es gibt **keine** Steuerungsmöglichkeit des Funkgeräts (Frequenz setzen, Modus wechseln) über das UI – nur Konfiguration. | ⬜ |

---

### 3.8 Logging

| ID | Anforderung | Status |
|---|---|---|
| LOG-01 | Das System schreibt strukturierte Log-Einträge (mindestens: Zeitstempel, Level, Modul, Nachricht). | ⬜ |
| LOG-02 | Das Log-Level ist konfigurierbar (`DEBUG`, `INFO`, `WARNING`, `ERROR`). | ⬜ |
| LOG-03 | Logs werden auf `stdout` ausgegeben (Docker-kompatibel). | ⬜ |
| LOG-04 | Optionale Ausgabe in eine Logdatei ist konfigurierbar. | ⬜ |

---

### 3.9 Deployment / Docker

> Docker gilt ausschließlich für **Linux**. Auf Windows wird die Anwendung nativ ausgeführt.

| ID | Anforderung | Status |
|---|---|---|
| DEP-01 | Die Anwendung ist auf Linux mit `docker compose up` startbar. | 🔄 (`docker-compose.yml` angelegt) |
| DEP-02 | Das Docker-Image basiert auf einem schlanken Linux-Basis-Image (Python slim). | 🔄 (`Dockerfile` angelegt) |
| DEP-03 | Der Container läuft ohne Root-Rechte (UID 1001). | ✅ (Non-Root-User + `chown` im `Dockerfile`) |
| DEP-04 | Alle Konfigurationswerte können über Umgebungsvariablen übergeben werden. | 🔄 (`.env.example` angelegt) |
| DEP-05 | USB-Geräte können dem Container auf Linux über den `devices`-Abschnitt übergeben werden. | ⬜ |
| DEP-06 | Ein Health-Check-Endpunkt ist im `docker-compose.yml` konfiguriert. | 🔄 (angelegt, Endpunkt noch nicht implementiert) |
| DEP-07 | Die Anwendung ist auf Windows **nativ** startbar (`python -m src.backend.api` o.Ä.), ohne Docker. | ⬜ |
| DEP-08 | Privilege-Eskalation im Container ist verboten (`no-new-privileges:true`). | ✅ (in `docker-compose.yml`) |
| DEP-09 | Alle Linux-Capabilities sind gedroppt (`cap_drop: ALL`). | ✅ (in `docker-compose.yml`) |
| DEP-10 | Das Container-Dateisystem ist read-only; `/tmp` als tmpfs mit `noexec,nosuid`. | ✅ (in `docker-compose.yml`) |
| DEP-11 | Der API-Port wird nur auf `127.0.0.1` gebunden (kein offenes `0.0.0.0`). | ✅ (in `docker-compose.yml`) |
| DEP-12 | Das Base-Image ist auf eine spezifische Patch-Version gepinnt (kein `:latest`). | ✅ (`python:3.11.12-slim` im `Dockerfile`) |
| DEP-13 | Ressourcen-Limits (CPU und RAM) sind im `docker-compose.yml` definiert. | ✅ (in `docker-compose.yml`) |
| DEP-14 | Der Container läuft in einem dedizierten Docker-Netzwerk (keine Nutzung des default-Netzwerks). | ✅ (`rigbridge_net` in `docker-compose.yml`) |
| DEP-15 | Das Image wird regelmäßig auf bekannte CVEs gescannt (`docker scout` oder `trivy`). | ⬜ (Prozess noch nicht eingerichtet) |

---

## 4. Nicht-funktionale Anforderungen (Kurzübersicht)

> Details siehe [design-rules.md](design-rules.md) und [coding-rules.md](coding-rules.md).

| ID | Anforderung |
|---|---|
| NF-01 | Plattformkompatibilität: Linux mit Docker (Produktion), Windows nativ ohne Docker (Entwicklung) – ohne Code-Anpassung lauffähig. |
| NF-02 | Code-Qualität: PEP 8, Type Hints, Docstrings, `ruff`/`black` als Formatter. |
| NF-03 | Testbarkeit: Hardware-Zugriff (USB) ist abstrahiert und mockbar. |
| NF-04 | Erweiterbarkeit: Neue Funkgeräte werden ausschließlich über YAML-Dateien hinzugefügt. |
| NF-05 | Sicherheit: Keine Secrets in Quellcode oder Logs; `.env`-Datei für alle sensitiven Werte. |

---

## 5. Offene Punkte / Entscheidungen

| ID | Frage | Status |
|---|---|---|
| Q-01 | Welches Web-Framework wird im Backend verwendet? (Flask, FastAPI, o.Ä.) | ⬜ Offen |
| Q-02 | Wie ist das CAT-Protokoll genau spezifiziert? (Hamlib-netrigctl, Wavelog-eigene API, …) | ⬜ Offen |
| Q-03 | Wird die Konfiguration dateibasiert (YAML/JSON) oder in einer lokalen Datenbank (SQLite) gespeichert? | ⬜ Offen |
| Q-04 | Polling oder Event-basierte Frequenz-/Modus-Übermittlung an Wavelog? | ⬜ Offen |
| Q-05 | Authentifizierung für die interne REST-API notwendig (lokales Netz vs. öffentlicher Zugriff)? | ⬜ Offen |
| Q-06 | Welche weiteren Hersteller / Geräte sollen unterstützt werden (über ICOM hinaus)? | ⬜ Offen |
| Q-07 | Muss HTTPS für die interne REST-API / Web-UI unterstützt werden, wenn der Zugriff über das lokale Netz erfolgt (nicht nur `localhost`)? Wenn ja: selbstsigniertes Zertifikat (`mkcert`) oder Let’s Encrypt? | ⬜ Offen |
| Q-08 | Soll der Wavelog API-Key verschlüsselt gespeichert werden (OS-Keychain / Windows Credential Manager / `cryptography`-Library) oder ist `chmod 600 .env` als Schutzmaßnahme ausreichend? | ⬜ Offen |

---

## 6. Änderungshistorie

| Datum | Änderung |
|---|---|
| 2026-03-03 | Initiale Erfassung der funktionalen Anforderungen |
