// --- KP45 Photo Strip & Animated GIF Engine ---
document.addEventListener('DOMContentLoaded', () => {
    // Stages & Layouts
    const welcomeStage = document.getElementById('welcome-stage');
    const cameraStage = document.getElementById('camera-stage');
    const layoutCards = document.querySelectorAll('.layout-card');
    const customCaptionInput = document.getElementById('custom-caption-input');
    const btnStartSession = document.getElementById('btn-start-session');
    const btnCancelSession = document.getElementById('btn-cancel-session');

    // Camera & Viewfinder Elements
    const previewVideo = document.getElementById('preview-video');
    const video = document.getElementById('video-stream');
    const poseIndicatorText = document.getElementById('pose-indicator-text');
    const centerCountdown = document.getElementById('center-countdown');
    const countdownNumber = document.getElementById('countdown-number');
    const cameraFlash = document.getElementById('camera-flash');
    const poseDotsContainer = document.getElementById('pose-dots-container');

    // Retake Elements
    const retakeQuotaBadge = document.getElementById('retake-quota-badge');
    const retakeCountText = document.getElementById('retake-count-text');
    const poseReviewOverlay = document.getElementById('pose-review-overlay');
    const poseReviewThumb = document.getElementById('pose-review-thumb');
    const poseReviewTitle = document.getElementById('pose-review-title');
    const poseReviewTimerText = document.getElementById('pose-review-timer-text');
    const btnRetakePose = document.getElementById('btn-retake-pose');
    const retakeQuotaBtnText = document.getElementById('retake-quota-btn-text');
    const btnNextPose = document.getElementById('btn-next-pose');

    // Camera & Mirror Controls
    const btnToggleMirrorWelcome = document.getElementById('btn-toggle-mirror-welcome');
    const btnSwitchCamWelcome = document.getElementById('btn-switch-cam-welcome');
    const btnToggleMirror = document.getElementById('btn-toggle-mirror');
    const btnSwitchCam = document.getElementById('btn-switch-cam');
    const timer3sBtn = document.getElementById('timer-3s');
    const timer5sBtn = document.getElementById('timer-5s');

    // Result Modal & Dispenser Elements
    const resultModal = document.getElementById('result-modal');
    const stitchPhotostripWrapper = document.getElementById('stitch-photostrip-wrapper');
    const stripPreviewPhoto1 = document.getElementById('strip-preview-photo-1');
    const stripPreviewPhoto2 = document.getElementById('strip-preview-photo-2');
    const stripPreviewPhoto3 = document.getElementById('strip-preview-photo-3');
    const stripPreviewMessage = document.getElementById('strip-preview-message');
    const stripPreviewDate = document.getElementById('strip-preview-date');
    const canvasPhotostripWrapper = document.getElementById('canvas-photostrip-wrapper');
    const gifPreviewWrapper = document.getElementById('gif-preview-wrapper');
    const resultStripImg = document.getElementById('result-strip-img');
    const resultGifImg = document.getElementById('result-gif-img');
    const tabShowStrip = document.getElementById('tab-show-strip');
    const tabShowGif = document.getElementById('tab-show-gif');
    const qrCodeContainer = document.getElementById('qr-code-container');
    const btnDownloadStrip = document.getElementById('btn-download-strip');
    const btnDownloadGif = document.getElementById('btn-download-gif');
    const btnRetake = document.getElementById('btn-retake');
    const btnCloseModal = document.getElementById('btn-close-modal');
    const autoResetTimerEl = document.getElementById('auto-reset-timer');
    const modalCustomCaption = document.getElementById('modal-custom-caption');

    // State Variables
    let currentStream = null;
    let isMirrored = true;
    let currentFacingMode = 'user';
    let selectedLayout = '3-strip';
    let targetPoses = 3;
    let timerDuration = 3;
    let remainingRetakes = 3;
    let isSessionRunning = false;
    let capturedPoses = []; // Array of snapshot canvases
    let countdownInterval = null;
    let reviewInterval = null;
    let reviewResolver = null;
    let autoResetInterval = null;
    let qrCodeInstance = null;

    // --- 1. Web Audio API Physical Sound Synthesizer ---
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

    function playPrinterSound() {
        if (audioCtx.state === 'suspended') audioCtx.resume();
        const bufferSize = audioCtx.sampleRate * 0.6;
        const buffer = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) {
            data[i] = ((Math.random() * 2 - 1) * 0.3) * (1 - i / bufferSize);
        }
        const noise = audioCtx.createBufferSource();
        noise.buffer = buffer;
        const filter = audioCtx.createBiquadFilter();
        filter.type = 'lowpass';
        filter.frequency.value = 800;
        noise.connect(filter);
        filter.connect(audioCtx.destination);
        noise.start();
    }

    // --- 2. Layout Selection Handling ---
    layoutCards.forEach(card => {
        card.addEventListener('click', () => {
            layoutCards.forEach(c => c.classList.remove('layout-card-active'));
            card.classList.add('layout-card-active');
            selectedLayout = card.getAttribute('data-layout');
            targetPoses = parseInt(card.getAttribute('data-poses'), 10) || 3;
        });
    });

    // Timer Selector Buttons (on Welcome Stage)
    if (timer3sBtn) {
        timer3sBtn.addEventListener('click', () => {
            timerDuration = 3;
            timer3sBtn.className = "flex-1 py-2 px-3 text-xs font-display font-extrabold rounded-2xl bg-merdeka-navy text-white border-2 border-merdeka-navy shadow-pesta-sm transition-all cursor-pointer flex items-center justify-center gap-1.5";
            timer5sBtn.className = "flex-1 py-2 px-3 text-xs font-display font-extrabold rounded-2xl bg-merdeka-surface-container text-merdeka-navy border-2 border-merdeka-navy hover:bg-white transition-all cursor-pointer flex items-center justify-center gap-1.5";
        });
    }

    if (timer5sBtn) {
        timer5sBtn.addEventListener('click', () => {
            timerDuration = 5;
            timer5sBtn.className = "flex-1 py-2 px-3 text-xs font-display font-extrabold rounded-2xl bg-merdeka-navy text-white border-2 border-merdeka-navy shadow-pesta-sm transition-all cursor-pointer flex items-center justify-center gap-1.5";
            timer3sBtn.className = "flex-1 py-2 px-3 text-xs font-display font-extrabold rounded-2xl bg-merdeka-surface-container text-merdeka-navy border-2 border-merdeka-navy hover:bg-white transition-all cursor-pointer flex items-center justify-center gap-1.5";
        });
    }

    // Camera Controls (Mirror & Switch)
    function applyMirrorState() {
        if (previewVideo) previewVideo.classList.toggle('-scale-x-100', isMirrored);
        if (video) video.classList.toggle('-scale-x-100', isMirrored);
    }

    function toggleMirror() {
        isMirrored = !isMirrored;
        applyMirrorState();
    }

    let availableVideoDevices = [];
    let currentDeviceIndex = 0;

    async function refreshVideoDevices() {
        try {
            const devices = await navigator.mediaDevices.enumerateDevices();
            availableVideoDevices = devices.filter(d => d.kind === 'videoinput');
        } catch (e) {
            availableVideoDevices = [];
        }
    }

    async function switchCamera() {
        await refreshVideoDevices();
        if (availableVideoDevices.length > 1) {
            currentDeviceIndex = (currentDeviceIndex + 1) % availableVideoDevices.length;
            const targetDevice = availableVideoDevices[currentDeviceIndex];
            await startCameraWithDeviceId(targetDevice.deviceId);
        } else {
            currentFacingMode = currentFacingMode === 'user' ? 'environment' : 'user';
            isMirrored = (currentFacingMode === 'user');
            applyMirrorState();
            await startCamera();
        }
    }

    if (btnToggleMirrorWelcome) btnToggleMirrorWelcome.addEventListener('click', toggleMirror);
    if (btnToggleMirror) btnToggleMirror.addEventListener('click', toggleMirror);
    if (btnSwitchCamWelcome) btnSwitchCamWelcome.addEventListener('click', switchCamera);
    if (btnSwitchCam) btnSwitchCam.addEventListener('click', switchCamera);

    async function startCameraWithDeviceId(deviceId) {
        if (currentStream) {
            currentStream.getTracks().forEach(track => track.stop());
            currentStream = null;
        }
        try {
            const constraints = {
                video: {
                    deviceId: { exact: deviceId },
                    width: { ideal: 1920 },
                    height: { ideal: 1080 }
                },
                audio: false
            };
            currentStream = await navigator.mediaDevices.getUserMedia(constraints);
            if (previewVideo) previewVideo.srcObject = currentStream;
            if (video) video.srcObject = currentStream;

            const activeTrack = currentStream.getVideoTracks()[0];
            const label = (activeTrack && activeTrack.label) ? activeTrack.label.toLowerCase() : '';
            if (label.includes('back') || label.includes('rear') || label.includes('environment')) {
                isMirrored = false;
            } else if (label.includes('iphone')) {
                isMirrored = false;
            } else {
                isMirrored = true;
            }
            applyMirrorState();
        } catch (err) {
            console.warn("Device switch fallback:", err);
            await startCamera();
        }
    }

    async function startCamera() {
        if (currentStream) {
            currentStream.getTracks().forEach(track => track.stop());
            currentStream = null;
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
            if (previewVideo) previewVideo.srcObject = currentStream;
            if (video) video.srcObject = currentStream;
            applyMirrorState();
            await refreshVideoDevices();
        } catch (err) {
            console.error("Camera access error:", err);
            Swal.fire({
                title: 'Akses Kamera Diperlukan',
                text: 'Harap izinkan akses kamera pada peramban Anda untuk memulai Photobooth.',
                icon: 'error',
                background: '#fff8f1',
                color: '#211b0b',
                confirmButtonColor: '#b7102a'
            });
        }
    }

    // --- 3. Stage Navigation & Burst Capture Loop ---
    btnStartSession.addEventListener('click', async () => {
        welcomeStage.classList.add('hidden');
        cameraStage.classList.remove('hidden');
        renderPoseDots();
        if (!currentStream || !currentStream.active) {
            await startCamera();
        }
        setTimeout(runMultiPoseCaptureSequence, 600);
    });

    btnCancelSession.addEventListener('click', returnToWelcomeStage);

    function returnToWelcomeStage() {
        isSessionRunning = false;
        if (countdownInterval) { clearInterval(countdownInterval); countdownInterval = null; }
        if (reviewInterval) { clearInterval(reviewInterval); reviewInterval = null; }
        if (reviewResolver) { reviewResolver('cancel'); reviewResolver = null; }

        if (centerCountdown) centerCountdown.classList.add('hidden');
        if (poseReviewOverlay) poseReviewOverlay.classList.add('hidden');

        cameraStage.classList.add('hidden');
        welcomeStage.classList.remove('hidden');
        remainingRetakes = 2;
        updateRetakeQuotaUI();
    }

    function renderPoseDots() {
        poseDotsContainer.innerHTML = '';
        for (let i = 0; i < targetPoses; i++) {
            const dot = document.createElement('span');
            dot.id = `dot-pose-${i}`;
            dot.className = "w-7 h-2.5 rounded-full bg-merdeka-surface-dim border border-merdeka-navy/30 transition-all";
            poseDotsContainer.appendChild(dot);
        }
    }

    function updatePoseDot(index, state) {
        const dot = document.getElementById(`dot-pose-${index}`);
        if (!dot) return;
        if (state === 'active') {
            dot.className = "w-9 h-2.5 rounded-full bg-merdeka-red shadow-pesta-sm transition-all border-2 border-merdeka-navy";
        } else if (state === 'done') {
            dot.className = "w-7 h-2.5 rounded-full bg-merdeka-navy shadow-pesta-sm transition-all border-2 border-merdeka-navy";
        }
    }

    function updateRetakeQuotaUI() {
        if (retakeCountText) retakeCountText.innerText = `${remainingRetakes}x`;
        if (retakeQuotaBtnText) retakeQuotaBtnText.innerText = `${remainingRetakes}x`;
        if (btnRetakePose) {
            btnRetakePose.disabled = (remainingRetakes <= 0);
            if (remainingRetakes <= 0) {
                btnRetakePose.classList.add('opacity-40', 'cursor-not-allowed');
            } else {
                btnRetakePose.classList.remove('opacity-40', 'cursor-not-allowed');
            }
        }
    }

    function showPoseReview(poseIndex, frameCanvas) {
        return new Promise(resolve => {
            if (reviewInterval) clearInterval(reviewInterval);
            reviewResolver = resolve;

            if (poseReviewThumb) {
                poseReviewThumb.src = frameCanvas.toDataURL('image/jpeg', 0.85);
            }
            if (poseReviewTitle) {
                poseReviewTitle.innerText = `Pose ${poseIndex + 1} Tersimpan`;
            }
            updateRetakeQuotaUI();

            if (poseReviewOverlay) {
                poseReviewOverlay.classList.remove('hidden');
            }

            let reviewRemainingMs = 3500;
            if (poseReviewTimerText) {
                poseReviewTimerText.innerText = `Lanjut otomatis (${(reviewRemainingMs / 1000).toFixed(1)}s)`;
            }

            reviewInterval = setInterval(() => {
                reviewRemainingMs -= 100;
                if (poseReviewTimerText) {
                    poseReviewTimerText.innerText = `Lanjut otomatis (${Math.max(0, reviewRemainingMs / 1000).toFixed(1)}s)`;
                }

                if (reviewRemainingMs <= 0) {
                    clearInterval(reviewInterval);
                    reviewInterval = null;
                    if (poseReviewOverlay) poseReviewOverlay.classList.add('hidden');
                    reviewResolver = null;
                    resolve('proceed');
                }
            }, 100);
        });
    }

    if (btnRetakePose) {
        btnRetakePose.addEventListener('click', () => {
            if (remainingRetakes > 0 && reviewResolver) {
                if (reviewInterval) clearInterval(reviewInterval);
                reviewInterval = null;
                if (poseReviewOverlay) poseReviewOverlay.classList.add('hidden');
                const resolver = reviewResolver;
                reviewResolver = null;
                resolver('retake');
            }
        });
    }

    if (btnNextPose) {
        btnNextPose.addEventListener('click', () => {
            if (reviewResolver) {
                if (reviewInterval) clearInterval(reviewInterval);
                reviewInterval = null;
                if (poseReviewOverlay) poseReviewOverlay.classList.add('hidden');
                const resolver = reviewResolver;
                reviewResolver = null;
                resolver('proceed');
            }
        });
    }

    async function runMultiPoseCaptureSequence() {
        if (isSessionRunning) return;
        isSessionRunning = true;
        capturedPoses = [];

        for (let i = 0; i < targetPoses; i++) {
            let currentPoseIndex = i;
            let poseAccepted = false;
            
            // Jatah retake 2x per ronde pose (restart setiap pose baru)
            remainingRetakes = 2;
            updateRetakeQuotaUI();

            while (!poseAccepted && isSessionRunning) {
                poseIndicatorText.innerText = `Pose ${currentPoseIndex + 1} dari ${targetPoses}`;
                updatePoseDot(currentPoseIndex, 'active');

                // 1. Center Floating Non-Intrusive Countdown (VIEWFINDER 100% CLEAR)
                const countdownSuccess = await runCenterCountdown(timerDuration);
                if (!countdownSuccess || !isSessionRunning) return;

                // 2. Flash & Mechanical Shutter
                triggerFlash();
                playShutterSound();
                const poseCanvas = captureSingleFrame();
                capturedPoses.push(poseCanvas);
                updatePoseDot(currentPoseIndex, 'done');

                // 3. Per-Pose Review Overlay (3.5s review with retake quota)
                const reviewAction = await showPoseReview(currentPoseIndex, poseCanvas);

                if (reviewAction === 'retake') {
                    remainingRetakes--;
                    updateRetakeQuotaUI();
                    capturedPoses.pop(); // Discard the retaken pose
                    poseAccepted = false;
                    updatePoseDot(currentPoseIndex, 'active');
                    await new Promise(r => setTimeout(r, 400));
                } else if (reviewAction === 'proceed') {
                    poseAccepted = true;
                    if (i < targetPoses - 1) {
                        await new Promise(r => setTimeout(r, 600));
                    }
                } else {
                    // Session canceled
                    return;
                }
            }
        }

        if (!isSessionRunning) return;

        poseIndicatorText.innerText = "Merangkai Foto...";
        await new Promise(r => setTimeout(r, 400));

        // 4. Generate Composite Strip & Animated GIF
        await processAndDeliverOutputs();

        isSessionRunning = false;
    }

    function runCenterCountdown(seconds) {
        return new Promise(resolve => {
            if (countdownInterval) clearInterval(countdownInterval);
            if (!centerCountdown || !countdownNumber) {
                resolve(true);
                return;
            }

            centerCountdown.classList.remove('hidden');
            let remaining = seconds;
            countdownNumber.innerText = remaining;
            playBeep(660, 0.1);

            countdownInterval = setInterval(() => {
                remaining--;
                if (!isSessionRunning) {
                    clearInterval(countdownInterval);
                    countdownInterval = null;
                    centerCountdown.classList.add('hidden');
                    resolve(false);
                    return;
                }

                if (remaining > 0) {
                    countdownNumber.innerText = remaining;
                    const badge = countdownNumber.parentElement;
                    if (badge) {
                        badge.classList.remove('animate-bounce');
                        void badge.offsetWidth;
                        badge.classList.add('animate-bounce');
                    }
                    playBeep(660, 0.1);
                } else {
                    clearInterval(countdownInterval);
                    countdownInterval = null;
                    centerCountdown.classList.add('hidden');
                    playBeep(1200, 0.2);
                    resolve(true);
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

    // Initialize Camera immediately on Landing Page
    startCamera();

    function captureSingleFrame() {
        const frameCanvas = document.createElement('canvas');
        const vW = video.videoWidth || 1280;
        const vH = video.videoHeight || 960;
        
        // Exact 4:3 Ratio for Crisp Portrait Slots (960x720)
        const targetW = 960;
        const targetH = 720;
        frameCanvas.width = targetW;
        frameCanvas.height = targetH;
        const ctx = frameCanvas.getContext('2d');

        let srcX = 0, srcY = 0, srcW = vW, srcH = vH;
        const videoRatio = vW / vH;
        const targetRatio = targetW / targetH;

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

        return frameCanvas;
    }

    function drawImageCover(ctx, img, dx, dy, dw, dh) {
        const imgW = img.width || img.videoWidth || 960;
        const imgH = img.height || img.videoHeight || 720;
        const imgRatio = imgW / imgH;
        const targetRatio = dw / dh;

        let sx = 0, sy = 0, sw = imgW, sh = imgH;

        if (imgRatio > targetRatio) {
            sw = imgH * targetRatio;
            sx = (imgW - sw) / 2;
        } else {
            sh = imgW / targetRatio;
            sy = (imgH - sh) / 2;
        }

        ctx.drawImage(img, sx, sy, sw, sh, dx, dy, dw, dh);
    }

    // --- 4. Editorial High-End Canvas Compositor (Stitch KP45 Design) ---
    function getCustomCaption() {
        return (modalCustomCaption ? modalCustomCaption.value : '').trim();
    }

    function renderCompositeStripCanvas() {
        const stripCanvas = document.createElement('canvas');
        const customCaption = getCustomCaption();
        const todayStr = new Intl.DateTimeFormat('id-ID', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date()).toUpperCase();

        let STRIP_W = 1080;
        let STRIP_H = 1920;

        if (selectedLayout === '4-strip') {
            STRIP_W = 1080;
            STRIP_H = 2480;
        } else if (selectedLayout === '2x2-grid') {
            STRIP_W = 1600;
            STRIP_H = 1800;
        } else if (selectedLayout === 'single-wide') {
            STRIP_W = 1200;
            STRIP_H = 1500;
        }

        stripCanvas.width = STRIP_W;
        stripCanvas.height = STRIP_H;
        const ctx = stripCanvas.getContext('2d');

        if (selectedLayout === '3-strip') {
            renderVertical3StripStitch(ctx, STRIP_W, STRIP_H, capturedPoses, customCaption, todayStr);
        } else if (selectedLayout === '4-strip') {
            renderVertical4Strip(ctx, STRIP_W, STRIP_H, capturedPoses, customCaption, todayStr);
        } else if (selectedLayout === '2x2-grid') {
            renderBentoEditorialGrid(ctx, STRIP_W, STRIP_H, capturedPoses, customCaption, todayStr);
        } else {
            renderSingleWideEditorial(ctx, STRIP_W, STRIP_H, capturedPoses[0], customCaption, todayStr);
        }

        return stripCanvas;
    }

    function renderVertical3StripStitch(ctx, W, H, poses, caption, dateStr) {
        // 1. Pure Crisp White Canvas
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, W, H);

        const sideBarW = 125;
        const centerAreaW = W - (sideBarW * 2); // 1080 - 250 = 830
        const photoMarginX = 35;
        const photoW = centerAreaW - (photoMarginX * 2); // 830 - 70 = 760
        const photoH = Math.round(photoW * 0.75); // 760 * 0.75 = 570 (Exact 4:3 Aspect Ratio)
        const gapY = 16;
        const startY = 24;

        // 2. Draw 3 Photos with 4:3 object-fit cover
        poses.forEach((pose, idx) => {
            if (idx < 3) {
                const posY = startY + idx * (photoH + gapY);
                const posX = sideBarW + photoMarginX;
                drawImageCover(ctx, pose, posX, posY, photoW, photoH);
            }
        });

        // 3. Bottom White Footer Area (Generous breathing room)
        const footerY = startY + 3 * (photoH + gapY);
        if (caption && caption.trim().length > 0) {
            ctx.fillStyle = '#b7102a';
            ctx.font = '800 36px "Bricolage Grotesque", "Plus Jakarta Sans", sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(caption.trim(), W / 2, footerY + 45);

            ctx.fillStyle = '#211b0b';
            ctx.font = '700 18px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(`${dateStr} • MALANG`, W / 2, footerY + 85);
        } else {
            ctx.fillStyle = '#211b0b';
            ctx.font = '700 20px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(`${dateStr} • MALANG`, W / 2, footerY + 65);
        }

        // 4. Left Crimson Red Column with Rotated Typography (Centered with textBaseline = 'middle')
        ctx.fillStyle = '#b7102a';
        ctx.fillRect(0, 0, sideBarW, H);

        // Left Column: Top Subtitle
        ctx.save();
        ctx.translate(sideBarW / 2, 280);
        ctx.rotate(-Math.PI / 2);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
        ctx.font = '700 16px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.letterSpacing = '2px';
        ctx.fillText('KOMISI PEMUDA GKI BROMO MALANG', 0, 0);
        ctx.restore();

        // Left Column: Center Logo (True Mathematical Center)
        ctx.save();
        ctx.translate(sideBarW / 2, H / 2);
        ctx.rotate(-Math.PI / 2);
        ctx.fillStyle = '#ffffff';
        ctx.font = '900 68px "Bricolage Grotesque", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('KP45', 0, 0);
        ctx.restore();

        // Left Column: Bottom Subtitle
        ctx.save();
        ctx.translate(sideBarW / 2, H - 280);
        ctx.rotate(-Math.PI / 2);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
        ctx.font = '700 16px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.letterSpacing = '2px';
        ctx.fillText('KOMISI PEMUDA GKI BROMO MALANG', 0, 0);
        ctx.restore();

        // 5. Right Crimson Red Column with Rotated Typography
        ctx.fillStyle = '#b7102a';
        ctx.fillRect(W - sideBarW, 0, sideBarW, H);

        // Right Column: Top Subtitle
        ctx.save();
        ctx.translate(W - (sideBarW / 2), 280);
        ctx.rotate(Math.PI / 2);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
        ctx.font = '700 16px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.letterSpacing = '2px';
        ctx.fillText('KOMISI PEMUDA GKI BROMO MALANG', 0, 0);
        ctx.restore();

        // Right Column: Center Logo (True Mathematical Center)
        ctx.save();
        ctx.translate(W - (sideBarW / 2), H / 2);
        ctx.rotate(Math.PI / 2);
        ctx.fillStyle = '#ffffff';
        ctx.font = '900 68px "Bricolage Grotesque", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('KP45', 0, 0);
        ctx.restore();

        // Right Column: Bottom Subtitle
        ctx.save();
        ctx.translate(W - (sideBarW / 2), H - 280);
        ctx.rotate(Math.PI / 2);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
        ctx.font = '700 16px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.letterSpacing = '2px';
        ctx.fillText('KOMISI PEMUDA GKI BROMO MALANG', 0, 0);
        ctx.restore();
    }

    function renderVertical4Strip(ctx, W, H, poses, caption, dateStr) {
        // Pure White Canvas & Harmonized Merdeka Theme
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, W, H);

        const sideBarW = 125;
        const centerAreaW = W - (sideBarW * 2);
        const photoMarginX = 35;
        const photoW = centerAreaW - (photoMarginX * 2); // 760
        const photoH = Math.round(photoW * 0.75); // 570 (True 4:3)
        const gapY = 16;
        const startY = 24;

        poses.forEach((pose, idx) => {
            if (idx < 4) {
                const posY = startY + idx * (photoH + gapY);
                const posX = sideBarW + photoMarginX;
                drawImageCover(ctx, pose, posX, posY, photoW, photoH);
            }
        });

        // Bottom Footer
        const footerY = startY + 4 * (photoH + gapY);
        if (caption && caption.trim().length > 0) {
            ctx.fillStyle = '#b7102a';
            ctx.font = '800 36px "Bricolage Grotesque", sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(caption.trim(), W / 2, footerY + 45);

            ctx.fillStyle = '#211b0b';
            ctx.font = '700 18px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(`${dateStr} • MALANG`, W / 2, footerY + 85);
        } else {
            ctx.fillStyle = '#211b0b';
            ctx.font = '700 20px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(`${dateStr} • MALANG`, W / 2, footerY + 65);
        }

        // Left Red Sidebar
        ctx.fillStyle = '#b7102a';
        ctx.fillRect(0, 0, sideBarW, H);

        ctx.save();
        ctx.translate(sideBarW / 2, 340);
        ctx.rotate(-Math.PI / 2);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
        ctx.font = '700 16px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.letterSpacing = '2px';
        ctx.fillText('KOMISI PEMUDA GKI BROMO MALANG', 0, 0);
        ctx.restore();

        ctx.save();
        ctx.translate(sideBarW / 2, H / 2);
        ctx.rotate(-Math.PI / 2);
        ctx.fillStyle = '#ffffff';
        ctx.font = '900 68px "Bricolage Grotesque", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('KP45', 0, 0);
        ctx.restore();

        ctx.save();
        ctx.translate(sideBarW / 2, H - 340);
        ctx.rotate(-Math.PI / 2);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
        ctx.font = '700 16px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.letterSpacing = '2px';
        ctx.fillText('KOMISI PEMUDA GKI BROMO MALANG', 0, 0);
        ctx.restore();

        // Right Red Sidebar
        ctx.fillStyle = '#b7102a';
        ctx.fillRect(W - sideBarW, 0, sideBarW, H);

        ctx.save();
        ctx.translate(W - sideBarW / 2, 340);
        ctx.rotate(Math.PI / 2);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
        ctx.font = '700 16px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.letterSpacing = '2px';
        ctx.fillText('KOMISI PEMUDA GKI BROMO MALANG', 0, 0);
        ctx.restore();

        ctx.save();
        ctx.translate(W - sideBarW / 2, H / 2);
        ctx.rotate(Math.PI / 2);
        ctx.fillStyle = '#ffffff';
        ctx.font = '900 68px "Bricolage Grotesque", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('KP45', 0, 0);
        ctx.restore();

        ctx.save();
        ctx.translate(W - sideBarW / 2, H - 340);
        ctx.rotate(Math.PI / 2);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
        ctx.font = '700 16px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.letterSpacing = '2px';
        ctx.fillText('KOMISI PEMUDA GKI BROMO MALANG', 0, 0);
        ctx.restore();
    }

    function renderBentoEditorialGrid(ctx, W, H, poses, caption, dateStr) {
        // Pure White Canvas & Top Merdeka Red Banner
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, W, H);

        // Top Header Banner
        const bannerH = 130;
        ctx.fillStyle = '#b7102a';
        ctx.fillRect(0, 0, W, bannerH);

        ctx.fillStyle = '#ffffff';
        ctx.font = '800 28px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        ctx.fillText('KOMISI PEMUDA GKI BROMO MALANG', 50, bannerH / 2);

        ctx.fillStyle = '#ffffff';
        ctx.font = '900 64px "Bricolage Grotesque", sans-serif';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';
        ctx.fillText('KP45', W - 50, bannerH / 2);

        // 2x2 Photos in True 4:3 Ratio
        const marginX = 50;
        const gapX = 36;
        const gapY = 24;
        const photoW = Math.round((W - (marginX * 2) - gapX) / 2); // 732px
        const photoH = Math.round(photoW * 0.75); // 549px
        const startY = bannerH + 30;

        poses.forEach((pose, idx) => {
            if (idx < 4) {
                const col = idx % 2;
                const row = Math.floor(idx / 2);
                const pX = marginX + col * (photoW + gapX);
                const pY = startY + row * (photoH + gapY);
                drawImageCover(ctx, pose, pX, pY, photoW, photoH);
            }
        });

        // Bottom Footer
        const footerY = startY + 2 * (photoH + gapY) + 10;
        if (caption && caption.trim().length > 0) {
            ctx.fillStyle = '#b7102a';
            ctx.font = '800 44px "Bricolage Grotesque", sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(caption.trim(), W / 2, footerY + 45);

            ctx.fillStyle = '#211b0b';
            ctx.font = '700 22px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(`${dateStr} • MALANG`, W / 2, footerY + 95);
        } else {
            ctx.fillStyle = '#211b0b';
            ctx.font = '700 26px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(`${dateStr} • MALANG`, W / 2, footerY + 65);
        }
    }

    function renderSingleWideEditorial(ctx, W, H, pose, caption, dateStr) {
        // Pure White Canvas & Left/Right Merdeka Red Bars
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, W, H);

        const sideBarW = 90;
        const centerW = W - (sideBarW * 2);
        const photoW = centerW - 60; // 960px
        const photoH = Math.round(photoW * 0.75); // 720px
        const photoX = sideBarW + 30;
        const photoY = 60;

        if (pose) {
            drawImageCover(ctx, pose, photoX, photoY, photoW, photoH);
        }

        // Left Red Sidebar
        ctx.fillStyle = '#b7102a';
        ctx.fillRect(0, 0, sideBarW, H);

        ctx.save();
        ctx.translate(sideBarW / 2, H / 2);
        ctx.rotate(-Math.PI / 2);
        ctx.fillStyle = '#ffffff';
        ctx.font = '900 54px "Bricolage Grotesque", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('KP45', 0, 0);
        ctx.restore();

        // Right Red Sidebar
        ctx.fillStyle = '#b7102a';
        ctx.fillRect(W - sideBarW, 0, sideBarW, H);

        ctx.save();
        ctx.translate(W - sideBarW / 2, H / 2);
        ctx.rotate(Math.PI / 2);
        ctx.fillStyle = '#ffffff';
        ctx.font = '900 54px "Bricolage Grotesque", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('KP45', 0, 0);
        ctx.restore();

        // Bottom Footer
        const footerY = photoY + photoH + 30;
        if (caption && caption.trim().length > 0) {
            ctx.fillStyle = '#b7102a';
            ctx.font = '800 42px "Bricolage Grotesque", sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(caption.trim(), W / 2, footerY + 50);

            ctx.fillStyle = '#211b0b';
            ctx.font = '700 22px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(`${dateStr} • MALANG`, W / 2, footerY + 100);
        } else {
            ctx.fillStyle = '#211b0b';
            ctx.font = '700 26px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(`${dateStr} • MALANG`, W / 2, footerY + 70);
        }
    }

    // --- 5. Animated Looping Framed GIF Generator ---
    function renderFramedGifFrame(poseCanvas, poseIdx, totalPoses, caption, dateStr) {
        const W = 600;
        const H = 720;
        const canvas = document.createElement('canvas');
        canvas.width = W;
        canvas.height = H;
        const ctx = canvas.getContext('2d');

        // Pure Crisp White Base
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, W, H);

        const sideBarW = 40;
        const photoMarginX = 14;
        const photoW = W - (sideBarW * 2) - (photoMarginX * 2); // 492px
        const photoH = Math.round(photoW * 0.75); // 369px (True 4:3)
        const photoX = sideBarW + photoMarginX;
        const photoY = 18;

        drawImageCover(ctx, poseCanvas, photoX, photoY, photoW, photoH);

        // Left Red Sidebar
        ctx.fillStyle = '#b7102a';
        ctx.fillRect(0, 0, sideBarW, H);

        ctx.save();
        ctx.translate(sideBarW / 2, H / 2);
        ctx.rotate(-Math.PI / 2);
        ctx.fillStyle = '#ffffff';
        ctx.font = '900 24px "Bricolage Grotesque", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('KP45', 0, 0);
        ctx.restore();

        // Right Red Sidebar
        ctx.fillStyle = '#b7102a';
        ctx.fillRect(W - sideBarW, 0, sideBarW, H);

        ctx.save();
        ctx.translate(W - sideBarW / 2, H / 2);
        ctx.rotate(Math.PI / 2);
        ctx.fillStyle = '#ffffff';
        ctx.font = '900 24px "Bricolage Grotesque", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('KP45', 0, 0);
        ctx.restore();

        // Footer Area
        const footerY = photoY + photoH + 16;
        
        // Pose Badge (e.g. "POSE 1/3")
        ctx.fillStyle = '#b7102a';
        ctx.font = '800 13px "JetBrains Mono", monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(`POSE ${poseIdx + 1}/${totalPoses}`, W / 2, footerY + 12);

        if (caption && caption.trim().length > 0) {
            ctx.fillStyle = '#b7102a';
            ctx.font = '800 22px "Bricolage Grotesque", sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(caption.trim(), W / 2, footerY + 44);

            ctx.fillStyle = '#211b0b';
            ctx.font = '700 13px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(`${dateStr} • MALANG`, W / 2, footerY + 76);
        } else {
            ctx.fillStyle = '#211b0b';
            ctx.font = '700 14px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(`${dateStr} • MALANG`, W / 2, footerY + 50);
        }

        return canvas;
    }

    function generateAnimatedGif(poses) {
        return new Promise((resolve) => {
            if (typeof gifshot === 'undefined' || !poses || poses.length === 0) {
                resolve(null);
                return;
            }

            // 2.5 second fallback timeout so UI NEVER hangs
            const timeoutId = setTimeout(() => {
                console.warn("GIF generation timed out, continuing without GIF.");
                resolve(null);
            }, 2500);

            try {
                const customCaption = getCustomCaption();
                const todayStr = new Intl.DateTimeFormat('id-ID', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date()).toUpperCase();

                // Render each frame inside the editorial KP45 frame
                const framedFrames = poses.map((poseCanvas, idx) => {
                    const framedCanvas = renderFramedGifFrame(poseCanvas, idx, poses.length, customCaption, todayStr);
                    return framedCanvas.toDataURL('image/jpeg', 0.85);
                });

                gifshot.createGIF({
                    images: framedFrames,
                    interval: 0.45,
                    gifWidth: 400,
                    gifHeight: 480,
                    numWorkers: 2,
                }, (obj) => {
                    clearTimeout(timeoutId);
                    if (obj && !obj.error && obj.image) {
                        resolve(obj.image);
                    } else {
                        console.error("GIF generation error:", obj ? obj.error : 'Unknown error');
                        resolve(null);
                    }
                });
            } catch (err) {
                clearTimeout(timeoutId);
                console.error("GIF generation exception:", err);
                resolve(null);
            }
        });
    }

    // --- 6. Processing & Output Delivery (Instant Presentation & Asynchronous Upload) ---
    async function processAndDeliverOutputs() {
        const customCaption = getCustomCaption();

        // 1. Generate local HD Photo Strip immediately in memory
        let base64Strip = '';
        try {
            const stripCanvas = renderCompositeStripCanvas();
            base64Strip = stripCanvas.toDataURL('image/jpeg', 0.95);
        } catch (canvasErr) {
            console.error("Error creating composite strip canvas:", canvasErr);
            if (capturedPoses.length > 0) {
                base64Strip = capturedPoses[0].toDataURL('image/jpeg', 0.95);
            }
        }

        // 2. IMMEDIATELY show Result Modal with local assets (Zero waiting for user!)
        showResultModal({ download_url: base64Strip, qr_url: window.location.href }, base64Strip, null);

        // 3. Generate GIF and Upload in background without blocking the user
        (async () => {
            let base64Gif = '';
            try {
                base64Gif = await generateAnimatedGif(capturedPoses);
                if (base64Gif && resultGifImg && btnDownloadGif && tabShowGif) {
                    resultGifImg.src = base64Gif;
                    btnDownloadGif.href = base64Gif;
                    btnDownloadGif.classList.remove('opacity-50', 'pointer-events-none');
                    tabShowGif.classList.remove('hidden');
                }
            } catch (gifErr) {
                console.warn("Background GIF generation skipped:", gifErr);
            }

            // Upload to server for permanent storage & mobile QR code
            try {
                const response = await fetch('/api/photobooth/upload', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        image: base64Strip,
                        gif_image: base64Gif || '',
                        frame: selectedLayout,
                        caption: customCaption
                    })
                });

                if (response.ok) {
                    const data = await response.json();
                    if (data && data.status === 'success') {
                        updateModalWithServerData(data);
                    }
                }
            } catch (uploadErr) {
                console.warn("Background upload error (offline fallback active):", uploadErr);
            }
        })();
    }

    // --- 7. Result Modal Presentation & Skeuomorphic Printing Animation ---
    function showResultModal(uploadData, localStrip, localGif) {
        try { playPrinterSound(); } catch(e) {}

        const customCaption = getCustomCaption();
        const todayStr = new Intl.DateTimeFormat('id-ID', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date()).toUpperCase();

        if (modalCustomCaption) {
            modalCustomCaption.value = customCaption;
        }

        if (selectedLayout === '3-strip' && capturedPoses.length >= 3 && stitchPhotostripWrapper) {
            stitchPhotostripWrapper.classList.remove('hidden');
            if (canvasPhotostripWrapper) canvasPhotostripWrapper.classList.add('hidden');
            
            if (stripPreviewPhoto1 && capturedPoses[0]) stripPreviewPhoto1.src = capturedPoses[0].toDataURL('image/jpeg', 0.95);
            if (stripPreviewPhoto2 && capturedPoses[1]) stripPreviewPhoto2.src = capturedPoses[1].toDataURL('image/jpeg', 0.95);
            if (stripPreviewPhoto3 && capturedPoses[2]) stripPreviewPhoto3.src = capturedPoses[2].toDataURL('image/jpeg', 0.95);
            if (stripPreviewMessage) stripPreviewMessage.innerText = customCaption; // Blank if empty
            if (stripPreviewDate) stripPreviewDate.innerText = `${todayStr} • MALANG`;
        } else {
            if (stitchPhotostripWrapper) stitchPhotostripWrapper.classList.add('hidden');
            if (canvasPhotostripWrapper) {
                canvasPhotostripWrapper.classList.remove('hidden');
                if (resultStripImg) resultStripImg.src = localStrip;
            }
        }

        if (btnDownloadStrip) {
            btnDownloadStrip.href = (uploadData && uploadData.download_url) || localStrip || '#';
            btnDownloadStrip.download = `KP45_PhotoStrip_${(uploadData && uploadData.photo_id) || 'strip'}.jpg`;
        }

        const gifUrl = (uploadData && uploadData.gif_download_url) || localGif;
        if (gifUrl && resultGifImg && btnDownloadGif && tabShowGif) {
            resultGifImg.src = gifUrl;
            btnDownloadGif.href = gifUrl;
            btnDownloadGif.download = `KP45_Animated_${(uploadData && uploadData.photo_id) || 'gif'}.gif`;
            btnDownloadGif.classList.remove('opacity-50', 'pointer-events-none');
            tabShowGif.classList.remove('hidden');
        } else if (btnDownloadGif && tabShowGif) {
            btnDownloadGif.classList.add('opacity-50', 'pointer-events-none');
            tabShowGif.classList.add('hidden');
        }

        showStripTab();

        renderQrCode((uploadData && uploadData.qr_url) || window.location.href);

        if (resultModal) {
            resultModal.classList.remove('hidden');
        }

        try {
            if (typeof confetti === 'function') {
                confetti({
                    particleCount: 85,
                    spread: 80,
                    origin: { y: 0.6 }
                });
            }
        } catch(e) {}

        startAutoResetTimer(45);
    }

    function renderQrCode(targetUrl) {
        if (!qrCodeContainer) return;
        qrCodeContainer.innerHTML = '';
        try {
            if (typeof QRCode !== 'undefined') {
                qrCodeInstance = new QRCode(qrCodeContainer, {
                    text: targetUrl,
                    width: 135,
                    height: 135,
                    colorDark: "#1d3557",
                    colorLight: "#ffffff",
                    correctLevel: QRCode.CorrectLevel.M
                });
            }
        } catch (qrErr) {
            console.warn("QR code generation warning:", qrErr);
        }
    }

    function updateModalWithServerData(data) {
        if (data.download_url && btnDownloadStrip) {
            btnDownloadStrip.href = data.download_url;
            btnDownloadStrip.download = `KP45_PhotoStrip_${data.photo_id}.jpg`;
        }
        if (data.gif_download_url && btnDownloadGif && resultGifImg && tabShowGif) {
            resultGifImg.src = data.gif_download_url;
            btnDownloadGif.href = data.gif_download_url;
            btnDownloadGif.download = `KP45_Animated_${data.photo_id}.gif`;
            btnDownloadGif.classList.remove('opacity-50', 'pointer-events-none');
            tabShowGif.classList.remove('hidden');
        }
        if (data.qr_url) {
            renderQrCode(data.qr_url);
        }
    }

    function showStripTab() {
        if (selectedLayout === '3-strip' && stitchPhotostripWrapper) {
            stitchPhotostripWrapper.classList.remove('hidden');
            if (canvasPhotostripWrapper) canvasPhotostripWrapper.classList.add('hidden');
        } else {
            if (stitchPhotostripWrapper) stitchPhotostripWrapper.classList.add('hidden');
            if (canvasPhotostripWrapper) canvasPhotostripWrapper.classList.remove('hidden');
        }
        if (gifPreviewWrapper) gifPreviewWrapper.classList.add('hidden');

        if (tabShowStrip) tabShowStrip.className = "py-1.5 px-5 bg-white border-2 border-merdeka-navy rounded-full text-xs md:text-sm font-display font-extrabold shadow-pesta-sm text-merdeka-red cursor-pointer";
        if (tabShowGif) tabShowGif.className = "py-1.5 px-5 bg-merdeka-surface-container border-2 border-merdeka-navy rounded-full text-xs md:text-sm font-display font-bold text-merdeka-on-surface-variant hover:bg-white transition-all cursor-pointer";
    }

    function showGifTab() {
        if (stitchPhotostripWrapper) stitchPhotostripWrapper.classList.add('hidden');
        if (canvasPhotostripWrapper) canvasPhotostripWrapper.classList.add('hidden');
        if (gifPreviewWrapper) gifPreviewWrapper.classList.remove('hidden');

        if (tabShowGif) tabShowGif.className = "py-1.5 px-5 bg-white border-2 border-merdeka-navy rounded-full text-xs md:text-sm font-display font-extrabold shadow-pesta-sm text-merdeka-navy cursor-pointer";
        if (tabShowStrip) tabShowStrip.className = "py-1.5 px-5 bg-merdeka-surface-container border-2 border-merdeka-navy rounded-full text-xs md:text-sm font-display font-bold text-merdeka-on-surface-variant hover:bg-white transition-all cursor-pointer";
    }

    if (tabShowStrip) tabShowStrip.addEventListener('click', showStripTab);
    if (tabShowGif) tabShowGif.addEventListener('click', showGifTab);

    // Live Custom Message Event Listener
    if (modalCustomCaption) {
        modalCustomCaption.addEventListener('input', () => {
            const caption = modalCustomCaption.value.trim();
            const todayStr = new Intl.DateTimeFormat('id-ID', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date()).toUpperCase();

            // 1. Live update DOM preview text
            if (stripPreviewMessage) {
                stripPreviewMessage.innerText = caption; // Blank if empty
            }

            // 2. Re-render the composite canvas for download
            const updatedCanvas = renderCompositeStripCanvas();
            const updatedDataUrl = updatedCanvas.toDataURL('image/jpeg', 0.95);
            if (btnDownloadStrip) btnDownloadStrip.href = updatedDataUrl;

            // 3. If non-3-strip layout, update the preview image as well
            if (selectedLayout !== '3-strip' && resultStripImg) {
                resultStripImg.src = updatedDataUrl;
            }
        });
    }

    function startAutoResetTimer(seconds) {
        clearInterval(autoResetInterval);
        let remaining = seconds;
        if (autoResetTimerEl) autoResetTimerEl.innerText = `${remaining}s`;

        autoResetInterval = setInterval(() => {
            remaining--;
            if (remaining >= 0) {
                if (autoResetTimerEl) autoResetTimerEl.innerText = `${remaining}s`;
            } else {
                clearInterval(autoResetInterval);
                closeResultModal();
            }
        }, 1000);
    }

    function closeResultModal() {
        clearInterval(autoResetInterval);
        if (resultModal) resultModal.classList.add('hidden');
        returnToWelcomeStage();
    }

    if (btnRetake) btnRetake.addEventListener('click', closeResultModal);
    if (btnCloseModal) btnCloseModal.addEventListener('click', closeResultModal);

    // Global Test Hook for Playwright E2E Automation
    window.__photobooth = {
        processAndDeliverOutputs,
        showResultModal,
        closeResultModal,
        getCapturedPoses: () => capturedPoses,
        setCapturedPoses: (poses) => { capturedPoses = poses; }
    };
});
