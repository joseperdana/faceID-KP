/**
 * Admin sign-in.
 *
 * Every failure used to read "Password Salah!", including rate limiting and
 * server errors — so a pengurus with the correct password, locked out after
 * five attempts, kept retrying and kept extending the lockout. A network
 * failure produced an unhandled rejection and nothing at all on screen.
 */
(function () {
  'use strict';

  var form = document.getElementById('login-form');
  var input = document.getElementById('password');
  var button = document.getElementById('btn-login');
  var error = document.getElementById('error');

  function showError(message) {
    error.innerText = message;
    error.classList.remove('hidden');
  }

  async function handleLogin(event) {
    event.preventDefault();
    error.classList.add('hidden');

    var originalLabel = button.innerHTML;
    // Guards against double submission, which otherwise burned two of the five
    // attempts the rate limiter allows per minute.
    button.disabled = true;
    button.innerHTML = '<span>Memeriksa…</span>';

    try {
      var response = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: input.value }),
      });

      if (response.ok) {
        window.location.href = '/dashboard';
        return;
      }

      if (response.status === 401) {
        showError('Password salah.');
      } else if (response.status === 429) {
        showError('Terlalu banyak percobaan. Tunggu satu menit sebelum mencoba lagi.');
      } else {
        showError('Server sedang bermasalah (kode ' + response.status + ').');
      }
    } catch (err) {
      showError('Tidak dapat terhubung ke server. Periksa koneksi jaringan.');
    } finally {
      button.disabled = false;
      button.innerHTML = originalLabel;
      input.select();
    }
  }

  form.addEventListener('submit', handleLogin);
})();
