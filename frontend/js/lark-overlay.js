// Form Lark ditampilkan menumpang di atas halaman kiosk, bukan dengan berpindah
// halaman. Alasannya bukan estetika:
//
//   - Berpindah halaman mematikan kamera kiosk, dan menghidupkannya lagi
//     menuntut izin serta waktu muat ulang MediaPipe.
//   - Setelah form terkirim, Lark tidak bisa kita suruh mengembalikan orangnya
//     ke kiosk. Perangkat akan tersangkut di halaman Lark sampai ada yang tahu
//     harus menekan Home atau Back — di 16 perangkat yang dipegang panitia
//     berbeda, itu titik gagal yang bisa dihilangkan sepenuhnya.
//   - Tab baru memindahkan masalahnya jadi urusan mengelola tab, yang di ponsel
//     justru lebih merepotkan.
//
// Lark mengizinkan form-nya ditanam (tidak ada X-Frame-Options maupun
// frame-ancestors), jadi menutup lapisan ini mengembalikan kiosk seketika.

(function () {
    let onCloseCallback = null;

    function buildOverlay() {
        if (document.getElementById('lark-overlay')) return;
        const el = document.createElement('div');
        el.id = 'lark-overlay';
        el.className = 'fixed inset-0 z-[200] hidden flex-col bg-obsidian-950';
        el.innerHTML = `
            <div class="flex items-center justify-between gap-3 border-b border-white/10 bg-obsidian-900 px-4 py-3">
                <div class="min-w-0">
                    <p class="font-mono text-[10px] uppercase tracking-wider text-azure-300">Melengkapi data diri</p>
                    <p class="truncate text-sm font-semibold text-white" id="lark-overlay-name">&nbsp;</p>
                </div>
                <div class="flex flex-none items-center gap-2">
                    <a id="lark-overlay-newtab" href="#" target="_blank" rel="noopener"
                       class="hidden rounded-xl border border-white/10 bg-obsidian-850 px-3 py-2 font-mono text-[11px] text-slate-300 hover:border-white/20">
                        Buka di tab baru
                    </a>
                    <button type="button" id="lark-overlay-close"
                        class="rounded-xl bg-azure-600 px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-azure-500 active:scale-[0.98]">
                        Selesai
                    </button>
                </div>
            </div>
            <iframe id="lark-overlay-frame" title="Form data diri KP"
                    class="w-full flex-1 border-0 bg-white"></iframe>`;
        document.body.appendChild(el);
        document.getElementById('lark-overlay-close').addEventListener('click', closeLarkOverlay);
    }

    window.openLarkOverlay = function (url, personName, onClose) {
        buildOverlay();
        onCloseCallback = onClose || null;
        const el = document.getElementById('lark-overlay');
        document.getElementById('lark-overlay-name').innerText = personName || '';
        document.getElementById('lark-overlay-frame').src = url;

        // Jalur cadangan kalau embed diblokir (mis. pembatasan penyimpanan pihak
        // ketiga di sebagian peramban): tautan tab baru muncul HANYA kalau form
        // tidak selesai termuat dalam 6 detik. Kalau embed-nya berhasil, jangan
        // tawarkan pilihan yang tidak dibutuhkan — itu cuma menambah keraguan.
        const newtab = document.getElementById('lark-overlay-newtab');
        const frame = document.getElementById('lark-overlay-frame');
        newtab.href = url;
        newtab.classList.add('hidden');
        clearTimeout(window.openLarkOverlay._t);
        let termuat = false;
        frame.onload = () => { termuat = true; newtab.classList.add('hidden'); };
        window.openLarkOverlay._t = setTimeout(() => {
            if (!termuat) newtab.classList.remove('hidden');
        }, 6000);

        el.classList.remove('hidden');
        el.classList.add('flex');
    };

    window.closeLarkOverlay = function () {
        const el = document.getElementById('lark-overlay');
        if (!el) return;
        clearTimeout(window.openLarkOverlay._t);
        el.classList.add('hidden');
        el.classList.remove('flex');
        // Kosongkan src supaya form berhenti berjalan di latar dan orang
        // berikutnya tidak melihat sisa isian orang sebelumnya.
        document.getElementById('lark-overlay-frame').src = 'about:blank';
        const cb = onCloseCallback;
        onCloseCallback = null;
        if (cb) cb();
    };
})();
