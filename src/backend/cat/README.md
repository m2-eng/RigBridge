# WaveLog CAT Client

Modul für die Integration von RigBridge mit WaveLog über die Radio API und WaveLogGate.

## Features

- ✅ **Radio-Status an WaveLog senden**: Frequenz, Modus und Leistung per HTTP POST
- ✅ **WaveLogGate HTTP-Integration**: QSY-Befehle von Bandmap-Klicks empfangen
- ✅ **WaveLogGate WebSocket**: Radio-Status-Events empfangen
- ✅ **Bridge-Modus**: Status von WaveLogGate empfangen und an WaveLog weiterleiten
- ✅ **Polling-Modus**: Regelmäßig Status an WaveLog senden (Test/Demo)

## Verwendung

### Programmatische Verwendung

```python
import asyncio
from src.backend.cat.cat_client import WavelogCatClient
from src.backend.config.settings import WavelogConfig

# Konfiguration erstellen
config = WavelogConfig(
    enabled=True,
    api_url='https://wavelog.example.com/',
    radio_name='ICOM IC-905',
    station_id='STATION1',
)

async def main():
    # Client initialisieren
    async with WavelogCatClient(config, api_key='your_api_key') as client:
        
        # Status senden
        success = await client.send_radio_status(
            frequency_hz=7100000,  # 7.1 MHz
            mode='USB',
            power_w=50.0,          # Optional
        )
        
        # QSY über WaveLogGate
        await client.set_radio_via_gate(
            frequency_hz=14200000,  # 14.2 MHz
            mode='CW',
        )
        
        # WebSocket-Status abonnieren
        def on_status(freq, mode, data):
            print(f'Radio: {freq} Hz, {mode}')
        
        await client.subscribe_gate_status(on_status)
        await asyncio.sleep(60)  # 60 Sekunden lauschen

asyncio.run(main())
```

### CLI-Beispiel

Aktuell nicht enthalten. Ein separates CLI/Service-Beispiel wird erst bei einer
Auslagerung der CAT-Schnittstelle als eigenstaendiges Modul bereitgestellt.

## Konfiguration

### config.json

```json
{
  "wavelog": {
    "enabled": true,
    "api_url": "https://wavelog.example.com/",
    "api_key_or_secret_ref": "abcd1234567890",
    "polling_interval": 5,
    "radio_name": "ICOM IC-905",
    "station_id": "STATION1",
    "wavelog_gate_http_base": "http://localhost:54321",
    "wavelog_gate_ws_url": "ws://localhost:54322"
  }
}
```

### Parameter

| Parameter | Beschreibung | Standard |
|---|---|---|
| `enabled` | Aktiviert WaveLog-Integration | `false` |
| `api_url` | WaveLog-API-URL | `https://api.wavelog.local` |
| `api_key_or_secret_ref` | WaveLog API-Key (direkter Klartext) oder Secret-Referenz via Vault (Format: `path#key`). Beide Formate werden unterstützt. | `""` |
| `polling_interval` | Polling-Intervall in Sekunden | `5` |
| `radio_name` | Name des Funkgeräts | `ICOM IC-905` |
| `station_id` | Optional: Station-ID für Multi-Station-Setups | `null` |
| `wavelog_gate_http_base` | WaveLogGate HTTP-Endpunkt | `http://localhost:54321` |
| `wavelog_gate_ws_url` | WaveLogGate WebSocket-URL | `ws://localhost:54322` |

## API-Referenz

### WavelogCatClient

#### `__init__(config: WavelogConfig, api_key: Optional[str] = None)`

Initialisiert den Client.

#### `async send_radio_status(frequency_hz: int, mode: str, power_w: Optional[float] = None) -> bool`

Sendet Radio-Status an WaveLog.

**Parameter:**
- `frequency_hz`: Frequenz in Hz (z.B. `7100000` für 7.1 MHz)
- `mode`: Betriebsmodus (z.B. `"USB"`, `"LSB"`, `"CW"`, `"FM"`)
- `power_w`: Optionale Sendeleistung in Watt

**Returns:** `True` bei Erfolg, `False` bei Fehler

**Beispiel:**
```python
success = await client.send_radio_status(
    frequency_hz=7100000,
    mode='USB',
    power_w=50.0,
)
```

#### `async set_radio_via_gate(frequency_hz: int, mode: str) -> bool`

Sendet QSY-Befehl über WaveLogGate.

**Parameter:**
- `frequency_hz`: Frequenz in Hz
- `mode`: Betriebsmodus

**Returns:** `True` bei Erfolg, `False` bei Fehler

**Beispiel:**
```python
await client.set_radio_via_gate(14200000, 'CW')
```

#### `async subscribe_gate_status(on_status: Callable[[int, str, Dict[str, Any]], None]) -> None`

Abonniert Radio-Status-Updates über WaveLogGate WebSocket.

**Parameter:**
- `on_status`: Callback-Funktion mit Signatur `(frequency_hz: int, mode: str, full_data: dict)`

**Beispiel:**
```python
def handle_status(freq, mode, data):
    print(f'Neuer Status: {freq} Hz, {mode}')
    print(f'Volle Daten: {data}')

await client.subscribe_gate_status(handle_status)
```

#### `is_ws_connected() -> bool`

Prüft, ob WebSocket-Verbindung aktiv ist.

## WaveLog API-Format

### Request

```http
POST /index.php/api/radio HTTP/1.1
Content-Type: application/json
Accept: application/json

{
  "key": "YOUR_API_KEY",
  "radio": "ICOM IC-905",
  "frequency": "7100000",
  "mode": "USB",
  "power": "50.0",
  "timestamp": "2026/03/05  14:30"
}
```

**Hinweis:** Timestamp-Format hat **zwei Leerzeichen** zwischen Datum und Zeit!

### Response (Erfolg)

```http
HTTP/1.1 200 OK

OK
```

## WaveLogGate Integration

### HTTP-Endpunkt (QSY)

```http
GET http://localhost:54321/{frequency}/{mode}
```

**Beispiel:**
```bash
curl http://localhost:54321/7155000/LSB
```

### WebSocket (Radio-Status)

```
ws://localhost:54322
```

**Event-Format:**
```json
{
  "type": "radio_status",
  "frequency": 7100000,
  "mode": "USB",
  "power": 50.0
}
```

## Tests

```bash
# Alle Tests ausführen
python -m pytest tests/backend/test_cat_client.py -v

# Mit Coverage
python -m pytest tests/backend/test_cat_client.py --cov=src.backend.cat

# Einzelner Test
python -m pytest tests/backend/test_cat_client.py::TestSendRadioStatus::test_send_status_success -v
```

## Dokumentation

- [WaveLog Radio API](https://docs.wavelog.org/en/latest/api/radio/)
- [WaveLogGate GitHub](https://github.com/Wavelog/WaveLogGate)
- [RigBridge Anforderungen](../../.copilot/requirements.md)

## Lizenz

Siehe [LICENSE](../../../LICENSE) im Projekt-Root.
