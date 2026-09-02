// --- Konstanta AI & DOM ---
const REQUIRED_STABLE_FRAMES = 15; 
const MOVEMENT_THRESHOLD = 0.045; 
const AUTO_RESET_DELAY = 3500; 
const SAFE_ZONE_X_MIN = 0.20; const SAFE_ZONE_X_MAX = 0.80;
const SAFE_ZONE_Y_MIN = 0.15; const SAFE_ZONE_Y_MAX = 0.85;

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
    updateStatus('idle', 'Memeriksa Lokasi GPS', 'Mohon izinkan akses GPS pada browser Anda.');
    
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                currentUserLat = position.coords.latitude;
                currentUserLng = position.coords.longitude;
                updateStatus('idle', 'Siap Absen', 'Silakan berdiri tegap dan tatap kamera.');
                camera.start(); 
            },
            (error) => {
                console.warn("GPS access error/denied:", error);
                currentUserLat = null;
                currentUserLng = null;
                updateStatus('warning', 'GPS Tidak Aktif', 'Harap izinkan akses lokasi (GPS) untuk absensi.');
                camera.start();
            },
            { enableHighAccuracy: true, timeout: 6000, maximumAge: 0 }
        );
    } else {
        currentUserLat = null;
        currentUserLng = null;
        updateStatus('warning', 'GPS Tidak Didukung', 'Browser tidak mendukung deteksi lokasi.');
        camera.start();
    }
}

// --- Inisialisasi MediaPipe AI ---
const faceDetection = new FaceDetection({locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_detection/${file}`});
faceDetection.setOptions({ model: 'short', minDetectionConfidence: 0.45 });
faceDetection.onResults(onResults);

const camera = new Camera(videoElement, {
    onFrame: async () => { if (!isProcessing) await faceDetection.send({image: videoElement}); }
});

// PEMICU UTAMA
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
            updateStatus('warning', 'Wajah Terlalu Pinggir', 'Posisikan wajah tepat di tengah oval.');
            stableFramesCount = 0; progressBar.style.width = '0%';
        }
    } else {
        updateStatus('idle', 'Mencari Wajah...', 'Pastikan wajah terlihat jelas dan tidak silau.');
        stableFramesCount = 0; progressBar.style.width = '0%';
    }
}

function checkStability(currentX, currentY) {
    if (isProcessing) return;
    if (lastNoseX !== null && lastNoseY !== null) {
        const movement = Math.sqrt(Math.pow(currentX - lastNoseX, 2) + Math.pow(currentY - lastNoseY, 2));
        if (movement < MOVEMENT_THRESHOLD) {
            stableFramesCount++;
            updateStatus('scanning', 'Tahan Posisi...', 'Memproses pemindaian wajah...');
        } else {
            stableFramesCount = 0;
            updateStatus('warning', 'Terlalu Banyak Bergerak', 'Harap diam sejenak...');
        }
    }
    lastNoseX = currentX; lastNoseY = currentY;
    progressBar.style.width = `${(stableFramesCount / REQUIRED_STABLE_FRAMES) * 100}%`;
    if (stableFramesCount >= REQUIRED_STABLE_FRAMES) { triggerAutoCapture(); }
}

function updateStatus(state, title, desc) {
    statusTitle.innerText = title; statusDesc.innerText = desc;
    statusTitle.className = "text-3xl font-extrabold mb-2 leading-tight transition-colors";

    if (state === 'idle') {
        statusTitle.classList.add('text-white');
        statusIcon.innerHTML = `
            <svg class="w-7 h-7 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
        `;
    } else if (state === 'warning') {
        statusTitle.classList.add('text-amber-400');
        statusIcon.innerHTML = `
            <svg class="w-7 h-7 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
        `;
    } else if (state === 'scanning') {
        statusTitle.classList.add('text-cyan-400');
        statusIcon.innerHTML = `
            <svg class="w-7 h-7 text-cyan-400 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                <path stroke-linecap="round" stroke-linejoin="round" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
        `;
    }
}

function showSuccessModal(data, message) {
    resultArea.classList.add('hidden');
    
    document.getElementById('success-name').innerText = data.name;
    document.getElementById('success-message').innerText = message;
    document.getElementById('success-streak').innerHTML = `${data.total_attendance || 1}<span class="text-sm font-normal text-cyan-400 ml-1">x</span>`;
    document.getElementById('success-last-seen').innerText = data.last_seen || "Hari Ini";

    const badgeEl = document.getElementById('success-badge-method');
    if (badgeEl) {
        if (data.method === 'manual') {
            badgeEl.innerText = "Absen Manual";
            badgeEl.className = "inline-block mb-5 text-[11px] font-bold font-mono px-3 py-1 rounded-full bg-amber-500/10 text-amber-300 border border-amber-500/20";
        } else {
            badgeEl.innerText = "Scan Wajah";
            badgeEl.className = "inline-block mb-5 text-[11px] font-bold font-mono px-3 py-1 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/20";
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
                    <div class="w-14 h-14 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center mb-4 mx-auto">
                        <svg class="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                            <path stroke-linecap="round" stroke-linejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                        </svg>
                    </div>
                    <h3 class="text-xl font-extrabold text-white mb-1.5">Lokasi di Luar Jangkauan</h3>
                    <p class="text-slate-400 text-xs mb-5 font-medium">${escapeHtml(data.message || 'Anda berada di luar area GKI Bromo.')}</p>
                    <button onclick="resetScan()" class="text-slate-400 text-xs font-mono hover:text-white underline">Coba Scan Lagi</button>
                `;
            } else {
                resultArea.innerHTML = `
                    <div class="w-14 h-14 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-center justify-center mb-4 mx-auto">
                        <svg class="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                    </div>
                    <h3 class="text-xl font-extrabold text-white mb-1.5">Wajah Belum Terdeteksi</h3>
                    <p class="text-slate-400 text-xs mb-5">Wajah belum terdaftar di database atau cahaya silau.</p>
                    <div class="flex flex-col gap-2.5 w-full max-w-xs">
                        <button onclick="openManualSearchModal()" class="py-3 px-4 bg-azure-600 hover:bg-azure-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-azure-600/25 transition-all flex items-center justify-center gap-2">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
                            Cari Nama Manual
                        </button>
                        <a href="/register" class="py-3 px-4 bg-obsidian-800 hover:bg-obsidian-750 text-slate-200 border border-white/10 rounded-xl text-xs font-semibold transition-all flex items-center justify-center gap-2">
                            <svg class="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"/></svg>
                            Daftar Anggota Baru
                        </a>
                    </div>
                    <button onclick="resetScan()" class="text-slate-500 text-xs font-mono hover:text-slate-300 underline mt-4">Coba Scan Lagi</button>
                `;
            }
        } catch (err) {
            loadingOverlay.classList.add('hidden');
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
            manualSearchResults.innerHTML = `<div class="text-center py-10 text-slate-500 font-mono text-xs">Ketik minimal 1 huruf untuk mencari nama jemaat.</div>`;
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
            manualSearchResults.innerHTML = `<div class="text-center py-10 text-slate-500 font-mono text-xs">Ketik minimal 1 huruf untuk mencari nama jemaat.</div>`;
            return;
        }

        searchDebounceTimer = setTimeout(async () => {
            try {
                manualSearchResults.innerHTML = `<div class="text-center py-8 text-cyan-400 font-mono text-xs animate-pulse">Mencari jemaat...</div>`;
                const res = await fetch(`/api/users/search?q=${encodeURIComponent(query)}`);
                const result = await res.json();

                if (result.status === 'success' && result.data && result.data.length > 0) {
                    manualSearchResults.innerHTML = result.data.map(user => `
                        <div class="p-3.5 bg-obsidian-850 hover:bg-obsidian-800 rounded-2xl border border-white/[0.06] flex items-center justify-between transition-all">
                            <div>
                                <h4 class="font-bold text-sm text-white">${escapeHtml(user.full_name)}</h4>
                                <p class="text-xs text-slate-500 font-mono">${escapeHtml(user.gender || '-')} • ${escapeHtml(user.phone_number || '-')}</p>
                            </div>
                            <button onclick="executeManualCheckin(${user.id})" class="py-2 px-4 bg-azure-600 hover:bg-azure-500 active:scale-95 text-white font-semibold text-xs rounded-xl transition-all shadow shadow-azure-600/30">
                                Check-in
                            </button>
                        </div>
                    `).join('');
                } else {
                    manualSearchResults.innerHTML = `
                        <div class="text-center py-10">
                            <p class="text-slate-400 text-xs mb-3">Tidak ada nama "${escapeHtml(query)}" ditemukan.</p>
                            <a href="/register" class="inline-flex items-center gap-1.5 py-2 px-4 bg-azure-600/20 hover:bg-azure-600/30 text-azure-300 text-xs font-semibold rounded-xl border border-azure-500/30 transition-all font-mono">
                                + Daftarkan Jemaat Baru
                            </a>
                        </div>
                    `;
                }
            } catch (err) {
                manualSearchResults.innerHTML = `<div class="text-center py-8 text-rose-400 font-mono text-xs">Gagal mencari data. Cek koneksi server.</div>`;
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
        if (currentUserLat !== null) {
            formData.append('lat', currentUserLat);
            formData.append('lng', currentUserLng);
        }

        const response = await fetch('/api/attendance/manual-checkin', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        loadingOverlay.classList.add('hidden');

        if (response.status === 403) {
            Swal.fire({
                icon: 'warning',
                title: 'Lokasi di Luar Jangkauan',
                text: data.message || 'Anda berada di luar area GKI Bromo.',
                confirmButtonColor: '#f59e0b',
                background: '#0b0d13',
                color: '#f8fafc'
            });
            resetScan();
        } else if (data.status === 'success') {
            showSuccessModal(data.data, data.message);
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Gagal Absen',
                text: data.message || 'Terjadi kesalahan sistem.',
                confirmButtonColor: '#ef4444',
                background: '#0b0d13',
                color: '#f8fafc'
            });
            resetScan();
        }
    } catch (err) {
        loadingOverlay.classList.add('hidden');
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
    updateStatus('idle', 'Siap Absen', 'Silakan berdiri tegap dan tatap kamera.');
    progressBar.style.width = '0%';
};
