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
> | 🔄 | Geändert |
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

## 3.1 Browser-Oberfläche (Frontend)

| ID | Status | Anforderung |
|---|---|---|
| UI-01 | ✅ Umgesetzt | Die Oberfläche ist über einen Browser erreichbar (kein separates Installationspaket nötig). |
| UI-02 | 🔄 Geändert  | Die Oberfläche zeigt den aktuellen Verbindungsstatus (USB/LAN, CAT) an, wobei nur der aktive Verbindungstyp (USB/LAN/SIM) angezeigt wird. |
|---|---|---|
| UI-03 | ✅ Umgesetzt | Einstellungsseite: USB-Verbindung konfigurieren (Port, Baud-Rate, Serial-Einstellungen). |
|---|---|---|
| UI-04 | 🔄 Geändert  | Einstellungsseite: Gerät auswählen (Dropdown aus verfügbaren YAML-Gerätedateien ohne die Hersteller YAML-Datei). |
|---|---|---|
| UI-05 | ✅ Umgesetzt | Einstellungsseite: CAT-Schnittstelle konfigurieren (Wavelog-URL, API-Key, wenn Verbindung möglich, dann Dorp-Down für Stationsauswahl). |
| UI-14 | ✅ Umgesetzt | Das Drop-Down bzgl. der Stataionsauswahl (CAT-Schnittstelle) bekommt seine Daten von Wavelog. |
| UI-15 | ✅ Umgesetzt | Die Oberfläche soll eine Test/Aktualisieren Button haben, welche die Verbindung zu Wavelog manuell testet. |
| UI-16 | ✅ Umgesetzt | Das Resultat des Verbindsungstests zu Wavelog soll in der Oberfläche angezeigt werden (keine PopUp-Anzeige; eine Status Zeile Einfügen). |
|---|---|---|
| UI-06 | 🔄 Geändert  | Einstellungsseite: API-Server konfigurieren. (Host nur lesend, Server-Port, Log-Level, HTTPS Aktivierung). |
|---|---|---|
| UI-07 | ✅ Umgesetzt | Alle Formulare bieten clientseitige Validierung vor dem Absenden. |
| UI-08 | ✅ Umgesetzt | Das UI ist responsiv und auf gängigen Desktop-Browsern nutzbar (Chrome, Firefox, Edge). |
| UI-09 | ✅ Umgesetzt | Das UI kommt ohne externe CSS-Frameworks aus (kein Bootstrap, Tailwind o.Ä.), sofern nicht explizit anders entschieden. |
| UI-10 | ✅ Umgesetzt | Es gibt **keine** Steuerungsmöglichkeit des Funkgeräts (Frequenz setzen, Modus wechseln) über das UI – nur Konfiguration. |
| UI-11 | ✅ Umgesetzt | Der Benutzer soll zwischen Light und Dark-Mode in der Benutzer Oberfläche umschalten können. |
| UI-12 | ✅ Umgesetzt | Der Benutzer soll die Möglichkeit haben die Farbgestalltung über eine css-Datei (Theme-Datei) zu beeinflussen. | 
| UI-13 | ✅ Umgesetzt | Diese Theme-Datei ist auch außerhalb des Docker Container sichtbar. (nur lesend für Docker Container, wenn nicht vorhanden die standard Theme verwenden) |


## 3.2 Application Layer

### 3.2.1 API

| ID | Status | Anforderung |
|---|---|---|
| API-01 | ✅ Umgesetzt | Das System stellt eine REST-API auf einem konfigurierbaren Port bereit (Standard: 8080). |
| API-14 | ✅ Umgesetzt | Nur die hier gelisteten APIs sollen implementiert werden. Alte `/command/{command_name}` Endpoints wurden entfernt. |
| API-02 | ✅ Umgesetzt | `GET /api/status` – liefert den aktuellen Verbindungsstatus (USB/LAN/SIM, CAT). |
| API-11 | ✅ Umgesetzt | `GET /api/rig/command?name=<command>` – generische API: Führt einen lesenden Befehl aus der YAML-Befehlsliste aus. |
| API-12 | ✅ Umgesetzt | `PUT /api/rig/command` mit Body `{command: str, data: dict}` – generische API: Führt einen schreibenden Befehl aus der YAML-Befehlsliste aus. |
| API-03 | ✅ Umgesetzt | `GET /api/rig/frequency` – liefert die aktuelle Frequenz des Funkgeräts. |
| API-05 | ✅ Umgesetzt | `GET /api/rig/mode` – liefert den aktuellen Betriebsmodus. |
| API-13 | 🔄 In Vorbereitung | `GET /api/rig/power` – liefert die aktuell eingestellte Sendeleistung in Watt [W] zurück. Endpoint existiert, aber Implementierung abhängig von YAML-Definitionen und Geräteunterstützung. |
| API-07 | ✅ Umgesetzt | `GET /api/config` – liefert die aktuelle Konfiguration. Secrets (API-Keys, Passwörter) werden **niemals** zurückgeliefert (Felder werden durch `***` ersetzt oder  weggelassen). |
| API-08 | ✅ Umgesetzt | `PUT /api/config` – speichert geänderte Konfigurationswerte persistent. |
| API-09 | ✅ Umgesetzt | `GET /health` – Health-Check-Endpunkt für Docker und Monitoring. |
| API-15 | ✅ Umgesetzt | `GET /api/license` – Rückgabe der Lizenz der Applikation |
| API-10 | ✅ Umgesetzt | Alle Fehlerantworten folgen dem einheitlichen Format: `{ "error": true, "code": "...", "message": "..." }`. |

### 3.2.2 Wavelog Integration

#### CAT Schnittstelle

| ID | Status | Anforderung |
|---|---|---|
| CAT-01 | ✅ Umgesetzt | Das System stellt eine CAT-kompatible Schnittstelle auf einem konfigurierbaren Port bereit. |
| CAT-02 | ✅ Umgesetzt | Die Schnittstelle ist kompatibel mit Wavelog über die Radio-API (`/index.php/api/radio`). |
| CAT-03 | ✅ Umgesetzt | Der CAT-API-Key zur Authentifizierung gegenüber Wavelog ist konfigurierbar. |
| CAT-04 | ✅ Umgesetzt | Die Wavelog-API-URL ist konfigurierbar. |
| CAT-05 | ✅ Umgesetzt | Frequenz und Modus werden per API-Request an Wavelog gemeldet (JSON-Payload mit `key`, `radio`, `frequency`, `mode`, `timestamp`, optional `power`). |
| CAT-06 | ✅ Umgesetzt | Die CAT-Schnittstelle kann unabhängig von der USB-Verbindung aktiviert/deaktiviert werden. |
| CAT-07 | ✅ Umgesetzt | Verbindungsfehler zur Wavelog-Instanz werden geloggt und führen nicht zum Absturz. |
| CAT-08 | ✅ Umgesetzt | Das System unterstützt WaveLogGate-Integration: HTTP-Endpoint (`http://localhost:54321/{frequency}/{mode}`) für QSY-Befehle (Bandmap-Klicks). |
| CAT-09 | ✅ Umgesetzt | Das System unterstützt WaveLogGate WebSocket (`ws://localhost:54322`) zum Empfangen von Radio-Status-Events. |
| CAT-10 | ✅ Umgesetzt | Der Radio-Name (z.B. "ICOM IC-905") ist konfigurierbar und wird im API-Payload an Wavelog gesendet. |
| CAT-11 | ✅ Umgesetzt | Die Station-ID ist optional konfigurierbar für Multi-Station-Setups. |
| CAT-12 | ✅ Umgesetzt | Bridge-Modus: Radio-Status kann von WaveLogGate WebSocket empfangen und automatisch an Wavelog weitergeleitet werden. |
| CAT-13 | ✅ Umgesetzt | Payload-Feld `power`: Optional in Wavelog-Payload enthalten; wenn kein CI-V-Befehl im YAML vorhanden, wird das Feld weggelassen (nicht als Dummy gesendet). Wird mit `power_w` Parameter von `send_radio_status()` übertragen wenn verfügbar. |
| CAT-14 | ✅ Umgesetzt | CAT-Statusübertragung aus USB-Daten ist aktiv für Frequenz/Modus. Fallback bei unvollständigen USB-Daten: Status wird nicht versendet; geloggt als `Radio-Status unvollständig, überspringe Update`. Verhindert ungültige Wavelog-Einträge. |
| CAT-15 | ⬜ Ausstehend | Für alle im Wavelog-Payload genutzten Felder existieren validierte CI-V-Befehlsmappings pro Gerät (YAML-abhängig). Aktuell fehlen je nach Gerät einzelne Felder (insb. `power`). |
| CAT-16 | ✅ Umgesetzt | Bei aktivierter Wavelog Integration werden Daten zyklisch (Polling-Intervall, Standard 5s) an Wavelog gesendet sobald eine Radio-Verbindung aktiv ist. Implementiert via Background-Task `start_cat_update_task()` mit Endpoints `/cat/start`, `/cat/stop`, `/cat/send-now`. |

**Hinweis zum aktuellen Payload-Stand (`/index.php/api/radio`):**
- `key`: Umgesetzt
- `radio`: Umgesetzt
- `frequency`: Umgesetzt (USB/CI-V)
- `mode`: Umgesetzt (USB/CI-V)
- `timestamp`: Umgesetzt
- `power`: Teilweise umgesetzt (optional, derzeit ggf. leer/Dummy wenn kein CI-V-Befehl verfügbar)

## 3.3 Interpreter Layer

### 3.3.1 Protokolldefinitionen (YAML)

| ID | Status | Anforderung |
|---|---|---|
| YAML-01 | ✅ Umgesetzt | Pro Funkgerät existiert eine eigene YAML-Datei in `protocols/manufacturers/<hersteller>/`. |
| YAML-02 | 🔄 Geändert | Pro Hersteller kann eine Hersteller-YAML mit gemeinsamen Definitionen existieren. |
| YAML-03 | ⬜ Ausstehend | In `protocols/general/` befinden sich herstellerübergreifende, generische Datentypen. |
| YAML-08 | ⬜ Ausstehend | Beim Laden der YAML-Gerätedatei werden die Datentypen, welche auf eine gemeinsame Definition (Hersteller und/oder generisch) verweisen durch jene ersetzt. |
|---|---|---|
| YAML-04 | ✅ Umgesetzt | Das System lädt die YAML-Datei beim Start anhand des konfigurierten Gerätenamens. |
| YAML-05 | 🔄 In Entwicklung | Das System validiert die YAML-Datei beim Laden gegen ein definiertes Schema. |
| YAML-06 | ✅ Umgesetzt | Ein unbekanntes oder fehlendes Gerät erzeugt eine klare Fehlermeldung beim Start. |
| YAML-07 | ✅ Umgesetzt | Neue Geräte können durch Ablegen einer YAML-Datei ohne Code-Änderung hinzugefügt werden. |

### 3.3.2 CI-V – Protokollverarbeitung

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

### 3.3.3 Unsolicited Frames Handling

| ID | Status | Anforderung |
|---|---|---|
| UNSOL-01 | 🔄 In Arbeit | Das System muss zwischen **Responses auf angefragte Befehle** und **Unsolicited Frames** (von der Hardware selbst initiiert) unterscheiden können. |
| UNSOL-02 | 🔄 In Arbeit | Die Unterscheidung erfolgt durch Vergleich der CI-V Command-Bytes: `cmd` (Main-Command) und optional `subcmd` (Sub-Command). Ein Response passt nur, wenn beide Bytes dem **gesendeten Request** entsprechen. |
| UNSOL-03 | 🔄 In Arbeit | Unsolicited Frames werden **verworfen** und nicht als Befehlsantwort interpretiert. Optional Pufferung für spätere Event-Verarbeitung (future feature). |
| UNSOL-04 | 🔄 In Arbeit | Verworfene Unsolicited Frames werden auf **DEBUG-Level** geloggt: `"Unsolicited Frame verworfen: cmd=0x03, subcmd=[0x00], hex=FE FE 94 E0 03 00 ..."` |
| UNSOL-05 | 🔄 In Arbeit | **Timeout-Schutz:** Wenn kein passendes Response-Frame innerhalb eines konfigurierbaren Zeitlimits (z.B. 0,7s für normale Befehle) empfangen wird, wird die Funktion mit Fehler zurückgegeben, nicht mit Unsolicited-Frame fehlinterpretiert. |
| UNSOL-06 | 🔄 In Arbeit | Die Receive-Funktion ist **Thread-Safe** durch Verwendung des existierenden TransportManager-Locks (`asyncio.Lock()`). Nur ein Befehl hat gleichzeitig Zugriff auf die Empfangsfunktion. |
| UNSOL-07 | 🔄 In Arbeit | Implementiert als neue Methode `read_response_with_command_filter()` in `USBConnection`, die den erwarteten `cmd` und `subcmd` als Parameter erwartet. Fallback auf alte `read_response()` ist nicht mehr notwendig, sobald diese vollständig migriert ist. |
| UNSOL-08 | ⬜ Ausstehend | Das System implementiert ein **Response-Tracking-System**, das erwartete Antworten (solicited) von unsolicited frames unterscheidet. Erwartete Antworten werden an den wartenden Command-Handler weitergeleitet, unsolicited frames in die Event-Queue. |
| UNSOL-09 | ⬜ Ausstehend | Beim Senden eines Befehls wird der erwartete Response-Frame (cmd/subcmd) im System registriert (z.B. via `_expected_responses`-Set oder ähnliche Tracking-Struktur). Nach Erhalt der Antwort oder Timeout wird die Registrierung entfernt. |
| UNSOL-10 | ⬜ Ausstehend | Der Background-Reader prüft eingehende Frames gegen registrierte erwartete Antworten: Bei Match → Weiterleitung an Command-Handler (wartende Coroutine), bei Mismatch → unsolicited frame in Event-Queue für Handler-Callbacks. |

### 3.3.4 Protocol Manager

| ID | Status | Anforderung |
|---|---|---|
| PROT-01 | ✅ Umgesetzt | Das System implementiert einen **ProtocolManager** als zentrale Verwaltungsinstanz für Protokoll-Implementierungen, analog zum TransportManager eine Schicht oberhalb des Transport-Layers. |
| PROT-02 | ✅ Umgesetzt | Der ProtocolManager ist als **Singleton** implementiert, um systemweit eine einzige Protokoll-Instanz zu garantieren. |
| PROT-03 | ✅ Umgesetzt | **BaseProtocol** definiert abstrakte Basisklasse für alle Protokolle mit Methoden: `execute_command()`, `list_commands()`, `is_valid_radio_id()`, `handle_unsolicited_frame()`. |
| PROT-04 | ✅ Umgesetzt | BaseProtocol stellt **Convenience-Methoden** bereit: `get_frequency()`, `get_mode()`, `get_power()` – intern delegieren diese an `execute_command()`. |
| PROT-05 | ✅ Umgesetzt | **CIVProtocol** implementiert BaseProtocol für CI-V-Protokoll (ICOM), delegiert Befehlsausführung an internen `CIVCommandExecutor`. |
| PROT-06 | ✅ Umgesetzt | Der ProtocolManager leitet alle **Command-Aufrufe** (generisch und Convenience) an die aktive Protokoll-Instanz weiter. |
| PROT-07 | ✅ Umgesetzt | **Unsolicited Frame Handling:** Transport registriert Handler beim ProtocolManager, dieser validiert Radio-ID und leitet Frames an Protokoll-Instanz weiter. |
| PROT-08 | ✅ Umgesetzt | **Radio-ID-Validierung:** ProtocolManager verwirft Frames mit ungültiger Radio-ID (z.B. falsche Preamble, falsche Adresse) vor Weiterleitung an Protokoll. |
| PROT-09 | ✅ Umgesetzt | **Wavelog-Integration Vorbereitung:** ProtocolManager unterstützt Registrierung von Unsolicited-Frame-Handlern (`register_unsolicited_handler()`) für spätere Auto-Weiterleitung an Wavelog. |
| PROT-10 | 🔄 In Arbeit | Unsolicited Frame Handler werden benachrichtigt, wenn spezifische Frames empfangen werden (Frequency-Change, Mode-Change) – vollständiges Frame-Parsing in Phase 2. |
| PROT-11 | 🔄 In Arbeit | **Power-Feature Support:** BaseProtocol definiert `get_power()` Methoden, ProtocolManager leitet diese weiter. Vollständige Implementierung abhängig von YAML-Definitionen. |
| PROT-12 | ✅ Umgesetzt | Der ProtocolManager stellt Debug-Informationen bereit (`get_protocol_info()`), die aktuelles Protokoll, verfügbare Commands und Status zurückgeben. |
| PROT-13 | ✅ Umgesetzt | Bei USB-Config-Änderung wird ProtocolManager-Instanz invalidiert und bei nächstem API-Zugriff neu initialisiert (analog TransportManager). |
| PROT-14 | ✅ Umgesetzt | Die Architektur ist **erweiterbar**: Neue Protokolle (z.B. CAT, HAMLib) können durch Implementierung von BaseProtocol ohne Änderung an ProtocolManager oder API hinzugefügt werden. |

## 3.4 Transport Manager

### 3.4.1 Connection Base Class

| ID | Status | Anforderung |
|---|---|---|
| TM-01 | ✅ Umgesetzt | BaseTransport definiert abstrakte Schnittstelle für alle Transport-Implementierungen (USB, LAN, SIM) mit gemeinsamer Funktionalität. |
| TM-02 | ✅ Umgesetzt | Hook-Methoden `_start_background_reader()` und `_stop_background_reader()` sind in BaseTransport definiert und ermöglichen Transport-spezifische Background-Reader-Implementierungen. |
| TM-03 | ✅ Umgesetzt | BaseTransport stellt Event-Queue (`_unsolicited_queue`) für unsolicited frames bereit und verwaltet Handler-Registrierung. |
| TM-04 | ✅ Umgesetzt | Methode `_push_unsolicited_frame(frame)` ist non-blocking und legt unsolicited frames in Event-Queue für Handler-Callbacks. |

### 3.4.2 Connection State Manager

### 3.4.3 Event-basiertes Datenempfangs-System

| ID | Status | Anforderung |
|---|---|---|
| EVT-01 | ✅ Umgesetzt | Das System verwendet ein **ereignisbasiertes** (event-driven) Datenempfangs-Modell statt zeitgesteuertem Polling für unsolicited frames. |
| EVT-02 | ✅ Umgesetzt | Unsolicited frames werden über eine asyncio.Queue (`_unsolicited_queue`) verarbeitet. Die Listener-Task wartet mit `await queue.get()` auf Events (kein aktives Polling). |
| EVT-03 | ✅ Umgesetzt | Transport-Implementierungen starten einen kontinuierlichen Background-Reader (`_continuous_reader()`), der eingehende Daten überwacht und bei Empfang `_push_unsolicited_frame()` aufruft. |
| EVT-04 | ✅ Umgesetzt | Der Background-Reader wird automatisch beim `connect()` gestartet und läuft unabhängig von Handler-Registrierungen. Queue-Listener für Handler werden erst bei tatsächlicher Handler-Registrierung gestartet. |
| EVT-05 | ✅ Umgesetzt | Die ereignisbasierte Architektur reduziert Latenz und CPU-Last im Vergleich zu zeitgesteuerten Polling-Ansätzen. |
| EVT-06 | ⬜ Ausstehend | Der Background-Reader unterscheidet zwischen erwarteten Antworten (für aktive Befehle) und unsolicited frames. Erwartete Antworten werden direkt an wartende Command-Handler weitergeleitet, nur unsolicited frames gehen in die Event-Queue. |

### 3.4.4 USB Connection

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
| USB-10 | ✅ Umgesetzt | USBConnection implementiert `_continuous_reader()` als Background-Task, der automatisch beim `connect()` gestartet wird und kontinuierlich USB-Daten überwacht. Empfangene Frames werden über `_push_unsolicited_frame()` in die Event-Queue gelegt. |
| USB-11 | ✅ Umgesetzt | Der Background-Reader läuft asynchron via `asyncio.create_task()` und nutzt `asyncio.to_thread()` für blockierende Serial-Reads, um Event Loop nicht zu blockieren. Startet automatisch wenn Event Loop verfügbar ist. |

### 3.4.5 LAN Connection

Noch nicht definiert

### 3.4.6 SIM Connection (Simulation/Testing)

Noch nicht definiert

## 3.5 Allgemeine Anforderungen

### 3.5.1 Konfiguration

| ID | Status | Anforderung |
|---|---|---|
| CFG-01 | ✅ Umgesetzt | Alle Konfigurationswerte werden persistent in einer JSON-Datei (config.json) gespeichert. |
| CFG-02 | ✅ Umgesetzt | Die Konfiguration wird beim Start automatisch geladen. |
| CFG-03 | ✅ Umgesetzt | API-Keys und andere Secrets werden in config.json gespeichert. Optional können Secret-Referenzen via Secret-Provider (HashiCorp Vault) verwendet werden (Format: `path#key`). Direkter API-Key im Klartext ist erlaubt. |
| CFG-04 | ✅ Umgesetzt | Konfigurierbare Parameter (Mindestumfang): USB-Port, Baud-Rate, Serial-Parameter, CAT-Port, Wavelog-URL, Wavelog-API-Key (direkt oder Secret-Referenz), Gerätename, API-Port, Log-Level. |
| CFG-05 | ✅ Umgesetzt | Secrets (API-Keys) werden nicht im Klartext in Logdateien ausgegeben. |
| CFG-07 | ✅ Umgesetzt | Die Konfigurationsdatei kann sowohl von der Applikation als auch von Benutzer bearbeitet werden. |
| CFG-08 | ✅ Umgesetzt | Der Inhalt der Konfigurationsdatei soll in der Oberflächje angezeigt werden. |

### 3.5.2 Sicherheit & Verschlüsselung

| ID | Status | Anforderung |
|---|---|---|
| SEC-01 | ✅ Umgesetzt | Secrets (API-Key, Passwörter) werden niemals in API-Antworten zurückgeliefert. |
| SEC-02 | ✅ Umgesetzt | Secrets werden nicht in Log-Einträgen ausgegeben (auch nicht auf `DEBUG`-Level). |
| SEC-03 | ⬜ Ausstehend | Die Verbindung von RigBridge zu Wavelog erfolgt **ausschließlich über HTTPS** (TLS). `verify=False` ist verboten. |
| SEC-04 | ✅ Umgesetzt | Der API-Port (8080) wird nur auf `127.0.0.1` gebunden, solange kein Netzwerkzugriff konfiguriert ist. |
| SEC-05 | 🔄 In Entwicklung | HTTPS für die interne REST-API ist optional aktivierbar (konfigurierbarer Zertifikatspfad), wenn Zugriff über Netzwerk nötig ist. |
| SEC-06 | ⬜ Ausstehend | Wird HTTPS aktiviert, wird das TLS-Zertifikat validiert (kein `verify=False`). |
| SEC-07 | ✅ Umgesetzt | Der Wavelog API-Key wird als Passwort-Eingabefeld (`type="password"`) im UI dargestellt. |

### 3.5.3 Logging

| ID | Status | Anforderung |
|---|---|---|
| LOG-01 | ✅ Umgesetzt | Das System schreibt strukturierte Log-Einträge (mindestens: Zeitstempel, Level, Modul, Nachricht). |
| LOG-02 | ✅ Umgesetzt | Das Log-Level ist konfigurierbar (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| LOG-03 | ✅ Umgesetzt | Logs werden auf `stdout` ausgegeben (Docker-kompatibel). |
| LOG-04 | ✅ Umgesetzt | Optionale Ausgabe in eine Logdatei ist konfigurierbar. |
| LOG-05 | ✅ Umgesetzt | **Alle** Log-Einträge (inkl. Uvicorn, Framework-Logs) verwenden das gleiche einheitliche Format: `[YYYY-MM-DD HH:MM:SS.mmm] [LEVEL] [MODULE] MESSAGE` |
| LOG-06 | ✅ Umgesetzt | Zeitstempel enthalten **Millisekunden** (nicht nur Sekunden). |

### 3.5.4 Deployment / Docker

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

# 4. Nicht-funktionale Anforderungen (Kurzübersicht)

> Details siehe [design-rules.md](design-rules.md) und [coding-rules.md](coding-rules.md).

| ID | Anforderung |
|---|---|
| NF-01 | Plattformkompatibilität: Linux mit Docker (Produktion), Windows nativ ohne Docker (Entwicklung) – ohne Code-Anpassung lauffähig. |
| NF-02 | Code-Qualität: PEP 8, Type Hints, Docstrings, `ruff`/`black` als Formatter. |
| NF-03 | Testbarkeit: Hardware-Zugriff (USB) ist abstrahiert und mockbar. |
| NF-04 | Erweiterbarkeit: Neue Funkgeräte werden ausschließlich über YAML-Dateien hinzugefügt. |
| NF-05 | Sicherheit: Keine Secrets in Quellcode oder Logs. |
