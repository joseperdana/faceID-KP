// --- Photo Strip Engine & State Management ---
document.addEventListener('DOMContentLoaded', () => {
    const video = document.getElementById('video-stream');
    const btnStartSession = document.getElementById('btn-start-session');
    const countdownOverlay = document.getElementById('countdown-overlay');
    const countdownNumber = document.getElementById('countdown-number');
    const countdownSubtext = document.getElementById('countdown-subtext');
    const interposeOverlay = document.getElementById('interpose-overlay');
    const interposeTitle = document.getElementById('interpose-title');
    const cameraFlash = document.getElementById('camera-flash');
    
    const btnToggleMirror = document.getElementById('btn-toggle-mirror');
    const btnSwitchCam = document.getElementById('btn-switch-cam');
    const timer3sBtn = document.getElementById('timer-3s');
    const timer5sBtn = document.getElementById('timer-5s');
    
    const poseIndicatorText = document.getElementById('pose-indicator-text');
    const dotPose1 = document.getElementById('dot-pose-1');
    const dotPose2 = document.getElementById('dot-pose-2');
    const dotPose3 = document.getElementById('dot-pose-3');
    
    const frameCards = document.querySelectorAll('.frame-card');
    const filterBtns = document.querySelectorAll('.filter-btn');
    const customCaptionInput = document.getElementById('custom-caption-input');
    
    const resultModal = document.getElementById('result-modal');
    const resultStripImg = document.getElementById('result-strip-img');
    const qrCodeContainer = document.getElementById('qr-code-container');
    const btnDownloadDirect = document.getElementById('btn-download-direct');
    const btnRetake = document.getElementById('btn-retake');
    const btnCloseModal = document.getElementById('btn-close-modal');
    const autoResetTimerEl = document.getElementById('auto-reset-timer');

    // State Variables
    let currentStream = null;
    let isMirrored = true;
    let currentFacingMode = 'user';
    let selectedFrame = 'merah-putih';
    let selectedFilter = 'natural';
    let timerDuration = 3;
    let isSessionRunning = false;
    let capturedPoses = []; // Array of 3 image bitmaps/canvases
    let autoResetInterval = null;
    let qrCodeInstance = null;

    // --- 1. Web Audio API Sound Synthesizer (Zero External Assets) ---
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    
    function playBeep(freq = 880, duration = 0.1) {
        if (audioCtx.state === 'suspended') audioCtx.resume();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
        gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + duration);
    }

    function playShutterSound() {
        if (audioCtx.state === 'suspended') audioCtx.resume();
        // Synthesize camera click + mechanical whir
        const bufferSize = audioCtx.sampleRate * 0.08;
        const buffer = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) {
            data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (bufferSize * 0.2));
        }
        const noise = audioCtx.createBufferSource();
        noise.buffer = buffer;
        const filter = audioCtx.createBiquadFilter();
        filter.type = 'bandpass';
        filter.frequency.value = 1200;
        noise.connect(filter);
        filter.connect(audioCtx.destination);
        noise.start();
    }

    // --- 2. Camera Setup ---
    async function startCamera() {
        if (currentStream) {
            currentStream.getTracks().forEach(track => track.stop());
        }
        try {
            const constraints = {
                video: {
                    facingMode: currentFacingMode,
                    width: { ideal: 1920 },
                    height: { ideal: 1080 }
                },
                audio: false
            };
            currentStream = await navigator.mediaDevices.getUserMedia(constraints);
            video.srcObject = currentStream;
        } catch (err) {
            console.error("Camera access error:", err);
            Swal.fire({
                title: 'Akses Kamera Ditolak',
                text: 'Harap izinkan akses kamera pada browser Anda untuk menggunakan Photobooth.',
                icon: 'error',
                background: '#0b0d13',
                color: '#f8fafc',
                confirmButtonColor: '#2563eb'
            });
        }
    }

    startCamera();

    // Mirroring & Camera Toggle Handlers
    btnToggleMirror.addEventListener('click', () => {
        isMirrored = !isMirrored;
        video.classList.toggle('-scale-x-100', isMirrored);
    });

    btnSwitchCam.addEventListener('click', () => {
        currentFacingMode = currentFacingMode === 'user' ? 'environment' : 'user';
        if (currentFacingMode === 'environment') {
            isMirrored = false;
            video.classList.remove('-scale-x-100');
        } else {
            isMirrored = true;
            video.classList.add('-scale-x-100');
        }
        startCamera();
    });

    // Timer Selector
    timer3sBtn.addEventListener('click', () => {
        timerDuration = 3;
        timer3sBtn.className = "px-3 py-1 text-xs font-mono font-bold rounded-lg bg-azure-600 text-white border border-azure-500 transition-all";
        timer5sBtn.className = "px-3 py-1 text-xs font-mono font-bold rounded-lg bg-obsidian-800 text-slate-400 border border-white/[0.08] hover:text-white transition-all";
    });

    timer5sBtn.addEventListener('click', () => {
        timerDuration = 5;
        timer5sBtn.className = "px-3 py-1 text-xs font-mono font-bold rounded-lg bg-azure-600 text-white border border-azure-500 transition-all";
        timer3sBtn.className = "px-3 py-1 text-xs font-mono font-bold rounded-lg bg-obsidian-800 text-slate-400 border border-white/[0.08] hover:text-white transition-all";
    });

    // Frame Selection Handlers
    frameCards.forEach(card => {
        card.addEventListener('click', () => {
            frameCards.forEach(c => c.classList.remove('frame-active'));
            card.classList.add('frame-active');
            selectedFrame = card.getAttribute('data-frame');
        });
    });

    // Color Tone Filter Handlers
    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            filterBtns.forEach(b => {
                b.classList.remove('filter-active');
                b.classList.add('text-slate-400');
            });
            btn.classList.add('filter-active');
            btn.classList.remove('text-slate-400');
            selectedFilter = btn.getAttribute('data-filter');
            applyVideoCssFilter();
        });
    });

    function applyVideoCssFilter() {
        if (selectedFilter === 'warm') {
            video.style.filter = 'sepia(0.25) saturate(1.2) contrast(1.05)';
        } else if (selectedFilter === 'mono') {
            video.style.filter = 'grayscale(1) contrast(1.25) brightness(0.95)';
        } else if (selectedFilter === 'soft') {
            video.style.filter = 'brightness(1.08) contrast(0.95) saturate(1.1)';
        } else {
            video.style.filter = 'none';
        }
    }

    // --- 3. Multi-Pose Automated Burst Capture Flow ---
    btnStartSession.addEventListener('click', startMultiPoseSession);

    async function startMultiPoseSession() {
        if (isSessionRunning) return;
        isSessionRunning = true;
        capturedPoses = [];
        btnStartSession.disabled = true;
        btnStartSession.classList.add('opacity-50', 'cursor-not-allowed');

        // Reset Indicators
        resetPoseDots();

        const posePrompts = [
            { text: "Pose 1 dari 3: Gaya Keren / Senyum Manis!", next: "Siapkan Gaya 2!" },
            { text: "Pose 2 dari 3: Gaya Lucu / Bebas!", next: "Pose Terakhir! Paling Heboh!" },
            { text: "Pose 3 dari 3: Pose Paling Heboh!", next: "Selesai! Merangkai Foto Strip..." }
        ];

        for (let i = 0; i < 3; i++) {
            poseIndicatorText.innerText = posePrompts[i].text;
            highlightPoseDot(i, 'active');

            // 1. Run Countdown
            await runCountdown(timerDuration, i + 1);

            // 2. Flash & Capture Frame
            triggerFlash();
            playShutterSound();
            const poseCanvas = captureSingleFrame();
            capturedPoses.push(poseCanvas);
            highlightPoseDot(i, 'done');

            // 3. Jeda Ganti Gaya (Inter-pose break)
            if (i < 2) {
                interposeTitle.innerText = posePrompts[i].next;
                interposeOverlay.classList.remove('hidden');
                await new Promise(r => setTimeout(r, 2200));
                interposeOverlay.classList.add('hidden');
            }
        }

        poseIndicatorText.innerText = "Merangkai Photo Strip...";
        await new Promise(r => setTimeout(r, 400));

        // 4. Compose Vertical Photo Strip
        await generateAndUploadPhotoStrip();

        isSessionRunning = false;
        btnStartSession.disabled = false;
        btnStartSession.classList.remove('opacity-50', 'cursor-not-allowed');
        poseIndicatorText.innerText = "Siap Foto Strip (3 Pose)";
    }

    function runCountdown(seconds, poseNum) {
        return new Promise(resolve => {
            countdownOverlay.classList.remove('hidden');
            countdownSubtext.innerText = `Pose ${poseNum} dari 3`;
            let remaining = seconds;
            countdownNumber.innerText = remaining;
            playBeep(660, 0.1);

            const timer = setInterval(() => {
                remaining--;
                if (remaining > 0) {
                    countdownNumber.innerText = remaining;
                    playBeep(660, 0.1);
                } else {
                    clearInterval(timer);
                    countdownOverlay.classList.add('hidden');
                    playBeep(1100, 0.2);
                    resolve();
                }
            }, 1000);
        });
    }

    function triggerFlash() {
        cameraFlash.classList.remove('hidden');
        cameraFlash.classList.add('flash-animation');
        setTimeout(() => {
            cameraFlash.classList.remove('flash-animation');
            cameraFlash.classList.add('hidden');
        }, 350);
    }

    function captureSingleFrame() {
        const frameCanvas = document.createElement('canvas');
        const vW = video.videoWidth || 1280;
        const vH = video.videoHeight || 960;
        
        // Desired standard portrait ratio for each slot: 4:3 (e.g. 960x720)
        const targetW = 960;
        const targetH = 720;
        frameCanvas.width = targetW;
        frameCanvas.height = targetH;
        const ctx = frameCanvas.getContext('2d');

        // Smart Center-Crop: Calculate source crop box
        let srcX = 0, srcY = 0, srcW = vW, srcH = vH;
        const videoRatio = vW / vH;
        const targetRatio = targetW / targetH; // 1.333

        if (videoRatio > targetRatio) {
            // Video is wider than 4:3, crop sides
            srcW = vH * targetRatio;
            srcX = (vW - srcW) / 2;
        } else {
            // Video is taller, crop top/bottom
            srcH = vW / targetRatio;
            srcY = (vH - srcH) / 2;
        }

        ctx.save();
        if (isMirrored) {
            ctx.translate(targetW, 0);
            ctx.scale(-1, 1);
        }

        // Draw cropped camera frame
        ctx.drawImage(video, srcX, srcY, srcW, srcH, 0, 0, targetW, targetH);
        ctx.restore();

        // Apply Color Filter to individual snapshot
        applyFilterToCanvas(ctx, targetW, targetH, selectedFilter);

        return frameCanvas;
    }

    function applyFilterToCanvas(ctx, w, h, filterName) {
        if (filterName === 'mono') {
            const imgData = ctx.getImageData(0, 0, w, h);
            const d = imgData.data;
            for (let i = 0; i < d.length; i += 4) {
                const gray = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
                const highContrast = (gray - 128) * 1.25 + 128;
                d[i] = highContrast;
                d[i + 1] = highContrast;
                d[i + 2] = highContrast;
            }
            ctx.putImageData(imgData, 0, 0);
        } else if (filterName === 'warm') {
            ctx.save();
            ctx.fillStyle = 'rgba(217, 119, 6, 0.12)';
            ctx.fillRect(0, 0, w, h);
            ctx.restore();
        } else if (filterName === 'soft') {
            ctx.save();
            ctx.fillStyle = 'rgba(255, 241, 242, 0.08)';
            ctx.fillRect(0, 0, w, h);
            ctx.restore();
        }
    }

    function resetPoseDots() {
        [dotPose1, dotPose2, dotPose3].forEach(dot => {
            dot.className = "w-6 h-2 rounded-full bg-obsidian-800 border border-white/10 transition-all";
        });
    }

    function highlightPoseDot(index, state) {
        const dots = [dotPose1, dotPose2, dotPose3];
        if (state === 'active') {
            dots[index].className = "w-8 h-2 rounded-full bg-cyan-400 shadow-sm shadow-cyan-400/50 transition-all animate-pulse";
        } else if (state === 'done') {
            dots[index].className = "w-6 h-2 rounded-full bg-emerald-400 shadow-sm shadow-emerald-400/30 transition-all";
        }
    }

    // --- 4. Vertical Photo Strip Canvas Compositor ---
    async function generateAndUploadPhotoStrip() {
        const stripCanvas = document.createElement('canvas');
        const STRIP_W = 1000;
        const STRIP_H = 3000;
        stripCanvas.width = STRIP_W;
        stripCanvas.height = STRIP_H;
        const ctx = stripCanvas.getContext('2d');

        const customCaption = (customCaptionInput.value || '').trim();
        const todayStr = new Intl.DateTimeFormat('id-ID', { day: 'numeric', month: 'long', year: 'numeric' }).format(new Date());

        // Draw Selected Frame Theme
        if (selectedFrame === 'merah-putih') {
            renderMerahPutihCuteTheme(ctx, STRIP_W, STRIP_H, capturedPoses, customCaption, todayStr);
        } else if (selectedFrame === 'batik-kawaii') {
            renderBatikKawaiiTheme(ctx, STRIP_W, STRIP_H, capturedPoses, customCaption, todayStr);
        } else if (selectedFrame === 'retro-kodak') {
            renderRetroKodakTheme(ctx, STRIP_W, STRIP_H, capturedPoses, customCaption, todayStr);
        } else {
            renderObsidianCyberTheme(ctx, STRIP_W, STRIP_H, capturedPoses, customCaption, todayStr);
        }

        // Convert Strip to Base64 JPEG
        const base64Image = stripCanvas.toDataURL('image/jpeg', 0.92);

        // Upload to Backend
        try {
            Swal.fire({
                title: 'Menyiapkan QR Code...',
                text: 'Mengunggah hasil strip foto...',
                allowOutsideClick: false,
                background: '#0b0d13',
                color: '#f8fafc',
                didOpen: () => { Swal.showLoading(); }
            });

            const response = await fetch('/api/photobooth/upload', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    image: base64Image,
                    frame: selectedFrame,
                    caption: customCaption
                })
            });

            const data = await response.json();
            Swal.close();

            if (data.status === 'success') {
                showResultModal(data, base64Image);
            } else {
                throw new Error(data.message || 'Gagal menyimpan foto');
            }
        } catch (err) {
            Swal.fire({
                title: 'Gagal Menyimpan',
                text: 'Terjadi kendala saat mengunggah foto. Anda tetap bisa mengunduhnya langsung.',
                icon: 'warning',
                background: '#0b0d13',
                color: '#f8fafc',
                confirmButtonColor: '#2563eb'
            });
            showResultModal({ download_url: base64Image, qr_url: window.location.href }, base64Image);
        }
    }

    // --- THEME 1: Merah Putih Cute Fest (Playful 17an) ---
    function renderMerahPutihCuteTheme(ctx, W, H, poses, caption, dateStr) {
        // Cream Warm Background
        ctx.fillStyle = '#fffdfa';
        ctx.fillRect(0, 0, W, H);

        // Vibrant Red Outer Wavy Border Accent
        ctx.fillStyle = '#dc2626';
        ctx.fillRect(0, 0, W, 30);
        ctx.fillRect(0, H - 30, W, 30);
        ctx.fillRect(0, 0, 30, H);
        ctx.fillRect(W - 30, 0, 30, H);

        // Top Header Banner
        ctx.fillStyle = '#dc2626';
        ctx.beginPath();
        ctx.roundRect(70, 70, W - 140, 160, 24);
        ctx.fill();

        ctx.fillStyle = '#ffffff';
        ctx.font = '900 46px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('DIRGAHAYU REPUBLIK INDONESIA', W / 2, 135);

        ctx.fillStyle = '#fecaca';
        ctx.font = '700 24px "JetBrains Mono", monospace';
        ctx.fillText('EDISI 17 AGUSTUS • KP BROMO MALANG', W / 2, 185);

        // 3 Photo Cutouts Layout
        const photoW = 840;
        const photoH = 630;
        const photoX = (W - photoW) / 2;
        const startY = 280;
        const gapY = 50;

        poses.forEach((pose, idx) => {
            const posY = startY + idx * (photoH + gapY);

            // Photo Shadow Card
            ctx.fillStyle = '#fee2e2';
            ctx.beginPath();
            ctx.roundRect(photoX - 8, posY - 8, photoW + 16, photoH + 16, 24);
            ctx.fill();

            // Draw Photo
            ctx.save();
            ctx.beginPath();
            ctx.roundRect(photoX, posY, photoW, photoH, 18);
            ctx.clip();
            ctx.drawImage(pose, photoX, posY, photoW, photoH);
            ctx.restore();

            // Red Photo Badge Number
            ctx.fillStyle = '#dc2626';
            ctx.beginPath();
            ctx.roundRect(photoX + 24, posY + 24, 70, 44, 12);
            ctx.fill();

            ctx.fillStyle = '#ffffff';
            ctx.font = '800 22px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.fillText(`0${idx + 1}`, photoX + 59, posY + 54);
        });

        // Bottom Footer Banner
        const footerY = startY + 3 * (photoH + gapY) + 40;
        
        ctx.fillStyle = '#1e293b';
        ctx.font = '800 36px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(caption || 'Komisi Pemuda GKI Bromo', W / 2, footerY + 60);

        ctx.fillStyle = '#64748b';
        ctx.font = '600 24px "JetBrains Mono", monospace';
        ctx.fillText(`Saturday Fellowship • ${dateStr}`, W / 2, footerY + 115);

        ctx.fillStyle = '#dc2626';
        ctx.font = '900 28px "Plus Jakarta Sans", sans-serif';
        ctx.fillText('YOUTH ON FIRE FOR CHRIST', W / 2, footerY + 175);
    }

    // --- THEME 2: Batik Pop Kawaii (Nusantara Heritage) ---
    function renderBatikKawaiiTheme(ctx, W, H, poses, caption, dateStr) {
        // Warm Latte Background
        ctx.fillStyle = '#fefce8';
        ctx.fillRect(0, 0, W, H);

        // Ornate Terracotta Border
        const bW = 35;
        ctx.strokeStyle = '#b45309';
        ctx.lineWidth = bW;
        ctx.strokeRect(bW / 2, bW / 2, W - bW, H - bW);

        // Inner Gold Hairline
        ctx.strokeStyle = '#f59e0b';
        ctx.lineWidth = 4;
        ctx.strokeRect(55, 55, W - 110, H - 110);

        // Header Plate
        ctx.fillStyle = '#78350f';
        ctx.beginPath();
        ctx.roundRect(80, 80, W - 160, 150, 24);
        ctx.fill();

        ctx.fillStyle = '#fef08a';
        ctx.font = '900 44px "Cinzel", serif';
        ctx.textAlign = 'center';
        ctx.fillText('NUSANTARA HERITAGE', W / 2, 145);

        ctx.fillStyle = '#fde68a';
        ctx.font = '700 22px "JetBrains Mono", monospace';
        ctx.fillText('KOMISI PEMUDA GKI BROMO', W / 2, 190);

        // 3 Photo Cutouts
        const photoW = 820;
        const photoH = 615;
        const photoX = (W - photoW) / 2;
        const startY = 280;
        const gapY = 55;

        poses.forEach((pose, idx) => {
            const posY = startY + idx * (photoH + gapY);

            // Gold Outer Frame
            ctx.fillStyle = '#fef3c7';
            ctx.beginPath();
            ctx.roundRect(photoX - 10, posY - 10, photoW + 20, photoH + 20, 20);
            ctx.fill();

            // Photo
            ctx.save();
            ctx.beginPath();
            ctx.roundRect(photoX, posY, photoW, photoH, 14);
            ctx.clip();
            ctx.drawImage(pose, photoX, posY, photoW, photoH);
            ctx.restore();
        });

        // Bottom Plate
        const footerY = startY + 3 * (photoH + gapY) + 30;
        ctx.fillStyle = '#78350f';
        ctx.beginPath();
        ctx.roundRect(80, footerY, W - 160, 210, 24);
        ctx.fill();

        ctx.fillStyle = '#fef08a';
        ctx.font = '800 36px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(caption || 'SATURDAY FELLOWSHIP', W / 2, footerY + 80);

        ctx.fillStyle = '#fde68a';
        ctx.font = '600 24px "JetBrains Mono", monospace';
        ctx.fillText(dateStr, W / 2, footerY + 140);
    }

    // --- THEME 3: Retro Kodachrome 1945 ---
    function renderRetroKodakTheme(ctx, W, H, poses, caption, dateStr) {
        // Kodak Film Cream
        ctx.fillStyle = '#f1f5f9';
        ctx.fillRect(0, 0, W, H);

        // Top Header Typewriter Text
        ctx.fillStyle = '#0f172a';
        ctx.font = '800 32px "JetBrains Mono", monospace';
        ctx.textAlign = 'left';
        ctx.fillText('SAFETY FILM 1945', 80, 110);

        ctx.textAlign = 'right';
        ctx.fillText('ISO 400 • KP45', W - 80, 110);

        // 3 Photo Cutouts with subtle borders
        const photoW = 840;
        const photoH = 630;
        const photoX = (W - photoW) / 2;
        const startY = 160;
        const gapY = 60;

        poses.forEach((pose, idx) => {
            const posY = startY + idx * (photoH + gapY);

            ctx.fillStyle = '#e2e8f0';
            ctx.fillRect(photoX - 6, posY - 6, photoW + 12, photoH + 12);

            ctx.save();
            ctx.drawImage(pose, photoX, posY, photoW, photoH);
            ctx.restore();

            // Film frame marker
            ctx.fillStyle = '#64748b';
            ctx.font = '700 20px "JetBrains Mono", monospace';
            ctx.textAlign = 'left';
            ctx.fillText(`FRAME ${idx + 1}A`, photoX, posY + photoH + 28);
        });

        // Bottom Typewriter Notes
        const footerY = startY + 3 * (photoH + gapY) + 50;
        
        ctx.fillStyle = '#0f172a';
        ctx.font = '900 40px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(caption || 'GKI BROMO YOUTH FELLOWSHIP', W / 2, footerY + 50);

        ctx.fillStyle = '#475569';
        ctx.font = '700 24px "JetBrains Mono", monospace';
        ctx.fillText(`${dateStr} • MALANG`, W / 2, footerY + 110);
    }

    // --- THEME 4: Obsidian Cyber Minimalist ---
    function renderObsidianCyberTheme(ctx, W, H, poses, caption, dateStr) {
        // Deep Obsidian Background
        ctx.fillStyle = '#06070a';
        ctx.fillRect(0, 0, W, H);

        // Subtle Neon Cyan Border
        ctx.strokeStyle = '#2563eb';
        ctx.lineWidth = 6;
        ctx.strokeRect(40, 40, W - 80, H - 80);

        // Top Monogram Header
        ctx.fillStyle = '#38bdf8';
        ctx.font = '900 36px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('KP BROMO PHOTO STRIP', W / 2, 130);

        ctx.fillStyle = '#64748b';
        ctx.font = '600 22px "JetBrains Mono", monospace';
        ctx.fillText('INTELLIGENCE PHOTOBOOTH TERMINAL', W / 2, 175);

        // 3 Photo Cutouts with Cyan Hairline
        const photoW = 840;
        const photoH = 630;
        const photoX = (W - photoW) / 2;
        const startY = 230;
        const gapY = 60;

        poses.forEach((pose, idx) => {
            const posY = startY + idx * (photoH + gapY);

            ctx.strokeStyle = 'rgba(56, 189, 248, 0.4)';
            ctx.lineWidth = 3;
            ctx.strokeRect(photoX - 4, posY - 4, photoW + 8, photoH + 8);

            ctx.save();
            ctx.beginPath();
            ctx.roundRect(photoX, posY, photoW, photoH, 12);
            ctx.clip();
            ctx.drawImage(pose, photoX, posY, photoW, photoH);
            ctx.restore();
        });

        // Bottom Footer
        const footerY = startY + 3 * (photoH + gapY) + 50;
        ctx.fillStyle = '#ffffff';
        ctx.font = '800 36px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(caption || 'Komisi Pemuda GKI Bromo', W / 2, footerY + 60);

        ctx.fillStyle = '#38bdf8';
        ctx.font = '600 24px "JetBrains Mono", monospace';
        ctx.fillText(`SATURDAY FELLOWSHIP • ${dateStr}`, W / 2, footerY + 120);
    }

    // --- 5. Result Modal & QR Code Delivery Presentation ---
    function showResultModal(uploadData, localBase64) {
        resultStripImg.src = localBase64;
        btnDownloadDirect.href = uploadData.download_url || localBase64;
        btnDownloadDirect.download = `KP_Bromo_PhotoStrip_${uploadData.photo_id || 'strip'}.jpg`;

        // Render QR Code
        qrCodeContainer.innerHTML = '';
        const qrTargetUrl = uploadData.qr_url || window.location.href;
        
        qrCodeInstance = new QRCode(qrCodeContainer, {
            text: qrTargetUrl,
            width: 170,
            height: 170,
            colorDark: "#06070a",
            colorLight: "#ffffff",
            correctLevel: QRCode.CorrectLevel.M
        });

        resultModal.classList.remove('hidden');

        // Confetti Celebration
        try {
            confetti({
                particleCount: 75,
                spread: 70,
                origin: { y: 0.6 }
            });
        } catch(e) {}

        // Start 45s Auto-Reset Countdown
        startAutoResetTimer(45);
    }

    function startAutoResetTimer(seconds) {
        clearInterval(autoResetInterval);
        let remaining = seconds;
        autoResetTimerEl.innerText = `${remaining}s`;

        autoResetInterval = setInterval(() => {
            remaining--;
            if (remaining >= 0) {
                autoResetTimerEl.innerText = `${remaining}s`;
            } else {
                clearInterval(autoResetInterval);
                closeResultModal();
            }
        }, 1000);
    }

    function closeResultModal() {
        clearInterval(autoResetInterval);
        resultModal.classList.add('hidden');
        resetPoseDots();
    }

    btnRetake.addEventListener('click', closeResultModal);
    btnCloseModal.addEventListener('click', closeResultModal);
});
