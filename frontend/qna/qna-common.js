// Bagian bersama halaman tanya jawab: identitas HP, error, dan escape HTML.
(function () {
  const DEVICE_KEY = "qna_device_id";
  let memoryDevice = null;

  function deviceId() {
    try {
      let id = localStorage.getItem(DEVICE_KEY);
      if (!id) {
        id = crypto.randomUUID();
        localStorage.setItem(DEVICE_KEY, id);
      }
      return id;
    } catch {
      // Mode privat / penyimpanan diblokir: tetap bisa kirim, hanya jeda dan
      // dukungan tidak bertahan setelah halaman dimuat ulang.
      memoryDevice = memoryDevice || crypto.randomUUID();
      return memoryDevice;
    }
  }

  const MESSAGES = {
    session_closed: "Sesi tanya jawab belum dibuka atau sudah ditutup.",
    cooldown: "Tunggu sebentar sebelum mengirim lagi.",
    invalid_body: "Pertanyaan harus 3–300 karakter.",
    invalid_device: "Perangkat tidak dikenali. Muat ulang halaman.",
    not_votable: "Pertanyaan ini sudah tidak bisa didukung.",
    not_found: "Pertanyaan tidak ditemukan.",
    invalid_transition: "Aksi ini tidak berlaku untuk status pertanyaan sekarang.",
    invalid_action: "Aksi tidak dikenal.",
    mode_locked: "Tutup sesi dulu sebelum mengganti mode poin.",
    nothing_showing: "Tidak ada pertanyaan yang sedang tampil.",
    forbidden: "Akses admin ditolak. Masuk lagi.",
    invalid_intro: "Pesan pembuka maksimal 120 karakter.",
    invalid_sfx: "Efek suara tidak dikenal.",
    tts_unavailable: "Suara cloud tidak tersedia.",
    network: "Gagal terhubung. Coba lagi.",
  };

  class QnaError extends Error {
    constructor(code, message, retryAfter) {
      const known = code in MESSAGES ? code : "network";
      super(message || MESSAGES[known]);
      this.code = known;
      this.retryAfter = retryAfter || null;
    }
  }

  // Pesan dari fungsi Postgres: "cooldown:12" atau kode polos seperti "session_closed".
  function parseServerMessage(message) {
    const text = String(message || "");
    if (text.startsWith("cooldown:")) {
      return { code: "cooldown", retryAfter: parseInt(text.slice(9), 10) || 30 };
    }
    return { code: text in MESSAGES ? text : "network", retryAfter: null };
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  // Fetch tanpa batas waktu bisa menggantung selamanya di WiFi gereja yang
  // putus-sambung; halaman lalu membeku karena menunggu jawaban yang tak datang.
  function requestTimeoutMs() { return window.QNA_REQUEST_TIMEOUT_MS || 10000; }
  async function fetchWithTimeout(url, options) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), requestTimeoutMs());
    try { return await fetch(url, { ...options, signal: controller.signal }); }
    finally { clearTimeout(timer); }
  }

  // Pesan pembuka yang dibacakan sebelum isi pertanyaan. Admin bisa memilih
  // salah satu, mengacaknya, atau menulis sendiri.
  const INTROS = [
    "Wow, pertanyaan bagus dari seseorang!",
    "Seorang anak Tuhan bertanya",
    "Eh, ada pertanyaan nih!",
    "Seseorang memberikan pesan menarik",
    "Ada yang penasaran nih!",
    "Ding! Ada pertanyaan baru",
    "Ini dia pertanyaan dari teman kita",
    "Seseorang lagi kepo, nih!",
    "Hmm, pertanyaan yang dalam nih",
    "Satu pertanyaan spesial buat narasumber",
    "Pertanyaan masuk, siap-siap ya!",
    "Seseorang mau tahu, nih",
  ];
  const SFX = ["ding", "tada", "confetti"];
  const pickRandom = (list) => list[Math.floor(Math.random() * list.length)];

  window.Qna = {
    deviceId, MESSAGES, QnaError, parseServerMessage, escapeHtml, fetchWithTimeout,
    INTROS, SFX, pickRandom,
  };
})();
