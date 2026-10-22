// "Try it now" demo: hold a key, talk, and a small Whisper model running in this page types the
// result. The cleanup below is a port of VoxScribe's own rule-based cleanup (core/cleanup.py).
(function () {
  var card = document.getElementById('try-card');
  if (!card) return;

  var $ = function (id) { return document.getElementById(id); };
  var els = {
    loadWrap: $('try-load-wrap'), progress: $('try-progress'), progressBar: $('try-progress-bar'),
    status: $('try-status'), talk: $('try-talk'), talkLabel: $('try-talk-label'), sample: $('try-sample'),
    bars: card.querySelectorAll('.try-meter i'), text: $('try-text'), caret: $('try-caret'),
    conn: $('try-conn'), connNote: $('try-conn-note'), reqs: $('try-reqs'), speed: $('try-speed'), model: $('try-model'),
    stage: $('try-stage'), hint: $('try-hint'),
  };

  var supported = !!(window.Worker && window.AudioContext);
  var canMic = !!(window.MediaRecorder && navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
  var calm = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var worker = null;
  var state = 'idle'; // idle, loading, ready, recording, working
  var stream = null, recorder = null, chunks = [], analyser = null, meterCtx = null, raf = 0, recStart = 0, autoStop = 0;
  var typingTimer = 0;
  var mainRequestsBefore = 0;
  var pressing = false, downAt = 0, toggleMode = false;

  function setState(next, message) {
    state = next;
    card.setAttribute('data-state', next);
    if (message !== undefined) els.status.textContent = message;
    els.talk.disabled = next === 'loading' || next === 'working';
    els.talkLabel.innerHTML = next === 'idle' ? 'Tap to load<br>the model (40 MB)' : next === 'loading' ? 'Loading...' : next === 'recording' ? 'Listening...' : next === 'working' ? 'Working...' : 'Hold to talk';
    els.sample.disabled = next !== 'ready';
  }

  // ---- cleanup: the same rules as the app (core/cleanup.py)
  var ABBR = { 'e.g': 1, 'i.e': 1, etc: 1, vs: 1, approx: 1, cf: 1, mr: 1, mrs: 1, ms: 1, dr: 1, 'a.m': 1, 'p.m': 1, 'u.s': 1, inc: 1, jr: 1, sr: 1, st: 1 };
  function cleanTranscript(text) {
    if (!text || !text.trim()) return text;
    var r = text;
    r = r.replace(/,\s*like\s*,/gi, ',');
    r = r.replace(/(^|[.!?]\s+)((?:so|and|but|well|ok|okay)\s+)?like\s*,\s*/gi, '$1$2');
    r = r.replace(/\byou know\b,?/gi, '');
    r = r.replace(/\b(?:um|uh|uhh|umm)\b,?/gi, '');
    r = r.replace(/\b(the|a|an|to|and|of|in|on|for|with|i|we|you|it|my|but)\b(\s+\1\b)+/gi, '$1');
    r = r.replace(/\s+([,.!?;:])/g, '$1');
    r = r.replace(/\s+/g, ' ').trim();
    r = r.replace(/^[,;:]\s*/, '');
    if (r) {
      r = r.charAt(0).toUpperCase() + r.slice(1);
      r = r.replace(/([.!?])(\s+)([a-z])/g, function (m, p, sp, ch, offset, whole) {
        var words = whole.slice(0, offset).split(/\s+/);
        var last = (words[words.length - 1] || '').toLowerCase();
        if (ABBR[last] && p === '.') return m;
        return p + sp + ch.toUpperCase();
      });
    }
    return r;
  }

  // ---- connection badge
  function paintConn() {
    var online = navigator.onLine;
    els.conn.textContent = online ? 'Online' : 'Offline';
    els.conn.className = 'try-val ' + (online ? '' : 'is-off');
    els.connNote.textContent = online
      ? (state === 'idle' || state === 'loading' ? 'Needed once, to load the model' : 'Now try airplane mode')
      : (state === 'idle' || state === 'loading' ? 'Go back online to load the model' : 'Still transcribing, no internet');
  }
  window.addEventListener('online', paintConn);
  window.addEventListener('offline', paintConn);

  // ---- typing output
  function typeOut(full) {
    clearInterval(typingTimer);
    els.text.textContent = '';
    if (calm) { els.text.textContent = full; return; }
    var i = 0;
    typingTimer = setInterval(function () {
      i += 1;
      els.text.textContent = full.slice(0, i);
      if (i >= full.length) clearInterval(typingTimer);
    }, 22);
  }

  // ---- model loading
  function loadModel() {
    if (state !== 'idle') return;
    setState('loading', 'Downloading the model...');
    els.progress.hidden = false;
    paintConn();
    try {
      worker = new Worker('assets/try-worker.js', { type: 'module' });
    } catch (e) {
      fail('This browser could not start the demo. The apps still work offline as described.');
      return;
    }
    worker.onmessage = function (e) {
      var m = e.data;
      if (m.type === 'progress') {
        var pct = Math.min(100, Math.round((m.loaded / m.total) * 100));
        els.progressBar.style.width = pct + '%';
        els.status.textContent = 'Downloading the model... ' + pct + '% (' + Math.round(m.loaded / 1048576) + ' of ' + Math.round(m.total / 1048576) + ' MB)';
      } else if (m.type === 'ready') {
        els.progress.hidden = true;
        els.loadWrap.hidden = true;
        els.model.textContent = 'Whisper tiny (English)';
        setState('ready', canMic ? 'Ready. Hold the button (or hold F9), or tap once to start and again to stop.' : 'Ready. This browser does not allow the microphone here, so use the sample voice.');
        els.hint.hidden = false;
        paintConn();
      } else if (m.type === 'result') {
        finish(m);
      } else if (m.type === 'error') {
        fail('Something went wrong: ' + m.message);
      }
    };
    worker.onerror = function () { fail('The engine could not load. Check your connection and try again.'); };
    worker.postMessage({ type: 'load' });
  }

  function fail(message) {
    els.progress.hidden = true;
    els.loadWrap.hidden = false;
    worker = null;
    setState('idle', message);
    paintConn();
  }

  // ---- recording
  function meterLoop() {
    if (!analyser) return;
    var data = new Uint8Array(analyser.fftSize);
    analyser.getByteTimeDomainData(data);
    var sum = 0;
    for (var i = 0; i < data.length; i++) { var v = (data[i] - 128) / 128; sum += v * v; }
    var level = Math.min(1, Math.sqrt(sum / data.length) * 5);
    els.bars.forEach(function (bar, i) {
      var weight = 1 - Math.abs(i - 2) * 0.18;
      bar.style.transform = 'scaleY(' + (0.15 + level * weight * 0.85).toFixed(2) + ')';
    });
    raf = requestAnimationFrame(meterLoop);
  }

  function stopMeter() {
    cancelAnimationFrame(raf);
    analyser = null;
    els.bars.forEach(function (bar) { bar.style.transform = ''; });
    if (meterCtx) { meterCtx.close(); meterCtx = null; }
  }

  async function startRecording() {
    if (state !== 'ready') return;
    if (!canMic) { setState('ready', 'This browser does not allow the microphone here. Use the sample voice.'); return; }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false } });
    } catch (e) {
      setState('ready', 'Microphone blocked. Allow it for this page, or use the sample voice.');
      return;
    }
    if (state !== 'ready') { stream.getTracks().forEach(function (t) { t.stop(); }); return; }
    chunks = [];
    recorder = new MediaRecorder(stream);
    recorder.ondataavailable = function (e) { if (e.data.size) chunks.push(e.data); };
    recorder.start();
    recStart = performance.now();
    meterCtx = new AudioContext();
    var source = meterCtx.createMediaStreamSource(stream);
    analyser = meterCtx.createAnalyser();
    analyser.fftSize = 512;
    source.connect(analyser);
    meterLoop();
    if (!pressing) toggleMode = true;
    setState('recording', toggleMode ? 'Listening. Tap again to stop.' : 'Listening. Let go when you are done.');
    autoStop = setTimeout(stopRecording, 30000);
  }

  function stopRecording() {
    if (state !== 'recording' || !recorder) return;
    clearTimeout(autoStop);
    toggleMode = false;
    var rec = recorder;
    recorder = null;
    rec.onstop = async function () {
      stream.getTracks().forEach(function (t) { t.stop(); });
      stopMeter();
      var seconds = (performance.now() - recStart) / 1000;
      if (seconds < 0.5 || !chunks.length) { setState('ready', 'That was too short. Hold the button a little longer.'); return; }
      try {
        var audio = await decode(await new Blob(chunks).arrayBuffer());
        transcribe(audio);
      } catch (e) {
        setState('ready', 'Could not read that recording. Try again.');
      }
    };
    rec.stop();
    setState('working', 'Transcribing on your device...');
  }

  async function decode(buffer) {
    var ctx = new AudioContext({ sampleRate: 16000 });
    try {
      var decoded = await ctx.decodeAudioData(buffer);
      return decoded.getChannelData(0).slice();
    } finally {
      ctx.close();
    }
  }

  function transcribe(audio) {
    setState('working', 'Transcribing on your device...');
    els.text.textContent = '';
    mainRequestsBefore = performance.getEntriesByType('resource').length;
    transcribe.seconds = audio.length / 16000;
    worker.postMessage({ type: 'transcribe', audio: audio }, [audio.buffer]);
  }

  function finish(m) {
    var mainRequests = performance.getEntriesByType('resource').length - mainRequestsBefore;
    var total = Math.max(0, m.requests) + Math.max(0, mainRequests);
    els.reqs.textContent = String(total);
    els.reqs.parentNode.classList.toggle('is-zero', total === 0);
    var seconds = transcribe.seconds || 0;
    els.speed.textContent = seconds.toFixed(1) + ' s of speech in ' + (m.ms / 1000).toFixed(1) + ' s';
    var raw = (m.text || '').replace(/\[[^\]]*\]|\([^)]*\)/g, ' ').trim();
    var clean = cleanTranscript(raw);
    if (!clean) {
      els.text.textContent = '';
      setState('ready', 'No speech heard. Try again a little closer to the microphone.');
      return;
    }
    typeOut(clean);
    setState('ready', navigator.onLine ? 'Done. Now turn on airplane mode and try again.' : 'Done, with no internet connection.');
  }

  async function useSample() {
    if (state !== 'ready') return;
    setState('working', 'Transcribing the sample on your device...');
    try {
      var response = await fetch('assets/sample-voice.wav');
      var audio = await decode(await response.arrayBuffer());
      transcribe(audio);
    } catch (e) {
      setState('ready', 'Could not load the sample. If you are offline, hold the button and talk instead.');
    }
  }

  // ---- wiring
  if (!supported) {
    card.setAttribute('data-state', 'unsupported');
    els.status.textContent = 'This browser cannot run the demo (it needs web workers and audio). Open this page in Chrome, Edge, Firefox or Safari. The apps work the same way, on your device.';
    els.talk.disabled = true;
    els.talk.style.filter = 'none';
    els.talk.style.opacity = '0.5';
    return;
  }

  els.talk.addEventListener('click', function () { if (state === 'idle') loadModel(); });
  els.sample.addEventListener('click', useSample);
  els.talk.addEventListener('pointerdown', function (e) {
    if (state === 'recording' && toggleMode) { e.preventDefault(); stopRecording(); return; }
    if (state !== 'ready') return;
    e.preventDefault();
    try { els.talk.setPointerCapture(e.pointerId); } catch (err) {}
    pressing = true;
    downAt = performance.now();
    toggleMode = false;
    startRecording();
  });
  function released() {
    if (!pressing) return;
    pressing = false;
    if (state !== 'recording') return;
    if (performance.now() - downAt < 300) {
      toggleMode = true;
      els.status.textContent = 'Listening. Tap again to stop.';
    } else {
      stopRecording();
    }
  }
  els.talk.addEventListener('pointerup', released);
  els.talk.addEventListener('pointercancel', released);
  els.talk.addEventListener('contextmenu', function (e) { e.preventDefault(); });
  els.talk.addEventListener('keydown', function (e) {
    if ((e.key === ' ' || e.key === 'Enter') && !e.repeat) { e.preventDefault(); if (state === 'idle') loadModel(); else startRecording(); }
  });
  els.talk.addEventListener('keyup', function (e) {
    if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); stopRecording(); }
  });
  window.addEventListener('keydown', function (e) {
    if (e.key === 'F9' && !e.repeat) { e.preventDefault(); startRecording(); }
  });
  window.addEventListener('keyup', function (e) {
    if (e.key === 'F9') { e.preventDefault(); stopRecording(); }
  });
  paintConn();
  setState('idle', 'Nothing is downloaded until you click.');
})();
