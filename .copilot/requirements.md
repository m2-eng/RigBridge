# RigBridge – Funktionale Anforderungen

> Diese Datei beschreibt **was** das System leisten muss.
> Sie dient als Referenz für Entwickler und AI-Assistenten, um:
> - den Umsetzungsstand zu prüfen
> - Inkonsistenzen zwischen Anforderung und Implementierung zu erkennen
> - neue Features gegen bestehende Anforderungen abzugleichen
> - den aktuellen fachlichen Soll-/Ist-Stand ohne Änderungshistorie zu dokumentieren
>
> **Hinweis:** Eine Änderungshistorie wird in diesem Dokument bewusst **nicht** geführt;
> Versionierung und Nachvollziehbarkeit erfolgen über Git.
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

| ID | Status | Anforderung |
|---|---|---|
| USB-01 | ✅ Umgesetzt | Das System stellt eine Verbindung zu einem Funkgerät über einen konfigurierbaren USB/Serial-Port her. |
| USB-02 | ✅ Umgesetzt | Der Port-Name ist konfigurierbar (Linux: `/dev/ttyUSB0`; Windows: `COM3`, aktuell `COM4`). |
| USB-03 | ✅ Umgesetzt | Die Baud-Rate ist konfigurierbar (Standardwert: 19200). |
| USB-04 | ✅ Umgesetzt | Weitere Serial-Parameter sind konfigurierbar: Datenbits, Stoppbits, Parität. |
| USB-05 | ✅ Umgesetzt | Das System erkennt, ob die USB-Verbindung aktiv oder unterbrochen ist, und meldet den Status über die API. |
| USB-06 | ✅ Umgesetzt | Bei Verbindungsabbruch versucht das System automatisch, die Verbindung nach konfigurierbarem Intervall wiederherzustellen. |
| USB-07 | ✅ Umgesetzt | Das System unterstützt sowohl Linux (`/dev/tty*`) als auch Windows (`COM*`) ohne Code-Änderung. |
| USB-08 | ✅ Umgesetzt | Die Verbindung zum Funkgerät soll zyklisch mittels 'read_transceiver_id' Befehl geprüft werden, da hier eine Antwort erwartet wird. Bei Verbindungsverlust wird automatisch ein Reconnect versucht. |
| USB-09 | ✅ Umgesetzt | **TransportManager für Ressourcen-Synchronisierung:** Nur EIN Befehl hat zu einem Zeitpunkt Zugriff auf die USB-Ressource. Verhindert Race Conditions zwischen Health-Check und API-Anfragen durch zentrale Koordination mit `asyncio.Lock()`. API-Anfragen erhalten HTTP 503 wenn Lock nicht in Zeit erworben wird. |

---

### 3.2 CI-V – Protokollverarbeitung

| ID | Status | Anforderung |
|---|---|---|
| CIV-01 | ✅ Umgesetzt | Das System baut CI-V-Befehle gemäß der gerätespezifischen YAML-Protokolldatei auf. |
| CIV-02 | ✅ Umgesetzt | Das System interpretiert CI-V-Antworten des Funkgeräts und wandelt sie in strukturierte Daten um. |
| CIV-03 | ✅ Umgesetzt | Unterstützte Befehle werden aus der YAML-Datei des aktiven Geräts geladen – kein Hardcoding von Befehlen im Code. |
| CIV-04 | ✅ Umgesetzt | Das System unterstützt den CI-V-Befehl zum Lesen der aktuellen Frequenz. |
| CIV-05 | ✅ Umgesetzt | Das System unterstützt den CI-V-Befehl zum Lesen des aktuellen Betriebsmodus (z.B. SSB, CW, FM). |
| CIV-06 | ✅ Umgesetzt | Das System unterstützt das Setzen der Frequenz über CI-V. |
| CIV-07 | ✅ Umgesetzt | Das System unterstützt das Setzen des Betriebsmodus über CI-V. |
| CIV-08 | ✅ Umgesetzt | Unbekannte oder fehlerhafte CI-V-Antworten werden geloggt und führen nicht zu einem Absturz. |

---

### 3.3 Protokolldefinitionen (YAML)

| ID | Status | Anforderung |
|---|---|---|
| YAML-01 | ✅ Umgesetzt | Pro Funkgerät existiert eine eigene YAML-Datei in `protocols/manufacturers/<hersteller>/`. |
| YAML-02 | 🔄 In Entwicklung | Pro Hersteller existiert eine Hersteller-YAML mit gemeinsamen Definitionen. |
| YAML-03 | ⬜ Ausstehend | In `protocols/general/` befinden sich herstellerübergreifende, generische Datentypen. |
| YAML-04 | ✅ Umgesetzt | Das System lädt die YAML-Datei beim Start anhand des konfigurierten Gerätenamens. |
| YAML-05 | 🔄 In Entwicklung | Das System validiert die YAML-Datei beim Laden gegen ein definiertes Schema. |
| YAML-06 | ✅ Umgesetzt | Ein unbekanntes oder fehlendes Gerät erzeugt eine klare Fehlermeldung beim Start. |
| YAML-07 | ✅ Umgesetzt | Neue Geräte können durch Ablegen einer YAML-Datei ohne Code-Änderung hinzugefügt werden. |

---

### 3.4 REST-API

| ID | Status | Anforderung |
|---|---|---|
| API-01 | ✅ Umgesetzt | Das System stellt eine REST-API auf einem konfigurierbaren Port bereit (Standard: 8080). |
| API-02 | ✅ Umgesetzt | `GET /api/status` – liefert den aktuellen Verbindungsstatus (USB, CAT). |
| API-03 | ✅ Umgesetzt | `GET /api/rig/frequency` – liefert die aktuelle Frequenz des Funkgeräts. |
| API-04 | ✅ Umgesetzt | `PUT /api/rig/frequency` – setzt die Frequenz des Funkgeräts. |
| API-05 | ✅ Umgesetzt | `GET /api/rig/mode` – liefert den aktuellen Betriebsmodus. |
| API-06 | ✅ Umgesetzt | `PUT /api/rig/mode` – setzt den Betriebsmodus. |
| API-07 | ✅ Umgesetzt | `GET /api/config` – liefert die aktuelle Konfiguration. Secrets (API-Keys, Passwörter) werden **niemals** zurückgeliefert (Felder werden durch `***` ersetzt oder weggelassen). |
| API-08 | ✅ Umgesetzt | `PUT /api/config` – speichert geänderte Konfigurationswerte persistent. |
| API-09 | ✅ Umgesetzt | `GET /health` – Health-Check-Endpunkt für Docker und Monitoring. |
| API-10 | ✅ Umgesetzt | Alle Fehlerantworten folgen dem einheitlichen Format: `{ "error": true, "code": "...", "message": "..." }`. |

---

### 3.5 CAT-Schnittstelle (Wavelog)

| ID | Status | Anforderung |
|---|---|---|
| CAT-01 | ⬜ Ausstehend | Das System stellt eine CAT-kompatible Schnittstelle auf einem konfigurierbaren Port bereit. |
| CAT-02 | ⬜ Ausstehend | Die Schnittstelle ist kompatibel mit Wavelog (Hamlib-Protokoll oder Wavelog-eigenes API). |
| CAT-03 | ⬜ Ausstehend | Der CAT-API-Key zur Authentifizierung gegenüber Wavelog ist konfigurierbar. |
| CAT-04 | ⬜ Ausstehend | Die Wavelog-API-URL ist konfigurierbar. |
| CAT-05 | ⬜ Ausstehend | Frequenz und Modus werden per Polling-Mechanismus automatisch an Wavelog gemeldet. |
| CAT-06 | ⬜ Ausstehend | Die CAT-Schnittstelle kann unabhängig von der USB-Verbindung aktiviert/deaktiviert werden. |
| CAT-07 | ⬜ Ausstehend | Verbindungsfehler zur Wavelog-Instanz werden geloggt und führen nicht zum Absturz. |

---

### 3.6 Konfiguration

| ID | Status | Anforderung |
|---|---|---|
| CFG-01 | ✅ Umgesetzt | Alle Konfigurationswerte werden persistent in einer JSON-Datei (config.json) gespeichert. |
| CFG-02 | ✅ Umgesetzt | Die Konfiguration wird beim Start automatisch geladen. |
| CFG-03 | 🔄 In Entwicklung | API-Keys und andere Secrets werden ausschließlich über einen Secret-Provider (HashiCorp Vault) bezogen. Eine Speicherung im Klartext in config.json ist nicht erlaubt. |
| CFG-04 | ✅ Umgesetzt | Konfigurierbare Parameter (Mindestumfang): USB-Port, Baud-Rate, Serial-Parameter, CAT-Port, Wavelog-URL, Wavelog-API-Key-Referenz, Gerätename, API-Port, Log-Level. |
| CFG-05 | ✅ Umgesetzt | Secrets (API-Keys) werden nicht im Klartext in Logdateien ausgegeben. |
| CFG-07 | ✅ Umgesetzt | Die Konfigurationsdatei kann sowohl von der Applikation als auch von Benutzer bearbeitet werden. |
| CFG-08 | ✅ Umgesetzt | Der Inhalt der Konfigurationsdatei soll in der Oberflächje angezeigt werden. |

---

### 3.10 Sicherheit & Verschlüsselung

| ID | Status | Anforderung |
|---|---|---|
| SEC-01 | ✅ Umgesetzt | Secrets (API-Key, Passwörter) werden niemals in API-Antworten zurückgeliefert. |
| SEC-02 | ✅ Umgesetzt | Secrets werden nicht in Log-Einträgen ausgegeben (auch nicht auf `DEBUG`-Level). |
| SEC-03 | ⬜ Ausstehend | Die Verbindung von RigBridge zu Wavelog erfolgt **ausschließlich über HTTPS** (TLS). `verify=False` ist verboten. |
| SEC-04 | ✅ Umgesetzt | Der API-Port (8080) wird nur auf `127.0.0.1` gebunden, solange kein Netzwerkzugriff konfiguriert ist. |
| SEC-05 | 🔄 In Entwicklung | HTTPS für die interne REST-API ist optional aktivierbar (konfigurierbarer Zertifikatspfad), wenn Zugriff über Netzwerk nötig ist. |
| SEC-06 | ⬜ Ausstehend | Wird HTTPS aktiviert, wird das TLS-Zertifikat validiert (kein `verify=False`). |
| SEC-07 | ✅ Umgesetzt | Der Wavelog API-Key wird als Passwort-Eingabefeld (`type="password"`) im UI dargestellt. |

---

### 3.7 Browser-Oberfläche (Frontend)

| ID | Status | Anforderung |
|---|---|---|
| UI-01 | ✅ Umgesetzt | Die Oberfläche ist über einen Browser erreichbar (kein separates Installationspaket nötig). |
| UI-02 | ✅ Umgesetzt | Die Oberfläche zeigt den aktuellen Verbindungsstatus (USB, CAT) an. |
| UI-03 | ✅ Umgesetzt | Einstellungsseite: USB-Verbindung konfigurieren (Port, Baud-Rate, Serial-Einstellungen). |
| UI-04 | ✅ Umgesetzt | Einstellungsseite: Gerät auswählen (Dropdown aus verfügbaren YAML-Gerätedateien). |
| UI-05 | ✅ Umgesetzt | Einstellungsseite: CAT-Schnittstelle konfigurieren (Wavelog-URL, API-Key, wenn Verbindung möglich, dann Dorp-Down für Stationsauswahl). |
| UI-06 | ✅ Umgesetzt | Einstellungsseite: API-Server-Port konfigurieren. |
| UI-07 | ✅ Umgesetzt | Alle Formulare bieten clientseitige Validierung vor dem Absenden. |
| UI-08 | ✅ Umgesetzt | Das UI ist responsiv und auf gängigen Desktop-Browsern nutzbar (Chrome, Firefox, Edge). |
| UI-09 | ✅ Umgesetzt | Das UI kommt ohne externe CSS-Frameworks aus (kein Bootstrap, Tailwind o.Ä.), sofern nicht explizit anders entschieden. |
| UI-10 | ✅ Umgesetzt | Es gibt **keine** Steuerungsmöglichkeit des Funkgeräts (Frequenz setzen, Modus wechseln) über das UI – nur Konfiguration. |
| UI-11 | ✅ Umgesetzt | Der Benutzer soll zwischen Light und Dark-Mode in der Benutzer Oberfläche umschalten können. |
| UI-12 | ✅ Umgesetzt | Der Benutzer soll die Möglichkeit haben die Farbgestalltung über eine css-Datei (Theme-Datei) zu beeinflussen. | 
| UI-13 | ✅ Umgesetzt | Diese Theme-Datei ist auch außerhalb des Docker Container sichtbar. (nur lesend für Docker Container, wenn nicht vorhanden die standard Theme verwenden) |
| UI-14 | ✅ Umgesetzt | Das Drop-Down bzgl. der Stataionsauswahl (CAT-Schnittstelle) bekommt seine Daten von Wavelog. |
| UI-15 | ✅ Umgesetzt | Die Oberfläche soll eine Test/Aktualisieren Button haben, welche die Verbindung zu Wavelog manuell testet. |
| UI-16 | ✅ Umgesetzt | Das Resultat des VErbindsungstests zu Wavelog soll in der Oberfläche angezeigt werden (keine PopUp-Anzeige; eine Status Zeile Einfügen). |

---

### 3.8 Logging

| ID | Status | Anforderung |
|---|---|---|
| LOG-01 | ✅ Umgesetzt | Das System schreibt strukturierte Log-Einträge (mindestens: Zeitstempel, Level, Modul, Nachricht). |
| LOG-02 | ✅ Umgesetzt | Das Log-Level ist konfigurierbar (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| LOG-03 | ✅ Umgesetzt | Logs werden auf `stdout` ausgegeben (Docker-kompatibel). |
| LOG-04 | ✅ Umgesetzt | Optionale Ausgabe in eine Logdatei ist konfigurierbar. |
| LOG-05 | ✅ Umgesetzt | **Alle** Log-Einträge (inkl. Uvicorn, Framework-Logs) verwenden das gleiche einheitliche Format: `[YYYY-MM-DD HH:MM:SS.mmm] [LEVEL] [MODULE] MESSAGE` |
| LOG-06 | ✅ Umgesetzt | Zeitstempel enthalten **Millisekunden** (nicht nur Sekunden). |

---

### 3.9 Deployment / Docker

> Docker gilt ausschließlich für **Linux**. Auf Windows wird die Anwendung nativ ausgeführt.

| ID | Status | Anforderung |
|---|---|---|
| DEP-01 | 🔄 In Entwicklung | Die Anwendung ist auf Linux mit `docker compose up` startbar. |
| DEP-02 | 🔄 In Entwicklung | Das Docker-Image basiert auf einem schlanken Linux-Basis-Image (Python slim). |
| DEP-03 | ✅ Umgesetzt | Der Container läuft ohne Root-Rechte (UID 1001). |
| DEP-04 | ✅ Umgesetzt | Konfigurationswerte werden ausschließlich über `config.json` bereitgestellt; Umgebungsvariablen sind kein Konfigurationskanal. |
| DEP-05 | ⬜ Ausstehend | USB-Geräte können dem Container auf Linux über den `devices`-Abschnitt übergeben werden. |
| DEP-06 | ✅ Umgesetzt | Ein Health-Check-Endpunkt ist im `docker-compose.yml` konfiguriert. |
| DEP-07 | ✅ Umgesetzt | Die Anwendung ist auf Windows **nativ** startbar (`python run_api.py`), ohne Docker. |
| DEP-08 | ✅ Umgesetzt | Privilege-Eskalation im Container ist verboten (`no-new-privileges:true`). |
| DEP-09 | ✅ Umgesetzt | Alle Linux-Capabilities sind gedroppt (`cap_drop: ALL`). |
| DEP-10 | ✅ Umgesetzt | Das Container-Dateisystem ist read-only; `/tmp` als tmpfs mit `noexec,nosuid`. |
| DEP-11 | ✅ Umgesetzt | Der API-Port wird nur auf `127.0.0.1` gebunden (kein offenes `0.0.0.0`). |
| DEP-12 | ✅ Umgesetzt | Das Base-Image ist auf eine spezifische Patch-Version gepinnt (kein `:latest`). |
| DEP-13 | ✅ Umgesetzt | Ressourcen-Limits (CPU und RAM) sind im `docker-compose.yml` definiert. |
| DEP-14 | ✅ Umgesetzt | Der Container läuft in einem dedizierten Docker-Netzwerk (keine Nutzung des default-Netzwerks). |
| DEP-15 | ⬜ Ausstehend | Das Image wird regelmäßig auf bekannte CVEs gescannt (`docker scout` oder `trivy`). |

---

## 4. Nicht-funktionale Anforderungen (Kurzübersicht)

> Details siehe [design-rules.md](design-rules.md) und [coding-rules.md](coding-rules.md).

| ID | Anforderung |
|---|---|
| NF-01 | Plattformkompatibilität: Linux mit Docker (Produktion), Windows nativ ohne Docker (Entwicklung) – ohne Code-Anpassung lauffähig. |
| NF-02 | Code-Qualität: PEP 8, Type Hints, Docstrings, `ruff`/`black` als Formatter. |
| NF-03 | Testbarkeit: Hardware-Zugriff (USB) ist abstrahiert und mockbar. |
| NF-04 | Erweiterbarkeit: Neue Funkgeräte werden ausschließlich über YAML-Dateien hinzugefügt. |
| NF-05 | Sicherheit: Keine Secrets in Quellcode oder Logs. |

---

## 5. Offene Punkte / Entscheidungen

| ID | Status | Frage |
|---|---|---|
| Q-02 | 🔄 In Klärung | Wie ist das CAT-Protokoll genau spezifiziert? (Hamlib-netrigctl, Wavelog-eigene API, …) |
| Q-05 | ⬜ Ausstehend | Authentifizierung für die interne REST-API notwendig (lokales Netz vs. öffentlicher Zugriff)? |
