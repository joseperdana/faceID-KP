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
      u.onend = () => resolve();
      u.onerror = () => resolve();
      speechSynthesis.speak(u);
    });
  }

  function withTimeout(promise, ms) {
    return Promise.race([promise, new Promise((_, reject) => setTimeout(() => reject(new Error("timeout")), ms))]);
  }

  async function speak(text, engine) {
    if (engine === "cloud") {
      try {
        const blob = await withTimeout(QnaApi.tts(text), CLOUD_TIMEOUT_MS);
        if (blob) {
          const audio = new Audio(URL.createObjectURL(blob));
          await new Promise((resolve, reject) => {
            audio.onended = resolve;
            audio.onerror = reject;
            audio.play().catch(reject);
          });
          return;
        }
      } catch { /* jatuh ke suara browser */ }
    }
    await speakBrowser(text);
  }

  // Tiga nada naik ala notifikasi donasi, dibangkitkan langsung tanpa file audio.
  function chime() {
    const now = audioCtx.currentTime;
    [[880, 0], [1318.5, 0.18], [1760, 0.36]].forEach(([freq, at]) => {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = "triangle";
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.0001, now + at);
      gain.gain.exponentialRampToValueAtTime(0.4, now + at + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + at + 0.8);
      osc.connect(gain).connect(audioCtx.destination);
      osc.start(now + at);
      osc.stop(now + at + 0.85);
    });
    return new Promise((resolve) => setTimeout(resolve, 1200));
  }

  function showCard(q) {
    $("points").textContent = q.points_text;
    $("qbody").textContent = q.body;
    const card = $("alert");
    card.hidden = true;
    void card.offsetWidth; // ulang animasi masuk
    card.hidden = false;
  }

  async function present(d, announce) {
    const mine = ++seq;
    speechSynthesis.cancel();
    if (!d.question) { $("alert").hidden = true; return; }
    if (announce) {
      $("alert").hidden = true;
      await chime();
      if (mine !== seq) return; // admin sudah menekan aksi lain saat bunyi berjalan
    }
    showCard(d.question);
    if (announce) await speak(`${d.question.points_text} ${d.question.body}`, d.tts_engine);
  }

  function setConn(on) { $("conn").classList.toggle("on", on); }

  async function sync() {
    let d;
    try {
      d = await QnaApi.display();
      setConn(true);
    } catch {
      setConn(false);
      return;
    }
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

  $("test").onclick = () => speakBrowser("Seseorang memberikan 10 poin! Ini contoh suara untuk uji coba.");

  // Chrome memblokir audio sampai ada interaksi; tombol ini membukanya sekali.
  $("start").onclick = async () => {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    await audioCtx.resume();
    $("setup").hidden = true;
    $("stage").hidden = false;
    QnaApi.subscribe((kind) => { if (kind !== "questions" && kind !== "settings") sync(); }, setConn);
  };
})();
