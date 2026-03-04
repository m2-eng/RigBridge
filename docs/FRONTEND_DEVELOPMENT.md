# Browser-UI Frontend Development

## Übersicht

Das RigBridge Browser-UI ist eine **Single-Page Application (SPA)** in **Vanilla JavaScript** (HTML5 + CSS3 + ES6+), ohne externe Frameworks (React, Vue, etc.). Die UI dient zur Konfiguration und Überwachung des RigBridge-Systems und der Wavelog-Integration.

## Architektur

### File Structure

```
src/frontend/
├── index.html              # SPA Main Entry Point (5 Tabs, Formen)
├── assets/
│   ├── base-styles.css     # CSS-Variables, Layout, Theme-System
│   ├── components.css      # Button, Form, Badge Styles
│   ├── theme.css           # User Customization Placeholder
│   ├── api-client.js       # Centralized API HTTP Abstraction
│   ├── config-manager.js   # Config Persistence & Validation
│   ├── status-widget.js    # Real-Time Status Polling (5s interval)
│   ├── theme-switcher.js   # Light/Dark Mode Toggle + LocalStorage
│   └── app.js              # Main Entry Point (Orchestrator)
```

### Design Principles

| Prinzip | Implementierung |
|---------|-----------------|
| **No Frameworks** | Pure HTML5, CSS3, ES6+ JavaScript |
| **Responsive Design** | Desktop-first, minimum 768px width |
| **Dark/Light Theme** | CSS-Variables + LocalStorage persistence |
| **Secret Handling** | Never display/log passwords or API-Keys plaintext |
| **Modular JavaScript** | Clean separation: API abstraction, Config mgmt, UI logic |
| **Progressive Enhancement** | Works without JavaScript (basic HTML visible) |
| **SPA Routing** | Client-side tab navigation, Server-side SPA fallback |

## Komponenten

### 1. index.html - SPA Struktur

**Verantwortung:** Layout, Navigation, HTML-Struktur für alle 5 Tabs

**Tabs:**
- **USB-Settings:** Port, Baud-Rate, Data-Bits, Stop-Bits, Parity, Timeout
- **Device-Choice:** Dropdown mit Geräte-Scan von `/api/devices`
- **API-Server:** Host, Port, Log-Level, HTTPS Toggle
- **Wavelog-Integration:** URL, API-Key, Station-Select, Test-Button, Polling-Interval
- **Info:** System-Informationen, API-Endpoints, Links zu Swagger/ReDoc

**Wichtige IDs:**
- Forms: `usb-form`, `device-form`, `api-form`, `wavelog-form`
- Inputs: `usb-port`, `usb-baud`, `device-select`, `api-host`, `wavelog-url`, etc.
- Status: `usb-status`, `cat-status`, `device-name`
- Messages: `usb-message`, `device-message`, `api-message`, `wavelog-message`

---

### 2. base-styles.css - Theme System

**Verantwortung:** CSS-Variables, Layout (Header/Main/Footer), Responsive Design

**CSS-Variables (Light-Mode Default):**

```css
/* Farben */
--color-primary:              #0066cc;  /* Blau */
--color-success:              #28a745;  /* Grün */
--color-warning:              #ffc107;  /* Gelb */
--color-danger:               #dc3545;  /* Rot */
--color-text:                 #333;
--color-text-light:           #666;
--bg-primary:                 #ffffff;
--bg-secondary:               #f8f9fa;
--border-color:               #ddd;

/* Spacing */
--spacing-xs:                 4px;
--spacing-sm:                 8px;
--spacing-md:                 16px;
--spacing-lg:                 24px;
--spacing-xl:                 32px;

/* Typography */
--font-family:                -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto;
--font-size-base:             14px;
--font-size-sm:               12px;
--font-size-large:            16px;
--line-height:                1.5;
```

**Dark-Mode Override:**
```css
body.dark-mode {
  --color-text: #e0e0e0;
  --color-text-light: #a0a0a0;
  --bg-primary: #1e1e1e;
  --bg-secondary: #2d2d2d;
  --border-color: #444;
}
```

---

### 3. components.css - Component Styles

**Verantwortung:** Button, Form, Status-Badge, Info-Box Styles

**Components:**
- `.btn-primary`, `.btn-secondary`, `.btn-danger`, `.btn-icon` - Button-Varianten
- `.form-group`, `.form-checkbox` - Form-Layouts
- `input`, `select` - Input-Styles mit Focus/Validation
- `.status-badge` - USB/CAT Status-Badges (🟢/🟡/⚫)
- `.info-box` - Info-Container
- `.form-message` - Success/Error/Info Messages
- `.endpoint-list` - Code-formatted Endpoint-Liste

---

### 4. theme.css - User Customization

**Verantwortung:** Placeholder für Benutzer-Anpassungen

**Beispiel (Benutzerdefiniert):**
```css
:root {
  --color-primary: #ff6b6b;      /* Custom Primary Color */
  --font-size-base: 15px;        /* Custom Font Size */
}
```

**Einbindung in Docker:**
```yaml
volumes:
  - ./theme.css:/app/src/frontend/assets/theme.css  # Mount ermöglicht Anpassung
```

---

### 5. api-client.js - HTTP Abstraction

**Verantwortung:** Centralisierte API-Kommunikation, Error-Handling

**Globale Instanz:**
```javascript
const api = new ApiClient('/api');
```

**Wichtige Methoden:**

| Methode | Beschreibung |
|---------|-------------|
| `request(method, path, body)` | Base HTTP Methode (GET/POST/PUT/DELETE) |
| `getConfig()` | GET /api/config |
| `updateConfig(section, data)` | PUT /api/config (section-level update) |
| `getStatus()` | GET /api/status |
| `getDevices()` | GET /api/devices (YAML-Scan) |
| `testWavelogConnection()` | GET /api/wavelog/test |
| `getWavelogStations()` | GET /api/wavelog/stations |
| `getFrequency()` | GET /api/rig/frequency |
| `setFrequency(value)` | PUT /api/rig/frequency |

**Error Handling:**
```javascript
try {
  const config = await api.getConfig();
} catch (error) {
  // error instanceof ApiError
  console.error(error.message, error.status, error.code);
}
```

---

### 6. config-manager.js - Config Persistence

**Verantwortung:** Load/Save/Validate Config, Secret Masking, Client-side Caching

**Globale Instanz:**
```javascript
const configManager = new ConfigManager();
```

**Wichtige Methoden:**

| Methode | Beschreibung |
|---------|-------------|
| `loadConfig()` | Lädt Config von `api.getConfig()`, cached Resultat |
| `saveSection(section, data)` | Speichert USB/Device/API/Wavelog Section |
| `getConfig()` | Gibt gecachte Config zurück |
| `getValue(path, default)` | Dot-notation Access: `"usb.port"` |
| `validate(section, data)` | Gibt Array von Validierungs-Fehlern |
| `displayValue(section, key)` | Gibt `"***"` für Secrets, sonst Wert |

**Validation:**
```javascript
const errors = configManager.validate('usb', {
  port: 'COM4',
  baud_rate: 115200,
});
// Returns: ['Port format invalid'] oder []
```

**Validierungs-Regeln:**

| Section | Regeln |
|---------|--------|
| **usb** | Port: Windows COM*/Linux /dev/tty*, Baud: enum [9600, 19200, 38400, 115200], Data: 7/8, Parity: N/E/O |
| **api** | Host: IPv4 oder valid Domain-Name, Port: 1-65535, Log-Level: DEBUG/INFO/WARNING/ERROR |
| **wavelog** | URL: valid HTTPS/HTTP, Polling: 5-300 seconds |
| **device** | Name: required (nicht leer) |

---

### 7. status-widget.js - Real-Time Status

**Verantwortung:** Poll `/api/status` alle 5 Sekunden, update Status-Badges

**Globale Instanz:**
```javascript
const statusWidget = new StatusWidget({
  pollInterval: 5000  // 5 Sekunden
});
```

**Methoden:**
- `start()` - Startet Polling
- `stop()` - Stoppt Polling
- `updateStatus()` - Ruft API auf, rendert Status

**Status-Mapping:**

| Badge | Condition | Icon | Text |
|-------|-----------|------|------|
| **USB** | usb_connected == true | 🟢 | Verbunden |
| **USB** | usb_connected == false | ⚫ | Getrennt |
| **CAT** | secret_provider_available && !degraded_mode | 🟢 | Aktiv |
| **CAT** | degraded_mode == true | 🟡 | Eingeschränkt |
| **CAT** | Default | ⚫ | Inaktiv |
| **Device** | - | - | device_name oder '-' |

---

### 8. theme-switcher.js - Light/Dark Mode

**Verantwortung:** Toggle Light/Dark, persist theme zu LocalStorage, system preference fallback

**Globale Instanz:**
```javascript
const themeSwitcher = new ThemeSwitcher({
  storageKey: 'rigbridge-theme',
  defaultTheme: 'light'
});
```

**Methoden:**
- `init()` - Lädt Theme beim Startup
- `toggle()` - Schaltet zwischen light/dark
- `setTheme(theme)` - Setzt spezifisches Theme
- `loadTheme()` - LocalStorage → fallback zu System-Preference

**Persistierung:**
```javascript
// LocalStorage key: 'rigbridge-theme'
// Values: 'light' oder 'dark'
// System-Fallback: prefers-color-scheme: dark media query
```

**Dark-Mode Class:**
```javascript
// body.dark-mode class wird gesetzt
// CSS-Variables werden automatisch überschrieben
```

---

### 9. app.js - Main Orchestrator

**Verantwortung:** Event-Handler, Form-Submission, Tab-Navigation, Initialization

**Initialization (DOMContentLoaded):**
1. `themeSwitcher.init()` - Theme laden
2. `statusWidget.start()` - Polling starten
3. `configManager.loadConfig()` - Config vom API laden
4. `loadDevices()` - Geräte-Dropdown populieren
5. `populateFormFields()` - Formularfelder mit Config-Werten füllen
6. `setupFormHandlers()` - Event-Listener registrieren
7. `setupTabNavigation()` - Tab-Switching initialisieren

**Form Handlers:**

| Form | Handler | Validierung |
|------|---------|-------------|
| `usb-form` | `submitUSBConfig()` | configManager.validate('usb', ...) |
| `device-form` | `submitDeviceConfig()` | JSON.parse(select.value) |
| `api-form` | `submitAPIConfig()` | configManager.validate('api', ...) |
| `wavelog-form` | `submitWavelogConfig()` | validate if enabled |
| Wavelog-Test-Btn | `testWavelogConnection()` | api.testWavelogConnection() |

**Tab Navigation:**
```javascript
// Click .nav-tab → toggle active class, show/hide .tab-content
navTabs.forEach(tab => {
  tab.addEventListener('click', () => {
    // Set active tab, show corresponding content
  });
});
```

---

## Workflow: Config ändern

```
┌─────────────────────────────────────────────────────────────┐
│ User fills form (e.g., USB Port) & clicks "Speichern"       │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ app.js: submitUSBConfig() called                            │
│  - Collect form values                                       │
│  - Call configManager.validate()                             │
│  - If errors, show showMessage('usb-message', errors)        │
└──────────────────────┬──────────────────────────────────────┘
                       │ (Valid)
┌──────────────────────▼──────────────────────────────────────┐
│ app.js: configManager.saveSection('usb', data)              │
│  - Call api.updateConfig('usb', data)                       │
│  - PUT /api/config with {usb: {...}}                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ Backend: PUT /api/config                                    │
│  - Validate config section                                  │
│  - Merge with existing config                                │
│  - Write to config.json                                      │
│  - Return {usb: {...}} or {error: ...}                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ ui-client: showMessage('usb-message', '✓ Saved!', 'success')│
│  - Auto-hide after 5s                                       │
│  - Update local cache (configManager)                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Theme Customization

### Light/Dark Mode Toggle

**Funktionsweise:**
1. User klickt auf 🌙 Button im Header
2. `themeSwitcher.toggle()` wird aufgerufen
3. `.dark-mode` class wird auf `<body>` gesetzt/entfernt
4. CSS-Variables werden automatisch überschrieben
5. Theme wird zu LocalStorage gespeichert

### Custom CSS-Variables

**Benutzer möchte Primary-Color ändern:**

**Option 1: theme.css Datei (für Docker/Production):**
```css
/* theme.css im Projekt-Root */
:root {
  --color-primary: #ff6b6b;  /* Benutzerdefinierte Farbe */
}
```

**Option 2: Browser DevTools (für schnelle Tests):**
```javascript
// In Browser Console:
document.documentElement.style.setProperty('--color-primary', '#ff6b6b');
```

**Verfügbare CSS-Variables:**
- Farben: `--color-primary`, `--color-success`, `--color-danger`, `--color-warning`
- Spacing: `--spacing-xs`, `--spacing-sm`, `--spacing-md`, `--spacing-lg`, `--spacing-xl`
- Typography: `--font-size-base`, `--font-size-sm`, `--font-size-large`
- Hintergründe: `--bg-primary`, `--bg-secondary`
- Borders: `--border-color`

---

## Security Best Practices

### Secret Handling

**❌ NEVER:**
```javascript
// WRONG: Display plaintext secrets
const apiKey = config.wavelog.api_key_secret_ref;
console.log(apiKey);  // 🔴 Logged to console!
```

**✅ DO:**
```javascript
// RIGHT: Use displayValue() for UI
const display = configManager.displayValue('wavelog', 'api_key_secret_ref');
console.log(display);  // "***" - safely masked

// API-Key nur zum Speichern:
await configManager.saveSection('wavelog', {
  api_key_secret_ref: document.getElementById('wavelog-apikey').value
});
```

### Form Security

- **Password Fields:** `<input type="password">` nicht `type="text"` für Secrets
- **No Cookies:** Stateless UI, kein Browser-Cookie-Storage für Secrets
- **HTTPS Only (Production):** API über HTTPS sichern
- **CSP Headers:** Server sollte Content-Security-Policy Headers setzen

---

## Error Handling

### API Errors

```javascript
try {
  const devices = await api.getDevices();
} catch (error) {
  if (error instanceof ApiError) {
    console.error(`API Error: ${error.message}`);
    console.error(`Status: ${error.status}`);
    console.error(`Code: ${error.code}`);
    
    showMessage('device-message', error.message, 'error');
  }
}
```

### Validation Errors

```javascript
const section = 'usb';
const data = { port: 'INVALID' };
const errors = configManager.validate(section, data);

if (errors.length > 0) {
  errors.forEach(err => console.warn(`Validation error: ${err}`));
  showMessage('usb-message', errors.join('; '), 'error');
}
```

---

## Testing Frontend Manually

### 1. Start Backend (Native on Windows)

```cmd
cd c:\Software\_repos\.GitHub\m2-eng\RigBridge
python run_api.py
```

Backend läuft auf http://127.0.0.1:8080

### 2. Open Browser

```
http://127.0.0.1:8080
```

### 3. Test USB Form

1. Fill in USB Port (e.g., `COM3` or `/dev/ttyUSB0`)
2. Set Baud-Rate to `115200`
3. Click "Speichern"
4. Should show ✓ success message
5. Refresh page - values should persist

### 4. Test Theme Toggle

1. Click 🌙 button in header
2. Should switch to dark-mode
3. Refresh page - dark-mode should persist
4. CSS-Variables should update (colors change)

### 5. Test Wavelog Integration

1. Go to Wavelog tab
2. Check "Wavelog-Integration aktivieren"
3. Fill in URL and API-Key
4. Click "Verbindung testen"
5. Should show mock stations or error message

### 6. Test Device Selection

1. Go to Device-Choice tab
2. Dropdown should populate with devices from `/api/devices`
3. Select device and click "Speichern"

### 7. Monitor Status Widget

1. Watch USB/CAT/Device badges at top
2. Should update every 5 seconds (color changes)
3. If USB connected, should show 🟢

---

## Browser Compatibility

| Browser | Version | Support |
|---------|---------|---------|
| Chrome | 90+ | ✅ Full |
| Firefox | 88+ | ✅ Full |
| Safari | 14+ | ✅ Full |
| Edge | 90+ | ✅ Full |
| IE 11 | - | ❌ Not supported (ES6 required) |

---

## Performance Optimization

### Caching

- **Config:** Cached by ConfigManager (load once on startup)
- **Devices:** Loaded once on startup (could add refresh button)
- **Status:** Polled every 5s (configurable in statusWidget)

### Lazy Loading

- Assets loaded from `/assets/` directory
- CSS-Variables loaded once at startup
- JavaScript modules loaded in dependency order

### Network

- Minimal network requests (only when needed)
- Batch config updates via `PUT /api/config`
- Status polling can be stopped with `statusWidget.stop()`

---

## Glossary

| Term | Definition |
|------|-----------|
| **SPA** | Single-Page Application - kein Page-Reload bei Navigation |
| **CSS-Variables** | CSS Custom Properties (--var-name) für Dynamic Styling |
| **LocalStorage** | Browser-Speicher für Persistence (theme, preferences) |
| **CAT** | Computer Aided Transceiver - digitale Funk-Steuerung |
| **Secret-Ref** | Reference zu Secret-Value in Vault (z.B. "rigbridge/wavelog#api_key") |
| **Degraded Mode** | API funktioniert aber mit eingeschränkter Funktionalität (z.B. kein Secret) |

---

## Support & Resources

- **Backend API Docs:** http://127.0.0.1:8080/api/docs (Swagger UI)
- **Alternative API Docs:** http://127.0.0.1:8080/api/redoc (ReDoc)
- **Config Storage:** `config.json` in Projekt-Root
- **Theme File:** `theme.css` in Projekt-Root (Docker-mountbar)
