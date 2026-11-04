// Adapter jalur utama: FastAPI web KP (cookie admin + SSE).
(function () {
  if (window.QNA_CONFIG.backend !== "kp") return;
  const { QnaError } = window.Qna;

  async function request(method, url, body) {
    let res;
    try {
      res = await window.Qna.fetchWithTimeout(url, {
        method,
        credentials: "same-origin",
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
    } catch {
      throw new QnaError("network");
    }
    if (res.status === 401) throw new QnaError("forbidden");
    if (res.ok && (res.headers.get("content-type") || "").startsWith("audio/")) return res.blob();
    const json = await res.json().catch(() => ({}));
    if (!res.ok) {
      const code = json.code || (res.status === 429 ? "cooldown" : "network");
      throw new QnaError(code, json.message, json.retry_after);
    }
    return json.data;
  }

  function subscribe(onChange, onStatus) {
    let es = null;
    let retryTimer = null;
    let closed = false;

    function connect() {
      retryTimer = null;
      es = new EventSource("/api/qna/admin/stream");
      es.addEventListener("hello", () => { onStatus(true); onChange("all"); });
      es.addEventListener("changed", (e) => onChange(JSON.parse(e.data).kind));
      es.onerror = () => {
        onStatus(false);
        // Putus biasa (CONNECTING) disambung ulang browser sendiri. Respons
        // non-2xx, mis. nginx 502 saat restart, menutup EventSource untuk
        // selamanya, jadi harus dibuat ulang manual atau stream mati sampai
        // halaman dimuat ulang.
        if (!closed && es.readyState === EventSource.CLOSED && !retryTimer) {
          es.close();
          retryTimer = setTimeout(connect, 3000);
        }
      };
    }
    connect();
    // Cadangan kalau SSE tertahan proxy atau sinyal terlewat.
    const poll = setInterval(() => onChange("poll"), 5000);
    return () => {
      closed = true;
      if (es) es.close();
      clearTimeout(retryTimer);
      clearInterval(poll);
    };
  }

  const device = () => window.Qna.deviceId();
  const enc = encodeURIComponent;

  window.QnaApi = {
    state: () => request("GET", "/api/qna/state"),
    submit: (body) => request("POST", "/api/qna/questions", { body, device_id: device() }),
    publicList: () => request("GET", `/api/qna/questions/public?device_id=${enc(device())}`),
    vote: (id, on) => request("POST", `/api/qna/questions/${enc(id)}/vote`, { device_id: device(), on }),
    display: () => request("GET", "/api/qna/display"),
    tts: (text) => request("POST", "/api/qna/admin/tts", { text }),
    subscribe,
    admin: {
      needsLogin: false, // login lewat /login web KP (cookie)
      hasPin: () => true,
      login: async () => {},
      list: () => request("GET", "/api/qna/admin/questions"),
      act: (id, action) => request("POST", `/api/qna/admin/questions/${enc(id)}/${enc(action)}`),
      screen: (action) => request("POST", `/api/qna/admin/screen/${enc(action)}`),
      settings: (patch) => request("PATCH", "/api/qna/admin/settings", patch),
    },
  };
})();
