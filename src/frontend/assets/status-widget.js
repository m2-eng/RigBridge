/**
 * Status Widget für RigBridge
 *
 * Pollt regelmäßig den System-Status und aktualisiert die Status-Anzeige.
 * Zeigt Informationen über USB-Verbindung, CAT-Status, etc.
 */

class StatusWidget {
  constructor(options = {}) {
    this.pollInterval = options.pollInterval || 5000; // 5 Sekunden
    this.isPolling = false;
    this.pollTimer = null;

    // Elemente
    this.usbStatusEl = document.getElementById('usb-status');
    this.catStatusEl = document.getElementById('cat-status');
    this.deviceNameEl = document.getElementById('device-name');
  }

  /**
   * Startet das Polling des Status.
   */
  start() {
    if (this.isPolling) {
      return;
    }

    this.isPolling = true;
    console.info('StatusWidget: starting polling');

    // Erste Abfrage sofort
    this.updateStatus();

    // Dann regelmäßig
    this.pollTimer = setInterval(() => {
      this.updateStatus();
    }, this.pollInterval);
  }

  /**
   * Stoppt das Polling.
   */
  stop() {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
    this.isPolling = false;
    console.info('StatusWidget: polling stopped');
  }

  /**
   * Aktualisiert den Status durch API-Call.
   * @private
   */
  async updateStatus() {
    try {
      const status = await api.getStatus();
      this.renderStatus(status);
    } catch (error) {
      console.error('Failed to update status:', error);
      this.renderError();
    }
  }

  /**
   * Rendert den Status in der UI.
   * @private
   * @param {object} status - StatusResponse von der API
   */
  renderStatus(status) {
    // USB Status mit drei Zuständen: disconnected, connected, communication_error
    if (this.usbStatusEl) {
      const usbStatus = status.usb_status || 'disconnected';

      switch (usbStatus) {
        case 'connected':
          this.usbStatusEl.textContent = '🟢 Verbunden';
          this.usbStatusEl.className = 'status-badge status-connected';
          break;
        case 'communication_error':
          this.usbStatusEl.textContent = '🟡 Kommunikationsfehler';
          this.usbStatusEl.className = 'status-badge status-warning';
          break;
        case 'disconnected':
        default:
          this.usbStatusEl.textContent = '⚫ Getrennt';
          this.usbStatusEl.className = 'status-badge status-disconnected';
          break;
      }
    }

    // CAT Status
    if (this.catStatusEl) {
      const catStatus = status.cat_status || {};
      let catText = '⚫ Getrennt';
      let catClass = 'status-badge status-disconnected';

      if (!catStatus.enabled) {
        catText = '⚫ Getrennt';
        catClass = 'status-badge status-disconnected';
      } else if (status.degraded_mode || !status.secret_provider_available) {
        catText = '🟡 Warnung';
        catClass = 'status-badge status-warning';
      } else if (catStatus.connection_status === 'connected' || catStatus.connected === true) {
        catText = '🟢 Verbunden';
        catClass = 'status-badge status-connected';
      } else if (catStatus.connection_status === 'warning') {
        catText = '🟡 Warnung';
        catClass = 'status-badge status-warning';
      } else {
        catText = '⚫ Getrennt';
        catClass = 'status-badge status-disconnected';
      }

      this.catStatusEl.textContent = catText;
      this.catStatusEl.className = catClass;
    }

    // Gerätenamen
    if (this.deviceNameEl) {
      this.deviceNameEl.textContent = status.device_name || '-';
    }

    console.debug('StatusWidget: status updated', status);
  }

  /**
   * Rendert einen Fehler-Status.
   * @private
   */
  renderError() {
    if (this.usbStatusEl) {
      this.usbStatusEl.textContent = '❌ Fehler';
      this.usbStatusEl.className = 'status-badge status-disconnected';
    }

    if (this.catStatusEl) {
      this.catStatusEl.textContent = '❌ Fehler';
      this.catStatusEl.className = 'status-badge status-disconnected';
    }
  }
}

// Globale Instanz
const statusWidget = new StatusWidget();
