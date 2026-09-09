/**
 * Attendance kiosk.
 *
 * This runs unattended on a tablet by the door with a queue behind it, so the
 * governing rule is: never leave the screen in a state that requires a person
 * who knows the system to intervene. Every failure path resets itself, and
 * every failure names something the next person in the queue can act on.
 */
(function () {
  'use strict';

  var REQUIRED_STABLE_FRAMES = 15;
  var MOVEMENT_THRESHOLD = 0.045;
  var SUCCESS_MODAL_MS = 3500;   // must match the .countdown-bar animation in index.html
  var ERROR_RESET_MS = 9000;     // longer than success: this text has to be read
  var POST_SUCCESS_COOLDOWN_MS = 2500;
  var MAX_CONSECUTIVE_FAILURES = 3;
  var SEARCH_DEBOUNCE_MS = 250;
  var SAFE_ZONE = { xMin: 0.28, xMax: 0.72, yMin: 0.18, yMax: 0.82 };

  var el = {
    video: document.getElementById('video'),
    canvas: document.getElementById('output_canvas'),
    loading: document.getElementById('loading'),
    statusIcon: document.getElementById('status-icon'),
    statusTitle: document.getElementById('status-title'),
    statusDesc: document.getElementById('status-desc'),
    progress: document.getElementById('scan-progress'),
    result: document.getElementById('result-area'),
    modal: document.getElementById('manual-search-modal'),
    searchInput: document.getElementById('manual-search-input'),
    searchResults: document.getElementById('manual-search-results'),
    btnOpenSearch: document.getElementById('btn-open-manual-search'),
    btnSidebarSearch: document.getElementById('btn-sidebar-manual-search'),
    btnCloseSearch: document.getElementById('btn-close-manual-search'),
  };
  var ctx = el.canvas.getContext('2d');

  var state = {
    processing: false,
    stableFrames: 0,
    lastNose: null,
    cooldownUntil: 0,
    consecutiveFailures: 0,
    lat: null,
    lng: null,
    accuracy: null,
    aiReady: false,
  };

  var camera = null;
  var faceDetection = null;
  var resetTimer = null;
  var searchTimer = null;

  // --- status -------------------------------------------------------------

  var STATUS_ICONS = {
    idle: '<path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>',
    warning: '<path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>',
    scanning: '<path stroke-linecap="round" stroke-linejoin="round" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"/>',
    error: '<path stroke-linecap="round" stroke-linejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"/>',
  };
  var STATUS_TONE = {
    idle: 'text-white',
    warning: 'text-amber-400',
    scanning: 'text-cyan-400',
    error: 'text-rose-400',
  };

  function updateStatus(tone, title, desc) {
    el.statusTitle.innerText = title;
    el.statusDesc.innerText = desc;
    // tracking-tight is preserved; rebuilding className without it made the
    // heading visibly jump the first time the status changed.
    el.statusTitle.className =
      'text-3xl font-extrabold mb-2 leading-tight tracking-tight transition-colors ' +
      (STATUS_TONE[tone] || STATUS_TONE.idle);
    // Drive the scanline from real state rather than letting it loop forever.
    document.body.classList.toggle('is-scanning', tone === 'scanning');
    el.statusIcon.innerHTML =
      '<svg class="w-7 h-7 ' +
      (STATUS_TONE[tone] || STATUS_TONE.idle) +
      (tone === 'scanning' ? ' animate-pulse' : '') +
      '" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">' +
      (STATUS_ICONS[tone] || STATUS_ICONS.idle) +
      '</svg>';
  }

  // --- recovery screens ---------------------------------------------------

  function clearResetTimer() {
    if (resetTimer) {
      clearTimeout(resetTimer);
      resetTimer = null;
    }
  }

  /**
   * Render a recovery screen and schedule its own dismissal.
   *
   * The old failure branch set isProcessing = true and never cleared it outside
   * an onclick, so one person who walked away after a failed scan left the
   * kiosk frozen for everyone behind them, with the camera loop stopped and no
   * sign that the screen was stale.
   */
  function showRecovery(options) {
    clearResetTimer();
    el.loading.classList.add('hidden');
    el.result.classList.remove('hidden');

    var actions = (options.actions || [])
      .map(function (action) {
        var base =
          'py-3.5 px-4 rounded-xl text-sm font-semibold transition-all flex items-center justify-center gap-2 w-full';
        if (action.kind === 'primary') {
          return (
            '<button type="button" data-action="' + action.id + '" class="' + base +
            ' bg-azure-600 hover:bg-azure-500 text-white shadow-lg shadow-azure-600/25">' +
            KP.escapeHtml(action.label) + '</button>'
          );
        }
        return (
          '<a href="' + action.href + '" class="' + base +
          ' bg-obsidian-750 hover:bg-obsidian-700 text-slate-100 border border-white/10">' +
          KP.escapeHtml(action.label) + '</a>'
        );
      })
      .join('');

    el.result.innerHTML =
      '<div class="w-14 h-14 rounded-2xl ' + options.iconClass +
      ' flex items-center justify-center mb-4 mx-auto">' +
      '<svg class="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">' +
      options.icon + '</svg></div>' +
      '<h3 class="text-xl font-extrabold text-white mb-1.5">' + KP.escapeHtml(options.title) + '</h3>' +
      // text-slate-400, not text-slate-500: on this background slate-500 is
      // about 4.1:1, below the 4.5:1 minimum, on a screen read at arm's length
      // in late-afternoon light.
      '<p class="text-slate-400 text-sm mb-5 max-w-xs mx-auto">' + KP.escapeHtml(options.message) + '</p>' +
      '<div class="flex flex-col gap-2.5 w-full max-w-xs">' + actions + '</div>' +
      '<button type="button" data-action="retry" class="text-slate-400 text-sm hover:text-white underline mt-4">Coba Scan Lagi</button>';

    el.result.querySelectorAll('[data-action]').forEach(function (node) {
      node.addEventListener('click', function () {
        var id = node.getAttribute('data-action');
        if (id === 'search') openSearch();
        else resetScan();
      });
    });

    if (options.autoResetMs !== 0) {
      resetTimer = setTimeout(resetScan, options.autoResetMs || ERROR_RESET_MS);
    }
  }

  var ICON_LOCATION =
    '<path stroke-linecap="round" stroke-linejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/>';
  var ICON_WARNING = STATUS_ICONS.warning;
  var ICON_OFFLINE =
    '<path stroke-linecap="round" stroke-linejoin="round" d="M18.364 5.636L5.636 18.364m0-12.728l12.728 12.728"/>';

  function showUnknownFace() {
    showRecovery({
      iconClass: 'bg-rose-500/10 border border-rose-500/20 text-rose-400',
      icon: ICON_WARNING,
      title: 'Wajah Belum Dikenali',
      message: 'Coba lagi menghadap kamera, atau cari namamu secara manual.',
      actions: [
        { kind: 'primary', id: 'search', label: 'Cari Nama Manual' },
        { kind: 'link', href: '/register', label: 'Saya Jemaat Baru' },
      ],
    });
  }

  function showServerProblem(message) {
    showRecovery({
      iconClass: 'bg-rose-500/10 border border-rose-500/20 text-rose-400',
      icon: ICON_OFFLINE,
      title: 'Server Sedang Bermasalah',
      message: message + ' Absensi tetap bisa dilakukan lewat pencarian nama.',
      actions: [{ kind: 'primary', id: 'search', label: 'Cari Nama Manual' }],
    });
  }

  // --- success / duplicate ------------------------------------------------

  function showResultModal(data, message, isDuplicate) {
    clearResetTimer();
    el.result.classList.add('hidden');

    var modal = document.getElementById('success-modal');
    var content = document.getElementById('success-modal-content');
    var icon = document.getElementById('success-icon');
    var heading = document.getElementById('success-heading');

    document.getElementById('success-name').innerText = data.name || '';
    document.getElementById('success-message').innerText = message || '';
    document.getElementById('success-streak').innerText = String(data.total_attendance || 1);
    document.getElementById('success-last-seen').innerText = data.last_seen || 'Hari Ini';

    // A duplicate must not look like a fresh check-in. Both used to render the
    // same green tick, so nobody could tell that a scan had recorded nothing —
    // which also hid misrecognition from the operator.
    if (icon && heading) {
      if (isDuplicate) {
        heading.innerText = 'Sudah Absen Hari Ini';
        heading.className = 'text-3xl font-extrabold text-amber-300 mb-1 tracking-tight';
        icon.className =
          'w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/25 text-amber-400 flex items-center justify-center mb-4 mx-auto';
        icon.innerHTML =
          '<svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>';
      } else {
        heading.innerText = 'Halo,';
        heading.className = 'text-3xl font-extrabold text-white mb-1 tracking-tight';
        icon.className =
          'w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/25 text-emerald-400 flex items-center justify-center mb-4 mx-auto';
        icon.innerHTML =
          '<svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>';
      }
    }

    var badge = document.getElementById('success-badge-method');
    if (badge) {
      var badgeBase =
        'inline-flex items-center gap-1.5 mb-5 text-xs font-bold px-3 py-1 rounded-full border ';
      if (isDuplicate && data.checked_in_at) {
        badge.innerText = 'Tercatat pukul ' + data.checked_in_at + ' WIB';
        badge.className = badgeBase + 'bg-amber-500/10 text-amber-300 border-amber-500/20';
      } else if (data.method === 'manual') {
        badge.innerText = 'Absen Manual';
        badge.className = badgeBase + 'bg-amber-500/10 text-amber-300 border-amber-500/20';
      } else {
        badge.innerText = 'Scan Wajah';
        badge.className = badgeBase + 'bg-cyan-500/10 text-cyan-300 border-cyan-500/20';
      }
    }

    modal.classList.remove('hidden');
    setTimeout(function () {
      content.classList.remove('scale-95', 'opacity-0');
      content.classList.add('scale-100', 'opacity-100');
    }, 10);

    resetTimer = setTimeout(function () {
      content.classList.remove('scale-100', 'opacity-100');
      content.classList.add('scale-95', 'opacity-0');
      setTimeout(function () {
        modal.classList.add('hidden');
        // Hold off scanning briefly: the person who just checked in is still
        // standing in frame, and without this they were immediately rescanned
        // and shown a duplicate notice.
        state.cooldownUntil = Date.now() + POST_SUCCESS_COOLDOWN_MS;
        resetScan();
        updateStatus('idle', 'Silakan Maju', 'Berikutnya, silakan berdiri di depan kamera.');
      }, 300);
    }, SUCCESS_MODAL_MS);
  }

  // --- detection loop -----------------------------------------------------

  function onResults(results) {
    // Assigning width/height reallocates the canvas backing store and forces a
    // layout pass. Doing it every frame meant ~324,000 reallocations of ~3.7 MB
    // over a three-hour service.
    if (el.canvas.width !== el.video.videoWidth) {
      el.canvas.width = el.video.videoWidth;
      el.canvas.height = el.video.videoHeight;
    }
    ctx.clearRect(0, 0, el.canvas.width, el.canvas.height);

    if (Date.now() < state.cooldownUntil) return;

    var detections = results.detections || [];
    if (detections.length === 0) {
      updateStatus('idle', 'Mencari Wajah', 'Pastikan wajah terlihat jelas dan tidak silau.');
      resetProgress();
      return;
    }

    if (detections.length > 1) {
      // detections[0] carries no ordering guarantee, so with two people in
      // frame the person behind could be captured and checked in instead.
      updateStatus('warning', 'Terdeteksi Lebih dari Satu Wajah', 'Mohon satu orang saja di depan kamera.');
      resetProgress();
      return;
    }

    var nose = detections[0].landmarks[2];
    var inZone =
      nose.x > SAFE_ZONE.xMin && nose.x < SAFE_ZONE.xMax &&
      nose.y > SAFE_ZONE.yMin && nose.y < SAFE_ZONE.yMax;

    if (!inZone) {
      updateStatus('warning', 'Posisikan Wajah di Oval', directionHint(nose));
      resetProgress();
      return;
    }
    checkStability(nose.x, nose.y);
  }

  /** Tell the person which way to move rather than repeating a generic warning. */
  function directionHint(nose) {
    if (nose.y <= SAFE_ZONE.yMin) return 'Sedikit turunkan posisi, atau turunkan sudut tablet.';
    if (nose.y >= SAFE_ZONE.yMax) return 'Sedikit naikkan posisi, atau naikkan sudut tablet.';
    if (nose.x <= SAFE_ZONE.xMin) return 'Geser sedikit ke kanan.';
    return 'Geser sedikit ke kiri.';
  }

  function resetProgress() {
    state.stableFrames = 0;
    state.lastNose = null;
    el.progress.style.width = '0%';
  }

  function checkStability(x, y) {
    if (state.processing) return;
    if (state.lastNose) {
      var dx = x - state.lastNose.x;
      var dy = y - state.lastNose.y;
      if (Math.sqrt(dx * dx + dy * dy) < MOVEMENT_THRESHOLD) {
        state.stableFrames += 1;
        updateStatus('scanning', 'Tahan Posisi', 'Sedang memindai wajah…');
      } else {
        state.stableFrames = 0;
        updateStatus('warning', 'Terlalu Banyak Bergerak', 'Mohon diam sejenak.');
      }
    }
    state.lastNose = { x: x, y: y };
    el.progress.style.width = (state.stableFrames / REQUIRED_STABLE_FRAMES) * 100 + '%';
    if (state.stableFrames >= REQUIRED_STABLE_FRAMES) captureAndRecognise();
  }

  // --- capture ------------------------------------------------------------

  function appendLocation(formData) {
    if (state.lat !== null && state.lng !== null) {
      formData.append('lat', state.lat);
      formData.append('lng', state.lng);
      if (state.accuracy !== null) formData.append('accuracy', state.accuracy);
    }
  }

  function captureAndRecognise() {
    state.processing = true;
    el.loading.classList.remove('hidden');

    var capture = document.createElement('canvas');
    // Downscale before upload. A 1280x720 JPEG at q0.95 is ~200 KB; 640 wide at
    // q0.82 is ~35 KB, which on a saturated hall wifi is the difference between
    // a fast response and a visible wait.
    var scale = Math.min(1, 640 / (el.video.videoWidth || 640));
    capture.width = Math.round(el.video.videoWidth * scale);
    capture.height = Math.round(el.video.videoHeight * scale);
    capture.getContext('2d').drawImage(el.video, 0, 0, capture.width, capture.height);

    capture.toBlob(
      function (blob) {
        var formData = new FormData();
        formData.append('file', blob, 'capture.jpg');
        appendLocation(formData);
        submitRecognition(formData);
      },
      'image/jpeg',
      0.82
    );
  }

  async function submitRecognition(formData) {
    try {
      var data = await KP.apiFetch('/api/recognize', { method: 'POST', body: formData });
      state.consecutiveFailures = 0;
      el.loading.classList.add('hidden');
      handleCheckInResponse(data);
    } catch (err) {
      el.loading.classList.add('hidden');
      handleRecognitionError(err);
    }
  }

  function handleCheckInResponse(data) {
    if (data.status === 'success') {
      showResultModal(data.data, data.message, false);
    } else if (data.status === 'already_checked_in') {
      showResultModal(data.data, data.message, true);
    } else if (data.status === 'ambiguous') {
      showRecovery({
        iconClass: 'bg-amber-500/10 border border-amber-500/20 text-amber-400',
        icon: ICON_WARNING,
        title: 'Wajah Mirip Lebih dari Satu Jemaat',
        message: 'Agar tidak salah catat, silakan pilih namamu sendiri.',
        actions: [{ kind: 'primary', id: 'search', label: 'Cari Nama Manual' }],
      });
    } else {
      showUnknownFace();
    }
  }

  /**
   * Distinguish the failure kinds instead of calling everything "not registered".
   *
   * The old catch-all sent members whose scan hit a 429 or a 500 to the
   * registration form, producing duplicate identities and hiding the real
   * incident from the committee.
   */
  function handleRecognitionError(err) {
    var status = err.status || 0;

    if (status === 403) {
      showRecovery({
        iconClass: 'bg-amber-500/10 border border-amber-500/20 text-amber-400',
        icon: ICON_LOCATION,
        title: 'Lokasi di Luar Jangkauan',
        message: err.message,
        actions: [{ kind: 'primary', id: 'search', label: 'Cari Nama Manual' }],
      });
      return;
    }

    if (status === 400) {
      showRecovery({
        iconClass: 'bg-amber-500/10 border border-amber-500/20 text-amber-400',
        icon: ICON_WARNING,
        title: 'Wajah Kurang Jelas',
        message: 'Coba lagi dengan pencahayaan lebih baik, atau cari namamu manual.',
        actions: [{ kind: 'primary', id: 'search', label: 'Cari Nama Manual' }],
      });
      return;
    }

    state.consecutiveFailures += 1;
    showServerProblem(err.message);

    // Stop the automatic retry loop. Without this the kiosk kept firing a fresh
    // JPEG at a dead server roughly every three seconds for the whole service.
    if (state.consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
      clearResetTimer();
      updateStatus('error', 'Pemindaian Dihentikan', 'Gunakan pencarian nama manual.');
      openSearch();
    }
  }

  // --- manual search ------------------------------------------------------

  function searchPlaceholder(text) {
    el.searchResults.innerHTML =
      '<div class="text-center py-10 text-slate-400 text-sm">' + KP.escapeHtml(text) + '</div>';
  }

  function openSearch() {
    clearResetTimer();
    if (!el.modal) return;
    el.modal.classList.remove('hidden');
    if (el.searchInput) {
      el.searchInput.value = '';
      el.searchInput.focus();
    }
    searchPlaceholder('Ketik minimal 2 huruf nama untuk mencari.');
  }

  function closeSearch() {
    if (el.modal) el.modal.classList.add('hidden');
  }

  function renderSearchResults(users, query) {
    if (!users.length) {
      el.searchResults.innerHTML =
        '<div class="text-center py-10">' +
        '<p class="text-slate-400 text-sm mb-3">Nama "' + KP.escapeHtml(query) + '" tidak ditemukan.</p>' +
        '<a href="/register" class="inline-flex items-center gap-1.5 py-2.5 px-4 bg-azure-600/20 hover:bg-azure-600/30 text-azure-300 text-sm font-semibold rounded-xl border border-azure-500/30 transition-all">Daftar sebagai Jemaat Baru</a>' +
        '</div>';
      return;
    }

    el.searchResults.innerHTML = users
      .map(function (user) {
        // data-user-id rather than an inline onclick with the id interpolated
        // into a JavaScript context, where HTML escaping would not have helped.
        return (
          '<div class="p-3.5 bg-obsidian-850 hover:bg-obsidian-800 rounded-2xl border border-white/[0.06] flex items-center justify-between gap-3 transition-all">' +
          '<h4 class="font-bold text-base text-white">' + KP.escapeHtml(user.full_name) + '</h4>' +
          '<button type="button" data-user-id="' + KP.escapeHtml(String(user.id)) +
          '" class="js-checkin shrink-0 py-2.5 px-5 bg-azure-600 hover:bg-azure-500 active:scale-95 text-white font-semibold text-sm rounded-xl transition-all shadow shadow-azure-600/30">Check-in</button>' +
          '</div>'
        );
      })
      .join('');
  }

  async function runSearch(query) {
    try {
      el.searchResults.innerHTML =
        '<div class="text-center py-8 text-cyan-400 text-sm animate-pulse">Mencari jemaat…</div>';
      var result = await KP.apiFetch('/api/users/search?q=' + encodeURIComponent(query));
      renderSearchResults(result.data || [], query);
    } catch (err) {
      el.searchResults.innerHTML =
        '<div class="text-center py-8 text-rose-400 text-sm">' + KP.escapeHtml(err.message) + '</div>';
    }
  }

  async function manualCheckIn(userId, button) {
    if (button) button.disabled = true;
    closeSearch();
    el.loading.classList.remove('hidden');

    try {
      var formData = new FormData();
      formData.append('user_id', userId);
      appendLocation(formData);
      var data = await KP.apiFetch('/api/attendance/manual-checkin', {
        method: 'POST',
        body: formData,
      });
      el.loading.classList.add('hidden');
      handleCheckInResponse(data);
    } catch (err) {
      el.loading.classList.add('hidden');
      if (err.status === 403) {
        KP.alertWarning('Lokasi di Luar Jangkauan', err.message);
      } else {
        KP.alertError('Gagal Absen', err.message);
      }
      resetScan();
    } finally {
      if (button) button.disabled = false;
    }
  }

  // --- camera lifecycle ---------------------------------------------------

  function showCameraProblem(detail) {
    updateStatus('error', 'Kamera Tidak Bisa Diakses', detail);
    showRecovery({
      iconClass: 'bg-rose-500/10 border border-rose-500/20 text-rose-400',
      icon: ICON_OFFLINE,
      title: 'Kamera Tidak Bisa Diakses',
      message: detail + ' Absensi tetap bisa dilakukan lewat pencarian nama.',
      actions: [{ kind: 'primary', id: 'search', label: 'Cari Nama Manual' }],
      autoResetMs: 0, // this one needs a person, so it must not clear itself
    });
  }

  function cameraErrorMessage(err) {
    var name = err && err.name;
    if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
      return 'Izin kamera ditolak. Buka pengaturan browser dan izinkan kamera untuk situs ini.';
    }
    if (name === 'NotReadableError' || name === 'TrackStartError') {
      return 'Kamera sedang dipakai aplikasi lain. Tutup aplikasi tersebut, lalu muat ulang halaman.';
    }
    if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
      return 'Tidak ada kamera yang terdeteksi pada perangkat ini.';
    }
    return 'Perangkat kamera tidak dapat dimulai.';
  }

  function startCamera() {
    if (!camera) return;
    // camera.start() returns a promise that rejects when permission is denied
    // or the device is busy. Without a catch the page kept saying "Siap Absen"
    // over a black rectangle — telling the queue it was ready while it was not.
    Promise.resolve(camera.start()).catch(function (err) {
      showCameraProblem(cameraErrorMessage(err));
    });
  }

  function releaseCamera() {
    try {
      if (camera) camera.stop();
    } catch (err) {
      /* the tab is going away; nothing useful to do */
    }
    var stream = el.video.srcObject;
    if (stream && stream.getTracks) {
      stream.getTracks().forEach(function (track) {
        track.stop();
      });
    }
    el.video.srcObject = null;
  }

  // --- geolocation --------------------------------------------------------

  function requestLocation() {
    updateStatus('idle', 'Memeriksa Lokasi', 'Mohon izinkan akses lokasi pada browser.');

    if (!navigator.geolocation) {
      updateStatus('warning', 'Lokasi Tidak Didukung', 'Browser ini tidak mendukung deteksi lokasi.');
      startCamera();
      return;
    }

    navigator.geolocation.getCurrentPosition(
      function (position) {
        state.lat = position.coords.latitude;
        state.lng = position.coords.longitude;
        // Sent to the server so a poor indoor fix is not treated as being far
        // away. Indoors the browser often falls back to a wifi fix accurate to
        // kilometres.
        state.accuracy = position.coords.accuracy;
        updateStatus('idle', 'Siap Absen', 'Posisikan wajah di dalam oval.');
        startCamera();
      },
      function () {
        state.lat = null;
        state.lng = null;
        state.accuracy = null;
        updateStatus(
          'warning',
          'Lokasi Tidak Aktif',
          'Absen wajah butuh izin lokasi. Tanpa itu, gunakan Cari Nama Manual.'
        );
        startCamera();
      },
      { enableHighAccuracy: true, timeout: 6000, maximumAge: 0 }
    );
  }

  // --- reset --------------------------------------------------------------

  function resetScan() {
    clearResetTimer();
    state.processing = false;
    resetProgress();
    el.result.classList.add('hidden');
    el.result.innerHTML = '';
    var modal = document.getElementById('success-modal');
    if (modal) modal.classList.add('hidden');
    if (state.aiReady) {
      updateStatus('idle', 'Siap Absen', 'Posisikan wajah di dalam oval.');
    }
  }
  window.resetScan = resetScan;

  // --- wiring -------------------------------------------------------------

  // The fallback UI is wired up FIRST, before anything that depends on a CDN.
  // Previously `new FaceDetection(...)` ran at the top level, so when jsDelivr
  // was unreachable it threw a ReferenceError that stopped the rest of the
  // file — including these listeners. The kiosk's manual fallback became a
  // dead button, silently, in exactly the situation it exists for.
  if (el.btnOpenSearch) el.btnOpenSearch.addEventListener('click', openSearch);
  if (el.btnSidebarSearch) el.btnSidebarSearch.addEventListener('click', openSearch);
  if (el.btnCloseSearch) el.btnCloseSearch.addEventListener('click', closeSearch);

  if (el.modal) {
    el.modal.addEventListener('click', function (event) {
      if (event.target === el.modal) closeSearch();
    });
  }
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') closeSearch();
  });

  if (el.searchResults) {
    el.searchResults.addEventListener('click', function (event) {
      var button = event.target.closest('.js-checkin');
      if (button) manualCheckIn(button.dataset.userId, button);
    });
  }

  if (el.searchInput) {
    el.searchInput.addEventListener('input', function (event) {
      clearTimeout(searchTimer);
      var query = event.target.value.trim();
      if (query.length < 2) {
        searchPlaceholder('Ketik minimal 2 huruf nama untuk mencari.');
        return;
      }
      searchTimer = setTimeout(function () {
        runSearch(query);
      }, SEARCH_DEBOUNCE_MS);
    });
  }

  window.addEventListener('pagehide', releaseCamera);
  document.addEventListener('visibilitychange', function () {
    // Holding the camera open while the operator is on another tab drains the
    // tablet and keeps the device locked against other apps.
    if (document.hidden) releaseCamera();
    else if (state.aiReady) startCamera();
  });

  function boot() {
    if (!KP.librariesPresent(['FaceDetection', 'Camera'])) {
      updateStatus('error', 'Mode Offline', 'Modul pengenalan wajah gagal dimuat.');
      showRecovery({
        iconClass: 'bg-amber-500/10 border border-amber-500/20 text-amber-400',
        icon: ICON_OFFLINE,
        title: 'Absen Wajah Tidak Tersedia',
        message:
          'Komponen pengenalan wajah gagal dimuat, kemungkinan karena koneksi internet. Absensi tetap berjalan lewat pencarian nama.',
        actions: [{ kind: 'primary', id: 'search', label: 'Cari Nama Manual' }],
        autoResetMs: 0,
      });
      openSearch();
      return;
    }

    faceDetection = new FaceDetection({
      locateFile: function (file) {
        // Served from our own origin when scripts/vendor_assets.sh has been run,
        // so the kiosk keeps working without internet access.
        return (window.KP_VENDOR_BASE || 'https://cdn.jsdelivr.net/npm/@mediapipe/face_detection@0.4.1646425229/') + file;
      },
    });
    faceDetection.setOptions({ model: 'short', minDetectionConfidence: 0.45 });
    faceDetection.onResults(onResults);

    camera = new Camera(el.video, {
      onFrame: async function () {
        if (!state.processing) await faceDetection.send({ image: el.video });
      },
    });

    state.aiReady = true;
    requestLocation();
  }

  window.addEventListener('load', boot);
})();
