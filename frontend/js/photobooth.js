// --- Superpower Photo Strip Engine & Tactile Compositor ---
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
    let capturedPoses = []; // Holds 3 frame canvases
    let autoResetInterval = null;
    let qrCodeInstance = null;

    // --- 1. Web Audio API Physical Shutter Synthesizer ---
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    
    function playBeep(freq = 880, duration = 0.1) {
        if (audioCtx.state === 'suspended') audioCtx.resume();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
        gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + duration);
    }

    function playShutterSound() {
        if (audioCtx.state === 'suspended') audioCtx.resume();
        // Mechanical shutter click: Noise burst + twin resonant clicks
        const bufferSize = audioCtx.sampleRate * 0.09;
        const buffer = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) {
            data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (bufferSize * 0.25));
        }
        const noise = audioCtx.createBufferSource();
        noise.buffer = buffer;
        const filter = audioCtx.createBiquadFilter();
        filter.type = 'bandpass';
        filter.frequency.value = 1400;
        noise.connect(filter);
        filter.connect(audioCtx.destination);
        noise.start();
    }

    // --- 2. Camera Setup & Streaming ---
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
                background: '#0c0f17',
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
        timer3sBtn.className = "px-3.5 py-1 text-xs font-mono font-extrabold rounded-xl bg-pop-blue text-white border-2 border-black shadow-neo-sm transition-all";
        timer5sBtn.className = "px-3.5 py-1 text-xs font-mono font-extrabold rounded-xl bg-canvas-800 text-slate-400 border-2 border-white/10 hover:text-white transition-all";
    });

    timer5sBtn.addEventListener('click', () => {
        timerDuration = 5;
        timer5sBtn.className = "px-3.5 py-1 text-xs font-mono font-extrabold rounded-xl bg-pop-blue text-white border-2 border-black shadow-neo-sm transition-all";
        timer3sBtn.className = "px-3.5 py-1 text-xs font-mono font-extrabold rounded-xl bg-canvas-800 text-slate-400 border-2 border-white/10 hover:text-white transition-all";
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
            video.style.filter = 'sepia(0.28) saturate(1.25) contrast(1.08)';
        } else if (selectedFilter === 'mono') {
            video.style.filter = 'grayscale(1) contrast(1.3) brightness(0.95)';
        } else if (selectedFilter === 'soft') {
            video.style.filter = 'brightness(1.1) contrast(0.95) saturate(1.15)';
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

        resetPoseDots();

        const posePrompts = [
            { text: "Pose 1 dari 3: Gaya Keren / Senyum Manis!", sub: "Pose 1 dari 3: Senyum Manis!", next: "Siapkan Gaya 2!" },
            { text: "Pose 2 dari 3: Gaya Lucu / Bebas!", sub: "Pose 2 dari 3: Gaya Lucu Bebas!", next: "Pose Terakhir! Paling Heboh!" },
            { text: "Pose 3 dari 3: Pose Paling Heboh!", sub: "Pose 3 dari 3: Pose Paling Heboh!", next: "Selesai! Merangkai Foto..." }
        ];

        for (let i = 0; i < 3; i++) {
            poseIndicatorText.innerText = posePrompts[i].text;
            highlightPoseDot(i, 'active');

            // 1. Run Countdown
            await runCountdown(timerDuration, i + 1, posePrompts[i].sub);

            // 2. Flash & Capture Frame
            triggerFlash();
            playShutterSound();
            const poseCanvas = captureSingleFrame();
            capturedPoses.push(poseCanvas);
            highlightPoseDot(i, 'done');

            // 3. Inter-pose Break
            if (i < 2) {
                interposeTitle.innerText = posePrompts[i].next;
                interposeOverlay.classList.remove('hidden');
                await new Promise(r => setTimeout(r, 2200));
                interposeOverlay.classList.add('hidden');
            }
        }

        poseIndicatorText.innerText = "Merangkai Photo Strip HD...";
        await new Promise(r => setTimeout(r, 400));

        // 4. Compose Canvas & Upload
        await generateAndUploadPhotoStrip();

        isSessionRunning = false;
        btnStartSession.disabled = false;
        btnStartSession.classList.remove('opacity-50', 'cursor-not-allowed');
        poseIndicatorText.innerText = "Siap Sesi Foto (3 Pose)";
    }

    function runCountdown(seconds, poseNum, subtext) {
        return new Promise(resolve => {
            countdownOverlay.classList.remove('hidden');
            countdownSubtext.innerText = subtext;
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
                    playBeep(1200, 0.25);
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
        
        // Exact 4:3 Ratio for Crisp Studio Portrait Slots
        const targetW = 960;
        const targetH = 720;
        frameCanvas.width = targetW;
        frameCanvas.height = targetH;
        const ctx = frameCanvas.getContext('2d');

        let srcX = 0, srcY = 0, srcW = vW, srcH = vH;
        const videoRatio = vW / vH;
        const targetRatio = targetW / targetH; // 1.333

        if (videoRatio > targetRatio) {
            srcW = vH * targetRatio;
            srcX = (vW - srcW) / 2;
        } else {
            srcH = vW / targetRatio;
            srcY = (vH - srcH) / 2;
        }

        ctx.save();
        if (isMirrored) {
            ctx.translate(targetW, 0);
            ctx.scale(-1, 1);
        }

        ctx.drawImage(video, srcX, srcY, srcW, srcH, 0, 0, targetW, targetH);
        ctx.restore();

        // Apply Color Filter
        applyFilterToCanvas(ctx, targetW, targetH, selectedFilter);

        return frameCanvas;
    }

    function applyFilterToCanvas(ctx, w, h, filterName) {
        if (filterName === 'mono') {
            const imgData = ctx.getImageData(0, 0, w, h);
            const d = imgData.data;
            for (let i = 0; i < d.length; i += 4) {
                const gray = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
                const highContrast = (gray - 128) * 1.28 + 128;
                d[i] = highContrast;
                d[i + 1] = highContrast;
                d[i + 2] = highContrast;
            }
            ctx.putImageData(imgData, 0, 0);
        } else if (filterName === 'warm') {
            ctx.save();
            ctx.fillStyle = 'rgba(245, 158, 11, 0.12)';
            ctx.fillRect(0, 0, w, h);
            ctx.restore();
        } else if (filterName === 'soft') {
            ctx.save();
            ctx.fillStyle = 'rgba(254, 242, 242, 0.08)';
            ctx.fillRect(0, 0, w, h);
            ctx.restore();
        }
    }

    function resetPoseDots() {
        [dotPose1, dotPose2, dotPose3].forEach(dot => {
            dot.className = "w-8 h-2.5 rounded-full bg-canvas-800 border-2 border-white/10 transition-all";
        });
    }

    function highlightPoseDot(index, state) {
        const dots = [dotPose1, dotPose2, dotPose3];
        if (state === 'active') {
            dots[index].className = "w-10 h-2.5 rounded-full bg-pop-yellow shadow-neo-sm transition-all animate-pulse border-2 border-black";
        } else if (state === 'done') {
            dots[index].className = "w-8 h-2.5 rounded-full bg-emerald-400 shadow-neo-sm transition-all border-2 border-black";
        }
    }

    // Helper: Draw 5-Point Sticker Star
    function drawStar(ctx, cx, cy, spikes, outerRadius, innerRadius, color) {
        let rot = Math.PI / 2 * 3;
        let x = cx;
        let y = cy;
        let step = Math.PI / spikes;

        ctx.save();
        ctx.beginPath();
        ctx.moveTo(cx, cy - outerRadius);
        for (let i = 0; i < spikes; i++) {
            x = cx + Math.cos(rot) * outerRadius;
            y = cy + Math.sin(rot) * outerRadius;
            ctx.lineTo(x, y);
            rot += step;

            x = cx + Math.cos(rot) * innerRadius;
            y = cy + Math.sin(rot) * innerRadius;
            ctx.lineTo(x, y);
            rot += step;
        }
        ctx.lineTo(cx, cy - outerRadius);
        ctx.closePath();
        ctx.fillStyle = color;
        ctx.fill();
        ctx.lineWidth = 4;
        ctx.strokeStyle = '#000000';
        ctx.stroke();
        ctx.restore();
    }

    // --- 4. High-Res Canvas Compositor (1000 x 3000 px, 300 DPI) ---
    async function generateAndUploadPhotoStrip() {
        const stripCanvas = document.createElement('canvas');
        const STRIP_W = 1000;
        const STRIP_H = 3000;
        stripCanvas.width = STRIP_W;
        stripCanvas.height = STRIP_H;
        const ctx = stripCanvas.getContext('2d');

        const customCaption = (customCaptionInput.value || '').trim();
        const todayStr = new Intl.DateTimeFormat('id-ID', { day: 'numeric', month: 'long', year: 'numeric' }).format(new Date());

        // Render Chosen Theme
        if (selectedFrame === 'merah-putih') {
            renderMerahPutihFestiveTheme(ctx, STRIP_W, STRIP_H, capturedPoses, customCaption, todayStr);
        } else if (selectedFrame === 'y2k-pastel') {
            renderY2KPastelTheme(ctx, STRIP_W, STRIP_H, capturedPoses, customCaption, todayStr);
        } else if (selectedFrame === 'batik-nusantara') {
            renderBatikNusantaraTheme(ctx, STRIP_W, STRIP_H, capturedPoses, customCaption, todayStr);
        } else {
            renderRetroKodakTheme(ctx, STRIP_W, STRIP_H, capturedPoses, customCaption, todayStr);
        }

        const base64Image = stripCanvas.toDataURL('image/jpeg', 0.92);

        try {
            Swal.fire({
                title: 'Menyiapkan QR Code...',
                text: 'Mengunggah hasil strip foto...',
                allowOutsideClick: false,
                background: '#0c0f17',
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
                title: 'Gagal Menyimpan Otomatis',
                text: 'Terjadi kendala jaringan saat upload. Anda tetap bisa mengunduh foto langsung.',
                icon: 'warning',
                background: '#0c0f17',
                color: '#f8fafc',
                confirmButtonColor: '#2563eb'
            });
            showResultModal({ download_url: base64Image, qr_url: window.location.href }, base64Image);
        }
    }

    // --- THEME 1: Merah Putih Festive 17an (Playful Neo-Brutalism) ---
    function renderMerahPutihFestiveTheme(ctx, W, H, poses, caption, dateStr) {
        // Warm Cream Paper Background
        ctx.fillStyle = '#fffdf8';
        ctx.fillRect(0, 0, W, H);

        // Chunky Red Outer Border
        ctx.fillStyle = '#dc2626';
        ctx.fillRect(0, 0, W, 36);
        ctx.fillRect(0, H - 36, W, 36);
        ctx.fillRect(0, 0, 36, H);
        ctx.fillRect(W - 36, 0, 36, H);

        // Top Red Header Banner with Neo-Shadow
        ctx.save();
        ctx.fillStyle = '#000000';
        ctx.beginPath();
        ctx.roundRect(76, 76, W - 140, 160, 24);
        ctx.fill();

        ctx.fillStyle = '#dc2626';
        ctx.beginPath();
        ctx.roundRect(70, 70, W - 140, 160, 24);
        ctx.fill();
        ctx.lineWidth = 4;
        ctx.strokeStyle = '#000000';
        ctx.stroke();

        ctx.fillStyle = '#ffffff';
        ctx.font = '900 44px "Space Grotesk", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('DIRGAHAYU INDONESIA', W / 2, 135);

        ctx.fillStyle = '#fef08a';
        ctx.font = '800 24px "JetBrains Mono", monospace';
        ctx.fillText('17 AGUSTUS • KOMISI PEMUDA GKI BROMO', W / 2, 185);
        ctx.restore();

        // 3 Photo Cutouts Layout with Solid Drop Shadows
        const photoW = 840;
        const photoH = 630;
        const photoX = (W - photoW) / 2;
        const startY = 280;
        const gapY = 55;

        poses.forEach((pose, idx) => {
            const posY = startY + idx * (photoH + gapY);

            // Solid Black Neo-Shadow
            ctx.fillStyle = '#000000';
            ctx.beginPath();
            ctx.roundRect(photoX + 8, posY + 8, photoW, photoH, 20);
            ctx.fill();

            // Photo Card Frame
            ctx.save();
            ctx.beginPath();
            ctx.roundRect(photoX, posY, photoW, photoH, 20);
            ctx.clip();
            ctx.drawImage(pose, photoX, posY, photoW, photoH);
            ctx.restore();

            // Solid Outer Border
            ctx.lineWidth = 4;
            ctx.strokeStyle = '#000000';
            ctx.strokeRect(photoX, posY, photoW, photoH);

            // Numbered Badge
            ctx.save();
            ctx.fillStyle = '#000000';
            ctx.beginPath();
            ctx.roundRect(photoX + 28, posY + 28, 70, 44, 12);
            ctx.fill();

            ctx.fillStyle = '#dc2626';
            ctx.beginPath();
            ctx.roundRect(photoX + 24, posY + 24, 70, 44, 12);
            ctx.fill();
            ctx.lineWidth = 3;
            ctx.strokeStyle = '#000000';
            ctx.stroke();

            ctx.fillStyle = '#ffffff';
            ctx.font = '900 24px "Space Grotesk", sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(`0${idx + 1}`, photoX + 59, posY + 55);
            ctx.restore();

            // Decorative Sticker Star on Alternate Corners
            if (idx === 0) drawStar(ctx, photoX + photoW - 35, posY + 35, 5, 26, 12, '#fbbf24');
            if (idx === 2) drawStar(ctx, photoX + photoW - 35, posY + photoH - 35, 5, 26, 12, '#38bdf8');
        });

        // Bottom Footer Banner
        const footerY = startY + 3 * (photoH + gapY) + 30;
        
        ctx.fillStyle = '#0f172a';
        ctx.font = '900 38px "Space Grotesk", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(caption || 'Komisi Pemuda GKI Bromo', W / 2, footerY + 65);

        ctx.fillStyle = '#64748b';
        ctx.font = '700 22px "JetBrains Mono", monospace';
        ctx.fillText(`Saturday Fellowship • ${dateStr}`, W / 2, footerY + 115);

        ctx.fillStyle = '#dc2626';
        ctx.font = '900 28px "Space Grotesk", sans-serif';
        ctx.fillText('YOUTH ON FIRE FOR CHRIST', W / 2, footerY + 165);
    }

    // --- THEME 2: Y2K Photomatix Seoul (Pastel & Stars Aesthetic) ---
    function renderY2KPastelTheme(ctx, W, H, poses, caption, dateStr) {
        // Pastel Lilac to Baby Blue Gradient
        const grad = ctx.createLinearGradient(0, 0, W, H);
        grad.addColorStop(0, '#f5f3ff');
        grad.addColorStop(0.5, '#ede9fe');
        grad.addColorStop(1, '#e0f2fe');
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, W, H);

        // Header Sticker Plate
        ctx.save();
        ctx.fillStyle = '#000000';
        ctx.beginPath();
        ctx.roundRect(76, 76, W - 140, 150, 24);
        ctx.fill();

        ctx.fillStyle = '#8b5cf6';
        ctx.beginPath();
        ctx.roundRect(70, 70, W - 140, 150, 24);
        ctx.fill();
        ctx.lineWidth = 4;
        ctx.strokeStyle = '#000000';
        ctx.stroke();

        ctx.fillStyle = '#ffffff';
        ctx.font = '900 46px "Space Grotesk", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Y2K PHOTO STUDIO', W / 2, 135);

        ctx.fillStyle = '#fde047';
        ctx.font = '800 22px "JetBrains Mono", monospace';
        ctx.fillText('SEOUL AESTHETIC • KP BROMO', W / 2, 180);
        ctx.restore();

        // 3 Photo Cutouts with Soft Lilac Cards
        const photoW = 840;
        const photoH = 630;
        const photoX = (W - photoW) / 2;
        const startY = 270;
        const gapY = 55;

        poses.forEach((pose, idx) => {
            const posY = startY + idx * (photoH + gapY);

            // Lilac Neo-Shadow
            ctx.fillStyle = '#c4b5fd';
            ctx.beginPath();
            ctx.roundRect(photoX + 8, posY + 8, photoW, photoH, 20);
            ctx.fill();

            // Photo
            ctx.save();
            ctx.beginPath();
            ctx.roundRect(photoX, posY, photoW, photoH, 20);
            ctx.clip();
            ctx.drawImage(pose, photoX, posY, photoW, photoH);
            ctx.restore();

            ctx.lineWidth = 4;
            ctx.strokeStyle = '#000000';
            ctx.strokeRect(photoX, posY, photoW, photoH);

            // Doodle Star Stickers
            drawStar(ctx, photoX + 40, posY + 40, 5, 22, 10, '#fde047');
            drawStar(ctx, photoX + photoW - 40, posY + 40, 5, 18, 8, '#f472b6');
        });

        // Bottom Footer with Barcode & Minimalist Tag
        const footerY = startY + 3 * (photoH + gapY) + 30;

        ctx.fillStyle = '#1e1b4b';
        ctx.font = '900 36px "Space Grotesk", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(caption || 'KP BROMO MEMORIES', W / 2, footerY + 60);

        ctx.fillStyle = '#6b7280';
        ctx.font = '700 22px "JetBrains Mono", monospace';
        ctx.fillText(`||| | |||| || | |||  ${dateStr}  ||| ||| |`, W / 2, footerY + 110);
    }

    // --- THEME 3: Nusantara Modern Batik ---
    function renderBatikNusantaraTheme(ctx, W, H, poses, caption, dateStr) {
        // Latte Kraft Background
        ctx.fillStyle = '#fefce8';
        ctx.fillRect(0, 0, W, H);

        // Ornate Terracotta Border
        ctx.strokeStyle = '#9a3412';
        ctx.lineWidth = 30;
        ctx.strokeRect(15, 15, W - 30, H - 30);

        ctx.strokeStyle = '#d97706';
        ctx.lineWidth = 4;
        ctx.strokeRect(45, 45, W - 90, H - 90);

        // Header Plate
        ctx.fillStyle = '#7c2d12';
        ctx.beginPath();
        ctx.roundRect(80, 80, W - 160, 150, 20);
        ctx.fill();

        ctx.fillStyle = '#fef08a';
        ctx.font = '900 44px "Cinzel", serif';
        ctx.textAlign = 'center';
        ctx.fillText('NUSANTARA HERITAGE', W / 2, 145);

        ctx.fillStyle = '#fed7aa';
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

            ctx.fillStyle = '#fef3c7';
            ctx.beginPath();
            ctx.roundRect(photoX - 8, posY - 8, photoW + 16, photoH + 16, 20);
            ctx.fill();

            ctx.save();
            ctx.beginPath();
            ctx.roundRect(photoX, posY, photoW, photoH, 16);
            ctx.clip();
            ctx.drawImage(pose, photoX, posY, photoW, photoH);
            ctx.restore();

            ctx.lineWidth = 3;
            ctx.strokeStyle = '#b45309';
            ctx.strokeRect(photoX, posY, photoW, photoH);
        });

        // Bottom Plate
        const footerY = startY + 3 * (photoH + gapY) + 30;
        ctx.fillStyle = '#7c2d12';
        ctx.beginPath();
        ctx.roundRect(80, footerY, W - 160, 210, 20);
        ctx.fill();

        ctx.fillStyle = '#fef08a';
        ctx.font = '800 36px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(caption || 'SATURDAY FELLOWSHIP', W / 2, footerY + 80);

        ctx.fillStyle = '#fed7aa';
        ctx.font = '600 24px "JetBrains Mono", monospace';
        ctx.fillText(dateStr, W / 2, footerY + 140);
    }

    // --- THEME 4: Retro Kodachrome 1945 (Film Analog Perforations) ---
    function renderRetroKodakTheme(ctx, W, H, poses, caption, dateStr) {
        // Dark Slate Analog Film Border
        ctx.fillStyle = '#18181b';
        ctx.fillRect(0, 0, W, H);

        // Film Sprocket Holes along left and right margins
        ctx.fillStyle = '#ffffff';
        const numHoles = 32;
        const holeH = 40;
        const holeW = 26;
        const holeGap = (H - 100) / numHoles;

        for (let i = 0; i < numHoles; i++) {
            const hY = 50 + i * holeGap;
            // Left Sprocket
            ctx.beginPath();
            ctx.roundRect(24, hY, holeW, holeH, 6);
            ctx.fill();

            // Right Sprocket
            ctx.beginPath();
            ctx.roundRect(W - 24 - holeW, hY, holeW, holeH, 6);
            ctx.fill();
        }

        // Header Typewriter Text
        ctx.fillStyle = '#fbbf24';
        ctx.font = '800 32px "JetBrains Mono", monospace';
        ctx.textAlign = 'left';
        ctx.fillText('SAFETY FILM 1945', 90, 110);

        ctx.textAlign = 'right';
        ctx.fillText('ISO 400 • KP45', W - 90, 110);

        // 3 Photo Cutouts
        const photoW = 780;
        const photoH = 585;
        const photoX = (W - photoW) / 2;
        const startY = 160;
        const gapY = 70;

        poses.forEach((pose, idx) => {
            const posY = startY + idx * (photoH + gapY);

            ctx.save();
            ctx.drawImage(pose, photoX, posY, photoW, photoH);
            ctx.restore();

            ctx.lineWidth = 2;
            ctx.strokeStyle = '#52525b';
            ctx.strokeRect(photoX, posY, photoW, photoH);

            // Film frame marker
            ctx.fillStyle = '#a1a1aa';
            ctx.font = '700 20px "JetBrains Mono", monospace';
            ctx.textAlign = 'left';
            ctx.fillText(`FRAME ${idx + 1}A  ••••`, photoX, posY + photoH + 30);
        });

        // Bottom Typewriter Notes
        const footerY = startY + 3 * (photoH + gapY) + 50;
        
        ctx.fillStyle = '#ffffff';
        ctx.font = '900 38px "Space Grotesk", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(caption || 'GKI BROMO YOUTH FELLOWSHIP', W / 2, footerY + 50);

        ctx.fillStyle = '#fbbf24';
        ctx.font = '700 24px "JetBrains Mono", monospace';
        ctx.fillText(`${dateStr} • MALANG`, W / 2, footerY + 110);
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
            width: 175,
            height: 175,
            colorDark: "#0c0f17",
            colorLight: "#ffffff",
            correctLevel: QRCode.CorrectLevel.M
        });

        resultModal.classList.remove('hidden');

        // Confetti Celebration
        try {
            confetti({
                particleCount: 80,
                spread: 75,
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
