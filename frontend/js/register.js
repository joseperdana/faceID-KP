const videoElement = document.getElementById('video');
const btnSubmit = document.getElementById('btn-submit');
const statusText = document.getElementById('status-text');
const form = document.getElementById('reg-form');
const resultMsg = document.getElementById('result-message');

let isFaceValid = false;

// --- Handoff ke Lark Form -----------------------------------------------
// Nama pertanyaan harus sama persis dengan label di form Lark; garis miring dan
// spasi wajib dikodekan. hide_ menyembunyikan pertanyaan nomor HP: nomor itu
// kunci gabung portal <-> Lark, jadi jangan sampai diubah setelah diverifikasi
// di counter.
const LARK_FORM_URL = 'https://x4qrxnkmlhv.sg.larksuite.com/share/base/form/shrlg0i0RM9kNlqV8wI3A2ulYph';
const LARK_Q_NAME = 'Nama Lengkap';
const LARK_Q_PHONE = 'No. Telp/Whatsapp';

function buildLarkUrl(fullName, phoneLark) {
    const p = [`prefill_${encodeURIComponent(LARK_Q_NAME)}=${encodeURIComponent(fullName)}`];
    if (phoneLark) {
        p.push(`prefill_${encodeURIComponent(LARK_Q_PHONE)}=${encodeURIComponent(phoneLark)}`);
        p.push(`hide_${encodeURIComponent(LARK_Q_PHONE)}=1`);
    }
    return `${LARK_FORM_URL}?${p.join('&')}`;
}

// Form Lark diisi di perangkat kiosk ini juga, bukan di HP jemaat. Jadi tidak
// ada QR — layarnya langsung pindah ke form yang sudah terisi separuh.
const REDIRECT_SECONDS = 3;
let redirectTimer = null;

function showLarkHandoff(fullName, phoneLark) {
    const url = buildLarkUrl(fullName, phoneLark);
    document.getElementById('handoff-name').innerText = fullName;
    document.getElementById('handoff-link').href = url;
    document.getElementById('lark-handoff').classList.remove('hidden');

    let left = REDIRECT_SECONDS;
    const counter = document.getElementById('handoff-count');
    counter.innerText = left;
    redirectTimer = setInterval(() => {
        left -= 1;
        counter.innerText = left;
        if (left <= 0) {
            clearInterval(redirectTimer);
            window.location.href = url;
        }
    }, 1000);
}

// Jalan keluar kalau orangnya tidak sempat mengisi sekarang — perpindahan
// halaman mematikan kamera, jadi harus selalu bisa dibatalkan.
document.getElementById('handoff-skip').addEventListener('click', () => {
    clearInterval(redirectTimer);
    document.getElementById('lark-handoff').classList.add('hidden');
    document.getElementById('result-message').classList.add('hidden');
    document.getElementById('full_name').focus();
});

// 1. Setup Kamera & MediaPipe
const faceDetection = new FaceDetection({locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_detection/${file}`});
faceDetection.setOptions({ model: 'short', minDetectionConfidence: 0.6 });

faceDetection.onResults((results) => {
    const canvas = document.getElementById('output_canvas');
    canvas.width = videoElement.videoWidth;
    canvas.height = videoElement.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    if (results.detections.length > 0) {
        const nose = results.detections[0].landmarks[2];
        const inSafeZone = (nose.x > 0.35 && nose.x < 0.65 && nose.y > 0.25 && nose.y < 0.75);
        
        if (inSafeZone) {
            isFaceValid = true;
            statusText.innerText = "Posisi Tepat (Siap Foto)";
            statusText.className = "font-bold text-emerald-400";
            btnSubmit.disabled = false;
            btnSubmit.classList.remove('opacity-50', 'cursor-not-allowed');
        } else {
            isFaceValid = false;
            statusText.innerText = "Geser ke Tengah Oval";
            statusText.className = "font-bold text-amber-400";
            btnSubmit.disabled = true;
        }
    } else {
        isFaceValid = false;
        statusText.innerText = "Wajah Tidak Terdeteksi";
        statusText.className = "font-bold text-rose-400";
        btnSubmit.disabled = true;
    }
});

const camera = new Camera(videoElement, {
    onFrame: async () => { await faceDetection.send({image: videoElement}); }
});
camera.start();

// 2. Handle Submit Form (Burst Mode Capture)
form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if(!isFaceValid) return;

    const originalText = btnSubmit.innerHTML;
    btnSubmit.disabled = true;
    resultMsg.classList.add('hidden');

    const isUpdate = document.getElementById('toggle-update').checked;

    const formData = new FormData();
    formData.append('full_name', document.getElementById('full_name').value);
    
    if (!isUpdate) {
        const selectedGender = document.querySelector('input[name="gender"]:checked').value;
        formData.append('gender', selectedGender);
        formData.append('phone_number', document.getElementById('phone_number').value);
    }

    const captureFrame = () => {
        return new Promise((resolve) => {
            const captureCanvas = document.createElement('canvas');
            captureCanvas.width = videoElement.videoWidth;
            captureCanvas.height = videoElement.videoHeight;
            captureCanvas.getContext('2d').drawImage(videoElement, 0, 0);
            captureCanvas.toBlob(resolve, 'image/jpeg', 0.95);
        });
    };

    try {
        btnSubmit.innerHTML = `<span>Mengambil foto 1/3...</span>`;
        const blob1 = await captureFrame();
        formData.append('files', blob1, 'frame1.jpg');
        
        await new Promise(r => setTimeout(r, 300));
        
        btnSubmit.innerHTML = `<span>Mengambil foto 2/3...</span>`;
        const blob2 = await captureFrame();
        formData.append('files', blob2, 'frame2.jpg');

        await new Promise(r => setTimeout(r, 300));
        
        btnSubmit.innerHTML = `<span>Mengambil foto 3/3...</span>`;
        const blob3 = await captureFrame();
        formData.append('files', blob3, 'frame3.jpg');

        btnSubmit.innerHTML = `<span>Memproses & Menyimpan Data...</span>`;

        const endpoint = isUpdate ? '/api/update-face' : '/api/register';
        const res = await fetch(endpoint, { method: 'POST', body: formData });
        const data = await res.json();

        resultMsg.classList.remove('hidden');
        if(data.status === 'success') {
            resultMsg.className = "mt-4 p-4 rounded-2xl text-center text-xs font-mono bg-emerald-500/10 text-emerald-300 border border-emerald-500/20";
            resultMsg.innerHTML = `<b>Pendaftaran Berhasil!</b><br>${data.message}`;
            const submitted = document.getElementById('full_name').value;
            form.reset();
            // Jangan sembunyikan otomatis: orangnya perlu waktu memindai QR, dan
            // petugas yang menentukan kapan lanjut ke pendaftar berikutnya.
            // Sistem yang memutuskan perlu-tidaknya QR, bukan petugas: kalau
            // nomornya sudah ada di Lark, menyuruh isi lagi = duplikat baru.
            if (!isUpdate && data.data && data.data.needs_lark) {
                showLarkHandoff(data.data.full_name || submitted, data.data.phone_lark);
            } else {
                if (data.data && data.data.needs_lark === false) {
                    resultMsg.innerHTML += `<br><span class="text-slate-400">Data diri sudah lengkap di Lark — tidak perlu isi form lagi.</span>`;
                }
                setTimeout(() => resultMsg.classList.add('hidden'), 5000);
            }
        } else {
            throw new Error(data.detail || data.message || "Gagal registrasi");
        }
    } catch (err) {
        resultMsg.classList.remove('hidden');
        resultMsg.className = "mt-4 p-4 rounded-2xl text-center text-xs font-mono bg-rose-500/10 text-rose-300 border border-rose-500/20";
        resultMsg.innerText = `Gagal: ${err.message}`;
    } finally {
        btnSubmit.innerHTML = originalText;
        btnSubmit.disabled = false;
    }
});

// 3. UI Toggle Handler
document.getElementById('toggle-update').addEventListener('change', (e) => {
    const isUpdate = e.target.checked;
    const genderWrapper = document.getElementById('gender-wrapper');
    const phoneWrapper = document.getElementById('phone-wrapper');
    const formTitle = document.getElementById('form-title');
    const btnSubmit = document.getElementById('btn-submit');

    if (isUpdate) {
        genderWrapper.classList.add('hidden');
        phoneWrapper.classList.add('hidden');
        document.querySelector('input[name="gender"]').required = false;
        document.getElementById('phone_number').required = false;
        formTitle.innerText = "Update Wajah Jemaat";
        btnSubmit.innerHTML = `
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Update Data Wajah
        `;
    } else {
        genderWrapper.classList.remove('hidden');
        phoneWrapper.classList.remove('hidden');
        document.querySelector('input[name="gender"]').required = true;
        document.getElementById('phone_number').required = true;
        formTitle.innerText = "Registrasi Anggota";
        btnSubmit.innerHTML = `
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                <path stroke-linecap="round" stroke-linejoin="round" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            Ambil 3 Foto & Simpan Data
        `;
    }
});
