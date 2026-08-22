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

    async function switchCamera() {
        currentFacingMode = currentFacingMode === 'user' ? 'environment' : 'user';
        if (currentFacingMode === 'environment') {
            isMirrored = false;
        } else {
            isMirrored = true;
        }
        applyMirrorState();
        await startCamera();
    }

    if (btnToggleMirrorWelcome) btnToggleMirrorWelcome.addEventListener('click', toggleMirror);
    if (btnToggleMirror) btnToggleMirror.addEventListener('click', toggleMirror);
    if (btnSwitchCamWelcome) btnSwitchCamWelcome.addEventListener('click', switchCamera);
    if (btnSwitchCam) btnSwitchCam.addEventListener('click', switchCamera);

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
    function renderCompositeStripCanvas() {
        const stripCanvas = document.createElement('canvas');
        const customCaption = (customCaptionInput.value || '').trim();
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

        // 3. Bottom White Footer Area (Matching Stitch - Generous 138px breathing room)
        const footerY = startY + 3 * (photoH + gapY);
        ctx.fillStyle = '#b7102a';
        ctx.font = '800 36px "Bricolage Grotesque", "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(caption || 'Geng Pemuda Bromo 2026', W / 2, footerY + 45);

        ctx.fillStyle = '#211b0b';
        ctx.font = '700 18px "JetBrains Mono", monospace';
        ctx.fillText(`${dateStr} • MALANG`, W / 2, footerY + 85);

        // 4. Left Crimson Red Column with Rotated Typography
        ctx.fillStyle = '#b7102a';
        ctx.fillRect(0, 0, sideBarW, H);

        // Left Column: Top Subtitle
        ctx.save();
        ctx.translate(sideBarW / 2, 340);
        ctx.rotate(-Math.PI / 2);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
        ctx.font = '700 16px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.letterSpacing = '2px';
        ctx.fillText('KOMISI PEMUDA GKI BROMO MALANG', 0, 0);
        ctx.restore();

        // Left Column: Center Logo
        ctx.save();
        ctx.translate(sideBarW / 2, H / 2);
        ctx.rotate(-Math.PI / 2);
        ctx.fillStyle = '#ffffff';
        ctx.font = '900 68px "Bricolage Grotesque", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('KP45', 0, 0);
        ctx.restore();

        // Left Column: Bottom Subtitle
        ctx.save();
        ctx.translate(sideBarW / 2, H - 340);
        ctx.rotate(-Math.PI / 2);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
        ctx.font = '700 16px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.letterSpacing = '2px';
        ctx.fillText('KOMISI PEMUDA GKI BROMO MALANG', 0, 0);
        ctx.restore();

        // 5. Right Crimson Red Column with Rotated Typography
        ctx.fillStyle = '#b7102a';
        ctx.fillRect(W - sideBarW, 0, sideBarW, H);

        // Right Column: Top Subtitle
        ctx.save();
        ctx.translate(W - (sideBarW / 2), 340);
        ctx.rotate(Math.PI / 2);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
        ctx.font = '700 16px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.letterSpacing = '2px';
        ctx.fillText('KOMISI PEMUDA GKI BROMO MALANG', 0, 0);
        ctx.restore();

        // Right Column: Center Logo
        ctx.save();
        ctx.translate(W - (sideBarW / 2), H / 2);
        ctx.rotate(Math.PI / 2);
        ctx.fillStyle = '#ffffff';
        ctx.font = '900 68px "Bricolage Grotesque", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('KP45', 0, 0);
        ctx.restore();

        // Right Column: Bottom Subtitle
        ctx.save();
        ctx.translate(W - (sideBarW / 2), H - 340);
        ctx.rotate(Math.PI / 2);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
        ctx.font = '700 16px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.letterSpacing = '2px';
        ctx.fillText('KOMISI PEMUDA GKI BROMO MALANG', 0, 0);
        ctx.restore();
    }

    function renderVertical4Strip(ctx, W, H, poses, caption, dateStr) {
        ctx.fillStyle = '#b7102a';
        ctx.fillRect(0, 0, W, H);

        const marginX = 174;
        const photoW = 732;
        const photoH = 549; // True 4:3 Aspect Ratio (732 * 0.75 = 549)
        const gapY = 16;
        const startY = 80;

        poses.forEach((pose, idx) => {
            const posY = startY + idx * (photoH + gapY);
            drawImageCover(ctx, pose, marginX, posY, photoW, photoH);
        });

        // Side branding bars (Vertical text matching KP45 style)
        ctx.save();
        ctx.fillStyle = '#ffffff';
        ctx.font = '900 68px "Bricolage Grotesque", sans-serif';
        ctx.textAlign = 'center';
        ctx.translate(90, H / 2);
        ctx.rotate(-Math.PI / 2);
        ctx.fillText('KP45 • PEMUDA BROMO', 0, 0);
        ctx.restore();

        ctx.save();
        ctx.fillStyle = '#ffffff';
        ctx.font = '900 68px "Bricolage Grotesque", sans-serif';
        ctx.textAlign = 'center';
        ctx.translate(W - 90, H / 2);
        ctx.rotate(Math.PI / 2);
        ctx.fillText('KP45 • GKI BROMO', 0, 0);
        ctx.restore();

        // Footer box
        const footerY = startY + 4 * (photoH + gapY) + 15;
        const footerH = H - footerY - 40;
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(marginX, footerY, photoW, footerH);

        ctx.fillStyle = '#b7102a';
        ctx.font = '900 52px "Bricolage Grotesque", sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText('kp.45', marginX + 30, footerY + 68);

        ctx.fillStyle = '#1d3557';
        ctx.font = '800 24px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(caption || 'Komisi Pemuda GKI Bromo', marginX + photoW - 30, footerY + 46);

        ctx.fillStyle = '#5b403f';
        ctx.font = '600 16px "JetBrains Mono", monospace';
        ctx.fillText(`${dateStr} • MALANG`, marginX + photoW - 30, footerY + 76);
    }

    function renderBentoEditorialGrid(ctx, W, H, poses, caption, dateStr) {
        ctx.fillStyle = '#b7102a';
        ctx.fillRect(0, 0, W, H);

        const margin = 70;
        const gapX = 40;
        const gapY = 30;
        const photoW = Math.round((W - (margin * 2) - gapX) / 2); // 710px
        const photoH = Math.round(photoW * 0.75); // 532px (True 4:3!)
        const startY = 70;

        poses.forEach((pose, idx) => {
            const col = idx % 2;
            const row = Math.floor(idx / 2);
            const pX = margin + col * (photoW + gapX);
            const pY = startY + row * (photoH + gapY);

            drawImageCover(ctx, pose, pX, pY, photoW, photoH);
        });

        const footerY = startY + 2 * photoH + gapY + 30;
        const footerH = H - footerY - 50;
        const footerW = W - (margin * 2);

        ctx.fillStyle = '#ffffff';
        ctx.fillRect(margin, footerY, footerW, footerH);

        ctx.fillStyle = '#b7102a';
        ctx.font = '900 88px "Bricolage Grotesque", sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText('kp.45', margin + 40, footerY + 115);

        ctx.fillStyle = '#1d3557';
        ctx.font = '800 34px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(caption || 'Komisi Pemuda GKI Bromo', margin + footerW - 40, footerY + 75);

        ctx.fillStyle = '#5b403f';
        ctx.font = '700 22px "JetBrains Mono", monospace';
        ctx.fillText(`${dateStr} • MALANG`, margin + footerW - 40, footerY + 120);
    }

    function renderSingleWideEditorial(ctx, W, H, pose, caption, dateStr) {
        ctx.fillStyle = '#b7102a';
        ctx.fillRect(0, 0, W, H);

        const margin = 70;
        const photoW = W - (margin * 2);
        const photoH = Math.round(photoW * 0.75); // 795px (True 4:3!)
        const photoY = 70;

        drawImageCover(ctx, pose, margin, photoY, photoW, photoH);

        const footerY = photoY + photoH + 40;
        const footerH = H - footerY - 50;

        ctx.fillStyle = '#ffffff';
        ctx.fillRect(margin, footerY, photoW, footerH);

        ctx.fillStyle = '#b7102a';
        ctx.font = '900 96px "Bricolage Grotesque", sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText('kp.45', margin + 50, footerY + 130);

        ctx.fillStyle = '#1d3557';
        ctx.font = '800 40px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(caption || 'Komisi Pemuda GKI Bromo', margin + photoW - 50, footerY + 80);

        ctx.fillStyle = '#5b403f';
        ctx.font = '700 24px "JetBrains Mono", monospace';
        ctx.fillText(`${dateStr} • MALANG`, margin + photoW - 50, footerY + 135);
    }

    // --- 5. Animated Looping Framed GIF Generator ---
    function renderFramedGifFrame(poseCanvas, poseIdx, totalPoses, caption, dateStr) {
        const W = 600;
        const H = 720;
        const canvas = document.createElement('canvas');
        canvas.width = W;
        canvas.height = H;
        const ctx = canvas.getContext('2d');

        // Bold Editorial Crimson Red Backdrop
        ctx.fillStyle = '#b7102a';
        ctx.fillRect(0, 0, W, H);

        // Photo slot in upper region
        const margin = 28;
        const photoW = W - (margin * 2);
        const photoH = Math.round(photoW * 0.75); // 4:3 Aspect Ratio (544 * 0.75 = 408)
        const photoY = 28;

        drawImageCover(ctx, poseCanvas, margin, photoY, photoW, photoH);

        // Inverted White Branding Footer Box
        const footerY = photoY + photoH + 18;
        const footerH = H - footerY - 24;
        const footerW = photoW;

        ctx.fillStyle = '#ffffff';
        ctx.fillRect(margin, footerY, footerW, footerH);

        // kp.45 Brand Logo (Left)
        ctx.fillStyle = '#b7102a';
        ctx.font = '900 48px "Bricolage Grotesque", sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText('kp.45', margin + 20, footerY + 54);

        // Pose Pill Stamp (e.g. "[1/3]")
        ctx.fillStyle = '#1d3557';
        ctx.font = '800 16px "JetBrains Mono", monospace';
        ctx.fillText(`[${poseIdx + 1}/${totalPoses}]`, margin + 20, footerY + 84);

        // Caption & Date (Right)
        ctx.fillStyle = '#1d3557';
        ctx.font = '800 20px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'right';
        const displayCaption = caption || 'Komisi Pemuda GKI Bromo';
        ctx.fillText(displayCaption, margin + footerW - 20, footerY + 44);

        ctx.fillStyle = '#5b403f';
        ctx.font = '700 14px "JetBrains Mono", monospace';
        ctx.fillText(`${dateStr} • MALANG`, margin + footerW - 20, footerY + 76);

        return canvas;
    }

    function generateAnimatedGif(poses) {
        return new Promise((resolve) => {
            if (typeof gifshot === 'undefined' || poses.length === 0) {
                resolve(null);
                return;
            }

            const customCaption = (customCaptionInput.value || '').trim();
            const todayStr = new Intl.DateTimeFormat('id-ID', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date()).toUpperCase();

            // Render each frame inside the editorial KP45 frame
            const framedFrames = poses.map((poseCanvas, idx) => {
                const framedCanvas = renderFramedGifFrame(poseCanvas, idx, poses.length, customCaption, todayStr);
                return framedCanvas.toDataURL('image/jpeg', 0.88);
            });

            gifshot.createGIF({
                images: framedFrames,
                interval: 0.5,
                gifWidth: 480,
                gifHeight: 576,
                numWorkers: 2,
            }, (obj) => {
                if (!obj.error) {
                    resolve(obj.image);
                } else {
                    console.error("GIF generation error:", obj.error);
                    resolve(null);
                }
            });
        });
    }

    // --- 6. Processing & Output Delivery ---
    async function processAndDeliverOutputs() {
        Swal.fire({
            title: 'Mencetak Foto KP45...',
            text: 'Merangkai strip foto beresolusi tinggi...',
            allowOutsideClick: false,
            background: '#fff8f1',
            color: '#211b0b',
            didOpen: () => { Swal.showLoading(); }
        });

        const stripCanvas = renderCompositeStripCanvas();
        const base64Strip = stripCanvas.toDataURL('image/jpeg', 0.92);
        const base64Gif = await generateAnimatedGif(capturedPoses);
        const customCaption = (customCaptionInput.value || '').trim();

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

            const data = await response.json();
            Swal.close();

            if (data.status === 'success') {
                showResultModal(data, base64Strip, base64Gif);
            } else {
                throw new Error(data.message || 'Gagal menyimpan hasil foto');
            }
        } catch (err) {
            Swal.close();
            showResultModal({ download_url: base64Strip, qr_url: window.location.href }, base64Strip, base64Gif);
        }
    }

    // --- 7. Result Modal Presentation & Skeuomorphic Printing Animation ---
    function showResultModal(uploadData, localStrip, localGif) {
        playPrinterSound();

        const customCaption = (customCaptionInput.value || '').trim();
        const todayStr = new Intl.DateTimeFormat('id-ID', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date()).toUpperCase();

        if (selectedLayout === '3-strip' && capturedPoses.length >= 3 && stitchPhotostripWrapper) {
            stitchPhotostripWrapper.classList.remove('hidden');
            if (canvasPhotostripWrapper) canvasPhotostripWrapper.classList.add('hidden');
            
            stripPreviewPhoto1.src = capturedPoses[0].toDataURL('image/jpeg', 0.95);
            stripPreviewPhoto2.src = capturedPoses[1].toDataURL('image/jpeg', 0.95);
            stripPreviewPhoto3.src = capturedPoses[2].toDataURL('image/jpeg', 0.95);
            stripPreviewMessage.innerText = customCaption || 'Geng Pemuda Bromo 2026';
            stripPreviewDate.innerText = `${todayStr} • MALANG`;
        } else {
            if (stitchPhotostripWrapper) stitchPhotostripWrapper.classList.add('hidden');
            if (canvasPhotostripWrapper) {
                canvasPhotostripWrapper.classList.remove('hidden');
                resultStripImg.src = localStrip;
            }
        }

        btnDownloadStrip.href = uploadData.download_url || localStrip;
        btnDownloadStrip.download = `KP45_PhotoStrip_${uploadData.photo_id || 'strip'}.jpg`;

        if (localGif || uploadData.gif_download_url) {
            resultGifImg.src = uploadData.gif_download_url || localGif;
            btnDownloadGif.href = uploadData.gif_download_url || localGif;
            btnDownloadGif.download = `KP45_Animated_${uploadData.photo_id || 'gif'}.gif`;
            btnDownloadGif.classList.remove('opacity-50', 'pointer-events-none');
            tabShowGif.classList.remove('hidden');
        } else {
            btnDownloadGif.classList.add('opacity-50', 'pointer-events-none');
            tabShowGif.classList.add('hidden');
        }

        showStripTab();

        qrCodeContainer.innerHTML = '';
        const qrTargetUrl = uploadData.qr_url || window.location.href;
        
        // Compact 135x135 QR Code
        qrCodeInstance = new QRCode(qrCodeContainer, {
            text: qrTargetUrl,
            width: 135,
            height: 135,
            colorDark: "#1d3557",
            colorLight: "#ffffff",
            correctLevel: QRCode.CorrectLevel.M
        });

        resultModal.classList.remove('hidden');

        try {
            confetti({
                particleCount: 85,
                spread: 80,
                origin: { y: 0.6 }
            });
        } catch(e) {}

        startAutoResetTimer(45);
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

        tabShowStrip.className = "py-1.5 px-5 bg-white border-2 border-merdeka-navy rounded-full text-xs md:text-sm font-display font-extrabold shadow-pesta-sm text-merdeka-red cursor-pointer";
        tabShowGif.className = "py-1.5 px-5 bg-merdeka-surface-container border-2 border-merdeka-navy rounded-full text-xs md:text-sm font-display font-bold text-merdeka-on-surface-variant hover:bg-white transition-all cursor-pointer";
    }

    function showGifTab() {
        if (stitchPhotostripWrapper) stitchPhotostripWrapper.classList.add('hidden');
        if (canvasPhotostripWrapper) canvasPhotostripWrapper.classList.add('hidden');
        if (gifPreviewWrapper) gifPreviewWrapper.classList.remove('hidden');

        tabShowGif.className = "py-1.5 px-5 bg-white border-2 border-merdeka-navy rounded-full text-xs md:text-sm font-display font-extrabold shadow-pesta-sm text-merdeka-navy cursor-pointer";
        tabShowStrip.className = "py-1.5 px-5 bg-merdeka-surface-container border-2 border-merdeka-navy rounded-full text-xs md:text-sm font-display font-bold text-merdeka-on-surface-variant hover:bg-white transition-all cursor-pointer";
    }

    tabShowStrip.addEventListener('click', showStripTab);
    tabShowGif.addEventListener('click', showGifTab);

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
        returnToWelcomeStage();
    }

    btnRetake.addEventListener('click', closeResultModal);
    btnCloseModal.addEventListener('click', closeResultModal);
});
