// Jalur utama: web KP. scripts/build_qna_standalone.sh menimpa file ini
// untuk jalur cadangan (adapter Supabase).
window.QNA_CONFIG = {
  backend: "kp",
  pages: { jemaat: "/tanya", admin: "/tanya/admin", display: "/tanya/display" },
};
