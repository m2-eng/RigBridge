/**
 * API-Client für RigBridge
 *
 * Zentrale Komponente für HTTP-Kommunikation mit der REST-API.
 * Alle API-Calls gehen durch diese Klasse für einheitliches Fehlerhandling,
 * Logging und Response-Parsing.
 */

class ApiClient {
  /**
   * Erstellt einen neuen API-Client.
   * @param {string} baseUrl - Basis-URL der API (z.B. "/api")
   */
  constructor(baseUrl = '/api') {
    this.baseUrl = baseUrl;
    this.headers = {
      'Content-Type': 'application/json',
    };
  }

  /**
   * Macht einen HTTP-Request.
   * @private
   * @param {string} method - HTTP-Methode (GET, POST, PUT, DELETE)
   * @param {string} path - API-Pfad (ohne /api Präfix)
   * @param {object} body - Request-Body (optional)
   * @returns {Promise<object>} Response-Daten
   */
  async request(method, path, body = null) {
    const url = `${this.baseUrl}${path}`;
    const options = {
      method,
      headers: this.headers,
    };

    if (body) {
      options.body = JSON.stringify(body);
    }

    try {
      const response = await fetch(url, options);

      // Error-Handling für HTTP-Fehler
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({
          error: true,
          code: `HTTP_${response.status}`,
          message: response.statusText || 'Unknown error',
        }));

        throw new ApiError(
          errorData.message || 'API request failed',
          response.status,
          errorData.code || 'UNKNOWN',
          errorData
        );
      }

      return await response.json();
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }

      throw new ApiError(
        error.message || 'Network error',
        0,
        'NETWORK_ERROR',
        { error: true, message: error.message }
      );
    }
  }

  // ========================================================================
  // CONFIG ENDPOINTS
  // ========================================================================

  /**
   * Lädt die aktuelle Konfiguration.
   * Secrets werden maskiert (api_key_secret_ref: "***").
   * @returns {Promise<object>} Aktuelle Konfiguration
   */
  async getConfig() {
    return this.request('GET', '/config');
  }

  /**
   * Speichert Konfigurationsänderungen.
   * @param {string} section - Sektion (usb, api, wavelog, device, secret_provider)
   * @param {object} data - Neue Werte für die Sektion
   * @returns {Promise<object>} {success, message}
   */
  async updateConfig(section, data) {
    const payload = {
      [section]: data,
    };
    return this.request('PUT', '/config', payload);
  }

  /**
   * Lädt die aktuelle Status-Information.
   * @returns {Promise<object>} StatusResponse
   */
  async getStatus() {
    return this.request('GET', '/status');
  }

  // ========================================================================
  // DEVICE ENDPOINTS
  // ========================================================================

  /**
   * Ruft die Liste der verfügbaren Funkgeräte ab.
   * @returns {Promise<object>} {devices: [...]}
   */
  async getDevices() {
    return this.request('GET', '/devices');
  }

  /**
   * Ruft die Liste der verfügbaren Befehle ab.
   * @returns {Promise<object>} {commands: [...]}
   */
  async getCommands() {
    return this.request('GET', '/commands');
  }

  // ========================================================================
  // WAVELOG ENDPOINTS
  // ========================================================================

  /**
   * Testet die Verbindung zu Wavelog.
   * @returns {Promise<object>} WavelogTestResponse
   */
  async testWavelogConnection() {
    return this.request('GET', '/wavelog/test');
  }

  /**
   * Ruft die Stationenliste von Wavelog ab.
   * @returns {Promise<object>} WavelogStationsResponse
   */
  async getWavelogStations() {
    return this.request('GET', '/wavelog/stations');
  }

  // ========================================================================
  // RIG ENDPOINTS - Diese sind auch über API erreichbar
  // ========================================================================

  /**
   * Liest die aktuelle Frequenz des Funkgeräts.
   * @returns {Promise<object>} FrequencyResponse
   */
  async getFrequency() {
    return this.request('GET', '/rig/frequency');
  }

  /**
   * Setzt die Frequenz des Funkgeräts.
   * @param {number} frequencyHz - Frequenz in Hz
   * @returns {Promise<object>} CommandResponse
   */
  async setFrequency(frequencyHz) {
    return this.request('PUT', '/rig/frequency', { frequency_hz: frequencyHz });
  }

  /**
   * Liest den aktuellen Betriebsmodus.
   * @returns {Promise<object>} ModeResponse
   */
  async getMode() {
    return this.request('GET', '/rig/mode');
  }

  /**
   * Setzt den Betriebsmodus.
   * @param {string} mode - Modus (z.B. "CW", "SSB")
   * @returns {Promise<object>} CommandResponse
   */
  async setMode(mode) {
    return this.request('PUT', '/rig/mode', { mode });
  }

  /**
   * Liest den S-Meter-Wert.
   * @returns {Promise<object>} SMeterResponse
   */
  async getSMeter() {
    return this.request('GET', '/rig/s-meter');
  }

  /**
   * Führt einen generischen Befehl aus.
   * @param {string} commandName - Befehlsname aus YAML
   * @param {object} data - Befehlsdaten (optional)
   * @returns {Promise<object>} CommandResponse
   */
  async executeCommand(commandName, data = null) {
    const body = { command: commandName };
    if (data) {
      body.data = data;
    }
    return this.request('PUT', '/command/' + commandName, body);
  }
}

/**
 * Custom Error-Klasse für API-Fehler.
 */
class ApiError extends Error {
  constructor(message, status = 0, code = 'UNKNOWN', details = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

// Globale Instanz
const api = new ApiClient('/api');
