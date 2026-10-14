/**
 * KPObs — pelaporan error, label perangkat, dan data performa sisi browser.
 *
 * Kenapa bukan Sentry Browser SDK: frontend ini vanilla JS tanpa build step dan
 * tidak diminifikasi, jadi source map (nilai jual utama SDK) tidak relevan.
 * Reporter ringan ini mengirim ke /api/client-error, yang meneruskan ke Sentry
 * project yang sama dengan backend — satu dashboard, tanpa dependensi CDN.
 *
 * Tiga tugas:
 * 1. Error browser → /api/client-error (seperti sebelumnya).
 * 2. Label perangkat (`kiosk-03`, atau `anon-xxxxxx`) yang ditempel sebagai
 *    header X-KP-Device ke setiap fetch /api/ — supaya log server bisa
 *    membedakan 16 HP pribadi yang dipakai sebagai kiosk saat Gibbor.
 * 3. RUM (Real User Monitoring) → /api/rum: Web Vitals, long task, resource
 *    paling lambat, RAM & jaringan perangkat. Untuk menjawab "HP mana yang
 *    lemot, dan karena apa" — Tailwind Play CDN, MediaPipe, atau jaringan venue.
 *
 * Muat sedini mungkin di <head>, sebelum script lain, supaya error saat boot,
 * long task dari kompilasi Tailwind, dan fetch pertama ikut tertangkap.
 * Semua bagian wajib diam saat gagal: observability tidak boleh merusak absensi.
 */
(function () {
    'use strict';

    var ENDPOINT = '/api/client-error';
    var RUM_ENDPOINT = '/api/rum';
    var MAX_PER_MINUTE = 10;   // Kiosk dipakai puluhan orang; jangan banjiri kuota.
    var DEDUPE_WINDOW_MS = 60000;

    var DEVICE_KEY = 'kp_device_label';
    var DEVICE_HEADER = 'X-KP-Device';

    var RUM_LOAD_DELAY_MS = 10000;          // Beri waktu LCP & long task awal selesai.
    var RUM_PERIODIC_MS = 15 * 60 * 1000;   // Kiosk terbuka berjam-jam; lihat degradasinya.
    var RUM_MAX_SENDS = 10;                 // Batas keras per umur halaman.

    var sentTimestamps = [];
    var recentSignatures = {};

    // ------------------------------------------------------------------
    // Label perangkat
    // ------------------------------------------------------------------

    var deviceLabel = null;

    function sanitizeLabel(raw) {
        if (raw == null) return '';
        // `Kiosk_03` / `kiosk 03` → `kiosk-03`; sisanya dibuang.
        return String(raw).toLowerCase().replace(/[\s_]+/g, '-').replace(/[^a-z0-9-]/g, '').slice(0, 40);
    }

    // localStorage bisa melempar di mode privat Safari / storage diblokir.
    function storageGet(key) {
        try { return window.localStorage.getItem(key); } catch (e) { return null; }
    }

    function storageSet(key, value) {
        try { window.localStorage.setItem(key, value); } catch (e) { /* cukup di memori */ }
    }

    function randomHex(n) {
        var out = '';
        try {
            var c = window.crypto || window.msCrypto;
            if (c && c.getRandomValues) {
                var bytes = new Uint8Array(Math.ceil(n / 2));
                c.getRandomValues(bytes);
                for (var i = 0; i < bytes.length; i++) {
                    out += ('0' + bytes[i].toString(16)).slice(-2);
                }
                return out.slice(0, n);
            }
        } catch (e) { /* jatuh ke Math.random */ }
        while (out.length < n) out += Math.floor(Math.random() * 16).toString(16);
        return out;
    }

    function resolveDevice() {
        // ?device=kiosk-03 dipakai panitia saat menyiapkan HP sebagai kiosk.
        var fromUrl = '';
        try {
            var m = /[?&]device=([^&#]*)/.exec(location.search);
            if (m) fromUrl = sanitizeLabel(decodeURIComponent(m[1].replace(/\+/g, ' ')));
        } catch (e) { /* URL rusak: abaikan */ }
        if (fromUrl) {
            storageSet(DEVICE_KEY, fromUrl);
            return fromUrl;
        }
        var stored = sanitizeLabel(storageGet(DEVICE_KEY));
        if (stored) return stored;
        var generated = 'anon-' + randomHex(6);
        storageSet(DEVICE_KEY, generated);
        return generated;
    }

    function device() {
        if (!deviceLabel) {
            try { deviceLabel = resolveDevice(); } catch (e) { deviceLabel = 'anon-000000'; }
        }
        return deviceLabel;
    }

    // ------------------------------------------------------------------
    // Header X-KP-Device pada fetch /api/ same-origin
    // ------------------------------------------------------------------

    function requestUrl(input) {
        if (typeof input === 'string') return input;
        if (input && typeof input.url === 'string') return input.url;     // Request
        if (input && typeof input.href === 'string') return input.href;   // URL
        return String(input);
    }

    function patchFetch() {
        if (typeof window.fetch !== 'function' || window.fetch.__kpDevicePatched) return;
        if (typeof Headers === 'undefined' || typeof URL === 'undefined') return;
        var original = window.fetch;

        var patched = function (input, init) {
            var finalInit = null;
            try {
                var u = new URL(requestUrl(input), location.href);
                if (u.origin === location.origin && u.pathname.indexOf('/api/') === 0) {
                    var isRequest = typeof Request !== 'undefined' && input instanceof Request;
                    // init.headers menimpa header milik Request sepenuhnya, jadi
                    // gabungkan dari sumber yang memang akan dipakai browser.
                    var source = (init && init.headers) || (isRequest ? input.headers : undefined);
                    var headers = new Headers(source);
                    if (!headers.has(DEVICE_HEADER)) headers.set(DEVICE_HEADER, device());
                    finalInit = {};
                    if (init) {
                        for (var k in init) {
                            if (Object.prototype.hasOwnProperty.call(init, k)) finalInit[k] = init[k];
                        }
                    }
                    // Content-Type tidak pernah disentuh: untuk body FormData,
                    // browser yang mengisi boundary multipart-nya sendiri.
                    finalInit.headers = headers;
                }
            } catch (e) {
                finalInit = null;
            }
            if (finalInit) return original.call(window, input, finalInit);
            return original.apply(window, arguments);
        };
        patched.__kpDevicePatched = true;
        window.fetch = patched;
    }

    // ------------------------------------------------------------------
    // Pelaporan error
    // ------------------------------------------------------------------

    function allowed(signature) {
        var now = Date.now();

        // Buang jejak yang lebih tua dari satu menit
        sentTimestamps = sentTimestamps.filter(function (t) { return now - t < 60000; });
        if (sentTimestamps.length >= MAX_PER_MINUTE) return false;

        // Satu error yang terjadi berulang tiap frame tidak perlu dikirim berkali-kali
        var last = recentSignatures[signature];
        if (last && now - last < DEDUPE_WINDOW_MS) return false;

        recentSignatures[signature] = now;
        sentTimestamps.push(now);
        return true;
    }

    // Kembalikan true bila laporan diserahkan ke browser.
    function post(url, payload) {
        var body = JSON.stringify(payload);
        try {
            // keepalive/sendBeacon supaya laporan tetap terkirim walau halaman
            // langsung di-reset atau ditutup. sendBeacon tidak bisa memberi
            // header, karena itu `device` selalu ikut di dalam body.
            if (navigator.sendBeacon &&
                navigator.sendBeacon(url, new Blob([body], { type: 'application/json' }))) {
                return true;
            }
            if (typeof window.fetch === 'function') {
                window.fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: body,
                    keepalive: true
                }).catch(function () { /* laporan gagal tidak boleh memicu laporan baru */ });
                return true;
            }
        } catch (e) { /* diam: observability tidak boleh merusak alur absensi */ }
        return false;
    }

    function report(kind, message, extra) {
        try {
            var msg = String(message == null ? 'unknown' : message).slice(0, 500);
            var signature = kind + '|' + msg;
            if (!allowed(signature)) return;

            var context = { device: device() };
            var given = extra && extra.context;
            if (given && typeof given === 'object') {
                for (var k in given) {
                    if (Object.prototype.hasOwnProperty.call(given, k) && k !== 'device') context[k] = given[k];
                }
            }

            post(ENDPOINT, {
                kind: String(kind || 'js_error').slice(0, 40),
                message: msg,
                source: (extra && extra.source ? String(extra.source) : '').slice(0, 300),
                stack: (extra && extra.stack ? String(extra.stack) : '').slice(0, 2000),
                page: location.pathname.slice(0, 300),
                user_agent: navigator.userAgent.slice(0, 300),
                context: context
            });
        } catch (e) { /* idem */ }
    }

    // ------------------------------------------------------------------
    // RUM — tanpa library; setiap metrik dijaga deteksi fitur (Safari tidak
    // punya LCP/INP/longtask/deviceMemory).
    // ------------------------------------------------------------------

    var vitals = { lcp: null, fcp: null, cls: 0, inp: null };
    var longLife = { count: 0, total: 0, max: 0 };       // sepanjang umur halaman
    var longInterval = { count: 0, total: 0, max: 0 };   // sejak snapshot terakhir
    var intervalStartedAt = 0;
    var rumSends = 0;
    var finalSent = false;

    function now() {
        try { return performance.now(); } catch (e) { return 0; }
    }

    function num(value, digits) {
        if (typeof value !== 'number' || !isFinite(value) || value < 0) return undefined;
        var f = Math.pow(10, digits || 0);
        return Math.round(value * f) / f;
    }

    function observe(type, handler, extraOpts) {
        try {
            if (!window.PerformanceObserver) return;
            var supported = PerformanceObserver.supportedEntryTypes;
            if (supported && supported.indexOf(type) === -1) return;
            var po = new PerformanceObserver(function (list) {
                try {
                    var entries = list.getEntries();
                    for (var i = 0; i < entries.length; i++) handler(entries[i]);
                } catch (e) { /* diam */ }
            });
            var opts = { type: type, buffered: true };
            if (extraOpts) {
                for (var k in extraOpts) opts[k] = extraOpts[k];
            }
            po.observe(opts);
        } catch (e) { /* browser lama: metrik ini kosong */ }
    }

    function startObservers() {
        observe('largest-contentful-paint', function (e) { vitals.lcp = e.startTime; });
        observe('paint', function (e) {
            if (e.name === 'first-contentful-paint') vitals.fcp = e.startTime;
        });
        observe('layout-shift', function (e) {
            if (!e.hadRecentInput) vitals.cls += e.value;
        });
        // Perkiraan INP: interaksi terlama. Bukan persentil resmi, tapi cukup
        // untuk membedakan HP yang "macet saat disentuh" dari yang tidak.
        var onInteraction = function (e) {
            if (vitals.inp === null || e.duration > vitals.inp) vitals.inp = e.duration;
        };
        observe('event', onInteraction, { durationThreshold: 40 });
        observe('first-input', onInteraction);
        observe('longtask', function (e) {
            var d = e.duration;
            longLife.count++; longLife.total += d; if (d > longLife.max) longLife.max = d;
            longInterval.count++; longInterval.total += d; if (d > longInterval.max) longInterval.max = d;
        });
    }

    function navigationTiming(out) {
        var nav = null;
        try {
            var list = performance.getEntriesByType && performance.getEntriesByType('navigation');
            nav = list && list[0];
        } catch (e) { nav = null; }
        if (nav) {
            out.ttfb_ms = num(nav.responseStart);
            out.dom_content_loaded_ms = num(nav.domContentLoadedEventEnd) || undefined;
            out.load_ms = num(nav.loadEventEnd) || undefined;
            out.transfer_kb = num(nav.transferSize / 1024, 1);
            return;
        }
        try {
            var t = performance.timing;   // Safari/browser lama
            if (t && t.navigationStart) {
                out.ttfb_ms = num(t.responseStart - t.navigationStart);
                if (t.domContentLoadedEventEnd) out.dom_content_loaded_ms = num(t.domContentLoadedEventEnd - t.navigationStart);
                if (t.loadEventEnd) out.load_ms = num(t.loadEventEnd - t.navigationStart);
            }
        } catch (e) { /* diam */ }
    }

    function resourceTiming(out) {
        var entries;
        try { entries = performance.getEntriesByType('resource') || []; } catch (e) { return; }
        var totalBytes = 0;
        var items = [];
        for (var i = 0; i < entries.length; i++) {
            var e = entries[i];
            totalBytes += e.transferSize || 0;
            // Beacon milik reporter ini sendiri bukan beban halaman.
            if (e.initiatorType !== 'beacon') items.push(e);
        }
        items.sort(function (a, b) { return b.duration - a.duration; });
        var top = [];
        for (var j = 0; j < items.length && top.length < 6; j++) {
            var host = '', path = '';
            try {
                var u = new URL(items[j].name);
                host = u.host;
                path = u.pathname;   // query dibuang: bisa berisi token URL bertanda tangan
            } catch (err) {
                path = String(items[j].name).split('?')[0];
            }
            top.push({
                host: host.slice(0, 120),
                path: path.slice(0, 80),
                initiator: String(items[j].initiatorType || '').slice(0, 20),
                duration_ms: num(items[j].duration),
                transfer_kb: num((items[j].transferSize || 0) / 1024, 1)
            });
        }
        out.resource_count = entries.length;
        out.resource_transfer_kb = num(totalBytes / 1024, 1);
        out.resources = top;
    }

    function deviceInfo(out) {
        var nav = navigator;
        if (typeof nav.deviceMemory === 'number') out.device_memory_gb = nav.deviceMemory;
        if (typeof nav.hardwareConcurrency === 'number') out.cpu_cores = nav.hardwareConcurrency;
        var conn = nav.connection || nav.mozConnection || nav.webkitConnection;
        if (conn) {
            if (conn.effectiveType) out.effective_type = String(conn.effectiveType).slice(0, 20);
            if (typeof conn.downlink === 'number') out.downlink_mbps = conn.downlink;
            if (typeof conn.rtt === 'number') out.rtt_ms = conn.rtt;
            if (typeof conn.saveData === 'boolean') out.save_data = conn.saveData;
        }
        out.viewport = (window.innerWidth || 0) + 'x' + (window.innerHeight || 0);
        out.dpr = num(window.devicePixelRatio || 1, 2);
        out.user_agent = String(nav.userAgent || '').slice(0, 300);
        try {
            var mem = performance.memory;   // hanya Chromium
            if (mem && mem.usedJSHeapSize) {
                out.js_heap_used_mb = num(mem.usedJSHeapSize / 1048576, 1);
                out.js_heap_limit_mb = num(mem.jsHeapSizeLimit / 1048576, 1);
            }
        } catch (e) { /* diam */ }
    }

    function snapshot(phase) {
        var out = {
            phase: phase,
            page: location.pathname.slice(0, 300),
            device: device(),
            visible_ms: num(now())
        };
        if (typeof window.KP_RELEASE === 'string') out.release = window.KP_RELEASE.slice(0, 64);

        navigationTiming(out);
        out.lcp_ms = num(vitals.lcp);
        out.fcp_ms = num(vitals.fcp);
        out.cls = num(vitals.cls, 4);
        out.inp_ms = num(vitals.inp);

        // Snapshot periodik membawa angka interval supaya kelihatan apakah kiosk
        // makin berat seiring malam; load/final membawa angka sepanjang umur.
        var lt = phase === 'periodic' ? longInterval : longLife;
        out.longtask_count = lt.count;
        out.longtask_total_ms = num(lt.total);
        out.longtask_max_ms = num(lt.max);
        if (phase === 'periodic') out.interval_ms = num(now() - intervalStartedAt);

        if (phase !== 'periodic') resourceTiming(out);
        deviceInfo(out);
        return out;
    }

    function resetInterval() {
        longInterval = { count: 0, total: 0, max: 0 };
        intervalStartedAt = now();
    }

    function sendRum(phase) {
        try {
            if (rumSends >= RUM_MAX_SENDS) return;
            // Sisakan satu jatah untuk snapshot final.
            if (phase !== 'final' && !finalSent && rumSends >= RUM_MAX_SENDS - 1) return;
            var payload = snapshot(phase);
            rumSends++;
            payload.seq = rumSends;
            post(RUM_ENDPOINT, payload);
            if (phase !== 'final') resetInterval();
        } catch (e) { /* diam */ }
    }

    function whenIdle(fn) {
        try {
            if (window.requestIdleCallback) {
                window.requestIdleCallback(fn, { timeout: 5000 });
                return;
            }
        } catch (e) { /* jatuh ke setTimeout */ }
        setTimeout(fn, 0);
    }

    function startRum() {
        var loadSent = false;
        startObservers();

        function scheduleLoad() {
            setTimeout(function () {
                // Tidak digantung pada finalSent: di HP, pindah aplikasi sebentar
                // sudah memicu "hidden" → final terkirim dini. Snapshot load
                // tetap dibutuhkan; kalau halaman benar-benar ditutup, timer
                // ini memang tidak akan pernah berjalan.
                whenIdle(function () {
                    if (loadSent) return;
                    loadSent = true;
                    sendRum('load');
                });
            }, RUM_LOAD_DELAY_MS);
        }
        if (document.readyState === 'complete') scheduleLoad();
        else window.addEventListener('load', scheduleLoad);

        // Final dikirim sinkron: saat halaman disembunyikan/ditutup, callback idle
        // mungkin tidak pernah sempat berjalan.
        function sendFinal() {
            if (finalSent) return;
            finalSent = true;
            sendRum('final');
        }
        document.addEventListener('visibilitychange', function () {
            if (document.visibilityState === 'hidden') sendFinal();
        });
        window.addEventListener('pagehide', sendFinal);

        var timer = setInterval(function () {
            whenIdle(function () {
                if (rumSends >= RUM_MAX_SENDS - (finalSent ? 0 : 1)) {
                    clearInterval(timer);
                    return;
                }
                sendRum('periodic');
            });
        }, RUM_PERIODIC_MS);
    }

    // ------------------------------------------------------------------
    // Pemasangan
    // ------------------------------------------------------------------

    try { device(); } catch (e) { /* diam */ }
    try { patchFetch(); } catch (e) { /* diam */ }

    window.addEventListener('error', function (event) {
        report('js_error', event.message, {
            source: (event.filename || '') + ':' + (event.lineno || 0),
            stack: event.error && event.error.stack
        });
    });

    window.addEventListener('unhandledrejection', function (event) {
        var reason = event.reason;
        report('unhandled_rejection', (reason && reason.message) || reason, {
            stack: reason && reason.stack
        });
    });

    try { startRum(); } catch (e) { /* diam */ }

    window.KPObs = {
        report: report,
        device: device,
        // Untuk diagnosis di konsol: KPObs.snapshot() tanpa mengirim apa pun.
        snapshot: function () {
            try { return snapshot('load'); } catch (e) { return null; }
        }
    };
})();
