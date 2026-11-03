// Adapter jalur cadangan: memanggil fungsi qna_* langsung lewat PostgREST
// dengan publishable key. Tanpa SSE — admin dan display polling tiap 2 detik.
// Hanya berfungsi setelah scripts/qna_fallback_on.sql dijalankan.
(function () {
  const cfg = window.QNA_CONFIG;
  if (cfg.backend !== "supabase") return;
  const { QnaError, parseServerMessage } = window.Qna;
  const PIN_KEY = "qna_admin_pin";
  let memoryPin = null;

  function pin() {
    try { return sessionStorage.getItem(PIN_KEY) || memoryPin; } catch { return memoryPin; }
  }
  function savePin(value) {
    memoryPin = value;
    try {
      if (value) sessionStorage.setItem(PIN_KEY, value);
      else sessionStorage.removeItem(PIN_KEY);
    } catch { /* cukup di memori */ }
  }

  async function rpc(fn, args) {
    let res;
    try {
      res = await fetch(`${cfg.supabaseUrl}/rest/v1/rpc/${fn}`, {
        method: "POST",
        headers: { apikey: cfg.supabaseKey, "Content-Type": "application/json" },
        body: JSON.stringify(args || {}),
      });
    } catch {
      throw new QnaError("network");
    }
    const json = await res.json().catch(() => null);
    if (!res.ok) {
      const parsed = parseServerMessage(json && json.message);
      throw new QnaError(parsed.code, null, parsed.retryAfter);
    }
    return json;
  }

  function subscribe(onChange, onStatus) {
    onStatus(true);
    onChange("all");
    const id = setInterval(() => onChange("poll"), 2000);
    return () => clearInterval(id);
  }

  const device = () => window.Qna.deviceId();
  const admin = (fn, args) => rpc(fn, { p_pin: pin(), ...args });

  window.QnaApi = {
    state: () => rpc("qna_state"),
    submit: (body) => rpc("qna_submit", { p_body: body, p_device: device() }),
    publicList: () => rpc("qna_public_list", { p_device: device() }),
    vote: (id, on) => rpc("qna_vote", { p_question: id, p_device: device(), p_on: on }),
    display: () => rpc("qna_display"),
    tts: async () => null, // TTS cloud butuh server; display memakai suara browser
    subscribe,
    admin: {
      needsLogin: true,
      hasPin: () => !!pin(),
      async login(value) {
        savePin(value);
        try {
          await admin("qna_admin_list", {});
        } catch (err) {
          savePin(null);
          throw err;
        }
      },
      list: () => admin("qna_admin_list", {}),
      act: (id, action) => admin("qna_admin_act", { p_id: id, p_action: action }),
      screen: (action) => admin("qna_admin_screen", { p_action: action }),
      settings: (patch) => admin("qna_admin_settings", {
        p_session_open: patch.session_open ?? null,
        p_points_mode: patch.points_mode ?? null,
        p_tts_engine: patch.tts_engine ?? null,
      }),
    },
  };
})();
