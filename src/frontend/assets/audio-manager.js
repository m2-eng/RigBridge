/**
 * Audio-Manager für RigBridge UI
 *
 * Verwaltet die Audio-Einstellungsseite:
 * - Geräteliste laden und in Dropdowns befüllen
 * - Konfiguration speichern/laden
 * - Stream-Status anzeigen und Streams starten/stoppen
 */

// ============================================================================
// AUDIO FORM POPULATION
// ============================================================================

/**
 * Lädt Audio-Geräte von der API und befüllt die Dropdown-Selects.
 */
async function loadAudioDevices() {
  const captureSelect = document.getElementById('audio-capture-device');
  const playbackSelect = document.getElementById('audio-playback-device');

  if (!captureSelect || !playbackSelect) return;

  captureSelect.innerHTML = '<option value="">-- Laden... --</option>';
  playbackSelect.innerHTML = '<option value="">-- Laden... --</option>';

  try {
    const response = await api.getAudioDevices();
    const devices = response.devices || [];

    const notAvailableNotice = document.getElementById('audio-unavailable-notice');
    if (!response.sounddevice_available && notAvailableNotice) {
      notAvailableNotice.style.display = 'block';
    } else if (notAvailableNotice) {
      notAvailableNotice.style.display = 'none';
    }

    // Capture (nur Geräte mit Input-Kanälen)
    captureSelect.innerHTML = '<option value="">-- Kein Gerät --</option>';
    devices
      .filter((d) => d.supports_capture)
      .forEach((d) => {
        const opt = document.createElement('option');
        opt.value = String(d.index);
        opt.textContent = `[${d.index}] ${d.name} (${d.default_samplerate} Hz)`;
        captureSelect.appendChild(opt);
      });

    // Playback (nur Geräte mit Output-Kanälen)
    playbackSelect.innerHTML = '<option value="">-- Kein Gerät --</option>';
    devices
      .filter((d) => d.supports_playback)
      .forEach((d) => {
        const opt = document.createElement('option');
        opt.value = String(d.index);
        opt.textContent = `[${d.index}] ${d.name} (${d.default_samplerate} Hz)`;
        playbackSelect.appendChild(opt);
      });

    console.info(`Audio-Geräte geladen: ${devices.length} gefunden`);
  } catch (error) {
    console.error('Audio-Geräte konnten nicht geladen werden:', error);
    captureSelect.innerHTML = '<option value="">-- Fehler beim Laden --</option>';
    playbackSelect.innerHTML = '<option value="">-- Fehler beim Laden --</option>';
  }
}

/**
 * Befüllt das Audio-Formular mit gespeicherten Konfigurationswerten
 * und setzt die Dropdown-Selektion passend.
 * @param {object} audioConfig - audio-Abschnitt aus der Konfiguration
 */
function populateAudioForm(audioConfig) {
  if (!audioConfig) return;

  const enabledCb = document.getElementById('audio-enabled');
  if (enabledCb) enabledCb.checked = audioConfig.enabled || false;

  const captureSelect = document.getElementById('audio-capture-device');
  if (captureSelect && audioConfig.capture_device !== undefined) {
    captureSelect.value = String(audioConfig.capture_device);
  }

  const playbackSelect = document.getElementById('audio-playback-device');
  if (playbackSelect && audioConfig.playback_device !== undefined) {
    playbackSelect.value = String(audioConfig.playback_device);
  }

  const sampleRate = document.getElementById('audio-samplerate');
  if (sampleRate && audioConfig.sample_rate) {
    sampleRate.value = String(audioConfig.sample_rate);
  }

  const format = document.getElementById('audio-format');
  if (format && audioConfig.format) {
    format.value = audioConfig.format;
  }

  const codec = document.getElementById('audio-codec');
  if (codec && audioConfig.codec) {
    codec.value = audioConfig.codec;
  }
}

// ============================================================================
// AUDIO STATUS
// ============================================================================

/**
 * Fragt den Audio-Status von der API ab und aktualisiert die Statusanzeige.
 */
async function refreshAudioStatus() {
  try {
    const status = await api.getAudioStatus();
    _updateAudioStatusDisplay(status);
  } catch (error) {
    console.error('Audio-Status konnte nicht abgerufen werden:', error);
  }
}

/**
 * Aktualisiert die Status-Badges und Client-Anzeige.
 * @param {object} status
 */
function _updateAudioStatusDisplay(status) {
  const rxBadge = document.getElementById('audio-rx-status');
  const txBadge = document.getElementById('audio-tx-status');
  const rxClients = document.getElementById('audio-rx-clients');
  const errorLine = document.getElementById('audio-error-line');

  if (rxBadge) {
    if (status.rx_active) {
      rxBadge.textContent = '🟢 Aktiv';
      rxBadge.className = 'status-badge status-connected';
    } else {
      rxBadge.textContent = '⚫ Inaktiv';
      rxBadge.className = 'status-badge status-disconnected';
    }
  }

  if (txBadge) {
    if (status.tx_active) {
      txBadge.textContent = '🟢 Aktiv';
      txBadge.className = 'status-badge status-connected';
    } else {
      txBadge.textContent = '⚫ Inaktiv';
      txBadge.className = 'status-badge status-disconnected';
    }
  }

  if (rxClients) {
    rxClients.textContent = String(status.rx_clients_connected || 0);
  }

  if (errorLine) {
    if (status.last_error) {
      errorLine.textContent = `⚠️ ${status.last_error}`;
      errorLine.style.display = 'block';
    } else {
      errorLine.style.display = 'none';
    }
  }
}

// ============================================================================
// AUDIO CONFIG SAVE
// ============================================================================

async function submitAudioConfig() {
  try {
    const data = {
      enabled: document.getElementById('audio-enabled').checked,
      capture_device: document.getElementById('audio-capture-device').value,
      playback_device: document.getElementById('audio-playback-device').value,
      sample_rate: parseInt(document.getElementById('audio-samplerate').value),
      format: document.getElementById('audio-format').value,
      codec: document.getElementById('audio-codec').value,
    };

    await configManager.saveSection('audio', data, { validateBeforeSave: false });

    await configManager.loadConfig();
    await populateFormFields();

    showMessage('audio-message', 'Audio-Konfiguration gespeichert!', 'success');
  } catch (error) {
    console.error('Audio-Konfiguration konnte nicht gespeichert werden:', error);
    showMessage('audio-message', `Fehler: ${error.message}`, 'error');
  }
}

// ============================================================================
// WEBSOCKET URL HELPER
// ============================================================================

/**
 * Zeigt die korrekten WebSocket-URLs für RX/TX im Info-Bereich an.
 */
function updateAudioWsUrls() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const base = `${proto}://${location.host}/api/audio`;

  const rxEl = document.getElementById('audio-ws-rx-url');
  const txEl = document.getElementById('audio-ws-tx-url');
  if (rxEl) rxEl.textContent = `${base}/rx`;
  if (txEl) txEl.textContent = `${base}/tx`;
}

// ============================================================================
// RX AUDIO PLAYER (Web Audio API – Browser-seitiger IC-905 Empfangsmonitor)
// ============================================================================

const _rxPlayer = {
  context: null,      // AudioContext
  gainNode: null,     // GainNode für Lautstärke
  analyser: null,     // AnalyserNode für VU-Meter
  ws: null,           // WebSocket
  nextTime: 0,        // Scheduling-Zeitstempel
  running: false,
  vuAnimId: null,     // requestAnimationFrame-ID
  format: 'S16_LE',
  sampleRate: 48000,
  channels: 1,
};

/**
 * Konvertiert rohe PCM-Daten (ArrayBuffer) in Float32Array für die Web Audio API.
 */
function _pcmToFloat32(buffer, format) {
  if (format === 'F32_LE') {
    return new Float32Array(buffer);
  }
  if (format === 'S32_LE') {
    const src = new Int32Array(buffer);
    const dst = new Float32Array(src.length);
    for (let i = 0; i < src.length; i++) dst[i] = src[i] / 2147483648;
    return dst;
  }
  // S16_LE (Standard)
  const src = new Int16Array(buffer);
  const dst = new Float32Array(src.length);
  for (let i = 0; i < src.length; i++) dst[i] = src[i] / 32768;
  return dst;
}

/**
 * Zeichnet den VU-Meter-Balken auf das Canvas.
 */
function _drawVuMeter() {
  if (!_rxPlayer.running || !_rxPlayer.analyser) return;

  const canvas = document.getElementById('audio-rx-vu-meter');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width;
  const H = canvas.height;

  const data = new Uint8Array(_rxPlayer.analyser.frequencyBinCount);
  _rxPlayer.analyser.getByteTimeDomainData(data);

  // RMS berechnen
  let sum = 0;
  for (let i = 0; i < data.length; i++) {
    const v = (data[i] - 128) / 128;
    sum += v * v;
  }
  const rms = Math.sqrt(sum / data.length);
  const level = Math.min(rms * 6, 1.0); // skalieren auf 0..1

  ctx.clearRect(0, 0, W, H);

  // Hintergrund
  ctx.fillStyle = getComputedStyle(canvas).backgroundColor || '#1a1a2e';
  ctx.fillRect(0, 0, W, H);

  // Balken: grün → gelb → rot
  const barW = Math.round(W * level);
  const gradient = ctx.createLinearGradient(0, 0, W, 0);
  gradient.addColorStop(0, '#22c55e');
  gradient.addColorStop(0.7, '#eab308');
  gradient.addColorStop(1.0, '#ef4444');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 2, barW, H - 4);

  _rxPlayer.vuAnimId = requestAnimationFrame(_drawVuMeter);
}

/**
 * Startet den Browser-seitigen RX-Audio-Player.
 */
async function startRxPlayer() {
  if (_rxPlayer.running) return;

  // Aktuelle Konfiguration lesen
  try {
    const cfg = configManager.getConfig();
    if (cfg?.audio) {
      _rxPlayer.sampleRate = cfg.audio.sample_rate || 48000;
      _rxPlayer.format = cfg.audio.format || 'S16_LE';
    }
  } catch (_) {}

  // AudioContext erfordert User-Gesture – wird hier direkt nach Button-Click erstellt
  try {
    _rxPlayer.context = new (window.AudioContext || window.webkitAudioContext)({
      sampleRate: _rxPlayer.sampleRate,
      latencyHint: 'interactive',
    });
  } catch (e) {
    _setRxPlayerError(`AudioContext konnte nicht erstellt werden: ${e.message}`);
    return;
  }

  // GainNode (Lautstärke)
  _rxPlayer.gainNode = _rxPlayer.context.createGain();
  const volSlider = document.getElementById('audio-rx-volume');
  _rxPlayer.gainNode.gain.value = volSlider ? parseFloat(volSlider.value) : 1.0;

  // AnalyserNode (VU-Meter)
  _rxPlayer.analyser = _rxPlayer.context.createAnalyser();
  _rxPlayer.analyser.fftSize = 1024;

  _rxPlayer.gainNode.connect(_rxPlayer.analyser);
  _rxPlayer.analyser.connect(_rxPlayer.context.destination);

  // WebSocket verbinden
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const wsUrl = `${proto}://${location.host}/api/audio/rx`;

  _rxPlayer.ws = new WebSocket(wsUrl);
  _rxPlayer.ws.binaryType = 'arraybuffer';
  _rxPlayer.nextTime = 0;

  _rxPlayer.ws.onopen = () => {
    _rxPlayer.running = true;
    _rxPlayer.nextTime = _rxPlayer.context.currentTime + 0.15;
    _setRxPlayerStatus(true, 'Verbinde…');
    _drawVuMeter();
    // Keep-Alive ping alle 10 Sekunden
    _rxPlayer._pingInterval = setInterval(() => {
      if (_rxPlayer.ws?.readyState === WebSocket.OPEN) _rxPlayer.ws.send('ping');
    }, 10000);

    // Timeout: wenn nach 4 Sekunden noch keine Audiodaten kamen → Warnung
    _rxPlayer._firstChunkReceived = false;
    _rxPlayer._timeoutId = setTimeout(() => {
      if (!_rxPlayer._firstChunkReceived && _rxPlayer.running) {
        _setRxPlayerError(
          'Keine Audiodaten empfangen. Capture-Gerät in der Konfiguration prüfen oder "Streams starten" klicken.'
        );
      }
    }, 4000);
  };

  _rxPlayer.ws.onmessage = (event) => {
    // JSON-Textnachrichten (Status, Fehler, Pong)
    if (typeof event.data === 'string') {
      try {
        const msg = JSON.parse(event.data);
        if (msg.error) {
          _setRxPlayerError(msg.error);
          stopRxPlayer();
          return;
        }
        if (msg.status === 'connected') {
          // Server bestätigt Verbindung und gibt Audio-Parameter zurück
          if (msg.sample_rate) _rxPlayer.sampleRate = msg.sample_rate;
          if (msg.format) _rxPlayer.format = msg.format;
          _setRxPlayerStatus(true, `${_rxPlayer.sampleRate} Hz · ${_rxPlayer.format}`);
        }
      } catch (_) { /* pong oder unbekannte Textnachricht → ignorieren */ }
      return;
    }

    if (!(event.data instanceof ArrayBuffer) || !_rxPlayer.context) return;

    // Erstes Daten-Chunk → Timeout abbrechen, Status aktualisieren
    if (!_rxPlayer._firstChunkReceived) {
      _rxPlayer._firstChunkReceived = true;
      clearTimeout(_rxPlayer._timeoutId);
      _setRxPlayerStatus(true, `${_rxPlayer.sampleRate} Hz · ${_rxPlayer.format} · Mono`);
    }

    try {
      const pcm = _pcmToFloat32(event.data, _rxPlayer.format);
      const numChannels = _rxPlayer.channels || 1;
      const numFrames = Math.floor(pcm.length / numChannels);
      const audioBuffer = _rxPlayer.context.createBuffer(numChannels, numFrames, _rxPlayer.sampleRate);

      for (let ch = 0; ch < numChannels; ch++) {
        const channelData = audioBuffer.getChannelData(ch);
        for (let i = 0; i < numFrames; i++) channelData[i] = pcm[i * numChannels + ch];
      }

      const source = _rxPlayer.context.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(_rxPlayer.gainNode);

      const now = _rxPlayer.context.currentTime;
      const startTime = Math.max(_rxPlayer.nextTime, now + 0.02);
      source.start(startTime);
      _rxPlayer.nextTime = startTime + audioBuffer.duration;
    } catch (e) {
      console.warn('RX-Player: PCM-Verarbeitung fehlgeschlagen:', e);
    }
  };

  _rxPlayer.ws.onerror = (e) => {
    _setRxPlayerError('WebSocket-Fehler. Ist der RX-Stream gestartet?');
  };

  _rxPlayer.ws.onclose = () => {
    if (_rxPlayer.running) stopRxPlayer();
  };
}

/**
 * Stoppt den Browser-seitigen RX-Audio-Player.
 */
function stopRxPlayer() {
  _rxPlayer.running = false;
  clearInterval(_rxPlayer._pingInterval);
  clearTimeout(_rxPlayer._timeoutId);
  if (_rxPlayer.vuAnimId) cancelAnimationFrame(_rxPlayer.vuAnimId);

  if (_rxPlayer.ws) {
    _rxPlayer.ws.onclose = null;
    _rxPlayer.ws.close();
    _rxPlayer.ws = null;
  }
  if (_rxPlayer.context) {
    _rxPlayer.context.close().catch(() => {});
    _rxPlayer.context = null;
    _rxPlayer.gainNode = null;
    _rxPlayer.analyser = null;
  }

  _setRxPlayerStatus(false);

  // Canvas leeren
  const canvas = document.getElementById('audio-rx-vu-meter');
  if (canvas) canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
}

function _setRxPlayerStatus(active, infoText) {
  const badge = document.getElementById('audio-rx-player-status');
  const btn = document.getElementById('audio-rx-play-btn');
  const info = document.getElementById('audio-rx-player-info');
  const errEl = document.getElementById('audio-rx-player-error');

  if (badge) {
    badge.textContent = active ? '🟢 Verbunden' : '⚫ Inaktiv';
    badge.className = active ? 'status-badge status-connected' : 'status-badge status-disconnected';
  }
  if (btn) {
    btn.textContent = active ? '■ Hören stoppen' : '▶ Hören starten';
  }
  if (info) {
    info.textContent = infoText !== undefined
      ? infoText
      : (active ? `${_rxPlayer.sampleRate} Hz · ${_rxPlayer.format} · Mono` : '');
  }
  if (errEl) errEl.style.display = 'none';
}

function _setRxPlayerError(msg) {
  const errEl = document.getElementById('audio-rx-player-error');
  if (errEl) {
    errEl.textContent = `⚠️ ${msg}`;
    errEl.style.display = 'block';
  }
  _setRxPlayerStatus(false);
  console.error('RX-Player:', msg);
}

// ============================================================================
// TX AUDIO SENDER (Browser-Mikrofon → IC-905 via WebSocket)
// ============================================================================

const _txSender = {
  context: null,
  stream: null,          // MediaStream (Mikrofon)
  processor: null,       // ScriptProcessorNode
  analyser: null,        // AnalyserNode (VU-Meter)
  ws: null,
  running: false,
  vuAnimId: null,
  sampleRate: 48000,
  format: 'S16_LE',
  pttCommandAvailable: null,   // null = noch nicht geprüft, true/false = Ergebnis
  PTT_COMMAND: 'send_transceiver_status',
};

/**
 * Lädt verfügbare Audioeingabegeräte und befüllt das Quellen-Dropdown.
 *
 * Browser geben ohne Mikrofonberechtigung keine Geräte-Labels zurück.
 * Wenn nötig, wird kurz getUserMedia aufgerufen (Berechtigung einholen),
 * der Stream sofort wieder gestoppt und die Liste danach neu geladen.
 */
async function loadTxAudioSources() {
  const select = document.getElementById('audio-tx-source');
  if (!select) return;

  // mediaDevices ist nur auf HTTPS oder localhost verfügbar
  if (!navigator.mediaDevices?.enumerateDevices) {
    select.innerHTML = '<option value="">⚠️ Nur auf HTTPS verfügbar</option>';
    return;
  }

  // Erste Enumeration – ohne Berechtigung kommen leere Labels zurück
  let devices;
  try {
    devices = await navigator.mediaDevices.enumerateDevices();
  } catch (e) {
    select.innerHTML = `<option value="">-- Fehler: ${e.message} --</option>`;
    return;
  }

  const inputs = devices.filter((d) => d.kind === 'audioinput');
  const hasLabels = inputs.some((d) => d.label);

  // Keine Labels → Berechtigung noch nicht erteilt → kurz getUserMedia aufrufen
  if (!hasLabels && inputs.length > 0) {
    select.innerHTML = '<option value="">🔑 Berechtigung wird angefordert…</option>';
    try {
      const tempStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      tempStream.getTracks().forEach((t) => t.stop()); // sofort wieder freigeben
      // Jetzt nochmal enumerate – diesmal mit Labels
      devices = await navigator.mediaDevices.enumerateDevices();
    } catch (e) {
      // Berechtigung verweigert → zeige generische Einträge mit index
      select.innerHTML = '';
      inputs.forEach((d, i) => {
        const opt = document.createElement('option');
        opt.value = d.deviceId;
        opt.textContent = `Mikrofon ${i + 1}`;
        select.appendChild(opt);
      });
      _setTxSenderError(`Mikrofonberechtigung verweigert: ${e.message}`);
      return;
    }
  }

  const labeledInputs = devices.filter((d) => d.kind === 'audioinput');

  select.innerHTML = '';
  if (labeledInputs.length === 0) {
    select.innerHTML = '<option value="">-- Kein Mikrofon gefunden --</option>';
    return;
  }

  labeledInputs.forEach((d, i) => {
    const opt = document.createElement('option');
    opt.value = d.deviceId;
    opt.textContent = d.label || `Mikrofon ${i + 1}`;
    select.appendChild(opt);
  });

  // Fehlermeldung ausblenden wenn vorher vorhanden
  const errEl = document.getElementById('audio-tx-sender-error');
  if (errEl) errEl.style.display = 'none';
}

/**
 * Float32Array → Int16Array (PCM S16_LE)
 */
function _float32ToInt16(float32) {
  const int16 = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    int16[i] = Math.max(-32768, Math.min(32767, Math.round(float32[i] * 32767)));
  }
  return int16;
}

/**
 * Zeichnet den TX VU-Meter-Balken.
 */
function _drawTxVuMeter() {
  if (!_txSender.running || !_txSender.analyser) return;
  const canvas = document.getElementById('audio-tx-vu-meter');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width;
  const H = canvas.height;

  const data = new Uint8Array(_txSender.analyser.frequencyBinCount);
  _txSender.analyser.getByteTimeDomainData(data);

  let sum = 0;
  for (let i = 0; i < data.length; i++) {
    const v = (data[i] - 128) / 128;
    sum += v * v;
  }
  const rms = Math.sqrt(sum / data.length);
  const level = Math.min(rms * 6, 1.0);

  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = getComputedStyle(canvas).backgroundColor || '#1a1a2e';
  ctx.fillRect(0, 0, W, H);

  const barW = Math.round(W * level);
  const gradient = ctx.createLinearGradient(0, 0, W, 0);
  gradient.addColorStop(0, '#22c55e');
  gradient.addColorStop(0.7, '#eab308');
  gradient.addColorStop(1.0, '#ef4444');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 2, barW, H - 4);

  _txSender.vuAnimId = requestAnimationFrame(_drawTxVuMeter);
}

/**
 * Prüft einmalig ob der PTT-CI-V-Befehl in der YAML-Befehlsliste vorhanden ist.
 * Ergebnis wird gecacht.
 */
async function _checkPttCommandAvailable() {
  if (_txSender.pttCommandAvailable !== null) return _txSender.pttCommandAvailable;
  try {
    const resp = await api.getCommands();
    const commands = resp.commands || [];
    _txSender.pttCommandAvailable = commands.some(
      (c) => (typeof c === 'string' ? c : c.name) === _txSender.PTT_COMMAND
    );
    console.info(`PTT CI-V Befehl "${_txSender.PTT_COMMAND}" verfügbar:`, _txSender.pttCommandAvailable);
  } catch (e) {
    console.warn('Befehlsliste konnte nicht abgerufen werden:', e);
    _txSender.pttCommandAvailable = false;
  }
  return _txSender.pttCommandAvailable;
}

/**
 * Sendet PTT-EIN oder PTT-AUS via CI-V falls Befehl verfügbar.
 * @param {boolean} txOn - true = TX (senden), false = RX (empfangen)
 */
async function _sendPtt(txOn) {
  const available = await _checkPttCommandAvailable();
  if (!available) return;
  try {
    await api.executeCommand(_txSender.PTT_COMMAND, { status: txOn });
    console.info(`PTT ${txOn ? 'EIN' : 'AUS'} gesendet`);
  } catch (e) {
    console.warn(`PTT ${txOn ? 'EIN' : 'AUS'} CI-V fehlgeschlagen:`, e.message);
  }
}

/**
 * Startet den TX-Sender: Mikrofon → PCM → WebSocket → IC-905.
 */
async function startTxSender() {
  if (_txSender.running) return;

  // Konfiguration aus gespeicherter Config lesen
  try {
    const cfg = configManager.getConfig();
    if (cfg?.audio) {
      _txSender.sampleRate = cfg.audio.sample_rate || 48000;
      _txSender.format = cfg.audio.format || 'S16_LE';
    }
  } catch (_) {}

  // Ausgewähltes Gerät
  const select = document.getElementById('audio-tx-source');
  const deviceId = select?.value || undefined;

  // Mikrofonzugriff anfordern
  try {
    _txSender.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        deviceId: deviceId ? { exact: deviceId } : undefined,
        sampleRate: _txSender.sampleRate,
        channelCount: 1,
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
      },
    });
  } catch (e) {
    _setTxSenderError(`Mikrofonzugriff verweigert: ${e.message}`);
    return;
  }

  // Gerätelabels jetzt verfügbar → Dropdown stille aktualisieren (ohne Berechtigung neu anzufordern)
  try {
    const freshDevices = await navigator.mediaDevices.enumerateDevices();
    const inputs = freshDevices.filter((d) => d.kind === 'audioinput');
    if (inputs.some((d) => d.label) && select) {
      const currentVal = select.value;
      select.innerHTML = '';
      inputs.forEach((d, i) => {
        const opt = document.createElement('option');
        opt.value = d.deviceId;
        opt.textContent = d.label || `Mikrofon ${i + 1}`;
        select.appendChild(opt);
      });
      if (currentVal) select.value = currentVal;
    }
  } catch (_) {}

  // AudioContext
  try {
    _txSender.context = new (window.AudioContext || window.webkitAudioContext)({
      sampleRate: _txSender.sampleRate,
      latencyHint: 'interactive',
    });
  } catch (e) {
    _txSender.stream.getTracks().forEach((t) => t.stop());
    _setTxSenderError(`AudioContext Fehler: ${e.message}`);
    return;
  }

  // AudioGraph: Mic → Analyser → ScriptProcessor → WS
  const source = _txSender.context.createMediaStreamSource(_txSender.stream);
  _txSender.analyser = _txSender.context.createAnalyser();
  _txSender.analyser.fftSize = 1024;

  // ScriptProcessor: konvertiert F32 → I16 und sendet per WS
  const bufferSize = 4096;
  _txSender.processor = _txSender.context.createScriptProcessor(bufferSize, 1, 1);

  // WebSocket erst verbinden
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  _txSender.ws = new WebSocket(`${proto}://${location.host}/api/audio/tx`);

  _txSender.ws.onopen = () => {
    _txSender.running = true;

    // Audio-Graph jetzt verdrahten (erst nach WS-Open, damit keine Chunks verloren gehen)
    source.connect(_txSender.analyser);
    source.connect(_txSender.processor);
    _txSender.processor.connect(_txSender.context.destination); // nötig für Chrome

    _txSender.processor.onaudioprocess = (e) => {
      if (!_txSender.running || _txSender.ws?.readyState !== WebSocket.OPEN) return;
      const float32 = e.inputBuffer.getChannelData(0);
      const int16 = _float32ToInt16(float32);
      _txSender.ws.send(int16.buffer);
    };

    // PTT EIN via CI-V (falls Befehl verfügbar)
    _sendPtt(true);

    _setTxSenderStatus(true);
    _drawTxVuMeter();
  };

  _txSender.ws.onmessage = (event) => {
    if (typeof event.data === 'string') {
      try {
        const msg = JSON.parse(event.data);
        if (msg.error) {
          _setTxSenderError(msg.error);
          stopTxSender();
        }
      } catch (_) {}
    }
  };

  _txSender.ws.onerror = () => {
    _setTxSenderError('WebSocket-Fehler. Ist der TX-Kanal frei und sounddevice verfügbar?');
  };

  _txSender.ws.onclose = () => {
    if (_txSender.running) stopTxSender();
  };
}

/**
 * Stoppt den TX-Sender.
 */
function stopTxSender() {
  _txSender.running = false;

  // PTT AUS via CI-V (fire-and-forget, Cleanup danach)
  _sendPtt(false);

  if (_txSender.vuAnimId) cancelAnimationFrame(_txSender.vuAnimId);

  if (_txSender.processor) {
    _txSender.processor.onaudioprocess = null;
    _txSender.processor.disconnect();
    _txSender.processor = null;
  }
  if (_txSender.stream) {
    _txSender.stream.getTracks().forEach((t) => t.stop());
    _txSender.stream = null;
  }
  if (_txSender.context) {
    _txSender.context.close().catch(() => {});
    _txSender.context = null;
    _txSender.analyser = null;
  }
  if (_txSender.ws) {
    _txSender.ws.onclose = null;
    _txSender.ws.close();
    _txSender.ws = null;
  }

  _setTxSenderStatus(false);
  const canvas = document.getElementById('audio-tx-vu-meter');
  if (canvas) canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
}

function _setTxSenderStatus(active, infoText) {
  const badge = document.getElementById('audio-tx-sender-status');
  const btn = document.getElementById('audio-tx-ptt-btn');
  const info = document.getElementById('audio-tx-sender-info');
  const errEl = document.getElementById('audio-tx-sender-error');

  if (badge) {
    badge.textContent = active ? '🔴 Sendet' : '⚫ Inaktiv';
    badge.className = active ? 'status-badge status-connected' : 'status-badge status-disconnected';
  }
  if (btn) {
    btn.textContent = active ? '⏹ PTT Senden stoppen' : '🔴 PTT Senden starten';
  }
  if (info) {
    info.textContent = infoText !== undefined
      ? infoText
      : (active ? `${_txSender.sampleRate} Hz · ${_txSender.format} · Mono` : '');
  }
  if (errEl) errEl.style.display = 'none';
}

function _setTxSenderError(msg) {
  const errEl = document.getElementById('audio-tx-sender-error');
  if (errEl) {
    errEl.textContent = `⚠️ ${msg}`;
    errEl.style.display = 'block';
  }
  _setTxSenderStatus(false);
  console.error('TX-Sender:', msg);
}

// ============================================================================
// EVENT HANDLER SETUP (erweitert um RX-Player)
// ============================================================================

function setupAudioHandlers() {
  // Formular speichern
  const audioForm = document.getElementById('audio-form');
  if (audioForm) {
    audioForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      await submitAudioConfig();
    });
  }

  // Stream starten
  const startBtn = document.getElementById('audio-start-btn');
  if (startBtn) {
    startBtn.addEventListener('click', async () => {
      try {
        showMessage('audio-message', 'Streams werden gestartet…', 'info');
        await api.startAudio();
        await refreshAudioStatus();
        showMessage('audio-message', 'Streams gestartet.', 'success');
      } catch (error) {
        showMessage('audio-message', `Start fehlgeschlagen: ${error.message}`, 'error');
      }
    });
  }

  // Stream stoppen
  const stopBtn = document.getElementById('audio-stop-btn');
  if (stopBtn) {
    stopBtn.addEventListener('click', async () => {
      try {
        await api.stopAudio();
        await refreshAudioStatus();
        showMessage('audio-message', 'Streams gestoppt.', 'success');
      } catch (error) {
        showMessage('audio-message', `Stop fehlgeschlagen: ${error.message}`, 'error');
      }
    });
  }

  // Status aktualisieren
  const statusRefreshBtn = document.getElementById('audio-status-refresh-btn');
  if (statusRefreshBtn) {
    statusRefreshBtn.addEventListener('click', async () => {
      await refreshAudioStatus();
    });
  }

  // Geräteliste aktualisieren
  const devicesRefreshBtn = document.getElementById('audio-refresh-devices-btn');
  if (devicesRefreshBtn) {
    devicesRefreshBtn.addEventListener('click', async () => {
      await loadAudioDevices();
      // Selektion wiederherstellen
      try {
        const config = configManager.getConfig();
        if (config.audio) populateAudioForm(config.audio);
      } catch (_) {}
    });
  }

  // RX Audio Player
  const rxPlayBtn = document.getElementById('audio-rx-play-btn');
  if (rxPlayBtn) {
    rxPlayBtn.addEventListener('click', async () => {
      if (_rxPlayer.running) {
        stopRxPlayer();
      } else {
        await startRxPlayer();
      }
    });
  }

  // Lautstärkeregler
  const volSlider = document.getElementById('audio-rx-volume');
  const volLabel = document.getElementById('audio-rx-volume-label');
  if (volSlider) {
    volSlider.addEventListener('input', () => {
      const val = parseFloat(volSlider.value);
      if (volLabel) volLabel.textContent = `${Math.round(val * 100)}%`;
      if (_rxPlayer.gainNode) _rxPlayer.gainNode.gain.value = val;
    });
  }

  // TX Sender – PTT Button
  const txPttBtn = document.getElementById('audio-tx-ptt-btn');
  if (txPttBtn) {
    txPttBtn.addEventListener('click', async () => {
      if (_txSender.running) {
        stopTxSender();
      } else {
        await startTxSender();
      }
    });
  }

  // TX Sender – Quellen-Refresh
  const txRefreshBtn = document.getElementById('audio-tx-refresh-sources-btn');
  if (txRefreshBtn) {
    txRefreshBtn.addEventListener('click', async () => {
      await loadTxAudioSources();
    });
  }

  // Audioquellen initial laden (ohne Mikrofonberechtigung – Labels kommen erst nach Erlaubnis)
  loadTxAudioSources();

  // WebSocket-URLs aktualisieren
  updateAudioWsUrls();
}
