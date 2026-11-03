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

  window.Qna = { deviceId, MESSAGES, QnaError, parseServerMessage, escapeHtml };
})();
