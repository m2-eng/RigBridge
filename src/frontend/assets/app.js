/**
 * Main App Initialization für RigBridge UI
 *
 * Stellt alle Komponenten zusammen und iniailisiert die Formulare.
 */

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', async () => {
  console.info('RigBridge UI initializing...');

  // Theme initialisieren
  themeSwitcher.init();

  // Status-Widget starten
  statusWidget.start();

  // Config laden
  try {
    await configManager.loadConfig();
    console.info('Config loaded successfully');
  } catch (error) {
    console.error('Failed to load config:', error);
    showMessage('api-message', `Error loading config: ${error.message}`, 'error');
  }

  // Geräte laden
  try {
    await loadDevices();
  } catch (error) {
    console.error('Failed to load devices:', error);
  }

  // UI mit Config-Werten füllen
  await populateFormFields();

  // Config in Info-Tab anzeigen
  displayConfigJson();

  // Event-Listener für Formulare
  setupFormHandlers();

  // Tab-Navigation
  setupTabNavigation();

  console.info('RigBridge UI initialized');
});

// ============================================================================
// TAB NAVIGATION
// ============================================================================

function setupTabNavigation() {
  const navTabs = document.querySelectorAll('.nav-tab');
  const tabContents = document.querySelectorAll('.tab-content');

  console.info(`Found ${navTabs.length} nav tabs and ${tabContents.length} tab contents`);

  navTabs.forEach((tab) => {
    tab.addEventListener('click', (e) => {
      e.preventDefault();
      console.info(`Tab clicked: ${tab.dataset.tab}`);

      // Tab als aktiv markieren
      navTabs.forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');

      // Content anzeigen
      const tabId = tab.dataset.tab;
      tabContents.forEach((content) => {
        content.classList.remove('active');
      });
      const activeContent = document.getElementById(`${tabId}-tab`);
      if (activeContent) {
        activeContent.classList.add('active');
        console.info(`Activated tab: ${tabId}-tab`);
      } else {
        console.warn(`Tab content not found: ${tabId}-tab`);
      }
    });
  });
}

// ============================================================================
// FORM POPULATION
// ============================================================================

async function populateFormFields() {
  try {
    const config = configManager.getConfig();
    console.info('Config loaded for form population:', config);

    // USB-Form
    if (config.usb) {
      const usbPort = document.getElementById('usb-port');
      if (usbPort) usbPort.value = config.usb.port || '';

      const usbBaud = document.getElementById('usb-baud');
      if (usbBaud) usbBaud.value = config.usb.baud_rate || 19200;

      const usbDatabits = document.getElementById('usb-databits');
      if (usbDatabits) usbDatabits.value = config.usb.data_bits || 8;

      const usbStopbits = document.getElementById('usb-stopbits');
      if (usbStopbits) usbStopbits.value = config.usb.stop_bits || 1;

      const usbParity = document.getElementById('usb-parity');
      if (usbParity) usbParity.value = config.usb.parity || 'N';

      const usbTimeout = document.getElementById('usb-timeout');
      if (usbTimeout) usbTimeout.value = config.usb.timeout || 2000;

      const usbReconnect = document.getElementById('usb-reconnect');
      if (usbReconnect) usbReconnect.value = config.usb.reconnect_interval || 5;

      console.info('USB form populated');
    }

    // Device-Form
    if (config.device) {
      // wird später mit der geladenen Gerätelist gefüllt
    }

    // API-Form
    if (config.api) {
      const apiHost = document.getElementById('api-host');
      if (apiHost) apiHost.value = config.api.host || '127.0.0.1';

      const apiPort = document.getElementById('api-port');
      if (apiPort) apiPort.value = config.api.port || 8080;

      const apiLoglevel = document.getElementById('api-loglevel');
      if (apiLoglevel) apiLoglevel.value = config.api.log_level || 'INFO';

      const apiHttps = document.getElementById('api-https');
      if (apiHttps) apiHttps.checked = config.api.enable_https || false;

      console.info('API form populated');
    }

    // Wavelog-Form
    if (config.wavelog) {
      const wavelogEnabled = document.getElementById('wavelog-enabled');
      if (wavelogEnabled) wavelogEnabled.checked = config.wavelog.enabled || false;

      const wavelogUrl = document.getElementById('wavelog-url');
      if (wavelogUrl) wavelogUrl.value = config.wavelog.api_url || '';

      const wavelogPolling = document.getElementById('wavelog-polling');
      if (wavelogPolling) wavelogPolling.value = config.wavelog.polling_interval || 30;

      // Toggle der Wavelog-Konfiguration
      toggleWavelogConfig(config.wavelog.enabled);

      console.info('Wavelog form populated');
    }

    // Info-Tab
    try {
      const status = await api.getStatus();
      const apiVersion = document.getElementById('api-version');
      if (apiVersion) apiVersion.textContent = status.api_version || '-';

      const infoDevice = document.getElementById('info-device');
      if (infoDevice) infoDevice.textContent = config.device?.name || '-';

      const infoPort = document.getElementById('info-port');
      if (infoPort) infoPort.textContent = config.usb?.port || '-';

      const infoStatus = document.getElementById('info-status');
      if (infoStatus) infoStatus.textContent = status.usb_connected ? 'Connected' : 'Disconnected';

      console.info('Info tab populated with status');
    } catch (statusError) {
      console.warn('Could not fetch status, but forms still populated:', statusError);
    }

    // Rig-Status laden (Frequenz und Modus)
    try {
      await updateRigStatus();
    } catch (rigError) {
      console.warn('Could not fetch rig status:', rigError);
    }

    console.info('Form population completed successfully');
  } catch (error) {
    console.error('Failed to populate forms:', error);
  }
}

// ============================================================================
// CONFIG JSON DISPLAY
// ============================================================================

function displayConfigJson() {
  try {
    const config = configManager.getConfig();

    // Tiefe Kopie des Config-Objekts erstellen
    const displayConfig = JSON.parse(JSON.stringify(config));

    // Alle Secret-Felder maskieren (Felder mit Namen *_secret_ref oder *_key, die mit _ oder _ aus mehreren Teilen bestehen)
    const maskSecrets = (obj) => {
      if (typeof obj !== 'object' || obj === null) {
        return;
      }

      for (const key in obj) {
        if (obj.hasOwnProperty(key)) {
          // Maskiere alle Felder, die auf *_secret_ref oder *_key enden
          if (key.includes('secret') || key.includes('key') || key.includes('password')) {
            obj[key] = '***';
          } else if (typeof obj[key] === 'object') {
            // Rekursiv in verschachtelten Objekten nach Secrets suchen
            maskSecrets(obj[key]);
          }
        }
      }
    };

    maskSecrets(displayConfig);

    // JSON formatieren und anzeigen
    const jsonString = JSON.stringify(displayConfig, null, 2);
    const codeElement = document.querySelector('#config-json code');
    if (codeElement) {
      codeElement.textContent = jsonString;
    }
  } catch (error) {
    console.error('Failed to display config JSON:', error);
    const codeElement = document.querySelector('#config-json code');
    if (codeElement) {
      codeElement.textContent = `Error loading config: ${error.message}`;
    }
  }
}

// ============================================================================
// FORM HANDLERS
// ============================================================================

function setupFormHandlers() {
  // USB-Form
  const usbForm = document.getElementById('usb-form');
  if (usbForm) {
    usbForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      await submitUSBConfig();
    });
  }

  // Device-Form
  const deviceForm = document.getElementById('device-form');
  if (deviceForm) {
    deviceForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      await submitDeviceConfig();
    });
  }

  // API-Form
  const apiForm = document.getElementById('api-form');
  if (apiForm) {
    apiForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      await submitAPIConfig();
    });
  }

  // Wavelog-Form
  const wavelogForm = document.getElementById('wavelog-form');
  const wavelogToggle = document.getElementById('wavelog-enabled');
  if (wavelogForm) {
    wavelogToggle.addEventListener('change', (e) => {
      toggleWavelogConfig(e.target.checked);
    });

    wavelogForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      await submitWavelogConfig();
    });

    // Wavelog-Test-Button
    const testBtn = document.getElementById('wavelog-test-btn');
    if (testBtn) {
      testBtn.addEventListener('click', async () => {
        await testWavelogConnection();
      });
    }
  }

  // Rig-Status Refresh-Button
  const refreshRigBtn = document.getElementById('refresh-rig-status');
  if (refreshRigBtn) {
    refreshRigBtn.addEventListener('click', async () => {
      await updateRigStatus();
    });
  }

  // LOGS Tab - Event Listener
  const logsRefreshBtn = document.getElementById('logs-refresh-btn');
  if (logsRefreshBtn) {
    logsRefreshBtn.addEventListener('click', async () => {
      await refreshLogs();
    });
  }

  const logsClearBtn = document.getElementById('logs-clear-btn');
  if (logsClearBtn) {
    logsClearBtn.addEventListener('click', () => {
      clearLogs();
    });
  }

  const logsAutoRefresh = document.getElementById('logs-auto-refresh');
  if (logsAutoRefresh) {
    logsAutoRefresh.addEventListener('change', (e) => {
      toggleAutoRefresh(e.target.checked);
    });
  }

  const logsFilterLevel = document.getElementById('logs-filter-level');
  if (logsFilterLevel) {
    logsFilterLevel.addEventListener('change', (e) => {
      filterLogs(e.target.value);
    });
  }

  const logsLimitInput = document.getElementById('logs-limit');
  if (logsLimitInput) {
    logsLimitInput.addEventListener('change', async () => {
      await refreshLogs();
    });
  }

  // Initialer Load der Logs beim Seitenload
  setTimeout(() => {
    const logsTab = document.getElementById('logs-tab');
    if (logsTab && !logsTab.innerHTML.includes('No logs')) {
      // Lade nur Logs, wenn der Tab noch leer ist
      loadLogs(100).catch(console.error);
    }
  }, 1000);
}

// ============================================================================
// USB CONFIG
// ============================================================================

async function submitUSBConfig() {
  try {
    const data = {
      port: document.getElementById('usb-port').value,
      baud_rate: parseInt(document.getElementById('usb-baud').value),
      data_bits: parseInt(document.getElementById('usb-databits').value),
      stop_bits: parseInt(document.getElementById('usb-stopbits').value),
      parity: document.getElementById('usb-parity').value,
      timeout: parseInt(document.getElementById('usb-timeout').value) || 2000,
      reconnect_interval: parseInt(document.getElementById('usb-reconnect').value) || 5,
    };

    // Validierung
    const errors = configManager.validate('usb', data);
    if (errors.length > 0) {
      showMessage('usb-message', errors.join('; '), 'error');
      return;
    }

    await configManager.saveSection('usb', data, { validateBeforeSave: false });

    // Lade die Konfiguration neu, um die vom Backend geänderten Werte zu synchronisieren
    await configManager.loadConfig();

    // Aktualisiere die Formulare mit den neuesten Werten
    await populateFormFields();

    showMessage('usb-message', 'USB configuration saved successfully!', 'success');
  } catch (error) {
    console.error('Failed to save USB config:', error);
    showMessage('usb-message', `Error: ${error.message}`, 'error');
  }
}

// ============================================================================
// DEVICE CONFIG
// ============================================================================

async function loadDevices() {
  try {
    const response = await api.getDevices();
    const select = document.getElementById('device-select');

    if (!select) {
      console.warn('device-select element not found');
      return;
    }

    // Lösche alte Optionen
    select.innerHTML = '<option value="">-- Wähle ein Gerät --</option>';

    // Füge Geräte hinzu
    response.devices.forEach((device) => {
      const option = document.createElement('option');
      option.value = JSON.stringify({
        name: device.name,
        manufacturer: device.manufacturer,
        protocol_file: device.protocol_file,
      });
      option.textContent = device.name;
      select.appendChild(option);
    });

    // Markiere aktuelles Gerät
    const config = configManager.getConfig();
    if (config.device) {
      const currentValue = JSON.stringify({
        name: config.device.name,
        manufacturer: config.device.manufacturer,
        protocol_file: config.device.protocol_file,
      });

      for (const option of select.options) {
        if (option.value === currentValue) {
          option.selected = true;
          break;
        }
      }
    }

    console.info('Devices loaded successfully');
  } catch (error) {
    console.error('Failed to load devices:', error);
  }
}

async function submitDeviceConfig() {
  try {
    const select = document.getElementById('device-select');
    if (!select.value) {
      showMessage('device-message', 'Please select a device', 'error');
      return;
    }

    const deviceData = JSON.parse(select.value);
    await configManager.saveSection('device', deviceData);

    // Lade die Konfiguration neu, um die vom Backend geänderten Werte zu synchronisieren
    await configManager.loadConfig();

    // Aktualisiere die Formulare mit den neuesten Werten
    await populateFormFields();

    showMessage('device-message', 'Device configuration saved successfully!', 'success');
  } catch (error) {
    console.error('Failed to save device config:', error);
    showMessage('device-message', `Error: ${error.message}`, 'error');
  }
}

// ============================================================================
// API CONFIG
// ============================================================================

async function submitAPIConfig() {
  try {
    const data = {
      host: document.getElementById('api-host').value,
      port: parseInt(document.getElementById('api-port').value),
      log_level: document.getElementById('api-loglevel').value,
      enable_https: document.getElementById('api-https').checked,
    };

    const errors = configManager.validate('api', data);
    if (errors.length > 0) {
      showMessage('api-message', errors.join('; '), 'error');
      return;
    }

    await configManager.saveSection('api', data, { validateBeforeSave: false });

    // Lade die Konfiguration neu, um die vom Backend geänderten Werte zu synchronisieren
    await configManager.loadConfig();

    // Aktualisiere die Formulare mit den neuesten Werten
    await populateFormFields();

    showMessage('api-message', 'API configuration saved successfully!', 'success');
  } catch (error) {
    console.error('Failed to save API config:', error);
    showMessage('api-message', `Error: ${error.message}`, 'error');
  }
}

// ============================================================================
// WAVELOG CONFIG
// ============================================================================

function toggleWavelogConfig(enabled) {
  const configSection = document.getElementById('wavelog-config');
  if (configSection) {
    configSection.style.display = enabled ? 'block' : 'none';
  }
}

async function submitWavelogConfig() {
  try {
    const enabled = document.getElementById('wavelog-enabled').checked;

    const data = {
      enabled,
      api_url: document.getElementById('wavelog-url').value || '',
      api_key_or_secret_ref: document.getElementById('wavelog-apikey').value || '',
      polling_interval: parseInt(document.getElementById('wavelog-polling').value) || 30,
    };

    // Nur validiere wenn enabled
    if (enabled) {
      const errors = configManager.validate('wavelog', data);
      if (errors.length > 0) {
        showMessage('wavelog-message', errors.join('; '), 'error');
        return;
      }
    }

    await configManager.saveSection('wavelog', data, { validateBeforeSave: false });

    // Lade die Konfiguration neu, um die vom Backend geänderten Werte zu synchronisieren
    await configManager.loadConfig();

    // Aktualisiere die Formulare mit den neuesten Werten
    await populateFormFields();

    showMessage('wavelog-message', 'Wavelog configuration saved successfully!', 'success');
  } catch (error) {
    console.error('Failed to save Wavelog config:', error);
    showMessage('wavelog-message', `Error: ${error.message}`, 'error');
  }
}

async function testWavelogConnection() {
  try {
    const statusEl = document.getElementById('wavelog-test-status');
    statusEl.textContent = 'Speichern und Verbindung wird getestet...';
    statusEl.className = 'status-line info';

    // Speichere zuerst die aktuelle Config
    const enabled = document.getElementById('wavelog-enabled').checked;
    const data = {
      enabled,
      api_url: document.getElementById('wavelog-url').value || '',
      api_key_or_secret_ref: document.getElementById('wavelog-apikey').value || '',
      polling_interval: parseInt(document.getElementById('wavelog-polling').value) || 30,
    };

    // Validiere dass Werte vorhanden sind
    if (!data.api_url || !data.api_key_or_secret_ref) {
      statusEl.textContent = '✗ Connection failed: Wavelog URL and API Key required';
      statusEl.className = 'status-line error';
      return;
    }

    // Speichere Config
    await configManager.saveSection('wavelog', data, { validateBeforeSave: false });

    // Jetzt teste die Verbindung
    const result = await api.testWavelogConnection();

    if (result.success) {
      statusEl.textContent = `✓ Connection successful. Stations found: ${result.station_count || '?'}`;
      statusEl.className = 'status-line success';

      // Laden Sie die Stationen
      try {
        const stationsResponse = await api.getWavelogStations();
        const stationSelect = document.getElementById('wavelog-station');
        stationSelect.innerHTML = '<option value="">-- Wähle eine Station --</option>';

        stationsResponse.stations.forEach((station) => {
          const option = document.createElement('option');
          option.value = station.id;
          option.textContent = `${station.name} (${station.callsign})`;
          stationSelect.appendChild(option);
        });
      } catch (error) {
        console.warn('Failed to load stations:', error);
      }
    } else {
      statusEl.textContent = `✗ Connection failed: ${result.message}`;
      statusEl.className = 'status-line error';
    }
  } catch (error) {
    const statusEl = document.getElementById('wavelog-test-status');
    statusEl.textContent = `✗ Test error: ${error.message}`;
    statusEl.className = 'status-line error';
    console.error('Wavelog test failed:', error);
  }
}

// ============================================================================
// RIG STATUS UPDATE
// ============================================================================

async function updateRigStatus() {
  try {
    const rigFrequency = document.getElementById('rig-frequency');
    const rigMode = document.getElementById('rig-mode');

    if (!rigFrequency || !rigMode) {
      console.warn('Rig status elements not found');
      return;
    }

    // Setze Ladezustand
    rigFrequency.textContent = 'Lädt...';
    rigMode.textContent = 'Lädt...';

    // Frequenz abrufen
    try {
      const freqResponse = await api.getFrequency();
      if (freqResponse && freqResponse.frequency_hz !== undefined) {
        const freqMHz = (freqResponse.frequency_hz / 1_000_000).toFixed(6);
        rigFrequency.textContent = `${freqMHz} MHz`;
        rigFrequency.classList.remove('error');
      } else {
        rigFrequency.textContent = 'Nicht verfügbar';
        rigFrequency.classList.add('error');
      }
    } catch (freqError) {
      console.error('Failed to get frequency:', freqError);
      rigFrequency.textContent = `Fehler: ${freqError.message}`;
      rigFrequency.classList.add('error');
    }

    // Modus abrufen
    try {
      const modeResponse = await api.getMode();
      if (modeResponse && modeResponse.mode) {
        rigMode.textContent = modeResponse.mode;
        rigMode.classList.remove('error');
      } else {
        rigMode.textContent = 'Nicht verfügbar';
        rigMode.classList.add('error');
      }
    } catch (modeError) {
      console.error('Failed to get mode:', modeError);
      rigMode.textContent = `Fehler: ${modeError.message}`;
      rigMode.classList.add('error');
    }

    console.info('Rig status updated');
  } catch (error) {
    console.error('Failed to update rig status:', error);
  }
}

// ============================================================================
// LOGS TAB
// ============================================================================

let logsAutoRefreshInterval = null;

function _getLimit() {
  return Math.max(1, parseInt(document.getElementById('logs-limit')?.value || 100));
}

function _getLevelFilter() {
  return (document.getElementById('logs-filter-level')?.value || '').trim().toLowerCase();
}

/**
 * Holt die letzten `limit` Einträge direkt vom API (kein Browser-Cache)
 * und rendert sie sofort. Sortierung und Filterung passieren serverseitig.
 */
async function loadLogs(limit = 100) {
  const logsContainer = document.getElementById('logs-container');
  if (!logsContainer) return;

  logsContainer.innerHTML = '<div class="log-entry info">Lade Logs...</div>';

  try {
    const params = new URLSearchParams({
      limit: String(limit),
      newest_first: 'true',
    });
    const levelFilter = _getLevelFilter();
    if (levelFilter && levelFilter !== 'all') {
      params.set('level', levelFilter.toUpperCase());
    }

    // cache: 'no-store' verhindert, dass der Browser eine veraltete Antwort liefert
    const response = await fetch(`/api/logs?${params.toString()}`, { cache: 'no-store' });
    if (!response.ok) {
      logsContainer.innerHTML = '<div class="log-entry error">Fehler beim Laden der Logs: ' + response.status + '</div>';
      return;
    }
    const data = await response.json();
    _renderLogs(data.logs || [], logsContainer);
  } catch (error) {
    console.error('Failed to load logs:', error);
    logsContainer.innerHTML = `<div class="log-entry error">Fehler: ${error.message}</div>`;
    return;
  }
}

/** Rendert serverseitig gefilterte/sortierte Logs. */
function _renderLogs(entries, container) {
  const logsContainer = container || document.getElementById('logs-container');
  if (!logsContainer) return;

  if (entries.length === 0) {
    logsContainer.innerHTML = '<div class="log-entry info">Keine Logs verfügbar</div>';
    return;
  }

  let html = '';
  for (const log of entries) {
    const timeString = log.timestamp || 'N/A';
    const levelLower = (log.level || 'INFO').toLowerCase();
    html += `<div class="log-entry log-level-${levelLower}">` +
      `<span class="log-time">[${timeString}]</span> ` +
      `<span class="log-level">[${log.level}]</span> ` +
      `<span class="log-module">[${log.name || 'ROOT'}]</span> ` +
      `<span class="log-message">${escapeHtml(log.message)}</span>` +
      `</div>`;
  }

  logsContainer.innerHTML = html;
  logsContainer.scrollTop = 0;
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, m =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' })[m]);
}

async function refreshLogs() {
  await loadLogs(_getLimit());
}

function clearLogs() {
  const logsContainer = document.getElementById('logs-container');
  if (logsContainer) {
    logsContainer.innerHTML = '<div class="log-entry info">Logs gelöscht.</div>';
  }
}

function filterLogs() {
  refreshLogs().catch(console.error);
}

function toggleAutoRefresh(enabled) {
  if (enabled) {
    if (!logsAutoRefreshInterval) {
      logsAutoRefreshInterval = setInterval(refreshLogs, 2000);
    }
  } else {
    if (logsAutoRefreshInterval) {
      clearInterval(logsAutoRefreshInterval);
      logsAutoRefreshInterval = null;
    }
  }
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Zeigt eine Nachricht in einem Form-Element an.
 * @param {string} elementId - ID des Nachrichten-Elements
 * @param {string} message - Nachrichtentext
 * @param {string} type - 'success', 'error', 'info'
 */
function showMessage(elementId, message, type = 'info') {
  const messageEl = document.getElementById(elementId);
  if (messageEl) {
    messageEl.textContent = message;
    messageEl.className = `form-message ${type}`;

    // Auto-Hide nach 5 Sekunden (nur für success)
    if (type === 'success') {
      setTimeout(() => {
        messageEl.textContent = '';
        messageEl.className = 'form-message';
      }, 5000);
    }
  }
}

// Cleanup beim Unload
window.addEventListener('beforeunload', () => {
  if (statusWidget && statusWidget.isPolling) {
    statusWidget.stop();
  }
});
