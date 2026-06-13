async function handleLogin(e) {
    e.preventDefault();
    const password = document.getElementById('password').value;
    
    const res = await fetch('/api/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ password: password })
    });

    if (res.ok) {
        window.location.href = "/";
    } else {
        document.getElementById('error').innerText = "Password Salah!";
        document.getElementById('error').classList.remove('hidden');
    }
}
