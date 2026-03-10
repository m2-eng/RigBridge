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
>
> | Symbol | Bedeutung |
> |---|---|
> | ⬜ | Nicht begonnen |
> | 🔄 | In Arbeit / teilweise umgesetzt |
> | ✏️ | Geändert gegenüber ursprünglicher Anforderung |
> | ✅ | Umgesetzt |
> | ❌ | Verworfen / nicht mehr relevant |

---

## 1. Systemübersicht

RigBridge ist eine **Browser-Applikation**, die folgende Kernaufgaben erfüllt:

1. Verbindung zu einem Amateurfunkgerät über **USB / Serial** mittels **CI-V-Protokoll** (primär ICOM).
2. Bereitstellung einer **REST-API** für Frontend und externe Integrationen.
3. Bereitstellung einer **Wavelog-CAT-Integration** (HTTP-basiert, inkl. Polling und manueller Trigger).
4. Bereitstellung einer **Browser-Oberfläche** zur Konfiguration und Diagnose.

---

## 2. Akteure

| Akteur | Beschreibung |
|---|---|
| **Benutzer** | Bedient die Browser-Oberfläche zur Konfiguration |
| **Wavelog** | Externe Software, die CAT-Daten konsumiert |
| **Funkgerät** | Hardware (z.B. ICOM IC-7300/IC-905), die über USB/Serial angebunden ist |

---

## 3. Funktionale Anforderungen

### 3.1 Browser-Oberfläche (Frontend)

| ID | Status | Anforderung |
|---|---|---|
| UI-01 | ✅ | Die Oberfläche ist über einen Browser erreichbar (kein separates Installationspaket nötig). |
| UI-02 | ✏️ | Die Oberfläche zeigt den Verbindungsstatus als **USB-Status** und **CAT-Status** an. Ein LAN/SIM-spezifischer Status ist derzeit nicht separat visualisiert. |
| UI-03 | ✅ | Einstellungsseite für USB-Verbindung (Port, Baud-Rate, Serial-Parameter). |
| UI-04 | ✅ | Gerätauswahl per Dropdown aus verfügbaren Geräte-YAML-Dateien (`/api/devices`), ohne Hersteller-Meta-Dateien (`manufacturer.yaml`, `meta.yaml`). |
| UI-05 | ✅ | Einstellungsseite für Wavelog-Integration (URL, API-Key/Secret-Ref, Polling, Station). |
| UI-06 | ✏️ | Einstellungsseite für API-Server: **Host ist fest vorgegeben**, konfigurierbar sind Port (nur außerhalb Container), Log-Level, Health-Check, HTTPS-Flag. |
| UI-07 | ✅ | Formulare bieten clientseitige Validierung vor dem Absenden. |
| UI-08 | ✅ | UI ist responsiv und für gängige Desktop-Browser nutzbar (Chrome, Firefox, Edge). |
| UI-09 | ✅ | UI kommt ohne externes CSS-Framework aus. |
| UI-10 | ✅ | Keine direkte Funkgeräte-Steuerung über UI-Widgets; UI dient primär Konfiguration/Status/Diagnose (Befehlsausführung erfolgt über API, nicht als dedizierte Steueroberfläche). |
| UI-11 | ✅ | Benutzer kann zwischen Light- und Dark-Mode umschalten. |
| UI-12 | ✅ | Farbgestaltung ist über Theme-CSS anpassbar. |
| UI-13 | ✅ | Theme-Datei ist außerhalb des Containers verfügbar und wird eingebunden (`./theme.css` -> `src/frontend/assets/theme.css`). |
| UI-14 | ✅ | Stations-Dropdown bezieht Daten aus Wavelog (`/api/wavelog/stations`). |
| UI-15 | ✅ | Manuelle Test/Aktualisieren-Funktion für Wavelog-Verbindung ist vorhanden. |
| UI-16 | ✅ | Ergebnis des Wavelog-Verbindungstests wird als Statuszeile im UI angezeigt (kein Popup zwingend). |
| UI-17 | ✅ | UI zeigt verfügbare YAML-Kommandos inkl. Suche und Refresh (`/api/commands`). |
| UI-18 | ✅ | UI bietet einen Log-Bereich mit Filter/Limit und Abruf über API (`/api/logs`). |
| UI-19 | ⬜ | Wavelog-API-Key wird im UI als Passwortfeld (`type="password"`) dargestellt. |

### 3.2 Application Layer

#### 3.2.1 API

| ID | Status | Anforderung |
|---|---|---|
| API-01 | ✅ | REST-API auf konfigurierbarem Port (Standard 8080). |
| API-02 | ✅ | `GET /api/status` liefert Verbindungs-/Systemstatus inkl. CAT-Statusdaten. |
| API-03 | ✅ | `GET /api/rig/frequency` liefert aktuelle Frequenz. |
| API-04 | ✅ | `GET /api/rig/s-meter` liefert S-Meter-Werte (raw + dB). |
| API-05 | ✅ | `GET /api/rig/mode` liefert aktuellen Betriebsmodus. |
| API-06 | ✅ | `GET /api/commands` listet verfügbare YAML-Kommandos. |
| API-07 | ✅ | `GET /api/config` liefert Konfiguration mit Secret-Maskierung (`***`). |
| API-08 | ✅ | `PUT /api/config` speichert geänderte Konfigurationswerte persistent. |
| API-09 | ✅ | `GET /health` ist als Health-Check-Endpunkt verfügbar. |
| API-10 | ✅ | Fehlerantworten folgen dem einheitlichen Format `{ "error": true, "code": "...", "message": "..." }`. |
| API-11 | ✅ | `GET /api/rig/command?name=<command>` führt lesende YAML-Kommandos aus. |
| API-12 | ✅ | `PUT /api/rig/command` mit `{command, data}` führt schreibende YAML-Kommandos aus. |
| API-13 | 🔄 | `GET /api/rig/power` existiert, liefert aber abhängig von Gerät/YAML teils `501 Not Implemented`. |
| API-14 | ✅ | `GET /api/wavelog/test` testet Erreichbarkeit/Auth gegen Wavelog. |
| API-15 | ✅ | `GET /api/license` liefert Lizenzinhalt. |
| API-16 | ✅ | `GET /api/wavelog/stations` liefert Stationsliste für UI-Dropdown. |
| API-17 | ✅ | `GET /api/devices` scannt verfügbare Geräteprotokolle. |
| API-18 | ✅ | `GET /api/logs` liefert In-Memory-Logs (Limit/Level/Sortierung). |
| API-19 | ✅ | CAT-Steuerendpunkte sind vorhanden: `/api/cat/start`, `/api/cat/stop`, `/api/cat/status`, `/api/cat/send-now`. |

#### 3.2.2 Wavelog Integration (CAT)

| ID | Status | Anforderung |
|---|---|---|
| CAT-01 | ✅ | Wavelog-Radio-API (`index.php/api/radio`) wird mit Payload (`key`, `radio`, `frequency`, `mode`, `timestamp`, optional `power`, optional `station_id`) bedient. |
| CAT-02 | ✅ | Wavelog-API-Key ist konfigurierbar (direkter Key oder Secret-Referenz). |
| CAT-03 | ✅ | Wavelog-API-URL ist konfigurierbar. |
| CAT-04 | ✅ | Frequenz und Modus werden zyklisch an Wavelog gemeldet (Polling-Task). |
| CAT-05 | ✅ | CAT-Integration kann unabhängig von USB aktiviert/deaktiviert werden. |
| CAT-06 | ✅ | Verbindungsfehler zu Wavelog werden geloggt und führen nicht zum Absturz. |
| CAT-07 | ✅ | Radio-Name ist konfigurierbar und wird im Payload gesendet. |
| CAT-08 | ✅ | Station-ID ist optional konfigurierbar und wird bei gesetztem Wert übertragen. |
| CAT-09 | ✅ | Fallback bei unvollständigem Radio-Status: Update wird übersprungen, kein ungültiger Payload. |
| CAT-10 | 🔄 | Optionales Feld `power` wird nur bei verfügbarer Leistung gesendet; geräteabhängig noch nicht flächendeckend. |
| CAT-11 | 🔄 | WaveLogGate HTTP (`.../{frequency}/{mode}`) und WebSocket-Client sind im CAT-Client vorhanden, aber End-to-End-Bridge-Fluss ist nicht vollständig produktiv verschaltet. |

### 3.3 Interpreter Layer

#### 3.3.1 Protokolldefinitionen (YAML)

| ID | Status | Anforderung |
|---|---|---|
| YAML-01 | ✅ | Pro Funkgerät existiert eine eigene YAML-Datei in `protocols/manufacturers/<hersteller>/`. |
| YAML-02 | ✅ | Pro Hersteller kann eine Hersteller-YAML mit gemeinsamen Definitionen existieren. |
| YAML-03 | ⬜ | In `protocols/general/` befinden sich herstellerübergreifende, generische Datentypen. |
| YAML-04 | ✅ | System lädt beim Start die konfigurierte Geräte-YAML. |
| YAML-05 | 🔄 | YAML-Validierung gegen konsistentes Schema ist teilweise vorhanden, aber nicht vollständig abgeschlossen. |
| YAML-06 | ✅ | Unbekanntes/fehlendes Gerät erzeugt klare Fehlermeldung. |
| YAML-07 | ✅ | Neue Geräte können durch Ablage einer YAML-Datei ohne Codeänderung ergänzt werden. |
| YAML-08 | ⬜ | Referenzauflösung gemeinsamer Datentypen (Hersteller/Generisch) beim Laden ist noch ausstehend. |

#### 3.3.2 CI-V Protokollverarbeitung

| ID | Status | Anforderung |
|---|---|---|
| CIV-01 | ✅ | CI-V-Befehle werden gemäß gerätespezifischer YAML aufgebaut. |
| CIV-02 | ✅ | CI-V-Antworten werden interpretiert und in strukturierte Daten gewandelt. |
| CIV-03 | ✅ | Unterstützte Befehle werden aus YAML geladen (kein Command-Hardcoding als Primärquelle). |
| CIV-04 | ✅ | Lesen der Frequenz über CI-V ist unterstützt. |
| CIV-05 | ✅ | Lesen des Modus über CI-V ist unterstützt. |
| CIV-06 | ✅ | Setzen der Frequenz über CI-V ist unterstützt. |
| CIV-07 | ✅ | Setzen des Modus über CI-V ist unterstützt. |
| CIV-08 | ✅ | Unbekannte/fehlerhafte CI-V-Antworten werden geloggt, ohne Absturz. |

#### 3.3.3 Unsolicited Frames Handling

| ID | Status | Anforderung |
|---|---|---|
| UNSOL-01 | 🔄 | System soll zwischen solicited Responses und unsolicited Frames unterscheiden. |
| UNSOL-02 | 🔄 | Matching über `cmd`/`subcmd` soll Response-Zuordnung steuern. |
| UNSOL-03 | 🔄 | Unsolicited Frames sollen nicht als Command-Response fehlinterpretiert werden. |
| UNSOL-04 | 🔄 | Verwerfungen unsolicited Frames sollen auf DEBUG nachvollziehbar sein. |
| UNSOL-05 | 🔄 | Timeout-Schutz gegen falsches Frame-Matching ist teilweise vorhanden, aber nicht vollständig command-filter-basiert. |
| UNSOL-06 | ✅ | Empfangspfad ist thread-safe synchronisiert (Serial-Lock). |
| UNSOL-07 | ⬜ | Spezifische Methode `read_response_with_command_filter()` in `USBConnection` ist noch nicht umgesetzt. |
| UNSOL-08 | ⬜ | Vollständiges Response-Tracking-System (wartende Handler vs Event-Queue) ist ausstehend. |
| UNSOL-09 | 🔄 | Grundstruktur `_expected_responses` ist vorhanden, aber noch nicht funktional angebunden. |
| UNSOL-10 | ⬜ | Background-Reader-Routing auf erwartete Antworten vs Queue ist noch ausstehend (TODO im Code vorhanden). |

#### 3.3.4 Protocol Manager

| ID | Status | Anforderung |
|---|---|---|
| PROT-01 | ✅ | ProtocolManager als zentrale Verwaltungsinstanz ist implementiert. |
| PROT-02 | ✅ | ProtocolManager ist als Singleton umgesetzt. |
| PROT-03 | ✅ | BaseProtocol definiert zentrale abstrakte Schnittstellen. |
| PROT-04 | ✅ | Convenience-Methoden `get_frequency()`, `get_mode()`, `get_power()` sind vorhanden. |
| PROT-05 | ✅ | `CIVProtocol` implementiert BaseProtocol für CI-V. |
| PROT-06 | ✅ | ProtocolManager delegiert Kommandos an aktive Protokollinstanz. |
| PROT-07 | ✅ | Unsolicited-Handling mit Vorvalidierung und Delegation ist implementiert. |
| PROT-08 | ✅ | Radio-ID-Validierung vor Weiterleitung ist implementiert. |
| PROT-09 | ✅ | Registrierung externer unsolicited Handler ist möglich. |
| PROT-10 | 🔄 | Vollständiges semantisches Parsing spezifischer unsolicited Frame-Typen ist noch nicht abgeschlossen. |
| PROT-11 | 🔄 | Power-Unterstützung ist vorhanden, aber YAML-/Geräteabhängigkeit limitiert Vollständigkeit. |
| PROT-12 | ✅ | Debug-Infos über aktives Protokoll und Kommandos sind abrufbar. |
| PROT-13 | ✅ | ProtocolManager wird bei USB-/Device-Config-Änderungen invalidiert und neu aufgebaut. |
| PROT-14 | ✅ | Architektur ist für zusätzliche Protokolle erweiterbar. |

### 3.4 Transport Layer

#### 3.4.1 BaseTransport und Event-System

| ID | Status | Anforderung |
|---|---|---|
| TM-01 | ✅ | BaseTransport definiert abstrakte Schnittstelle für Transporte (USB/LAN/SIM). |
| TM-02 | ✅ | Hook-Methoden für transport-spezifische Background-Reader sind vorhanden. |
| TM-03 | ✅ | Event-Queue für unsolicited Frames ist vorhanden. |
| TM-04 | ✅ | `_push_unsolicited_frame()` legt non-blocking in Queue ab. |
| EVT-01 | ✅ | Ereignisbasiertes Datenempfangsmodell statt Polling für unsolicited Frames ist umgesetzt. |
| EVT-02 | ✅ | Queue-basierte Verarbeitung (`asyncio.Queue`) ist umgesetzt. |
| EVT-03 | ✅ | Kontinuierlicher Background-Reader überwacht eingehende Frames. |
| EVT-04 | ✅ | Reader startet bei `connect()` und läuft unabhängig von Handler-Registrierungen. |
| EVT-05 | ✅ | Architektur reduziert Last gegenüber aktivem Polling. |
| EVT-06 | ⬜ | Trennung erwarteter Antworten vs unsolicited Frames im Reader ist noch nicht fertig umgesetzt. |

#### 3.4.2 USB Connection

| ID | Status | Anforderung |
|---|---|---|
| USB-01 | ✅ | Verbindung über konfigurierbaren USB/Serial-Port wird aufgebaut. |
| USB-02 | ✅ | Portname ist konfigurierbar (Linux `/dev/tty*`, Windows `COM*`). |
| USB-03 | ✅ | Baud-Rate ist konfigurierbar. |
| USB-04 | ✅ | Datenbits, Stoppbits, Parität sind konfigurierbar. |
| USB-05 | ✅ | Verbindungsstatus wird erkannt und über API bereitgestellt. |
| USB-06 | ✅ | Bei Verbindungsabbruch erfolgt Reconnect-Versuch im konfigurierten Intervall. |
| USB-07 | ✅ | Linux und Windows werden ohne Codeänderung unterstützt. |
| USB-08 | ✅ | Zyklischer Health-Check via `read_transceiver_id` ist implementiert. |
| USB-09 | ✅ | Synchronisierung konkurrierender Zugriffe erfolgt zentral über Transport/Protocol-Mechanismen. |
| USB-10 | ✅ | `_continuous_reader()` als Background-Task ist implementiert. |
| USB-11 | ✏️ | Blockierende Serial-Reads werden im Reader via `run_in_executor` in Threadpool ausgelagert (statt `asyncio.to_thread`). |

### 3.5 Allgemeine Anforderungen

#### 3.5.1 Konfiguration

| ID | Status | Anforderung |
|---|---|---|
| CFG-01 | ✅ | Konfigurationswerte werden persistent in `config.json` gespeichert. |
| CFG-02 | ✅ | Konfiguration wird beim Start automatisch geladen. |
| CFG-03 | ✅ | Wavelog-API-Key kann direkt oder als Secret-Referenz (`path#key`) konfiguriert werden. |
| CFG-04 | ✅ | Mindestumfang konfigurierbarer Parameter ist abgedeckt (USB, API, Wavelog, Device). |
| CFG-05 | ✅ | Secrets werden in Logs redaktioniert. |
| CFG-06 | ✅ | `GET /api/config` maskiert Secret-Felder. |
| CFG-07 | ✅ | Konfigurationsdatei ist sowohl durch Anwendung als auch Benutzer änderbar. |
| CFG-08 | ✅ | Konfigurationsinhalte sind über UI sichtbar und editierbar (mit Laufzeitrestriktionen). |

#### 3.5.2 Sicherheit und TLS

| ID | Status | Anforderung |
|---|---|---|
| SEC-01 | ✅ | Secrets werden nicht in API-Responses im Klartext zurückgeliefert. |
| SEC-02 | ✅ | Secrets werden nicht im Log im Klartext ausgegeben. |
| SEC-03 | ⬜ | Verbindung RigBridge -> Wavelog wird ausschließlich über HTTPS erzwungen. |
| SEC-04 | ✏️ | API-Host ist im Backend fest auf `0.0.0.0`; tatsächliche Exponierung wird über Docker-Port-Binding (`127.0.0.1:...`) begrenzt. |
| SEC-05 | 🔄 | HTTPS-Option für interne REST-API ist in Config/UI vorhanden, aber Serverstart mit TLS-Zertifikaten ist noch nicht vollständig verschaltet. |
| SEC-06 | ⬜ | Wenn HTTPS aktiv ist, muss Zertifikatsvalidierung durchgängig sichergestellt sein (kein unsicherer Fallback). |
| SEC-07 | ⬜ | Wavelog-API-Key-Feld im UI als Passwortfeld (`type="password"`). |

#### 3.5.3 Logging

| ID | Status | Anforderung |
|---|---|---|
| LOG-01 | ✅ | Strukturierte Logs (Zeit, Level, Modul, Nachricht) sind umgesetzt. |
| LOG-02 | ✅ | Log-Level ist konfigurierbar (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| LOG-03 | ✅ | Logs werden Docker-kompatibel auf stdout ausgegeben. |
| LOG-04 | ✅ | Optionale Dateiausgabe ist im Logger vorgesehen (FileHandler). |
| LOG-05 | ✅ | Einheitliches Log-Format wird inkl. Uvicorn-Loggern angewendet. |
| LOG-06 | ✅ | Zeitstempel enthalten Millisekunden. |

#### 3.5.4 Deployment / Docker

> Docker gilt für Linux. Auf Windows ist der primäre Weg der native Start.

| ID | Status | Anforderung |
|---|---|---|
| DEP-01 | 🔄 | Anwendung ist per `docker compose up` betreibbar (abhängig von vorhandenem Image/Umgebung). |
| DEP-02 | ✅ | Docker-Image basiert auf schlankem Python-Slim-Image. |
| DEP-03 | ✅ | Container läuft ohne Root-Rechte (UID 1001 / `appuser`). |
| DEP-04 | ✅ | App-Konfiguration läuft über `config.json`; Env-Variablen steuern primär Container-/Compose-Runtime. |
| DEP-05 | ✅ | USB-Geräte können per `devices`-Abschnitt in den Container durchgereicht werden. |
| DEP-06 | ✅ | Health-Check ist in `docker-compose.yml` konfiguriert. |
| DEP-07 | ✅ | Anwendung ist auf Windows nativ (`python run_api.py`) startbar. |
| DEP-08 | ✅ | `no-new-privileges:true` ist gesetzt. |
| DEP-09 | ✅ | `cap_drop: ALL` ist gesetzt. |
| DEP-10 | ✅ | Read-only Root-FS + `tmpfs` für `/tmp` ist gesetzt. |
| DEP-11 | ✅ | Standard-Portmapping bindet auf `127.0.0.1` (über Compose-`BIND_ADDRESS`). |
| DEP-12 | ⬜ | Base-Image ist auf Patch-Version gepinnt (derzeit nur `python:3.11-slim`). |
| DEP-13 | ✅ | Ressourcenlimits für CPU/RAM sind in Compose definiert. |
| DEP-14 | ✅ | Dediziertes Docker-Netzwerk wird verwendet. |
| DEP-15 | ⬜ | Regelmäßiger CVE-Scan (z.B. `docker scout`/`trivy`) ist noch nicht als Prozess verankert. |

---

## 4. Nicht-funktionale Anforderungen (Kurz)

| ID | Anforderung |
|---|---|
| NF-01 | Plattformkompatibilität: Linux (Docker), Windows (nativ), ohne Codeanpassung lauffähig. |
| NF-02 | Code-Qualität: PEP 8, Type Hints, klare Modulgrenzen, testbarer Aufbau. |
| NF-03 | Testbarkeit: Hardware-Zugriff ist abstrahiert und mockbar. |
| NF-04 | Erweiterbarkeit: Neue Funkgeräte primär über YAML-Dateien integrierbar. |
| NF-05 | Sicherheit: Keine Secrets in Sourcecode/Logs/API-Responses im Klartext. |
