# YAML CI-V-Protokoll – Syntax-Dokumentation

## Übersicht

RigBridge nutzt eine hierarchische YAML-Struktur zur Definition von CI-V-Kommunikationsprotokollen für ICOM-Funkgeräte. Diese Dokumentation erläutert Aufbau und Syntax, damit Protokolldefinitionen für weitere Gerätemodelle ergänzt werden können.

### Dateiorganisation

Die CI-V-Protokolldefinition ist auf **zwei YAML-Dateien** aufgeteilt:

1. **`protocols/manufacturers/icom/<model>.yaml`** — Gerätespezifische Befehle und Strukturen
2. **`protocols/manufacturers/icom.yaml`** — Gemeinsame Datentypen für alle ICOM-Modelle

Diese Aufteilung ermöglicht:
- **Wiederverwendbarkeit**: Datentypen werden einmal definiert und in mehreren Gerätemodellen genutzt
- **Wartbarkeit**: Änderungen an gemeinsamen Typen gelten automatisch für alle Geräte
- **Erweiterbarkeit**: Neue Geräte können vorhandene Datentypen referenzieren

---

## 1. Protokoll-Grundstruktur

### 1.1 Grundgerüst des Schemas

Die YAML-Protokolldefinition besteht aus einem Wurzel-Element `protocol` mit folgenden Hauptbestandteilen:

```yaml
protocol:
  name: "Icom IC-905"
  model: "ic905"
  manufacturer: "Icom"
  description: "Multi-band transceiver with complete CI-V command set"

  frame:
    preamble: [0xFE, 0xFE]
    terminator: 0xFD
    default_controller: 0xE0
    default_radio: 0xAC

  commands:
    read_operating_frequency:
      cmd: 0x03
      # ... weitere Befehlsdefinitionen
```

### 1.2 Protocol-Element (Wurzelebene)

Das `protocol`-Element enthält die Metadaten und strukturellen Definitionen für ein Funkgerätemodell:

| **Feld** | **Typ** | **Pflicht** | **Beschreibung** |
|----------|---------|-------------|------------------|
| `name` | string | Ja | Vollständiger Name des Funkgeräts (z.B. "Icom IC-905") |
| `model` | string | Ja | Modellbezeichnung, wird als Dateiname verwendet (z.B. "ic905") |
| `manufacturer` | string | Ja | Hersteller des Geräts (z.B. "Icom", "Yaesu", "Kenwood") |
| `description` | string | Nein | Kurzbeschreibung des Geräts und seiner Fähigkeiten |
| `frame` | object | Ja | Definiert die Frame-Struktur der seriellen Kommunikation |
| `commands` | object | Ja | Sammlung aller verfügbaren Befehle für dieses Gerät |

### 1.3 Frame-Element (CI-V Frame-Struktur)

Das `frame`-Element definiert das Kommunikationsprotokoll auf Byte-Ebene:

| **Feld** | **Typ** | **Pflicht** | **Beschreibung** |
|----------|---------|-------------|------------------|
| `preamble` | array[int] | Ja | Frame-Startbytes, die jeder Nachricht vorangestellt werden<br/>Beispiel: `[0xFE, 0xFE]` (ICOM-Standard) |
| `terminator` | int | Ja | Frame-Endbyte, das jede Nachricht abschließt<br/>Beispiel: `0xFD` (ICOM-Standard) |
| `default_controller` | int | Ja | Standard-Adresse des steuernden Computers<br/>Beispiel: `0xE0` (ICOM-Standard für PC) |
| `default_radio` | int | Ja | Standard-Adresse des Funkgeräts<br/>Beispiel: `0xAC` (IC-905), `0x94` (IC-7300) |

**Hinweis zu Adressen:**  
Die tatsächlich verwendeten CI-V-Adressen (`controller` und `radio`) werden nicht in der YAML-Datei, sondern in der `config.json` gespeichert. Dadurch können Benutzer diese über die Web-Oberfläche konfigurieren, falls vom Standard abweichende Adressen benötigt werden. Die `default_*`-Felder im Frame dienen nur als Referenzwerte.

### 1.4 Commands-Element (Befehlssammlung)

Das `commands`-Element ist ein Objekt, dessen Schlüssel die individuellen Befehlsnamen sind. Jeder Befehlsname (z.B. `read_operating_frequency`, `set_af_level`) definiert einen CI-V-Befehl mit seiner spezifischen Struktur.

```yaml
commands:
  read_operating_frequency:
    cmd: 0x03
    subcmd: null
    description: "Read operating frequency"
    # ... weitere Befehlsdetails

  set_af_level:
    cmd: 0x14
    subcmd: 0x01
    description: "Set AF level"
    # ... weitere Befehlsdetails
```

Die Befehlsnamen folgen der Konvention `snake_case` und sollten die Funktion des Befehls klar beschreiben. Die detaillierte Struktur einzelner Befehle wird im Abschnitt [3. Befehle](#3-befehle-ic905yaml) beschrieben

---

# Alles nachfolgende ist alt und wird noch überarbeietet, zum Teil inkorrekt

## 2. Datentypen (icom.yaml)

### 2.1 Zweck

Datentypen definieren **wie Binärdaten für bestimmte Parameter kodiert/dekodiert werden**. Sie sind in `icom.yaml` gespeichert und können von mehreren Gerätemodellen wiederverwendet werden.

### 2.2 Struktur



#### Skalierungstypen

- `lookup_linear`

#### Aufzählungstypen (Enumerations)

```yaml
operating_mode:
  name: "Operating Mode"
  size: 2
  description: "Betriebsart und Filterauswahl jeweils als 1-Byte-Enum-Wert"
  bytes:
    - index: 0
      role: "mode"
      description: "Betriebsart (LSB, USB, AM, FM, …)"
    - index: 1
      role: "filter"
      description: "Filterauswahl (FIL1, FIL2, FIL3)"
  encoding:
    method: "enum_pair"
  values:
    modes:
      0x00: "LSB"
      0x01: "USB"
      0x02: "AM"
      0x03: "CWR"
      # ... weitere Modes
    filters:
      0x00: "FIL1"
      0x01: "FIL2"
      0x02: "FIL3"
```

---

## 3. Befehle (ic905.yaml)

### 3.1 Grundstruktur eines Befehls

```yaml
commands:
  read_operating_frequency:
    cmd: 0x03
    subcmd: null
    description: "Read operating frequency"
    request:
      structure: []              # Keine Anfragedaten erforderlich
    response:
      alternatives:
        - name: "frequency"
          type: "bcd5_freq"
          description: "Frequenz als BCD (10 Stellen)"
        - name: "frequency"
          type: "bcd6_freq"
          description: "Frequenz als BCD (12 Stellen für 10-GHz-Band)"
```

### 3.2 Befehlsfelder im Überblick

| Feld | Typ | Bedeutung |
|------|-----|-----------|
| **cmd** | hex | Primäres Befehlsbyte (0x00–0xFF) |
| **subcmd** | hex oder Array | Unterbefehl(e). Möglich: `null`, `0xXX` oder `[0xXX, 0xYY, ...]` |
| **description** | string | Menschenlesbarer Zweck |
| **request** | object | Datenstruktur zum Senden des Befehls |
| **response** | object | Erwartete Antwortstruktur |
| **data** | string | Zusätzliche Metadaten (z. B. „See p. 18“ als Manual-Verweis) |

### 3.3 Anfrage- und Antwortstrukturen

#### Einfache Anfrage (keine Parameter)

```yaml
cancel_scan:
  cmd: 0x0E
  subcmd: 0x00
  description: "Cancel scan"
  request:
    structure: []              # Leer – keine Parameter
  response: *status_ok_ng      # Referenz auf YAML-Anchor
```

#### Anfrage mit Parametern

```yaml
set_af_level:
  cmd: 0x14
  subcmd: 0x01
  description: "Set AF level"
  request:
    structure:
      - name: "AF_level"
        type: "uint8_percent"
        description: "Audio-Frequenzpegel (0–100%)"
  response: *status_ok_ng
```

#### Antwort mit Alternativen

```yaml
read_operating_frequency:
  cmd: 0x03
  description: "Read operating frequency"
  response:
    alternatives:
      - type: "bcd5_freq"
        description: "Standard-Band-Frequenzen"
      - type: "bcd6_freq"
        description: "10-GHz-Band-Frequenzen"
```

### 3.4 Mehrstufige Unterbefehle (Erweiterte Einstellungen)

Der IC-905 verfügt über komplexe verschachtelte Unterbefehle in der Befehlsgruppe 0x1A:

```yaml
ext_setting_005:
  cmd: 0x1A
  subcmd: [0x05, 0x00, 0x01]    # Dreistufiger Unterbefehl
  description: "RX > SSB > Send/read RX HPF/LPF settings"
  data: "See p. 20"
```

**Lesart:**
- **cmd**: 0x1A (Erweiterte Einstellungen)
- **subcmd[0]**: 0x05 (Einstellungsgruppe)
- **subcmd[1]**: 0x00 (RX-Einstellungen)
- **subcmd[2]**: 0x01 (SSB-Modus)
- **data**: „See p. 20“ = Noch nicht vollständig dokumentiert, siehe Handbuch Seite 20

---

## 4. YAML-Templates & Anchors

Wiederverwendbare Definitionen mit YAML-Anchors (`&`) und Aliases (`*`):

```yaml
templates:
  status_ok_ng: &status_ok_ng         # Definieren mit &
    type: "alternatives"
    description: "Returns either success or error"
    alternatives:
      - name: "success"
        value: 0xFB
      - name: "error"
        value: 0xFA

commands:
  power_off:
    cmd: 0x18
    response: *status_ok_ng            # Verwenden mit *
```

**Vorteil**: Einmal definieren, überall verwenden. Änderungen wirken sich automatisch auf alle Verwendungen aus.

---

## 5. Vollständiges Beispiel: Neuen Befehl hinzufügen

### Szenario: Befehl „S-Meter-Pegel lesen“ hinzufügen

#### Schritt 1: Befehl identifizieren

Aus der IC-905-Referenz:
- Befehl: 0x15 (Messgerät-Ablesungen)
- Unterbefehl: 0x02 (S-Meter)
- Antwort: 1 Byte (0x00=S0, 0x78=S9, 0xF1=S9+60 dB)

#### Schritt 2: Datentyp erstellen/aktualisieren (icom.yaml)

```yaml
data_types:
  uint8_s_meter:
    name: "S-Meter Reading"
    size: 1
    description: "S-Meter-Pegel 0–255 mit bekannten Referenzpunkten (nicht rein linear)"
    encoding:
      method: "lookup_scaled"
    scaling:
      type: "piecewise_linear"
      unit: "dBm"
      reference_points:
        - { raw: 0x00, label: "S0",     dbuv: 0   }
        - { raw: 0x78, label: "S9",     dbuv: 74  }
        - { raw: 0xF1, label: "S9+60",  dbuv: 134 }
      note: "Interpolation linear zwischen den Stützpunkten"
```

#### Schritt 3: Befehlseintrag erstellen (ic905.yaml)

```yaml
commands:
  read_s_meter:
    cmd: 0x15
    subcmd: 0x02
    description: "S-Meter-Pegel lesen (0x00=S0, 0x78=S9, 0xF1=S9+60 dB)"
    request:
      structure: []                    # Keine Parameter erforderlich
    response:
      structure:
        - name: "s_meter_level"
          type: "uint8_s_meter"
          offset: 0
          length: 1
          description: "S-Meter-Wert"
```

#### Schritt 4: Verwendung in der Anwendung

```python
# Pseudocode: Verwendung im Programm
response = radio.send_command('read_s_meter')
s_meter_value = response['s_meter_level']  # z. B. 0x78
s_db = decode_s_meter(s_meter_value)       # Lookup/Skalierung in dB
```

---

## 6. Best Practices & Konventionen

### 6.1 Namenskonventionen

```yaml
# GUT: Klare, beschreibende Namen
read_operating_frequency
set_af_level
read_s_meter

# SCHLECHT: Vage oder abgekürzte Namen
read_freq
setafl
rdsm
```

### 6.2 Dokumentation

Immer angeben:

```yaml
command_name:
  cmd: 0xXX
  description: "Was macht dieser Befehl und wann wird er verwendet?"
  # Weiterer Kontext:
  data: "See p. 42"              # Verweis auf die Manual-Seite
```

### 6.3 Datentypgrößen

Byte-Angaben präzise machen:

```yaml
# GUT: Explizites Offset-Tracking
response:
  structure:
    - name: "frequency"
      offset: 0
      length: 5
    - name: "mode"
      offset: 5
      length: 1

# AKZEPTABEL: Parser berechnet Offset automatisch
response:
  structure:
    - name: "frequency"
      type: "bcd5_freq"
    - name: "mode"
      type: "operating_mode"
```

---

## 7. Erweiterung auf weitere Gerätemodelle

### 7.1 Neues Gerät hinzufügen (z. B. IC-7300)

1. **Neue Befehlsdatei erstellen**: `protocols/manufacturers/icom/ic7300.yaml`
2. **Datentypen wiederverwenden**: `icom.yaml` referenzieren (dieselben Typen gelten)
3. **Neue Befehle definieren**: Nur IC-7300-spezifische Befehle

```yaml
protocol:
  name: "Icom IC-7300"
  model: "ic7300"
  manufacturer: "Icom"
  description: "KW-Transceiver"
  
  config:
    # Gleiche Timeouts und Frame-Struktur wie beim IC-905
    timeouts:
      command_response: 1.0
      session_idle: 300.0
    
    frame:
      preamble: [0xFE, 0xFE]
      terminator: 0xFD
      default_controller: 0xE0
      default_radio: 0x94      # IC-7300-Adresse (abweichend!)
  
  addresses:
    controller: 0xE0
    radio: 0x94
  
  commands:
    # Der IC-7300 verfügt über ähnliche, aber nicht identische Befehle
    read_operating_frequency:
      cmd: 0x03
      # ... gleiche Struktur wie beim IC-905
```

### 7.2 Neue Datentypen hinzufügen

Falls ein neues Gerät eine abweichende Kodierung verwendet:

```yaml
# icom.yaml
data_types:
  # Existing types...

  # Neu für IC-7300 S-Meter (2-Byte statt 1-Byte)
  uint16_s_meter_ic7300:
    name: "IC-7300 S-Meter Reading"
    size: 2
    description: "S-Meter 2-Byte-Kodierung 0x0000–0xFFFF"
    encoding:
      method: "lookup_scaled"
      byte_order: "little_endian"
    scaling:
      type: "piecewise_linear"
      unit: "dBµV"
      reference_points:
        - { raw: 0x0000, label: "S0", dbuv: 0  }
        - { raw: 0x7800, label: "S9", dbuv: 74 }
```

---

## 8. Diskussionspunkte & zukünftige Verbesserungen

### 8.1 Validierungsschicht

**Vorschlag**: JSON-Schema für YAML-Validierung hinzufügen

```yaml
# Schema-Validierung könnte prüfen:
- Befehlsbyte-Bereiche (0x00–0xFF)
- Eindeutigkeit der Unterbefehle pro Befehl
- Konsistenz von Datentypexistenz und Größe
- Symmetrie von Anfrage und Antwort

Vorteile:
- Tippfehler frühzeitig erkennen
- Konsistenz über Gerätemodelle hinweg sicherstellen
- IDE-Autovervollständigung ermöglichen
```

### 8.2 Typ-Hinweise für komplexe Strukturen

**Vorschlag**: TypeScript-ähnliche Typannotationen hinzufügen

```yaml
commands:
  set_frequency:
    cmd: 0x05
    request:
      structure:
        - name: frequency
          type: bcd5_freq
          required: true
        - name vfo_select
          type: uint8
          enum: [0x00, 0x01]
          description: "0x00=VFO-A, 0x01=VFO-B"
          required: false
```

### 8.3 Automatische Generierung von API-Dokumentation

**Vorschlag**: REST-API-Dokumentation aus YAML generieren

```python
# Werkzeug würde YAML lesen und generieren:
POST /api/v1/radio/frequency
  Anfrage: frequency (bcd5_freq)
  Antwort: 0xFB (Erfolg) oder 0xFA (Fehler)
  Beispiel: POST /api/v1/radio/frequency {"frequency": "144.500"}
```

### 8.4 Bidirektionale Anfrage/Antwort

**Aktuell**: Manche Befehle sind „set“ (Daten senden) oder ‚get“ (Daten empfangen)

**Vorschlag**: Befehle unterstützen, die gleichzeitig senden und empfangen

```yaml
query_frequency:
  cmd: 0x03
  mode: bidirectional
  # Manche Geräte antworten mit der aktuellen Frequenz,
  # während gleichzeitig eine neue gesetzt wird
  request:
    structure:
      - name: frequency
        type: bcd5_freq
  response:
    structure:
      - name: previous_frequency
        type: bcd5_freq
```

### 8.5 Fehlerantwort-Codes

**Vorschlag**: Erwartete Fehlerantworten pro Befehl definieren

```yaml
set_frequency:
  cmd: 0x05
  errors:
    - code: 0xFA
      description: "Ungültige Frequenz für das aktuelle Band"
    - code: 0xFB
      description: "Erfolg"
    - code: 0xFC
      description: "Transceiver besetzt (anderer Befehl in Bearbeitung)"
```

---

## 9. Schnellreferenz: Befehlsvorlage

Diese Vorlage beim Hinzufügen neuer Befehle verwenden:

```yaml
command_name:                          # Beschreibendes snake_case
  cmd: 0xXX                            # Primärbyte des Befehls (hex)
  subcmd: null                         # null, 0xXX oder [0xXX, 0xYY, ...]
  description: "Klare Beschreibung"   # Was macht der Befehl?
  
  request:                             # Was wird an das Gerät gesendet
    structure:
      - name: "parametername"
        type: "datentyp_name"
        description: "Wofür steht dieser Parameter?"
  
  response:                            # Was schickt das Gerät zurück
    structure:
      - name: "antwort_feld"
        type: "datentyp_name"
        description: "Welche Bedeutung hat dieser Wert?"
  
  data: "See p. XX"                    # Optional: Verweis auf Handbuch
```

---

## 10. Referenzen

- **IC-905 CI-V-Referenz**: [Icom IC-905 CI-V Protocol Reference Manual](https://www.icomjapan.com/support/manual/3792/)
- **YAML-Spezifikation**: https://yaml.org/spec/
- **BCD-Kodierung**: https://en.wikipedia.org/wiki/Binary-coded_decimal

---

## Dokumentenversion

- **Version**: 0.1
- **Datum**: 2026-03-02
- **Autor**: DD0MM
- **Status**: Entwurf — strukturiertes `bytes`/`scaling`-Schema eingeführt (v0.1)

**Nächste Schritte**:
1. Verbesserungsvorschläge besprechen und abstimmen
2. Validierungsschema implementieren
3. Werkzeuge zur automatischen Generierung von Dokumentation & APIs erstellen
