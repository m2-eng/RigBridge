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

Die Befehlsnamen folgen der Konvention `snake_case` und sollten die Funktion des Befehls klar beschreiben. Die detaillierte Struktur einzelner Befehle wird im Abschnitt [2. Befehle](#2-befehle-ic905yaml) beschrieben

---

## 2. Befehle

### 2.1 Grundgerüst des Schemas

Die Befehlsdefinitionen stehen im Element `protocol.commands` in z.B. `protocols/manufacturers/icom/ic905.yaml`. Jeder Schlüssel unterhalb von `commands` repräsentiert genau einen logischen CI-V-Befehl.

```yaml
protocol:
  commands:
    read_operating_frequency:
      cmd: 0x03

    set_af_level:
      cmd: 0x14
```

### 2.2 Command-Element (`commands`)

Ein Befehl ist ein YAML-Objekt mit einem sprechenden `snake_case`-Namen als Schlüssel. Im aktuell aktiven Stand von `ic905.yaml` sind für die nicht auskommentierten Befehle vor allem die Felder `cmd` und optional `subcmd` relevant.

| **Feld** | **Typ** | **Pflicht** | **Beschreibung** |
|----------|---------|-------------|------------------|
| `cmd` | int (hex) | Ja | Primäres CI-V-Befehlsbyte (z.B. `0x14`) |
| `subcmd` | int, array[int] oder `null` | Nein | Unterbefehl zur Differenzierung innerhalb eines `cmd` |
| `description` | string | Nein | Fachliche Beschreibung des Befehlszwecks |
| `request` | array[object] | Nein | Liste der Nutzdatenfelder, die an das Gerät gesendet werden |
| `response` | array[object] | Nein | Liste der erwarteten Nutzdatenfelder vom Gerät |
| `data` | string | Nein | Zusätzlicher Hinweis, z.B. Verweis auf Manual-Seiten |

Viele logische Befehle teilen sich dasselbe `cmd`-Byte. Die fachliche Differenzierung erfolgt über den Befehlsnamen und in späteren Ausbaustufen über `subcmd`-Strukturen.

Beispiel:
- `cmd: 0x14` umfasst zahlreiche Level-/Audio-/Gain-Befehle.
- `cmd: 0x16` umfasst Funktionsschalter (z.B. `preamp`, `vox`, `dtcs`).

**Namenskonventionen für Befehle**

Die aktiven Befehlsnamen folgen überwiegend diesen Mustern:

| **Muster** | **Bedeutung** | **Beispiele** |
|-----------|----------------|---------------|
| `read_*` | Zustand/Wert vom Gerät lesen | `read_operating_frequency`, `read_rf_gain` |
| `send_*` | Zustand/Wert am Gerät setzen/senden | `send_frequency_offset`, `send_attenuator_off` |
| Aktionsname ohne Präfix | Direkter Geräte-Trigger | `power_off`, `memory_write`, `exchange_vfo` |

**Hinweis zu read/send:**
Die Unterscheidung mittels read/send erfolgt dadurch, da der Befehlswert für beides verwendet werden kann.

### 2.3 Request-Element (`request`)

Das `request`-Element ist ein **Array** von Feldobjekten, die die Nutzdaten beschreiben, die beim Senden eines Befehls an das Gerät übermittelt werden. Mit `request: []` wird angegeben, dass der Befehl keine Nutzdaten benötigt.

**Feldstruktur innerhalb von `request`/`response`-Arrays:**

| **Feld** | **Typ** | **Pflicht** | **Beschreibung** |
|----------|---------|-------------|------------------|
| `name` | string | Ja | Feldname in Klartext (z.B. `"frequency"`, `"mode"`) |
| `type` | string | Ja | Referenz zu einem Datentyp aus `icom.yaml` (z.B. `"bcd5_freq"`, `"operating_mode"`) |
| `description` | string | Nein | Erklärende Beschreibung des Feldes |

**Typische Formen:**
- `request: []` — Der Befehl erfordert keine Nutzdaten beim Senden (z.B. `read_operating_frequency`).
- `request: [...]` — Ein oder mehrere Felder, die gesendet werden (noch nicht in aktiven Befehlen vorhanden).

**Beispiel**

```yaml
commands:
  receive_frequency_data:
    cmd: 0x00
    request: []
    response:
      - name: "frequency"
        type: "bcd5_freq"
        description: "Receive the operating frequency in BCD"
      - name: "frequency"
        type: "bcd6_freq"
        description: "Receive the operating frequency in BCD (10 GHz band)"
```

### 2.4 Response-Element (`response`)

Das `response`-Element ist ein **Array** von Feldobjekten, die die Nutzdaten beschreiben, die als Antwort vom Gerät erwartet werden.

Das Array kann mehrere Alternativen enthalten (wie in `read_operating_frequency`), falls das Gerät je nach Modus unterschiedliche Antwortformate sendet.

**Feldstruktur innerhalb von `request`/`response`-Arrays** (s. Tabelle in Abschnitt 2.5):

| **Feld** | **Typ** | **Pflicht** | **Beschreibung** |
|----------|---------|-------------|------------------|
| `name` | string | Ja | Feldname in Klartext (z.B. `"frequency"`, `"mode"`) |
| `type` | string | Ja | Referenz zu einem Datentyp aus `icom.yaml` (z.B. `"bcd5_freq"`, `"operating_mode"`) |
| `description` | string | Nein | Erklärende Beschreibung des Feldes |

**Typische Formen:**
- `response: []` — Keine Antwort erwartet (noch nicht in aktiven Befehlen dokumentiert).
- `response: [...]` — Ein oder mehrere Felder in der Antwort (wie `read_operating_frequency`).

**Beispiel**

```yaml
commands:
  read_operating_frequency:
    cmd: 0x03
    request: []
    response:
      - name: "frequency"
        type: "bcd5_freq"
        description: "Read the operating frequency in BCD"
      - name: "frequency"
        type: "bcd6_freq"
        description: "Read the operating frequency in BCD (10 GHz band)"
```

---

## 3. Datentypen

### 3.1 Grundgerüst des Schemas

Gemeinsame Datentypen werden in z.B. `protocols/manufacturers/icom.yaml` - für den entsprechenden Hersteller - unterhalb des Wurzel-Elements `data_types` definiert. Jeder Eintrag beschreibt Aufbau, Kodierung und Bedeutung eines wiederverwendbaren Formats.

```yaml
data_types:
  uint8:
    size: 1
    description: "Single byte 0x00-0xFF"
    encoding: "direct"
    range:
      min: 0
      max: 255

  bcd5_freq:
    name: "frequency"
    size: 5
    description: "5-Byte BCD-kodierte Frequenz"
    bytes:
      - index: 0
        high_nibble: { place: "10Hz", weight: 10 }
        low_nibble:  { place: "1Hz",  weight: 1 }
    encoding:
      method: "bcd_packed"
      byte_order: "little_endian"
```

### 3.2 Datentyp-Element (`data_types`)

Ein Datentyp ist ein YAML-Objekt mit einem frei wählbaren Schlüssel (z.B. `uint8`, `operating_mode`, `bcd6_freq`). Dieser Schlüssel wird in `ic905.yaml` als Typreferenz verwendet.

| **Feld** | **Typ** | **Pflicht** | **Beschreibung** |
|----------|---------|-------------|------------------|
| `name` | string | Nein | Name des Typs (z.B. `"frequency"`) überschreibt den im Befehl angegebenen Namen und wird als Rückgabenamen im Code verwendet|
| `size` | int | Ja | Länge in Bytes |
| `description` | string | Ja | Beschreibung des Inhalts |
| `encoding` | string | Ja | Kodierungsverfahren, wird im Code zur Auswahl der entsprechenden (De-)Codier Funktion verwendet. |
| `range` | object | Nein | Wertebereich (roh und/oder physikalisch) |
| `scaling` | object | Nur bei z.B. Kennfeldern | Abbildung zwischen Rohwert und physikalischem Wert |
| `bytes` | array[object] | Nein | Byteweise Struktur für zusammengesetzte Typen |
| `note` | string | Nein | Zusätzlicher Hinweis, z.B. einsatzabhängige Besonderheiten |

**Referenzierung in `ic905.yaml`:**  
Datentypen werden über ihren Schlüssel verwendet, z.B. `type: "bcd5_freq"` oder `type: "operating_mode"`. In diesem Abschnitt wird nur der Typaufbau beschrieben; die Befehlsstruktur wird im Commands-Abschnitt behandelt.

### 3.3 Byte-Struktur (`bytes`)

Für strukturierte Datentypen (z.B. `status_ok_ng`, `operating_mode`, `bcd*_freq`) kann der Byte-Aufbau explizit beschrieben werden.

| **Feld** | **Typ** | **Pflicht** | **Beschreibung** |
|----------|---------|-------------|------------------|
| `index` | int | Ja | Byteposition innerhalb des Datentyps (0-basiert) |
| `length` | int | Nein | Länge des Feldes in Bytes (typisch `1`) |
| `name` | string | Nein | Feldname innerhalb des Datentyps |
| `encoding` | string | Nein | Kodierung auf Feldebene (z.B. `enum`) |
| `values` | object | Nein | Enum-Zuordnung für festspezifizierte Werte |
| `high_nibble` | object | Nein | Bedeutung des oberen Nibbles bei BCD-Typen |
| `low_nibble` | object | Nein | Bedeutung des unteren Nibbles bei BCD-Typen |
| `description` | string | Nein | Beschreibung des Bytefeldes |

### 3.4 Kodierungsarten

In `icom.yaml` werden aktuell folgende Kodierungsmuster verwendet:

| **Kodierung** | **Verwendung** | **Beispiele** |
|---------------|----------------|---------------|
| `direct` | Unskalierte Rohwerte | `uint8` |
| `enum` | Feste Wertemengen | `boolean` |
| `linear_scaled` | Lineare Abbildung Rohwert ↔ physikalischer Wert | `uint8_percent`, `uint8_percent_pos_neg` |
| `bytes` | Mehrbyte-Strukturen mit feldweiser Definition | `status_ok_ng`, `attenuator_enum`, `operating_mode` |
| `bcd_packed` | BCD-kodierte Frequenzen mit Nibble-Zuordnung | `bcd3_freq`, `bcd5_freq`, `bcd6_freq` |

---

## 4. Praxisanleitungen

### 4.1 Schritt fuer Schritt: Neuen Befehl einfuegen

1. **Befehl in der CI-V-Referenz identifizieren**: `cmd`, optional `subcmd`, Richtung (lesen/senden) und Antwortformat festlegen.
2. **Befehlsnamen waehlen**: `snake_case` verwenden, z.B. `read_s_meter` oder `send_rf_gain`.
3. **Befehl in `protocols/manufacturers/icom/<model>.yaml` unter `protocol.commands` anlegen**: Grundfelder `cmd`, optional `subcmd`, `description`, `request`, `response` setzen.
4. **Datentyp festlegen**: Bestehenden Typ aus `protocols/manufacturers/icom.yaml` referenzieren oder den Typ direkt im Befehl beschreiben.
5. **Plausibilitaet pruefen**: Felder, Typnamen und Rueckgabeform zum Geraeteverhalten abgleichen.

**Wichtiger Hinweis:** Ein Datentyp in der Hersteller-Datei ist nicht zwingend erforderlich. Einfache oder einmalige Strukturen koennen direkt im Befehl beschrieben werden.

**Variante A: Datentyp aus `icom.yaml` referenzieren**

```yaml
commands:
  read_s_meter:
    cmd: 0x15
    subcmd: 0x02
    description: "Read S-meter"
    request: []
    response:
      - name: "s_meter_level"
        type: "uint8"
        description: "S-meter raw value"
```

**Variante B: Typ direkt im Befehl beschreiben**

```yaml
commands:
  read_s_meter:
    cmd: 0x15
    subcmd: 0x02
    description: "Read S-meter"
    request: []
    response:
      - name: "s_meter_level"
        size: 1
        encoding: "direct"
        range:
          min: 0
          max: 255
        description: "S-meter raw value"
```

### 4.2 Schritt fuer Schritt: Weiteres Geraet hinzufuegen

1. **Neue Geraetedatei erstellen**: `protocols/manufacturers/icom/<neues_modell>.yaml` anlegen.
2. **`protocol`-Metadaten eintragen**: `name`, `model`, `manufacturer`, `description` setzen.
3. **`frame` definieren**: `preamble`, `terminator`, `default_controller`, `default_radio` fuer das neue Geraet eintragen.
4. **Befehle uebernehmen und anpassen**: Bestehende Befehle als Startpunkt nutzen und nur gueltige Befehle fuer das neue Geraet belassen.
5. **Datentypstrategie waehlen**: Gemeinsame Typen in `icom.yaml` wiederverwenden; modellspezifische Sonderfaelle entweder in `icom.yaml` erweitern oder direkt im jeweiligen Befehl beschreiben.
6. **Konsistenz pruefen**: `model` und Dateiname, Befehlsnamen, `cmd`/`subcmd` und Typreferenzen auf Vollstaendigkeit und Korrektheit kontrollieren.

**Minimalbeispiel fuer eine neue Geraetedatei**

```yaml
protocol:
  name: "Icom IC-7300"
  model: "ic7300"
  manufacturer: "Icom"
  description: "HF transceiver"

  frame:
    preamble: [0xFE, 0xFE]
    terminator: 0xFD
    default_controller: 0xE0
    default_radio: 0x94

  commands:
    read_operating_frequency:
      cmd: 0x03
      subcmd: null
      description: "Read operating frequency"
      request: []
      response:
        - name: "frequency"
          type: "bcd5_freq"
          description: "Operating frequency"
```

---

## 5. Referenzen

- **IC-905 CI-V-Referenz**: [Icom IC-905 CI-V Protocol Reference Manual](https://www.icomjapan.com/support/manual/3792/)
- **YAML-Spezifikation**: https://yaml.org/spec/
- **BCD-Kodierung**: https://en.wikipedia.org/wiki/Binary-coded_decimal

---

## 6. Dokumentenversion

- **Version**: 0.1 (Entwurf)
- **Datum**: 2026-03-10
- **Autor**: DD0MM
