// Translator (web): hears Japanese or Brazilian Portuguese and shows it in English.
// Speech recognition: the browser's built-in Web Speech API (no key needed).
// Translation: Chrome's built-in on-device translator when the browser has it,
// otherwise Google's free web translation endpoint, then MyMemory as a backup.
// Read-aloud: the browser's built-in speech synthesis.
(() => {
  "use strict";

  const LANGS = {
    ja: { speech: "ja-JP", code: "ja", name: "Japanese" },
    pt: { speech: "pt-BR", code: "pt", name: "Portuguese" },
  };
  const SILENCE_MS = 1500; // a pause this long ends a sentence

  const $ = (id) => document.getElementById(id);
  const feed = $("feed"), live = $("live"), empty = $("empty");
  const micBtn = $("mic"), speakBtn = $("speak"), clearBtn = $("clear");
  const statusEl = $("status"), noticeEl = $("notice");
  const langBtns = [...document.querySelectorAll(".lang")];

  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const ua = navigator.userAgent;
  const isIOS = /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
  const isMobile = isIOS || /Android/.test(ua);

  // ---------- settings ----------
  const store = {
    get(k, d) { try { const v = localStorage.getItem("translator." + k); return v === null ? d : v; } catch { return d; } },
    set(k, v) { try { localStorage.setItem("translator." + k, v); } catch { /* private mode */ } },
  };
  const urlLang = new URLSearchParams(location.search).get("lang");
  let lang = LANGS[urlLang] ? urlLang : (LANGS[store.get("lang", "ja")] ? store.get("lang", "ja") : "ja");
  let readAloud = store.get("readAloud", "0") === "1";

  // ---------- state ----------
  let recog = null;
  let wantListening = false;   // the user wants the mic on
  let running = false;         // a recognition session is active
  let pausedForSpeech = false; // mic paused while English is read aloud
  let userStarted = false;     // started by a tap/key (not the automatic start)
  let interim = "";
  let silenceTimer = 0;
  let restartTimer = 0;
  let quickFails = 0;
  let lastStart = 0;
  let wakeLock = null;

  // ---------- UI helpers ----------
  function setStatus(t) { statusEl.textContent = t; }
  function notice(t) { noticeEl.textContent = t || ""; noticeEl.hidden = !t; }
  function renderLang() {
    langBtns.forEach((b) => b.setAttribute("aria-checked", String(b.dataset.lang === lang)));
    document.documentElement.lang = "en";
  }
  function renderMic() {
    micBtn.setAttribute("aria-pressed", String(wantListening));
    micBtn.setAttribute("aria-label", wantListening ? "Stop listening" : "Start listening");
  }
  function renderSpeak() {
    speakBtn.setAttribute("aria-pressed", String(readAloud));
    speakBtn.querySelector(".ico").textContent = readAloud ? "🔊" : "🔈";
    speakBtn.querySelector(".lbl").textContent = readAloud ? "Reading aloud" : "Read aloud";
  }
  function refreshStatus() {
    if (!SR) return;
    if (pausedForSpeech) setStatus("Reading the English aloud…");
    else if (wantListening) setStatus(`Listening for ${LANGS[lang].name}…` + (isMobile ? "" : "  (Space to stop)"));
    else setStatus(isMobile ? "Stopped. Tap the microphone to start." : "Stopped. Click the microphone or press Space to start.");
  }
  function nearBottom() { return feed.scrollHeight - feed.scrollTop - feed.clientHeight < 120; }
  function scrollDown(force) { if (force || nearBottom()) feed.scrollTop = feed.scrollHeight; }
  function showLive(text) {
    const stick = nearBottom();
    live.textContent = text;
    live.hidden = !text;
    if (text) empty.hidden = true;
    scrollDown(stick);
  }

  // ---------- translation ----------
  // Chrome's on-device translator is prepared in the background and used once it is ready.
  // Until then (and in every other browser) the online translators are used.
  const builtIn = { ja: null, pt: null };
  const builtInBusy = { ja: false, pt: false };
  const withTimeout = (p, ms) => Promise.race([p, new Promise((_, no) => setTimeout(() => no(new Error("timeout")), ms))]);

  async function prepareBuiltIn(code, fromGesture) {
    if (builtIn[code] || builtInBusy[code] || !("Translator" in self)) return;
    builtInBusy[code] = true;
    try {
      const opts = { sourceLanguage: code, targetLanguage: "en" };
      const a = await withTimeout(self.Translator.availability(opts), 3000);
      // A model that still needs downloading can only be fetched after a tap or key press.
      if (a === "available" || (a !== "unavailable" && fromGesture)) {
        builtIn[code] = await self.Translator.create(opts);
      }
    } catch { /* not available; keep using the online translators */ }
    builtInBusy[code] = false;
  }

  async function translateOnlineGoogle(text, code) {
    const u = "https://translate.googleapis.com/translate_a/single?client=gtx&dt=t&tl=en&sl=" +
      encodeURIComponent(code) + "&q=" + encodeURIComponent(text);
    const r = await fetch(u);
    if (!r.ok) throw new Error("google " + r.status);
    const j = await r.json();
    const out = (j[0] || []).map((p) => p[0] || "").join("").trim();
    if (!out) throw new Error("google empty");
    return out;
  }

  async function translateOnlineMyMemory(text, code) {
    const pair = code === "pt" ? "pt-BR|en" : "ja|en";
    const u = "https://api.mymemory.translated.net/get?langpair=" + encodeURIComponent(pair) +
      "&q=" + encodeURIComponent(text.slice(0, 480));
    const r = await fetch(u);
    if (!r.ok) throw new Error("mymemory " + r.status);
    const j = await r.json();
    const out = (j.responseData && j.responseData.translatedText || "").trim();
    if (!out || j.responseStatus >= 400) throw new Error("mymemory " + j.responseStatus);
    return out;
  }

  async function translate(text, code) {
    const t = builtIn[code];
    if (t) {
      try { const out = (await withTimeout(t.translate(text), 4000)).trim(); if (out) return out; } catch { /* fall through */ }
    }
    try { return await translateOnlineGoogle(text, code); }
    catch (e1) {
      try { return await translateOnlineMyMemory(text, code); }
      catch (e2) {
        throw new Error(navigator.onLine === false
          ? "No internet connection."
          : "Couldn't translate this line. Check your internet connection.");
      }
    }
  }

  // ---------- transcript ----------
  let speakChain = Promise.resolve();

  function addSegment(original) {
    original = original.trim();
    if (!original) return;
    const code = LANGS[lang].code;
    const stick = nearBottom();
    empty.hidden = true;

    const seg = document.createElement("article");
    seg.className = "seg";
    const o = document.createElement("p");
    o.className = "orig"; o.lang = code; o.textContent = original;
    const e = document.createElement("p");
    e.className = "en pending"; e.lang = "en"; e.textContent = "Translating…";
    seg.append(o, e);
    feed.insertBefore(seg, live);
    scrollDown(stick);

    const done = translate(original, code).then(
      (en) => { e.className = "en"; e.textContent = en; scrollDown(nearBottom()); return en; },
      (err) => { e.className = "en err"; e.textContent = err.message; return null; },
    );
    // Read aloud in the order the lines were heard.
    speakChain = speakChain.then(() => done).then((en) => (en && readAloud ? speak(en) : null));
  }

  // ---------- read aloud ----------
  let enVoice = null;
  function pickVoice() {
    const vs = speechSynthesis.getVoices();
    enVoice = vs.find((v) => /^en[-_]US/i.test(v.lang) && v.localService) ||
      vs.find((v) => /^en[-_]US/i.test(v.lang)) || vs.find((v) => /^en/i.test(v.lang)) || null;
  }
  if ("speechSynthesis" in window) {
    pickVoice();
    speechSynthesis.addEventListener?.("voiceschanged", pickVoice);
  }

  function speak(text) {
    if (!("speechSynthesis" in window)) return Promise.resolve();
    return new Promise((resolve) => {
      const u = new SpeechSynthesisUtterance(text);
      u.lang = "en-US";
      if (enVoice) u.voice = enVoice;
      // Pause the mic so it doesn't hear the English and try to translate it.
      pausedForSpeech = true;
      refreshStatus();
      if (running && recog) { try { recog.abort(); } catch { /* ignore */ } }
      let finished = false;
      const end = () => {
        if (finished) return;
        finished = true;
        pausedForSpeech = false;
        refreshStatus();
        if (wantListening) scheduleRestart(150);
        resolve();
      };
      u.onend = end; u.onerror = end;
      // Safety net if the browser never reports the end.
      setTimeout(end, 4000 + text.length * 120);
      speechSynthesis.speak(u);
    });
  }

  // iPhone only allows speech after a tap; say nothing once to unlock it.
  let speechUnlocked = false;
  function unlockSpeech() {
    if (speechUnlocked || !("speechSynthesis" in window)) return;
    speechUnlocked = true;
    try { const u = new SpeechSynthesisUtterance(" "); u.volume = 0; speechSynthesis.speak(u); } catch { /* ignore */ }
  }

  // ---------- speech recognition ----------
  function commitInterim() {
    clearTimeout(silenceTimer);
    if (interim.trim()) addSegment(interim);
    interim = "";
    showLive("");
  }

  function buildRecognizer() {
    const r = new SR();
    r.lang = LANGS[lang].speech;
    r.interimResults = true;
    r.continuous = !isMobile; // phones behave better with one phrase per session
    r.maxAlternatives = 1;

    r.onstart = () => { running = true; lastStart = Date.now(); notice(""); refreshStatus(); };

    r.onresult = (ev) => {
      if (recog !== r) return;
      let pending = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const res = ev.results[i];
        const text = res[0].transcript;
        if (res.isFinal) { interim = ""; addSegment(text); }
        else pending += text;
      }
      interim = pending;
      showLive(interim);
      clearTimeout(silenceTimer);
      if (interim) {
        // Some browsers (iPhone especially) rarely mark a phrase as finished; end it after a pause.
        silenceTimer = setTimeout(() => { if (running) { try { r.stop(); } catch { /* ignore */ } } }, SILENCE_MS);
      }
    };

    r.onerror = (ev) => {
      if (recog !== r) return;
      const e = ev.error;
      if (e === "no-speech" || e === "aborted") return;
      if (e === "not-allowed" || e === "service-not-allowed") {
        wantListening = false;
        renderMic();
        if (!userStarted) notice("Tap the microphone to start. Your browser needs a tap before it can use the mic.");
        else if (e === "service-not-allowed" && isIOS) notice("Speech recognition is off. On iPhone, turn on Settings > General > Keyboard > Enable Dictation, then reload.");
        else notice("The microphone is blocked. Allow microphone access for this site in your browser settings, then tap the microphone.");
      } else if (e === "audio-capture") {
        wantListening = false; renderMic();
        notice("No microphone was found. Plug one in or check your sound settings.");
      } else if (e === "network") {
        notice("Speech recognition needs an internet connection. Retrying…");
      } else if (e === "language-not-supported") {
        wantListening = false; renderMic();
        notice(`This browser can't recognise ${LANGS[lang].name}. Try Chrome or Edge on a computer, or Safari on iPhone.`);
      }
      refreshStatus();
    };

    r.onend = () => {
      if (recog !== r) return; // replaced (language changed)
      running = false;
      commitInterim();
      if (wantListening && !pausedForSpeech) {
        // Back off if the browser keeps ending sessions straight away.
        quickFails = Date.now() - lastStart < 1000 ? quickFails + 1 : 0;
        if (quickFails > 6) {
          wantListening = false; renderMic();
          notice("Listening keeps stopping. Tap the microphone to try again.");
          quickFails = 0;
        } else {
          scheduleRestart(quickFails ? 400 * quickFails : 100);
        }
      }
      refreshStatus();
    };
    return r;
  }

  function startRecognizer() {
    clearTimeout(restartTimer);
    if (!wantListening || pausedForSpeech || running) return;
    if (!recog || recog.lang !== LANGS[lang].speech) recog = buildRecognizer();
    try { recog.start(); running = true; }
    catch (err) {
      // "already started" or a refused start without a tap.
      if (err && err.name === "InvalidStateError") return;
      wantListening = false; renderMic();
      notice("Tap the microphone to start.");
      refreshStatus();
    }
  }
  function scheduleRestart(ms) { clearTimeout(restartTimer); restartTimer = setTimeout(startRecognizer, ms); }

  function stopRecognizer() {
    clearTimeout(restartTimer);
    clearTimeout(silenceTimer);
    if (recog && running) { try { recog.stop(); } catch { /* ignore */ } }
  }

  async function keepAwake(on) {
    try {
      if (on && "wakeLock" in navigator && !wakeLock && document.visibilityState === "visible") {
        wakeLock = await navigator.wakeLock.request("screen");
        wakeLock.addEventListener("release", () => { wakeLock = null; });
      } else if (!on && wakeLock) { await wakeLock.release(); wakeLock = null; }
    } catch { /* not supported or refused */ }
  }

  function start(fromUser) {
    if (!SR) return;
    if (fromUser) { userStarted = true; unlockSpeech(); prepareBuiltIn(LANGS[lang].code, true); }
    wantListening = true;
    quickFails = 0;
    notice("");
    renderMic();
    refreshStatus();
    keepAwake(true);
    startRecognizer();
  }
  function stop() {
    wantListening = false;
    renderMic();
    stopRecognizer();
    keepAwake(false);
    refreshStatus();
  }
  function toggle() { wantListening ? stop() : start(true); }

  function setLang(next, fromUser) {
    if (!LANGS[next] || next === lang) return;
    commitInterim();
    lang = next;
    store.set("lang", lang);
    renderLang();
    if (fromUser) prepareBuiltIn(LANGS[lang].code, true);
    // Restart recognition in the new language.
    if (recog) {
      const old = recog;
      recog = null;
      running = false;
      try { old.abort(); } catch { /* ignore */ }
    }
    if (wantListening) scheduleRestart(250);
    refreshStatus();
  }

  function setReadAloud(on) {
    readAloud = on;
    store.set("readAloud", on ? "1" : "0");
    renderSpeak();
    if (on) unlockSpeech();
    else if ("speechSynthesis" in window) speechSynthesis.cancel();
  }

  // ---------- events ----------
  micBtn.addEventListener("click", () => { micBtn.blur(); toggle(); });
  speakBtn.addEventListener("click", () => { speakBtn.blur(); setReadAloud(!readAloud); });
  clearBtn.addEventListener("click", () => {
    clearBtn.blur();
    feed.querySelectorAll(".seg").forEach((n) => n.remove());
    empty.hidden = false;
    showLive("");
  });
  langBtns.forEach((b) => b.addEventListener("click", () => { b.blur(); setLang(b.dataset.lang, true); }));

  document.addEventListener("keydown", (e) => {
    if (e.target && /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)) return;
    const k = e.key.toLowerCase();
    if ((e.code === "Space" && !e.ctrlKey && !e.metaKey && !e.altKey) || (e.ctrlKey && e.altKey && k === "t")) {
      e.preventDefault(); if (!e.repeat) toggle();
    } else if (!e.ctrlKey && !e.metaKey && !e.altKey) {
      if (k === "j") setLang("ja", true);
      else if (k === "p") setLang("pt", true);
      else if (k === "r") setReadAloud(!readAloud);
    }
  });

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && wantListening) { keepAwake(true); scheduleRestart(200); }
  });

  // ---------- start ----------
  renderLang();
  renderMic();
  renderSpeak();

  if (!SR) {
    micBtn.disabled = true;
    setStatus("Speech recognition isn't available in this browser.");
    notice(isIOS
      ? "Open this page in Safari (iOS 14.5 or newer) and make sure Dictation is on in Settings > General > Keyboard."
      : "This browser can't listen. Please use Chrome or Edge on a computer or Android phone, or Safari on iPhone.");
    return;
  }
  prepareBuiltIn(LANGS[lang].code, false);
  // Start listening as soon as the page opens. If the browser wants a tap first, a hint appears.
  start(false);
})();
