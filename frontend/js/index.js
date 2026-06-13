// --- Konstanta AI & DOM ---
const REQUIRED_STABLE_FRAMES = 45; 
const MOVEMENT_THRESHOLD = 0.03; 
const AUTO_RESET_DELAY = 3500; 
const SAFE_ZONE_X_MIN = 0.30; const SAFE_ZONE_X_MAX = 0.70;
const SAFE_ZONE_Y_MIN = 0.20; const SAFE_ZONE_Y_MAX = 0.80;

const videoElement = document.getElementById('video');
const canvasElement = document.getElementById('output_canvas');
const canvasCtx = canvasElement.getContext('2d');
const loadingOverlay = document.getElementById('loading');

const statusIcon = document.getElementById('status-icon');
const statusTitle = document.getElementById('status-title');
const statusDesc = document.getElementById('status-desc');
const progressBar = document.getElementById('scan-progress');
const resultArea = document.getElementById('result-area');

let isProcessing = false;
let stableFramesCount = 0;
let lastNoseX = null; let lastNoseY = null;

let currentUserLat = null;
let currentUserLng = null;

function requestLocation() {
    updateStatus('idle', '📍 Mengecek Lokasi...', 'Mohon izinkan akses GPS di browser Anda.');
    
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                currentUserLat = position.coords.latitude;
                currentUserLng = position.coords.longitude;
                updateStatus('idle', 'Siap Absen', 'Silakan berdiri tegap di dalam pola oval.');
                camera.start(); 
            },
            (error) => {
                console.error(error);
                Swal.fire({
                    icon: 'warning',
                    title: 'GPS Wajib Aktif',
                    text: 'Mohon izinkan akses Lokasi (GPS) di browser Anda untuk melakukan absensi.',
                    confirmButtonColor: '#f59e0b'
                });
                updateStatus('warning', 'GPS Tidak Aktif', 'Izinkan akses lokasi lalu muat ulang (refresh) halaman.');
            },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
        );
    } else {
        alert("Browser Anda tidak mendukung fitur GPS.");
    }
}

// --- Inisialisasi MediaPipe AI ---
const faceDetection = new FaceDetection({locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_detection/${file}`});
faceDetection.setOptions({ model: 'short', minDetectionConfidence: 0.6 });
faceDetection.onResults(onResults);

const camera = new Camera(videoElement, {
    onFrame: async () => { if (!isProcessing) await faceDetection.send({image: videoElement}); }
});

// 🚀 PEMICU UTAMA
window.addEventListener('load', requestLocation);

// --- Fungsi Logika Inti ---
function onResults(results) {
    canvasElement.width = videoElement.videoWidth;
    canvasElement.height = videoElement.videoHeight;
    canvasCtx.clearRect(0, 0, canvasElement.width, canvasElement.height);
    
    if (results.detections.length > 0) {
        const detection = results.detections[0];
        const noseTip = detection.landmarks[2]; 
        const inSafeZone = (noseTip.x > SAFE_ZONE_X_MIN && noseTip.x < SAFE_ZONE_X_MAX && noseTip.y > SAFE_ZONE_Y_MIN && noseTip.y < SAFE_ZONE_Y_MAX);

        if (inSafeZone) { checkStability(noseTip.x, noseTip.y); } 
        else { 
            updateStatus('warning', 'Wajah Terlalu Pinggir', 'Geser wajah ke tengah oval.');
            stableFramesCount = 0; progressBar.style.width = '0%';
        }
    } else {
        updateStatus('idle', 'Mencari Wajah...', 'Pastikan wajah terlihat jelas.');
        stableFramesCount = 0; progressBar.style.width = '0%';
    }
}

function checkStability(currentX, currentY) {
    if (isProcessing) return;
    if (lastNoseX !== null && lastNoseY !== null) {
        const movement = Math.sqrt(Math.pow(currentX - lastNoseX, 2) + Math.pow(currentY - lastNoseY, 2));
        if (movement < MOVEMENT_THRESHOLD) {
            stableFramesCount++;
            updateStatus('scanning', 'Tahan Posisi...', 'Jangan bergerak...');
        } else {
            stableFramesCount = 0;
            updateStatus('warning', 'Terlalu Banyak Gerak', 'Diam sejenak...');
        }
    }
    lastNoseX = currentX; lastNoseY = currentY;
    progressBar.style.width = `${(stableFramesCount / REQUIRED_STABLE_FRAMES) * 100}%`;
    if (stableFramesCount >= REQUIRED_STABLE_FRAMES) { triggerAutoCapture(); }
}

function updateStatus(state, title, desc) {
    statusTitle.innerText = title; statusDesc.innerText = desc;
    statusTitle.className = "text-3xl font-extrabold mb-2 leading-tight transition-colors";
    statusIcon.className = "text-6xl mb-4 transition-all duration-300";

    if (state === 'idle') {
        statusTitle.classList.add('text-white');
        statusIcon.innerText = "👤";
        statusIcon.classList.add('text-slate-500');
    } else if (state === 'warning') {
        statusTitle.classList.add('text-orange-400');
        statusIcon.innerText = "⚠️";
        statusIcon.classList.add('text-orange-500', 'animate-bounce');
    } else if (state === 'scanning') {
        statusTitle.classList.add('text-yellow-400');
        statusIcon.innerText = "📸";
        statusIcon.classList.add('text-yellow-400', 'scale-110');
    }
}

async function triggerAutoCapture() {
    isProcessing = true;
    loadingOverlay.classList.remove('hidden');
    
    const captureCanvas = document.createElement('canvas');
    captureCanvas.width = videoElement.videoWidth;
    captureCanvas.height = videoElement.videoHeight;
    captureCanvas.getContext('2d').drawImage(videoElement, 0, 0);

    captureCanvas.toBlob(async (blob) => {
        const formData = new FormData();
        formData.append('file', blob, 'capture.jpg');
        if (currentUserLat !== null) {
            formData.append('lat', currentUserLat);
            formData.append('lng', currentUserLng);
        }

        try {
            const response = await fetch('/api/recognize', { method: 'POST', body: formData });
            const data = await response.json();

            loadingOverlay.classList.add('hidden');
            resultArea.classList.remove('hidden');
            
            let resultHTML = '';
            let isError = false;

            if (data.status === 'success') {
                resultHTML = `
                    <div class="text-6xl mb-4">🎉</div>
                    <h3 class="text-2xl font-bold text-white mb-2">Halo, ${data.data.name}!</h3>
                    <div class="inline-block bg-emerald-600 text-white text-xs px-3 py-1 rounded-full mb-4">Absensi Berhasil</div>
                    <p class="text-emerald-200 text-sm mb-6">${data.message}</p>
                    <div class="w-full bg-slate-700 h-1 mt-4 rounded-full overflow-hidden"><div class="bg-slate-400 h-full countdown-bar"></div></div>
                    <p class="text-xs text-slate-500 mt-2">Reset otomatis...</p>
                `;
            } else if (response.status === 403) {
                isError = true;
                resultHTML = `
                    <div class="text-6xl mb-4">📍</div>
                    <h3 class="text-xl font-bold text-orange-400 mb-2">Akses Ditolak</h3>
                    <p class="text-red-200 text-sm mb-6">${data.message || 'Anda berada di luar area GKI Bromo.'}</p>
                    <button onclick="resetScan()" class="text-slate-400 text-sm hover:text-white underline mt-2">Coba Scan Lagi</button>
                `;
            } else {
                isError = true;
                resultHTML = `
                    <div class="text-6xl mb-4">🤔</div>
                    <h3 class="text-xl font-bold text-white mb-2">Belum Terdaftar?</h3>
                    <p class="text-red-200 text-sm mb-6">Wajah tidak dikenali di database.</p>
                    <a href="/register" class="inline-flex items-center gap-2 bg-sky-600 hover:bg-sky-500 text-white font-bold py-3 px-6 rounded-xl transition-transform active:scale-95 shadow-lg shadow-sky-900/50 mb-4">
                        📝 Daftar Anggota Baru
                    </a>
                    <br>
                    <button onclick="resetScan()" class="text-slate-400 text-sm hover:text-white underline mt-2">Coba Scan Lagi</button>
                `;
            }

            resultArea.innerHTML = resultHTML;

            if (!isError) {
                setTimeout(() => { resetScan(); }, AUTO_RESET_DELAY);
            }
        } catch (err) {
            loadingOverlay.classList.add('hidden');
            alert("Koneksi Error");
            resetScan();
        }
    }, 'image/jpeg', 0.95);
}

window.resetScan = function() {
    isProcessing = false;
    resultArea.classList.add('hidden');
    resultArea.innerHTML = '';
    stableFramesCount = 0;
    updateStatus('idle', 'Siap Absen', 'Silakan berdiri tegap...');
    progressBar.style.width = '0%';
}
