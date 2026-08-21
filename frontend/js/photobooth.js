/**
 * KP45 Special Edition Indonesian Photobooth Engine
 * Zero-Latency Client-Side HTML5 Canvas Processor
 * Komisi Pemuda GKI Bromo Malang
 */

(function () {
    'use strict';

    // State Variables
    let currentStream = null;
    let selectedFrame = 'merah-putih';
    let timerDuration = 3;
    let isMirrored = true;
    let currentFacingMode = 'user'; // 'user' (front) or 'environment' (back)
    let isCapturing = false;

    // DOM Elements
    const video = document.getElementById('video-stream');
    const frameOverlayCanvas = document.getElementById('frame-overlay-canvas');
    const overlayCtx = frameOverlayCanvas ? frameOverlayCanvas.getContext('2d') : null;
    const snapshotCanvas = document.getElementById('snapshot-canvas');
    const snapshotCtx = snapshotCanvas ? snapshotCanvas.getContext('2d') : null;

    const countdownOverlay = document.getElementById('countdown-overlay');
    const countdownNumber = document.getElementById('countdown-number');
    const cameraFlash = document.getElementById('camera-flash');

    const btnCapture = document.getElementById('btn-capture');
    const btnSwitchCam = document.getElementById('btn-switch-cam');
    const btnToggleMirror = document.getElementById('btn-toggle-mirror');
    const timer3sBtn = document.getElementById('timer-3s');
    const timer5sBtn = document.getElementById('timer-5s');
    const customCaptionInput = document.getElementById('custom-caption-input');
    const frameCards = document.querySelectorAll('.frame-card');

    const resultModal = document.getElementById('result-modal');
    const resultImagePreview = document.getElementById('result-image-preview');
    const btnCloseModal = document.getElementById('btn-close-modal');
    const btnRetake = document.getElementById('btn-retake');
    const btnDownload = document.getElementById('btn-download');

    // 1. Camera Stream Management
    async function initCamera() {
        if (currentStream) {
            currentStream.getTracks().forEach(track => track.stop());
        }

        const constraints = {
            video: {
                facingMode: currentFacingMode,
                width: { ideal: 1920 },
                height: { ideal: 1080 }
            },
            audio: false
        };

        try {
            const stream = await navigator.mediaDevices.getUserMedia(constraints);
            currentStream = stream;
            video.srcObject = stream;
            await video.play();
            updateLiveOverlay();
        } catch (err) {
            console.error('Kamera gagal diakses:', err);
            Swal.fire({
                icon: 'error',
                title: 'Akses Kamera Gagal',
                text: 'Mohon izinkan akses kamera di browser Anda untuk menggunakan photobooth.',
                confirmButtonColor: '#ef4444'
            });
        }
    }

    // 2. Camera Controls
    if (btnSwitchCam) {
        btnSwitchCam.addEventListener('click', () => {
            currentFacingMode = currentFacingMode === 'user' ? 'environment' : 'user';
            // Disable mirror by default for back camera
            if (currentFacingMode === 'environment') {
                isMirrored = false;
                video.classList.remove('-scale-x-100');
            } else {
                isMirrored = true;
                video.classList.add('-scale-x-100');
            }
            initCamera();
        });
    }

    if (btnToggleMirror) {
        btnToggleMirror.addEventListener('click', () => {
            isMirrored = !isMirrored;
            if (isMirrored) {
                video.classList.add('-scale-x-100');
            } else {
                video.classList.remove('-scale-x-100');
            }
        });
    }

    // 3. Timer Selection
    if (timer3sBtn && timer5sBtn) {
        timer3sBtn.addEventListener('click', () => {
            timerDuration = 3;
            timer3sBtn.className = 'px-3 py-1.5 text-xs font-mono font-bold rounded-lg bg-rose-600 text-white border border-rose-500 transition-all';
            timer5sBtn.className = 'px-3 py-1.5 text-xs font-mono font-bold rounded-lg bg-obsidian-800 text-slate-400 border border-white/[0.08] hover:text-white transition-all';
        });

        timer5sBtn.addEventListener('click', () => {
            timerDuration = 5;
            timer5sBtn.className = 'px-3 py-1.5 text-xs font-mono font-bold rounded-lg bg-rose-600 text-white border border-rose-500 transition-all';
            timer3sBtn.className = 'px-3 py-1.5 text-xs font-mono font-bold rounded-lg bg-obsidian-800 text-slate-400 border border-white/[0.08] hover:text-white transition-all';
        });
    }

    // 4. Frame Selection
    frameCards.forEach(card => {
        card.addEventListener('click', () => {
            frameCards.forEach(c => c.classList.remove('frame-active'));
            card.classList.add('frame-active');
            selectedFrame = card.getAttribute('data-frame');
            updateLiveOverlay();
        });
    });

    if (customCaptionInput) {
        customCaptionInput.addEventListener('input', () => {
            updateLiveOverlay();
        });
    }

    // 5. Sound Synthesizer (Zero asset dependency)
    function playCameraShutterSound() {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'triangle';
            osc.frequency.setValueAtTime(800, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(120, ctx.currentTime + 0.12);
            gain.gain.setValueAtTime(0.3, ctx.currentTime);
            gain.gain.linearRampToValueAtTime(0.01, ctx.currentTime + 0.12);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.13);
        } catch (e) {
            // Ignore audio context errors
        }
    }

    // 6. Draw Frame Art (Reusable for Live Overlay and Snapshot Canvas)
    function drawFrame(ctx, width, height, isHD = false) {
        const scale = isHD ? width / 360 : 1;
        const caption = customCaptionInput ? customCaptionInput.value.trim() : '';
        const todayStr = new Date().toLocaleDateString('id-ID', {
            day: 'numeric',
            month: 'short',
            year: 'numeric'
        });

        if (selectedFrame === 'merah-putih') {
            // Top Ribbon
            const gradTop = ctx.createLinearGradient(0, 0, 0, 60 * scale);
            gradTop.addColorStop(0, '#dc2626');
            gradTop.addColorStop(1, 'rgba(220, 38, 38, 0)');
            ctx.fillStyle = gradTop;
            ctx.fillRect(0, 0, width, 65 * scale);

            // Red-White Corner Ribbon Banner
            ctx.fillStyle = '#ef4444';
            ctx.fillRect(15 * scale, 15 * scale, 120 * scale, 28 * scale);
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(15 * scale, 43 * scale, 120 * scale, 14 * scale);

            ctx.fillStyle = '#ffffff';
            ctx.font = `900 ${14 * scale}px sans-serif`;
            ctx.fillText('KP 45', 24 * scale, 34 * scale);

            ctx.fillStyle = '#991b1b';
            ctx.font = `800 ${9 * scale}px sans-serif`;
            ctx.fillText('EDISI NUSANTARA', 24 * scale, 53 * scale);

            // Bottom Banner
            const bannerH = 75 * scale;
            const bannerY = height - bannerH;

            ctx.fillStyle = 'rgba(15, 23, 42, 0.92)';
            ctx.fillRect(0, bannerY, width, bannerH);

            // Red accent line
            ctx.fillStyle = '#ef4444';
            ctx.fillRect(0, bannerY, width, 4 * scale);

            ctx.fillStyle = '#ffffff';
            ctx.font = `bold ${13 * scale}px sans-serif`;
            ctx.fillText(caption || 'Komisi Pemuda GKI Bromo Malang', 20 * scale, bannerY + 30 * scale);

            ctx.fillStyle = '#94a3b8';
            ctx.font = `${10 * scale}px sans-serif`;
            ctx.fillText(`Saturday Fellowship • ${todayStr}`, 20 * scale, bannerY + 52 * scale);

            // Gold Star Badge
            ctx.fillStyle = '#fbbf24';
            ctx.font = `bold ${18 * scale}px sans-serif`;
            ctx.fillText('KP45', width - 85 * scale, bannerY + 42 * scale);

        } else if (selectedFrame === 'batik-gold') {
            // Ornate Gold Border
            const borderW = 12 * scale;
            ctx.strokeStyle = '#d97706';
            ctx.lineWidth = borderW;
            ctx.strokeRect(borderW / 2, borderW / 2, width - borderW, height - borderW);

            // Inner Gold Line
            ctx.strokeStyle = '#fef3c7';
            ctx.lineWidth = 2 * scale;
            ctx.strokeRect(borderW + 6 * scale, borderW + 6 * scale, width - (borderW * 2 + 12 * scale), height - (borderW * 2 + 12 * scale));

            // Corner Batik Accent Diamonds
            function drawDiamond(cx, cy, s) {
                ctx.fillStyle = '#b45309';
                ctx.beginPath();
                ctx.moveTo(cx, cy - s);
                ctx.lineTo(cx + s, cy);
                ctx.lineTo(cx, cy + s);
                ctx.lineTo(cx - s, cy);
                ctx.closePath();
                ctx.fill();
                ctx.strokeStyle = '#fbbf24';
                ctx.lineWidth = 2 * scale;
                ctx.stroke();
            }

            const cornerOff = 25 * scale;
            drawDiamond(cornerOff, cornerOff, 10 * scale);
            drawDiamond(width - cornerOff, cornerOff, 10 * scale);
            drawDiamond(cornerOff, height - cornerOff, 10 * scale);
            drawDiamond(width - cornerOff, height - cornerOff, 10 * scale);

            // Bottom Plate
            const plateH = 65 * scale;
            const plateY = height - plateH - borderW;

            ctx.fillStyle = 'rgba(24, 24, 27, 0.95)';
            ctx.fillRect(borderW, plateY, width - (borderW * 2), plateH);

            ctx.fillStyle = '#fef08a';
            ctx.font = `bold ${13 * scale}px serif`;
            ctx.textAlign = 'center';
            ctx.fillText(caption || 'KOMISI PEMUDA GKI BROMO', width / 2, plateY + 28 * scale);

            ctx.fillStyle = '#d4d4d8';
            ctx.font = `italic ${10 * scale}px serif`;
            ctx.fillText(`Special Event KP45 • ${todayStr}`, width / 2, plateY + 48 * scale);
            ctx.textAlign = 'left';

        } else if (selectedFrame === 'retro-polaroid') {
            // White Polaroid Border
            const sideBorder = 14 * scale;
            const topBorder = 14 * scale;
            const bottomBorder = 85 * scale;

            ctx.fillStyle = '#f8fafc';
            ctx.fillRect(0, 0, width, topBorder);
            ctx.fillRect(0, 0, sideBorder, height);
            ctx.fillRect(width - sideBorder, 0, sideBorder, height);
            ctx.fillRect(0, height - bottomBorder, width, bottomBorder);

            // Bottom Border Divider Line
            ctx.fillStyle = '#e2e8f0';
            ctx.fillRect(sideBorder, height - bottomBorder, width - (sideBorder * 2), 2 * scale);

            // Handwritten-style text
            ctx.fillStyle = '#0f172a';
            ctx.font = `900 ${15 * scale}px sans-serif`;
            ctx.fillText(caption || 'Youth on Fire!', 25 * scale, height - 48 * scale);

            ctx.fillStyle = '#64748b';
            ctx.font = `600 ${11 * scale}px monospace`;
            ctx.fillText(`GKI BROMO KP45 • ${todayStr}`, 25 * scale, height - 26 * scale);

            // Stamp sticker
            ctx.fillStyle = '#ef4444';
            ctx.fillRect(width - 85 * scale, height - 68 * scale, 65 * scale, 45 * scale);
            ctx.fillStyle = '#ffffff';
            ctx.font = `bold ${10 * scale}px sans-serif`;
            ctx.fillText('MALANG', width - 80 * scale, height - 48 * scale);
            ctx.font = `900 ${14 * scale}px sans-serif`;
            ctx.fillText('2026', width - 77 * scale, height - 30 * scale);
        }
    }

    // 7. Live Preview Overlay Update
    function updateLiveOverlay() {
        if (!frameOverlayCanvas || !overlayCtx || !video) return;
        const rect = frameOverlayCanvas.getBoundingClientRect();
        frameOverlayCanvas.width = rect.width;
        frameOverlayCanvas.height = rect.height;
        overlayCtx.clearRect(0, 0, frameOverlayCanvas.width, frameOverlayCanvas.height);
        drawFrame(overlayCtx, frameOverlayCanvas.width, frameOverlayCanvas.height, false);
    }

    window.addEventListener('resize', updateLiveOverlay);

    // 8. Capture & High-Res Snapshot Flow
    async function triggerCapture() {
        if (isCapturing || !video.srcObject) return;
        isCapturing = true;

        countdownOverlay.classList.remove('hidden');
        let remaining = timerDuration;
        countdownNumber.textContent = remaining;

        const interval = setInterval(() => {
            remaining--;
            if (remaining > 0) {
                countdownNumber.textContent = remaining;
            } else {
                clearInterval(interval);
                takeSnapshot();
            }
        }, 1000);
    }

    function takeSnapshot() {
        countdownOverlay.classList.add('hidden');

        // Camera Flash Animation & Sound
        playCameraShutterSound();
        cameraFlash.classList.remove('hidden');
        cameraFlash.classList.add('flash-animation');
        setTimeout(() => {
            cameraFlash.classList.add('hidden');
            cameraFlash.classList.remove('flash-animation');
        }, 400);

        // Render High-Resolution Composite Image (1080 x 1350)
        const HD_WIDTH = 1080;
        const HD_HEIGHT = 1350;

        snapshotCanvas.width = HD_WIDTH;
        snapshotCanvas.height = HD_HEIGHT;

        snapshotCtx.save();

        // 1. Draw Video Frame (Center-crop to 4:5 aspect ratio)
        const vW = video.videoWidth || 1280;
        const vH = video.videoHeight || 720;
        const targetAspect = HD_WIDTH / HD_HEIGHT;
        const videoAspect = vW / vH;

        let srcX = 0, srcY = 0, srcW = vW, srcH = vH;
        if (videoAspect > targetAspect) {
            srcW = vH * targetAspect;
            srcX = (vW - srcW) / 2;
        } else {
            srcH = vW / targetAspect;
            srcY = (vH - srcH) / 2;
        }

        // Handle Mirroring
        if (isMirrored) {
            snapshotCtx.translate(HD_WIDTH, 0);
            snapshotCtx.scale(-1, 1);
        }

        snapshotCtx.drawImage(video, srcX, srcY, srcW, srcH, 0, 0, HD_WIDTH, HD_HEIGHT);
        snapshotCtx.restore();

        // 2. Overlay HD Frame Art & Text
        drawFrame(snapshotCtx, HD_WIDTH, HD_HEIGHT, true);

        // 3. Export High-Res Data URL
        const dataUrl = snapshotCanvas.toDataURL('image/jpeg', 0.95);
        resultImagePreview.src = dataUrl;
        btnDownload.href = dataUrl;
        btnDownload.download = `KP45_Photobooth_${Date.now()}.jpg`;

        // Confetti celebration
        if (typeof confetti === 'function') {
            confetti({
                particleCount: 70,
                spread: 60,
                origin: { y: 0.6 },
                colors: ['#ef4444', '#ffffff', '#fbbf24']
            });
        }

        resultModal.classList.remove('hidden');
        isCapturing = false;
    }

    if (btnCapture) {
        btnCapture.addEventListener('click', triggerCapture);
    }

    if (btnCloseModal) {
        btnCloseModal.addEventListener('click', () => {
            resultModal.classList.add('hidden');
        });
    }

    if (btnRetake) {
        btnRetake.addEventListener('click', () => {
            resultModal.classList.add('hidden');
        });
    }

    // Initialize on page load
    window.addEventListener('load', () => {
        initCamera();
    });

})();
