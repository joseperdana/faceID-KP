const videoElement = document.getElementById('video');
const btnSubmit = document.getElementById('btn-submit');
const statusText = document.getElementById('status-text');
const form = document.getElementById('reg-form');
const resultMsg = document.getElementById('result-message');

let isFaceValid = false;

// 1. Setup Kamera & MediaPipe (Logic Sederhana)
const faceDetection = new FaceDetection({locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_detection/${file}`});
faceDetection.setOptions({ model: 'short', minDetectionConfidence: 0.6 });

faceDetection.onResults((results) => {
    // Gambar video ke canvas (biar admin liat)
    const canvas = document.getElementById('output_canvas');
    canvas.width = videoElement.videoWidth;
    canvas.height = videoElement.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    if (results.detections.length > 0) {
        // Cek apakah wajah di tengah (Logic Zona Aman)
        const nose = results.detections[0].landmarks[2];
        const inSafeZone = (nose.x > 0.35 && nose.x < 0.65 && nose.y > 0.25 && nose.y < 0.75);
        
        if (inSafeZone) {
            isFaceValid = true;
            statusText.innerText = "✅ Oke (Siap Foto)";
            statusText.className = "font-bold text-emerald-400";
            btnSubmit.disabled = false;
            btnSubmit.classList.remove('opacity-50', 'cursor-not-allowed');
        } else {
            isFaceValid = false;
            statusText.innerText = "⚠️ Geser ke Tengah";
            statusText.className = "font-bold text-orange-400";
            btnSubmit.disabled = true;
        }
    } else {
        isFaceValid = false;
        statusText.innerText = "❌ Wajah Tidak Terbaca";
        statusText.className = "font-bold text-red-400";
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

    const originalText = btnSubmit.innerText;
    btnSubmit.disabled = true;
    resultMsg.classList.add('hidden');

    const formData = new FormData();
    formData.append('full_name', document.getElementById('full_name').value);
    const selectedGender = document.querySelector('input[name="gender"]:checked').value;
    formData.append('gender', selectedGender);
    formData.append('phone_number', document.getElementById('phone_number').value);

    // Fungsi pembantu untuk mengambil 1 frame menjadi Blob
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
        // AMBIL 3 FOTO BERTURUT-TURUT DENGAN JEDA 300ms
        btnSubmit.innerText = "📸 Mengambil foto 1/3...";
        const blob1 = await captureFrame();
        formData.append('files', blob1, 'frame1.jpg');
        
        await new Promise(r => setTimeout(r, 300)); // Jeda 300ms
        
        btnSubmit.innerText = "📸 Mengambil foto 2/3...";
        const blob2 = await captureFrame();
        formData.append('files', blob2, 'frame2.jpg');

        await new Promise(r => setTimeout(r, 300)); // Jeda 300ms
        
        btnSubmit.innerText = "📸 Mengambil foto 3/3...";
        const blob3 = await captureFrame();
        formData.append('files', blob3, 'frame3.jpg');

        btnSubmit.innerText = "⏳ Memproses & Menyimpan...";

        // Kirim ke server
        const res = await fetch('/api/register', { method: 'POST', body: formData });
        const data = await res.json();

        resultMsg.classList.remove('hidden');
        if(data.status === 'success') {
            resultMsg.className = "mt-4 p-4 rounded-xl text-center text-sm bg-emerald-900/50 text-emerald-200 border border-emerald-500/50";
            resultMsg.innerHTML = `✅ <b>Berhasil!</b><br>${data.message}`;
            form.reset(); 
            setTimeout(() => resultMsg.classList.add('hidden'), 4000);
        } else {
            throw new Error(data.detail || data.message || "Gagal registrasi");
        }
    } catch (err) {
        resultMsg.classList.remove('hidden');
        resultMsg.className = "mt-4 p-4 rounded-xl text-center text-sm bg-red-900/50 text-red-200 border border-red-500/50";
        resultMsg.innerText = `❌ Error: ${err.message}`;
    } finally {
        btnSubmit.innerText = originalText;
        btnSubmit.disabled = false;
    }
});
