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

// Manual Search DOM
const manualSearchModal = document.getElementById('manual-search-modal');
const manualSearchInput = document.getElementById('manual-search-input');
const manualSearchResults = document.getElementById('manual-search-results');
const btnOpenManualSearch = document.getElementById('btn-open-manual-search');
const btnSidebarManualSearch = document.getElementById('btn-sidebar-manual-search');
const btnCloseManualSearch = document.getElementById('btn-close-manual-search');

let isProcessing = false;
let stableFramesCount = 0;
let lastNoseX = null; let lastNoseY = null;
let searchDebounceTimer = null;

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

function showSuccessModal(data, message) {
    resultArea.classList.add('hidden');
    
    document.getElementById('success-name').innerText = data.name;
    document.getElementById('success-message').innerText = message;
    document.getElementById('success-streak').innerHTML = `${data.total_attendance || 1}<span class="text-sm font-normal text-sky-600 ml-1">x</span>`;
    document.getElementById('success-last-seen').innerText = data.last_seen || "Hari Ini";

    const badgeEl = document.getElementById('success-badge-method');
    if (badgeEl) {
        if (data.method === 'manual') {
            badgeEl.innerText = "📝 Absen Manual";
            badgeEl.className = "inline-block mb-5 text-[11px] font-bold px-3 py-1 rounded-full bg-amber-900/40 text-amber-300 border border-amber-600/40";
        } else {
            badgeEl.innerText = "📸 Scan Wajah";
            badgeEl.className = "inline-block mb-5 text-[11px] font-bold px-3 py-1 rounded-full bg-sky-900/40 text-sky-300 border border-sky-600/40";
        }
    }
    
    const successModal = document.getElementById('success-modal');
    const successContent = document.getElementById('success-modal-content');
    successModal.classList.remove('hidden');
    
    setTimeout(() => {
        successContent.classList.remove('scale-95', 'opacity-0');
        successContent.classList.add('scale-100', 'opacity-100');
    }, 10);

    setTimeout(() => { 
        successContent.classList.remove('scale-100', 'opacity-100');
        successContent.classList.add('scale-95', 'opacity-0');
        
        setTimeout(() => {
            successModal.classList.add('hidden');
            resetScan(); 
        }, 300);
    }, AUTO_RESET_DELAY);
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
            
            if (data.status === 'success') {
                showSuccessModal(data.data, data.message);
            } else if (response.status === 403) {
                resultArea.innerHTML = `
                    <div class="text-6xl mb-4">📍</div>
                    <h3 class="text-xl font-bold text-orange-400 mb-2">Akses Ditolak</h3>
                    <p class="text-red-200 text-sm mb-6">${data.message || 'Anda berada di luar area GKI Bromo.'}</p>
                    <button onclick="resetScan()" class="text-slate-400 text-sm hover:text-white underline mt-2">Coba Scan Lagi</button>
                `;
            } else {
                resultArea.innerHTML = `
                    <div class="text-6xl mb-4">🤔</div>
                    <h3 class="text-xl font-bold text-white mb-2">Belum Terdaftar?</h3>
                    <p class="text-red-200 text-sm mb-4">Wajah tidak dikenali di database.</p>
                    <div class="flex flex-col gap-2 w-full max-w-xs">
                        <button onclick="openManualSearchModal()" class="py-2.5 px-4 bg-slate-700 hover:bg-slate-600 text-white rounded-xl text-sm font-semibold transition-all">
                            🔍 Cari Nama Manual
                        </button>
                        <a href="/register" class="py-2.5 px-4 bg-sky-600 hover:bg-sky-500 text-white rounded-xl text-sm font-bold shadow transition-all">
                            📝 Daftar Anggota Baru
                        </a>
                    </div>
                    <button onclick="resetScan()" class="text-slate-400 text-xs hover:text-white underline mt-4">Coba Scan Lagi</button>
                `;
            }
        } catch (err) {
            loadingOverlay.classList.add('hidden');
            alert("Koneksi Error");
            resetScan();
        }
    }, 'image/jpeg', 0.95);
}

// --- Fast Manual Search Fallback Flow ---
function openManualSearchModal() {
    if (manualSearchModal) {
        manualSearchModal.classList.remove('hidden');
        if (manualSearchInput) {
            manualSearchInput.value = '';
            manualSearchInput.focus();
        }
        if (manualSearchResults) {
            manualSearchResults.innerHTML = `<div class="text-center py-10 text-slate-500 text-xs">Ketik minimal 1 huruf untuk mencari nama jemaat.</div>`;
        }
    }
}

function closeManualSearchModal() {
    if (manualSearchModal) {
        manualSearchModal.classList.add('hidden');
    }
}

if (btnOpenManualSearch) btnOpenManualSearch.addEventListener('click', openManualSearchModal);
if (btnSidebarManualSearch) btnSidebarManualSearch.addEventListener('click', openManualSearchModal);
if (btnCloseManualSearch) btnCloseManualSearch.addEventListener('click', closeManualSearchModal);

if (manualSearchInput) {
    manualSearchInput.addEventListener('input', (e) => {
        clearTimeout(searchDebounceTimer);
        const query = e.target.value.trim();

        if (query.length === 0) {
            manualSearchResults.innerHTML = `<div class="text-center py-10 text-slate-500 text-xs">Ketik minimal 1 huruf untuk mencari nama jemaat.</div>`;
            return;
        }

        searchDebounceTimer = setTimeout(async () => {
            try {
                manualSearchResults.innerHTML = `<div class="text-center py-8 text-sky-400 text-xs animate-pulse">Mencari jemaat...</div>`;
                const res = await fetch(`/api/users/search?q=${encodeURIComponent(query)}`);
                const result = await res.json();

                if (result.status === 'success' && result.data && result.data.length > 0) {
                    manualSearchResults.innerHTML = result.data.map(user => `
                        <div class="p-3 bg-slate-800/80 hover:bg-slate-700/80 rounded-2xl border border-slate-700/60 flex items-center justify-between transition-all">
                            <div>
                                <h4 class="font-bold text-sm text-white">${escapeHtml(user.full_name)}</h4>
                                <p class="text-[11px] text-slate-400">${escapeHtml(user.gender || '-')} • ${escapeHtml(user.phone_number || '')}</p>
                            </div>
                            <button onclick="executeManualCheckin(${user.id})" class="py-1.5 px-3.5 bg-sky-600 hover:bg-sky-500 active:scale-95 text-white font-bold text-xs rounded-xl transition-all shadow shadow-sky-900/40">
                                Absen
                            </button>
                        </div>
                    `).join('');
                } else {
                    manualSearchResults.innerHTML = `
                        <div class="text-center py-10">
                            <p class="text-slate-400 text-xs mb-3">Tidak ada nama "${escapeHtml(query)}" ditemukan.</p>
                            <a href="/register" class="inline-block py-2 px-4 bg-sky-600/30 hover:bg-sky-600/50 text-sky-300 text-xs font-semibold rounded-xl border border-sky-500/40 transition-all">
                                📝 Daftar Anggota Baru
                            </a>
                        </div>
                    `;
                }
            } catch (err) {
                manualSearchResults.innerHTML = `<div class="text-center py-8 text-red-400 text-xs">Gagal mencari data. Cek koneksi.</div>`;
            }
        }, 250);
    });
}

window.executeManualCheckin = async function(userId) {
    closeManualSearchModal();
    loadingOverlay.classList.remove('hidden');

    try {
        const formData = new FormData();
        formData.append('user_id', userId);

        const response = await fetch('/api/attendance/manual-checkin', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        loadingOverlay.classList.add('hidden');

        if (data.status === 'success') {
            showSuccessModal(data.data, data.message);
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Gagal Absen',
                text: data.message || 'Terjadi kesalahan sistem.',
                confirmButtonColor: '#ef4444'
            });
            resetScan();
        }
    } catch (err) {
        loadingOverlay.classList.add('hidden');
        alert("Koneksi gagal. Coba lagi.");
        resetScan();
    }
};

function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/[&<>'"]/g, 
        tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
    );
}

window.resetScan = function() {
    isProcessing = false;
    resultArea.classList.add('hidden');
    resultArea.innerHTML = '';
    
    const successModal = document.getElementById('success-modal');
    if (successModal) successModal.classList.add('hidden');
    
    stableFramesCount = 0;
    updateStatus('idle', 'Siap Absen', 'Silakan berdiri tegap...');
    progressBar.style.width = '0%';
};
