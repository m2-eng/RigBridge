/**
 * Theme Switcher für RigBridge
 *
 * Verwaltet Light/Dark-Mode und persistiert die Präferenz in LocalStorage.
 */

class ThemeSwitcher {
  constructor(options = {}) {
    this.storageKey = options.storageKey || 'rigbridge-theme';
    this.defaultTheme = options.defaultTheme || 'light';
    this.toggleSelector = options.toggleSelector || '#theme-toggle';

    this.toggleEl = document.querySelector(this.toggleSelector);
    this.currentTheme = this.loadTheme();
    this.setupToggle();
  }

  /**
   * Lädt das gespeichert Theme aus LocalStorage.
   * Fallback: System-Präferenz oder Default-Theme
   * @private
   * @returns {string} 'light' oder 'dark'
   */
  loadTheme() {
    // Versuche aus LocalStorage zu laden
    const stored = localStorage.getItem(this.storageKey);
    if (stored && ['light', 'dark'].includes(stored)) {
      return stored;
    }

    // Fallback: System-Präferenz
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }

    return this.defaultTheme;
  }

  /**
   * Speichert das Theme in LocalStorage.
   * @private
   * @param {string} theme - 'light' oder 'dark'
   */
  saveTheme(theme) {
    localStorage.setItem(this.storageKey, theme);
  }

  /**
   * Richtet das Toggle-Button Event auf.
   * @private
   */
  setupToggle() {
    if (this.toggleEl) {
      this.toggleEl.addEventListener('click', () => {
        this.toggle();
      });
    }

    // Überwache System-Einstellungsänderungen
    if (window.matchMedia) {
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        // Nur fallback wenn der Nutzer keine explizite Präferenz hat
        if (localStorage.getItem(this.storageKey) === null) {
          this.setTheme(e.matches ? 'dark' : 'light');
        }
      });
    }
  }

  /**
   * Setzt das Theme auf einen bestimmten Wert.
   * @param {string} theme - 'light' oder 'dark'
   */
  setTheme(theme) {
    if (!['light', 'dark'].includes(theme)) {
      console.warn(`Invalid theme: ${theme}`);
      return;
    }

    this.currentTheme = theme;
    this.saveTheme(theme);
    this.applyTheme();
  }

  /**
   * Togglet zwischen Light und Dark Mode.
   */
  toggle() {
    const newTheme = this.currentTheme === 'light' ? 'dark' : 'light';
    this.setTheme(newTheme);
  }

  /**
   * Wendet das aktuelle Theme auf das DOM an.
   * @private
   */
  applyTheme() {
    if (this.currentTheme === 'dark') {
      document.body.classList.add('dark-mode');
      if (this.toggleEl) {
        this.toggleEl.textContent = '☀️';
        this.toggleEl.title = 'zur Light Mode wechseln';
      }
    } else {
      document.body.classList.remove('dark-mode');
      if (this.toggleEl) {
        this.toggleEl.textContent = '🌙';
        this.toggleEl.title = 'zur Dark Mode wechseln';
      }
    }

    console.info(`Theme changed to: ${this.currentTheme}`);
  }

  /**
   * Initialisiert das Theme beim Start.
   */
  init() {
    this.applyTheme();
  }
}

// Globale Instanz
const themeSwitcher = new ThemeSwitcher();
