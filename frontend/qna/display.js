(function () {
  const $ = (id) => document.getElementById(id);
  const mode = new URLSearchParams(location.search).get("mode") === "overlay" ? "overlay" : "full";
  document.body.classList.add(`mode-${mode}`);
  $("modeLabel").textContent = mode === "overlay" ? "overlay (transparan, untuk OBS)" : "layar penuh";

  const VOICE_KEY = "qna_voice";
  const CLOUD_TIMEOUT_MS = 4500;
  let audioCtx = null;
  let lastNonce = null;
  let seq = 0;
  let syncSeq = 0;
  let currentAudio = null;
  const SPEECH_MAX_MS = 60000; // jaring pengaman kalau onend tidak pernah datang

  // Daftar suara berbeda di tiap laptop, jadi pilihannya disimpan di laptop ini.
  function fillVoices() {
    const list = speechSynthesis.getVoices().slice().sort((a, b) =>
      (b.lang.startsWith("id") - a.lang.startsWith("id")) || a.name.localeCompare(b.name));
    let saved = null;
    try { saved = localStorage.getItem(VOICE_KEY); } catch { /* tanpa penyimpanan */ }
    $("voice").innerHTML = list.map((v) =>
      `<option value="${Qna.escapeHtml(v.name)}">${Qna.escapeHtml(v.name)} (${Qna.escapeHtml(v.lang)})</option>`).join("");
    if (saved && list.some((v) => v.name === saved)) $("voice").value = saved;
  }
  fillVoices();
  speechSynthesis.onvoiceschanged = fillVoices;
  $("voice").onchange = () => {
    try { localStorage.setItem(VOICE_KEY, $("voice").value); } catch { /* tanpa penyimpanan */ }
  };

  function speakBrowser(text) {
    return new Promise((resolve) => {
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = "id-ID";
      const voice = speechSynthesis.getVoices().find((v) => v.name === $("voice").value);
      if (voice) u.voice = voice;
      // Sebagian browser tidak pernah memanggil onend; jangan biarkan janji menggantung.
      const safety = setTimeout(resolve, SPEECH_MAX_MS);
      u.onend = u.onerror = () => { clearTimeout(safety); resolve(); };
      speechSynthesis.speak(u);
    });
  }

  function withTimeout(promise, ms) {
    return Promise.race([promise, new Promise((_, reject) => setTimeout(() => reject(new Error("timeout")), ms))]);
  }

  // Hentikan suara alert sebelumnya (browser maupun cloud) sebelum alert baru atau layar kosong.
  function stopSpeech() {
    speechSynthesis.cancel();
    if (currentAudio) {
      currentAudio.pause();
      URL.revokeObjectURL(currentAudio.src);
      currentAudio = null;
    }
  }

  function playCloud(blob) {
    const audio = new Audio(URL.createObjectURL(blob));
    currentAudio = audio;
    return new Promise((resolve, reject) => {
      const safety = setTimeout(resolve, SPEECH_MAX_MS);
      audio.onended = () => { clearTimeout(safety); resolve(); };
      audio.onerror = () => { clearTimeout(safety); reject(new Error("audio")); };
      audio.play().catch((err) => { clearTimeout(safety); reject(err); });
    }).finally(() => {
      if (currentAudio === audio) {
        URL.revokeObjectURL(audio.src);
        currentAudio = null;
      }
    });
  }

  async function speak(text, engine, mine) {
    if (engine === "cloud") {
      try {
        const blob = await withTimeout(QnaApi.tts(text), CLOUD_TIMEOUT_MS);
        if (mine !== seq) return; // sudah ada alert lain selama menunggu suara cloud
        if (blob) {
          await playCloud(blob);
          return;
        }
      } catch { /* jatuh ke suara browser */ }
    }
    if (mine !== seq) return;
    await speakBrowser(text);
  }

  const INTRO_PAUSE_MS = 700; // jeda antara pesan pembuka dan isi pertanyaan
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  function tone(freq, at, dur, { type = "triangle", peak = 0.4 } = {}) {
    const now = audioCtx.currentTime;
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = type;
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.0001, now + at);
    gain.gain.exponentialRampToValueAtTime(peak, now + at + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + at + dur);
    osc.connect(gain).connect(audioCtx.destination);
    osc.start(now + at);
    osc.stop(now + at + dur + 0.05);
  }

  // Semua efek dibangkitkan langsung dengan Web Audio, tanpa file audio.
  // Masing-masing mengembalikan lamanya (ms) supaya kartu muncul setelah bunyi.
  // Tiga nada naik ala notifikasi donasi.
  function sfxDing() {
    [[880, 0], [1318.5, 0.18], [1760, 0.36]].forEach(([freq, at]) => tone(freq, at, 0.8));
    return 1200;
  }

  // Fanfare singkat: satu ketukan pendek, lalu akor mayor yang ditahan.
  function sfxTada() {
    tone(392, 0, 0.14, { type: "sawtooth", peak: 0.18 });
    [523.25, 659.25, 783.99, 1046.5].forEach((freq) => tone(freq, 0.16, 1.1, { type: "sawtooth", peak: 0.12 }));
    return 1400;
  }

  // Letupan confetti (desis pendek) disusul kilau nada-nada tinggi.
  function sfxConfetti() {
    const now = audioCtx.currentTime;
    const length = Math.floor(audioCtx.sampleRate * 0.25);
    const buffer = audioCtx.createBuffer(1, length, audioCtx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < length; i++) data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / length, 3);
    [0, 0.08].forEach((at) => {
      const source = audioCtx.createBufferSource();
      source.buffer = buffer;
      const filter = audioCtx.createBiquadFilter();
      filter.type = "highpass";
      filter.frequency.value = 1500;
      const gain = audioCtx.createGain();
      gain.gain.value = 0.5;
      source.connect(filter).connect(gain).connect(audioCtx.destination);
      source.start(now + at);
    });
    for (let i = 0; i < 8; i++) {
      tone(2000 + Math.random() * 2500, 0.15 + i * 0.09, 0.3, { type: "sine", peak: 0.15 });
    }
    return 1300;
  }

  const SOUNDS = { ding: sfxDing, tada: sfxTada, confetti: sfxConfetti };

  function playSfx(name) {
    if (!audioCtx) return Promise.resolve();
    return sleep((SOUNDS[name] || sfxDing)());
  }

  function showCard(q) {
    $("points").textContent = q.points_text;
    $("qbody").textContent = q.body;
    const votes = q.votes || 0;
    $("votes").textContent = votes > 0 ? `▲ ${votes} teman ikut penasaran` : "";
    $("votes").hidden = votes <= 0;
    const card = $("alert");
    card.hidden = true;
    void card.offsetWidth; // ulang animasi masuk
    card.hidden = false;
  }

  async function present(d, announce) {
    const mine = ++seq;
    stopSpeech();
    if (!d.question) { $("alert").hidden = true; return; }
    if (announce) {
      $("alert").hidden = true;
      try { await playSfx(d.question.sfx); } catch { /* tanpa bunyi pun kartu harus tetap muncul */ }
      if (mine !== seq) return; // admin sudah menekan aksi lain saat bunyi berjalan
    }
    showCard(d.question);
    if (!announce) return;
    // Dibacakan terpisah dengan jeda supaya pesan pembuka tidak menyambung ke isi.
    await speak(d.question.points_text, d.tts_engine, mine);
    if (mine !== seq) return;
    await sleep(INTRO_PAUSE_MS);
    if (mine !== seq) return;
    await speak(d.question.body, d.tts_engine, mine);
  }

  function setConn(on) { $("conn").classList.toggle("on", on); }

  async function sync() {
    const mine = ++syncSeq;
    let d;
    try {
      d = await QnaApi.display();
      setConn(true);
    } catch {
      setConn(false);
      return;
    }
    // SSE dan polling bisa memicu beberapa sync bersamaan; jawaban lama yang
    // datang belakangan tidak boleh memundurkan nonce dan mengulang alert basi.
    if (mine !== syncSeq) return;
    if (lastNonce === null) {
      // Pertama kali: tampilkan apa adanya tanpa bunyi, supaya laptop yang
      // dimuat ulang di tengah acara tidak mengulang alert.
      lastNonce = d.nonce;
      present(d, false);
      return;
    }
    if (d.nonce === lastNonce) return;
    lastNonce = d.nonce;
    present(d, true);
  }

  $("test").onclick = () => speakBrowser("Eh, ada pertanyaan nih! Ini contoh suara untuk uji coba.");

  // Chrome memblokir audio sampai ada interaksi; tombol ini membukanya sekali.
  $("start").onclick = async () => {
    try {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      await audioCtx.resume();
    } catch {
      audioCtx = null; // tetap jalan tanpa bunyi notifikasi
    }
    $("setup").hidden = true;
    $("stage").hidden = false;
    QnaApi.subscribe((kind) => { if (kind !== "questions" && kind !== "settings") sync(); }, setConn);
  };
})();
