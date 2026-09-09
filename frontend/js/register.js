/**
 * Newcomer registration and face-data update.
 *
 * Reached from the kiosk when recognition fails, so it has to be usable by
 * someone who has never seen it before, standing at a tablet with a queue
 * behind them.
 */
(function () {
  'use strict';

  var BURST_FRAMES = 3;
  var BURST_GAP_MS = 300;
  var REDIRECT_MS = 4000;

  var el = {
    video: document.getElementById('video'),
    canvas: document.getElementById('output_canvas'),
    form: document.getElementById('reg-form'),
    submit: document.getElementById('btn-submit'),
    statusText: document.getElementById('status-text'),
    result: document.getElementById('result-message'),
    toggleUpdate: document.getElementById('toggle-update'),
    consent: document.getElementById('consent'),
    consentWrapper: document.getElementById('consent-wrapper'),
    fullName: document.getElementById('full_name'),
    phone: document.getElementById('phone_number'),
    genderWrapper: document.getElementById('gender-wrapper'),
    phoneWrapper: document.getElementById('phone-wrapper'),
    formTitle: document.getElementById('form-title'),
  };

  var camera = null;
  var faceValid = false;

  // --- result panel -------------------------------------------------------

  /**
   * Render a message as text, never as markup.
   *
   * `resultMsg.innerHTML` interpolated the server's message, which echoes the
   * submitted full_name straight back. On a page that holds face images and
   * phone numbers that was a stored-XSS path into an admin's session.
   */
  function showResult(kind, title, detail) {
    el.result.className =
      'mt-4 p-4 rounded-xl text-center text-sm ' +
      (kind === 'success'
        ? 'bg-emerald-500/10 text-emerald-200 border border-emerald-500/20'
        : 'bg-rose-500/10 text-rose-200 border border-rose-500/20');
    el.result.replaceChildren(
      Object.assign(document.createElement('strong'), { textContent: title }),
      document.createElement('br'),
      document.createTextNode(detail || '')
    );
    el.result.classList.remove('hidden');
  }

  function setStatus(text, tone) {
    el.statusText.innerText = text;
    el.statusText.className =
      'font-bold ' +
      ({ ok: 'text-emerald-400', warn: 'text-amber-400', bad: 'text-rose-400' }[tone] ||
        'text-slate-300');
  }

  function setSubmitEnabled(enabled) {
    faceValid = enabled;
    el.submit.disabled = !enabled;
    el.submit.classList.toggle('opacity-50', !enabled);
    el.submit.classList.toggle('cursor-not-allowed', !enabled);
  }

  // --- camera -------------------------------------------------------------

  function onResults(results) {
    if (el.canvas.width !== el.video.videoWidth) {
      el.canvas.width = el.video.videoWidth;
      el.canvas.height = el.video.videoHeight;
    }
    el.canvas.getContext('2d').clearRect(0, 0, el.canvas.width, el.canvas.height);

    var detections = results.detections || [];
    if (detections.length === 0) {
      setStatus('Wajah Tidak Terdeteksi', 'bad');
      setSubmitEnabled(false);
      return;
    }
    if (detections.length > 1) {
      setStatus('Lebih dari Satu Wajah', 'warn');
      setSubmitEnabled(false);
      return;
    }
    var nose = detections[0].landmarks[2];
    if (nose.x > 0.35 && nose.x < 0.65 && nose.y > 0.25 && nose.y < 0.75) {
      setStatus('Posisi Tepat — Siap Foto', 'ok');
      setSubmitEnabled(true);
    } else {
      setStatus('Geser ke Tengah Oval', 'warn');
      setSubmitEnabled(false);
    }
  }

  function cameraErrorMessage(err) {
    var name = err && err.name;
    if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
      return 'Izin kamera ditolak. Izinkan akses kamera di pengaturan browser, lalu muat ulang halaman.';
    }
    if (name === 'NotReadableError' || name === 'TrackStartError') {
      return 'Kamera sedang dipakai aplikasi lain. Tutup aplikasi tersebut lalu muat ulang halaman.';
    }
    return 'Kamera tidak dapat dimulai di perangkat ini.';
  }

  function startCamera() {
    // Without this catch the status froze at "Menunggu kamera..." and the
    // submit button stayed disabled forever, with nothing on screen explaining
    // why. The photobooth already handled this correctly; the pattern just was
    // not applied here.
    Promise.resolve(camera.start()).catch(function (err) {
      setStatus('Kamera Bermasalah', 'bad');
      setSubmitEnabled(false);
      showResult('error', 'Kamera Tidak Bisa Diakses', cameraErrorMessage(err));
    });
  }

  function releaseCamera() {
    try {
      if (camera) camera.stop();
    } catch (err) {
      /* page is unloading */
    }
    var stream = el.video.srcObject;
    if (stream && stream.getTracks) stream.getTracks().forEach(function (t) { t.stop(); });
    el.video.srcObject = null;
  }

  // --- capture ------------------------------------------------------------

  function captureFrame() {
    return new Promise(function (resolve) {
      var canvas = document.createElement('canvas');
      var scale = Math.min(1, 640 / (el.video.videoWidth || 640));
      canvas.width = Math.round(el.video.videoWidth * scale);
      canvas.height = Math.round(el.video.videoHeight * scale);
      canvas.getContext('2d').drawImage(el.video, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(resolve, 'image/jpeg', 0.85);
    });
  }

  function wait(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
  }

  // --- geolocation --------------------------------------------------------

  // Registration writes an attendance row, so the server applies the same
  // location rule as a check-in. Sending coordinates here keeps the two paths
  // consistent instead of leaving registration as a geofence bypass.
  var position = { lat: null, lng: null, accuracy: null };

  function captureLocation() {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      function (pos) {
        position.lat = pos.coords.latitude;
        position.lng = pos.coords.longitude;
        position.accuracy = pos.coords.accuracy;
      },
      function () { /* the server will explain if it is required */ },
      { enableHighAccuracy: true, timeout: 6000, maximumAge: 0 }
    );
  }

  // --- submit -------------------------------------------------------------

  async function handleSubmit(event) {
    event.preventDefault();
    if (!faceValid) return;

    var isUpdate = el.toggleUpdate.checked;
    if (!isUpdate && el.consent && !el.consent.checked) {
      showResult(
        'error',
        'Persetujuan Diperlukan',
        'Centang persetujuan penyimpanan data wajah sebelum mendaftar.'
      );
      el.consent.focus();
      return;
    }

    var originalLabel = el.submit.innerHTML;
    el.submit.disabled = true;
    el.result.classList.add('hidden');

    var formData = new FormData();
    formData.append('full_name', el.fullName.value.trim());

    if (!isUpdate) {
      var gender = document.querySelector('input[name="gender"]:checked');
      formData.append('gender', gender ? gender.value : '');
      formData.append('phone_number', el.phone.value.trim());
      formData.append('consent', 'true');
      if (position.lat !== null) {
        formData.append('lat', position.lat);
        formData.append('lng', position.lng);
        if (position.accuracy !== null) formData.append('accuracy', position.accuracy);
      }
    }

    try {
      for (var i = 1; i <= BURST_FRAMES; i += 1) {
        el.submit.innerHTML = '<span>Mengambil foto ' + i + '/' + BURST_FRAMES + '…</span>';
        formData.append('files', await captureFrame(), 'frame' + i + '.jpg');
        if (i < BURST_FRAMES) await wait(BURST_GAP_MS);
      }

      el.submit.innerHTML = '<span>Menyimpan data…</span>';
      var data = await KP.apiFetch(isUpdate ? '/api/update-face' : '/api/register', {
        method: 'POST',
        body: formData,
      });

      if (isUpdate) {
        showResult('success', 'Data Wajah Diperbarui', data.message || '');
        el.submit.innerHTML = originalLabel;
        el.submit.disabled = false;
        return;
      }

      // Say plainly that attendance was recorded, then return to the kiosk.
      // Previously the message mentioned only "kualitas wajah super" and the
      // page just reset, so a newcomer had no idea they were already marked
      // present and often went back to scan again.
      showResult('success', 'Pendaftaran Berhasil', data.message || '');
      el.form.reset();
      el.submit.innerHTML = '<span>Kembali ke layar absensi…</span>';
      setTimeout(function () {
        window.location.href = '/';
      }, REDIRECT_MS);
    } catch (err) {
      showResult('error', 'Pendaftaran Gagal', err.message);
      el.submit.innerHTML = originalLabel;
      el.submit.disabled = false;
    }
  }

  // --- update-mode toggle -------------------------------------------------

  function applyUpdateMode(isUpdate) {
    el.genderWrapper.classList.toggle('hidden', isUpdate);
    el.phoneWrapper.classList.toggle('hidden', isUpdate);
    if (el.consentWrapper) el.consentWrapper.classList.toggle('hidden', isUpdate);

    document.querySelectorAll('input[name="gender"]').forEach(function (input) {
      input.required = !isUpdate;
    });
    el.phone.required = !isUpdate;
    if (el.consent) el.consent.required = !isUpdate;

    el.formTitle.innerText = isUpdate ? 'Perbarui Data Wajah' : 'Registrasi Jemaat Baru';
    el.submit.innerHTML = isUpdate
      ? 'Perbarui Data Wajah'
      : 'Ambil 3 Foto &amp; Daftar';
  }

  // --- boot ---------------------------------------------------------------

  function boot() {
    if (!KP.librariesPresent(['FaceDetection', 'Camera'])) {
      setStatus('Modul Kamera Gagal Dimuat', 'bad');
      setSubmitEnabled(false);
      showResult(
        'error',
        'Pendaftaran Wajah Tidak Tersedia',
        'Komponen pengenalan wajah gagal dimuat, kemungkinan karena koneksi internet. Hubungi pengurus.'
      );
      return;
    }

    var faceDetection = new FaceDetection({
      locateFile: function (file) {
        return (
          (window.KP_VENDOR_BASE ||
            'https://cdn.jsdelivr.net/npm/@mediapipe/face_detection@0.4.1646425229/') + file
        );
      },
    });
    faceDetection.setOptions({ model: 'short', minDetectionConfidence: 0.6 });
    faceDetection.onResults(onResults);

    camera = new Camera(el.video, {
      onFrame: async function () {
        await faceDetection.send({ image: el.video });
      },
    });

    captureLocation();
    startCamera();
  }

  el.form.addEventListener('submit', handleSubmit);
  el.toggleUpdate.addEventListener('change', function (event) {
    applyUpdateMode(event.target.checked);
  });
  window.addEventListener('pagehide', releaseCamera);
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) releaseCamera();
    else if (camera) startCamera();
  });

  window.addEventListener('load', boot);
})();
