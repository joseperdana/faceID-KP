// Pesan per kode status. Dulu semua non-200 tampil "Password Salah!", termasuk
// blokir 5 percobaan per menit: pengurus terus mencoba dan blokirnya justru
// diperpanjang.
function loginErrorMessage(status) {
    if (status === 401) return "Password salah.";
    if (status === 429) return "Terlalu sering mencoba. Tunggu 1 menit, lalu coba lagi.";
    if (status >= 500) return "Server sedang bermasalah. Coba lagi beberapa saat lagi.";
    return "Login gagal (kode " + status + "). Coba lagi.";
}

function showLoginError(text) {
    const el = document.getElementById('error');
    el.innerText = text;
    el.classList.remove('hidden');
}

async function handleLogin(e) {
    e.preventDefault();
    const password = document.getElementById('password').value;

    let res;
    try {
        res = await fetch('/api/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ password: password })
        });
    } catch (err) {
        showLoginError("Tidak tersambung ke server. Periksa koneksi internet, lalu coba lagi.");
        return;
    }

    if (res.ok) {
        window.location.href = "/dashboard";
    } else {
        showLoginError(loginErrorMessage(res.status));
    }
}
