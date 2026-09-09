/**
 * Utilities shared by every page.
 *
 * Previously each page carried its own copy of escapeHtml (two spellings, two
 * implementations, and two files with none at all), its own fetch error
 * handling (or none), and its own inline dialog theme repeated ten times.
 */
(function (global) {
  'use strict';

  /** Escape a value for interpolation into HTML text or an attribute. */
  function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value).replace(/[&<>'"]/g, function (char) {
      return {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        "'": '&#39;',
        '"': '&quot;',
      }[char];
    });
  }

  /**
   * Wrapper around fetch that turns every failure into a usable message.
   *
   * Callers used to do `if (!res.ok) throw new Error("Gagal")` and then log to
   * the console, so an expired session rendered as empty tables and dashes —
   * indistinguishable from "nobody has checked in yet".
   */
  async function apiFetch(url, options) {
    let response;
    try {
      response = await fetch(url, options);
    } catch (err) {
      throw new ApiError(
        'Tidak dapat terhubung ke server. Periksa koneksi jaringan.',
        0
      );
    }

    if (response.status === 401) {
      // Redirect rather than surface a message: the session is gone and there
      // is nothing the current page can usefully do.
      if (!global.__faceidRedirecting) {
        global.__faceidRedirecting = true;
        global.location.href = '/login';
      }
      throw new ApiError('Sesi berakhir. Mengalihkan ke halaman masuk…', 401);
    }

    let body = null;
    try {
      body = await response.json();
    } catch (err) {
      body = null;
    }

    if (!response.ok) {
      throw new ApiError(messageForStatus(response.status, body), response.status, body);
    }
    return body;
  }

  function ApiError(message, status, body) {
    const error = new Error(message);
    error.name = 'ApiError';
    error.status = status;
    error.body = body;
    return error;
  }

  /**
   * Human-readable message per status.
   *
   * Server `detail` strings are deliberately not shown for 5xx: they used to
   * carry raw PostgREST errors, so a member could read "PGRST204 ... column
   * 'method' of 'attendance_logs'" on the kiosk screen.
   */
  function messageForStatus(status, body) {
    if (status === 429) {
      return 'Terlalu banyak permintaan. Tunggu sekitar satu menit, lalu coba lagi.';
    }
    if (status === 503) {
      return 'Layanan sedang bermasalah. Coba lagi sebentar lagi.';
    }
    if (status >= 500) {
      return 'Server sedang bermasalah. Hubungi panitia teknis.';
    }
    if (body && typeof body.detail === 'string') return body.detail;
    if (body && typeof body.message === 'string') return body.message;
    if (status === 404) return 'Data tidak ditemukan.';
    if (status === 403) return 'Akses ditolak.';
    return 'Permintaan gagal diproses.';
  }

  /** Dialog defaults matching the dark theme, instead of repeating them inline. */
  var swalTheme = {
    background: '#0b0d13',
    color: '#f8fafc',
    confirmButtonColor: '#0284c7',
    cancelButtonColor: '#334155',
  };

  function alertError(title, text) {
    if (!global.Swal) {
      global.alert(title + '\n\n' + text);
      return Promise.resolve();
    }
    return global.Swal.fire(
      Object.assign({}, swalTheme, {
        icon: 'error',
        title: title,
        text: text,
        confirmButtonColor: '#ef4444',
      })
    );
  }

  function alertWarning(title, text) {
    if (!global.Swal) {
      global.alert(title + '\n\n' + text);
      return Promise.resolve();
    }
    return global.Swal.fire(
      Object.assign({}, swalTheme, {
        icon: 'warning',
        title: title,
        text: text,
        confirmButtonColor: '#f59e0b',
      })
    );
  }

  /**
   * Are the third-party libraries this page needs actually present?
   *
   * The kiosk runs in a church hall on shared wifi. When a CDN is unreachable
   * the page must degrade to manual search rather than throw a ReferenceError
   * at the top level, which stopped the rest of the script — including the
   * listener that wires up the fallback button.
   */
  function librariesPresent(names) {
    return names.every(function (name) {
      return typeof global[name] !== 'undefined';
    });
  }

  global.KP = {
    escapeHtml: escapeHtml,
    apiFetch: apiFetch,
    ApiError: ApiError,
    messageForStatus: messageForStatus,
    swalTheme: swalTheme,
    alertError: alertError,
    alertWarning: alertWarning,
    librariesPresent: librariesPresent,
  };
})(window);
