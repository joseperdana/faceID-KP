/**
 * KPObs — pelaporan error sisi browser ke backend.
 *
 * Kenapa bukan Sentry Browser SDK: frontend ini vanilla JS tanpa build step dan
 * tidak diminifikasi, jadi source map (nilai jual utama SDK) tidak relevan.
 * Reporter ringan ini mengirim ke /api/client-error, yang meneruskan ke Sentry
 * project yang sama dengan backend — satu dashboard, tanpa dependensi CDN.
 *
 * Muat sedini mungkin di <head>, sebelum script lain, supaya error saat boot
 * ikut tertangkap.
 */
(function () {
    'use strict';

    var ENDPOINT = '/api/client-error';
    var MAX_PER_MINUTE = 10;   // Kiosk dipakai puluhan orang; jangan banjiri kuota.
    var DEDUPE_WINDOW_MS = 60000;

    var sentTimestamps = [];
    var recentSignatures = {};

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

    function send(payload) {
        var body = JSON.stringify(payload);
        try {
            // keepalive/sendBeacon supaya laporan tetap terkirim walau halaman
            // langsung di-reset atau ditutup setelah error.
            if (navigator.sendBeacon) {
                navigator.sendBeacon(ENDPOINT, new Blob([body], { type: 'application/json' }));
                return;
            }
            fetch(ENDPOINT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: body,
                keepalive: true
            }).catch(function () { /* laporan gagal tidak boleh memicu laporan baru */ });
        } catch (e) { /* diam: observability tidak boleh merusak alur absensi */ }
    }

    function report(kind, message, extra) {
        try {
            var msg = String(message == null ? 'unknown' : message).slice(0, 500);
            var signature = kind + '|' + msg;
            if (!allowed(signature)) return;

            send({
                kind: String(kind || 'js_error').slice(0, 40),
                message: msg,
                source: (extra && extra.source ? String(extra.source) : '').slice(0, 300),
                stack: (extra && extra.stack ? String(extra.stack) : '').slice(0, 2000),
                page: location.pathname.slice(0, 300),
                user_agent: navigator.userAgent.slice(0, 300),
                context: (extra && extra.context) || {}
            });
        } catch (e) { /* idem */ }
    }

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

    window.KPObs = { report: report };
})();
