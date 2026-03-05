/**
 * Config Manager für RigBridge
 *
 * Verwaltet das Laden, Speichern und lokale Caching der Konfiguration.
 * Bietet auch Hilfsfunktionen für Validierung und Maskierung von Secrets.
 */

class ConfigManager {
  constructor() {
    this.config = null;
    this.isLoading = false;
    this.loadPromise = null;
  }

  /**
   * Lädt die aktuelle Konfiguration von der API.
   * @returns {Promise<object>} Die aktuelle Konfiguration
   */
  async loadConfig() {
    // Verhindere mehrfaches Laden
    if (this.isLoading) {
      return this.loadPromise;
    }

    this.isLoading = true;
    this.loadPromise = api
      .getConfig()
      .then((data) => {
        this.config = data;
        console.debug('Config loaded:', data);
        return data;
      })
      .catch((error) => {
        console.error('Failed to load config:', error);
        throw error;
      })
      .finally(() => {
        this.isLoading = false;
      });

    return this.loadPromise;
  }

  /**
   * Gibt die aktuell gecachte Konfiguration zurück.
   * Wirft einen Fehler, wenn nicht geladen.
   * @returns {object} Die Konfiguration
   */
  getConfig() {
    if (!this.config) {
      throw new Error('Config not loaded. Call loadConfig() first.');
    }
    return this.config;
  }

  /**
   * Gibt einen Konfigurationswert mit Pfad zurück.
   * @param {string} path - Pfad im Format "section.key" oder "section.subsection.key"
   * @param {any} defaultValue - Standardwert wenn nicht gefunden
   * @returns {any} Der Konfigurationswert oder defaultValue
   */
  getValue(path, defaultValue = undefined) {
    const config = this.getConfig();
    const keys = path.split('.');
    let value = config;

    for (const key of keys) {
      if (value && typeof value === 'object' && key in value) {
        value = value[key];
      } else {
        return defaultValue;
      }
    }

    return value;
  }

  /**
   * Speichert Konfigurationsänderungen für einen Abschnitt.
   * @param {string} section - Sektion (usb, api, wavelog, device, secret_provider)
   * @param {object} data - Neue Werte
   * @param {object} options - Optionen {validateBeforeSave, showMessage}
   * @returns {Promise<object>} Response von der API
   */
  async saveSection(section, data, options = {}) {
    const { validateBeforeSave = true, showMessage = true } = options;

    // Validierung
    if (validateBeforeSave) {
      const errors = this.validate(section, data);
      if (errors.length > 0) {
        throw new ValidationError('Validation failed', errors);
      }
    }

    try {
      const response = await api.updateConfig(section, data);

      // Update lokales Cache
      if (this.config && this.config[section]) {
        this.config[section] = { ...this.config[section], ...data };
      }

      console.info(`Config section "${section}" saved successfully`);
      return response;
    } catch (error) {
      console.error(`Failed to save config section "${section}":`, error);
      throw error;
    }
  }

  /**
   * Validiert Konfigurationsdaten für einen Abschnitt.
   * @param {string} section - Sektion
   * @param {object} data - Zu validierende Daten
   * @returns {string[]} Array von Fehlermeldungen (leer wenn valid)
   */
  validate(section, data) {
    const errors = [];

    switch (section) {
      case 'usb':
        if (data.port && !this.isValidPort(data.port)) {
          errors.push('Port must be a valid device path (e.g., COM3 or /dev/ttyUSB0)');
        }
        if (data.baud_rate && ![9600, 19200, 38400, 57600, 115200].includes(data.baud_rate)) {
          errors.push('Invalid baud rate');
        }
        if (data.data_bits && ![7, 8].includes(data.data_bits)) {
          errors.push('Data bits must be 7 or 8');
        }
        if (data.stop_bits && ![1, 2].includes(data.stop_bits)) {
          errors.push('Stop bits must be 1 or 2');
        }
        if (data.parity && !['N', 'E', 'O'].includes(data.parity)) {
          errors.push('Invalid parity');
        }
        break;

      case 'api':
        if (data.host && !this.isValidHost(data.host)) {
          errors.push('Invalid host address');
        }
        if (data.port && (data.port < 1 || data.port > 65535)) {
          errors.push('Port must be between 1 and 65535');
        }
        if (data.log_level && !['DEBUG', 'INFO', 'WARNING', 'ERROR'].includes(data.log_level)) {
          errors.push('Invalid log level');
        }
        break;

      case 'wavelog':
        if (data.api_url && !this.isValidUrl(data.api_url)) {
          errors.push('Wavelog API URL must be a valid URL');
        }
        if (data.polling_interval && (data.polling_interval < 1 || data.polling_interval > 300)) {
          errors.push('Polling interval must be between 1 and 300 seconds');
        }
        break;

      case 'device':
        if (data.name && data.name.trim().length === 0) {
          errors.push('Device name is required');
        }
        break;
    }

    return errors;
  }

  /**
   * Validiert, ob ein Port ein gültiger Pfad ist.
   * @private
   * @param {string} port - Zu validierender Port
   * @returns {boolean} true wenn valide
   */
  isValidPort(port) {
    // Windows: COM1-COM9, COM10+
    const windowsPattern = /^COM\d+$/i;
    // Linux: /dev/tty* oder /dev/cu.*
    const linuxPattern = /^\/dev\/(tty|cu)\w+$/;

    return windowsPattern.test(port) || linuxPattern.test(port);
  }

  /**
   * Validiert, ob ein Host gültig ist.
   * @private
   * @param {string} host - Zu validierender Host
   * @returns {boolean} true wenn valide
   */
  isValidHost(host) {
    // Einfache Validierung: localhost, 127.0.0.1, 0.0.0.0, oder DNS-Name
    const ipv4Pattern = /^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
    const localhostPattern = /^localhost$/i;
    const dnsPattern = /^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/;

    return ipv4Pattern.test(host) || localhostPattern.test(host) || dnsPattern.test(host);
  }

  /**
   * Validiert, ob eine URL gültig ist.
   * @private
   * @param {string} url - Zu validierende URL
   * @returns {boolean} true wenn valide
   */
  isValidUrl(url) {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Gibt einen Wert ohne Secrets zurück (maskiert für Anzeige).
   * @param {string} section - Sektion
   * @param {string} key - Schlüssel
   * @returns {string} Der Wert oder "***" wenn es ein Secret ist
   */
  displayValue(section, key) {
    const value = this.getValue(`${section}.${key}`);

    // Maskiere bekannte Secret-Felder
    if (key.includes('secret_ref') || key.includes('api_key') || key.includes('token') || key.includes('password')) {
      return value ? '***' : '';
    }

    return String(value);
  }
}

/**
 * Custom Error-Klasse für Validierungsfehler.
 */
class ValidationError extends Error {
  constructor(message, errors = []) {
    super(message);
    this.name = 'ValidationError';
    this.errors = errors;
  }
}

// Globale Instanz
const configManager = new ConfigManager();
