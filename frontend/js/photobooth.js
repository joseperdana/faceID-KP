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
    const video = document.getElementById('video-stream');
    const poseIndicatorText = document.getElementById('pose-indicator-text');
    const floatingCountdown = document.getElementById('floating-countdown');
    const countdownNumber = document.getElementById('countdown-number');
    const cameraFlash = document.getElementById('camera-flash');
    const poseDotsContainer = document.getElementById('pose-dots-container');

    const btnToggleMirror = document.getElementById('btn-toggle-mirror');
    const btnSwitchCam = document.getElementById('btn-switch-cam');
    const timer3sBtn = document.getElementById('timer-3s');
    const timer5sBtn = document.getElementById('timer-5s');

    // Result Modal & Dispenser Elements
    const resultModal = document.getElementById('result-modal');
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
    let isSessionRunning = false;
    let capturedPoses = []; // Array of snapshot canvases
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

    // Timer Selector Buttons
    timer3sBtn.addEventListener('click', () => {
        timerDuration = 3;
        timer3sBtn.className = "px-3.5 py-1 text-xs font-mono font-extrabold rounded-full bg-merdeka-navy text-white border-2 border-merdeka-navy shadow-pesta-sm transition-all";
        timer5sBtn.className = "px-3.5 py-1 text-xs font-mono font-extrabold rounded-full bg-white text-merdeka-navy border-2 border-merdeka-navy hover:bg-merdeka-surface-container transition-all";
    });

    timer5sBtn.addEventListener('click', () => {
        timerDuration = 5;
        timer5sBtn.className = "px-3.5 py-1 text-xs font-mono font-extrabold rounded-full bg-merdeka-navy text-white border-2 border-merdeka-navy shadow-pesta-sm transition-all";
        timer3sBtn.className = "px-3.5 py-1 text-xs font-mono font-extrabold rounded-full bg-white text-merdeka-navy border-2 border-merdeka-navy hover:bg-merdeka-surface-container transition-all";
    });

    // Camera Controls
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
        await startCamera();
        setTimeout(runMultiPoseCaptureSequence, 800);
    });

    btnCancelSession.addEventListener('click', returnToWelcomeStage);

    function returnToWelcomeStage() {
        if (currentStream) {
            currentStream.getTracks().forEach(track => track.stop());
            currentStream = null;
        }
        isSessionRunning = false;
        cameraStage.classList.add('hidden');
        welcomeStage.classList.remove('hidden');
        floatingCountdown.classList.add('hidden');
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

    async function runMultiPoseCaptureSequence() {
        if (isSessionRunning) return;
        isSessionRunning = true;
        capturedPoses = [];

        for (let i = 0; i < targetPoses; i++) {
            poseIndicatorText.innerText = `Pose ${i + 1} dari ${targetPoses}`;
            updatePoseDot(i, 'active');

            // 1. Floating Non-Intrusive Countdown (VIEWFINDER 100% CLEAR)
            await runFloatingCountdown(timerDuration);

            // 2. Flash & Mechanical Shutter
            triggerFlash();
            playShutterSound();
            const poseCanvas = captureSingleFrame();
            capturedPoses.push(poseCanvas);
            updatePoseDot(i, 'done');

            // 3. Short 1.2s Breather (No Intrusive Text Modal)
            if (i < targetPoses - 1) {
                poseIndicatorText.innerText = `Pose ${i + 2} dari ${targetPoses}`;
                await new Promise(r => setTimeout(r, 1200));
            }
        }

        poseIndicatorText.innerText = "Merangkai Foto...";
        await new Promise(r => setTimeout(r, 400));

        // 4. Generate Composite Strip & Animated GIF
        await processAndDeliverOutputs();

        isSessionRunning = false;
    }

    function runFloatingCountdown(seconds) {
        return new Promise(resolve => {
            floatingCountdown.classList.remove('hidden');
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
                    floatingCountdown.classList.add('hidden');
                    playBeep(1200, 0.2);
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

    // --- 4. Editorial High-End Canvas Compositor (Red Backdrop Inspired by se.du) ---
    function renderCompositeStripCanvas() {
        const stripCanvas = document.createElement('canvas');
        const customCaption = (customCaptionInput.value || '').trim();
        const todayStr = new Intl.DateTimeFormat('id-ID', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date()).toUpperCase();

        let STRIP_W = 1000;
        let STRIP_H = 3000;

        if (selectedLayout === '4-strip') {
            STRIP_H = 3400;
        } else if (selectedLayout === '2x2-grid') {
            STRIP_W = 2000;
            STRIP_H = 2100;
        } else if (selectedLayout === 'single-wide') {
            STRIP_W = 1600;
            STRIP_H = 1900;
        }

        stripCanvas.width = STRIP_W;
        stripCanvas.height = STRIP_H;
        const ctx = stripCanvas.getContext('2d');

        // Bold Crimson Editorial Red Backdrop
        ctx.fillStyle = '#b7102a';
        ctx.fillRect(0, 0, STRIP_W, STRIP_H);

        if (selectedLayout === '3-strip' || selectedLayout === '4-strip') {
            renderVerticalEditorialStrip(ctx, STRIP_W, STRIP_H, capturedPoses, customCaption, todayStr);
        } else if (selectedLayout === '2x2-grid') {
            renderBentoEditorialGrid(ctx, STRIP_W, STRIP_H, capturedPoses, customCaption, todayStr);
        } else {
            renderSingleWideEditorial(ctx, STRIP_W, STRIP_H, capturedPoses[0], customCaption, todayStr);
        }

        return stripCanvas;
    }

    function renderVerticalEditorialStrip(ctx, W, H, poses, caption, dateStr) {
        const count = poses.length;
        const marginX = 60;
        const photoW = W - (marginX * 2);
        const photoH = count === 3 ? 660 : 570;
        const gapY = 40;
        const startY = 80;

        poses.forEach((pose, idx) => {
            const posY = startY + idx * (photoH + gapY);

            ctx.save();
            ctx.drawImage(pose, marginX, posY, photoW, photoH);
            ctx.restore();
        });

        const footerY = startY + count * (photoH + gapY) + 30;
        const brandBoxW = photoW;
        const brandBoxH = H - footerY - 80;

        ctx.fillStyle = '#ffffff';
        ctx.fillRect(marginX, footerY, brandBoxW, brandBoxH);

        ctx.fillStyle = '#b7102a';
        ctx.font = '900 76px "Bricolage Grotesque", sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText('kp.45', marginX + 40, footerY + 95);

        ctx.fillStyle = '#1d3557';
        ctx.font = '700 28px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(caption || 'Komisi Pemuda GKI Bromo', marginX + brandBoxW - 40, footerY + 65);

        ctx.fillStyle = '#5b403f';
        ctx.font = '600 20px "JetBrains Mono", monospace';
        ctx.fillText(`${dateStr} • MALANG`, marginX + brandBoxW - 40, footerY + 105);
    }

    function renderBentoEditorialGrid(ctx, W, H, poses, caption, dateStr) {
        const gap = 50;
        const margin = 70;
        const photoW = (W - (margin * 2) - gap) / 2;
        const photoH = photoW * 0.75;
        const startY = 80;

        poses.forEach((pose, idx) => {
            const col = idx % 2;
            const row = Math.floor(idx / 2);
            const pX = margin + col * (photoW + gap);
            const pY = startY + row * (photoH + gap);

            ctx.drawImage(pose, pX, pY, photoW, photoH);
        });

        const footerY = startY + 2 * (photoH + gap) + 20;
        const brandBoxH = H - footerY - 70;

        ctx.fillStyle = '#ffffff';
        ctx.fillRect(margin, footerY, W - (margin * 2), brandBoxH);

        ctx.fillStyle = '#b7102a';
        ctx.font = '900 84px "Bricolage Grotesque", sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText('kp.45', margin + 50, footerY + 110);

        ctx.fillStyle = '#1d3557';
        ctx.font = '800 36px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(caption || 'Komisi Pemuda GKI Bromo', W - margin - 50, footerY + 75);

        ctx.fillStyle = '#5b403f';
        ctx.font = '600 24px "JetBrains Mono", monospace';
        ctx.fillText(`${dateStr} • MALANG`, W - margin - 50, footerY + 120);
    }

    function renderSingleWideEditorial(ctx, W, H, pose, caption, dateStr) {
        const margin = 80;
        const photoW = W - (margin * 2);
        const photoH = photoW * 0.75;
        const photoY = 80;

        ctx.drawImage(pose, margin, photoY, photoW, photoH);

        const footerY = photoY + photoH + 50;
        const brandBoxH = H - footerY - 80;

        ctx.fillStyle = '#ffffff';
        ctx.fillRect(margin, footerY, photoW, brandBoxH);

        ctx.fillStyle = '#b7102a';
        ctx.font = '900 96px "Bricolage Grotesque", sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText('kp.45', margin + 60, footerY + 130);

        ctx.fillStyle = '#1d3557';
        ctx.font = '800 42px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(caption || 'Komisi Pemuda GKI Bromo', margin + photoW - 60, footerY + 85);

        ctx.fillStyle = '#5b403f';
        ctx.font = '600 26px "JetBrains Mono", monospace';
        ctx.fillText(`${dateStr} • MALANG`, margin + photoW - 60, footerY + 140);
    }

    // --- 5. Animated Looping GIF Generator ---
    function generateAnimatedGif(poses) {
        return new Promise((resolve) => {
            if (typeof gifshot === 'undefined' || poses.length === 0) {
                resolve(null);
                return;
            }

            const frameImages = poses.map(c => c.toDataURL('image/jpeg', 0.85));

            gifshot.createGIF({
                images: frameImages,
                interval: 0.45,
                gifWidth: 480,
                gifHeight: 360,
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

        resultStripImg.src = localStrip;
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

        resultStripImg.classList.remove('animate-print-slide');
        void resultStripImg.offsetWidth;
        resultStripImg.classList.add('animate-print-slide');

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
        resultStripImg.classList.remove('hidden');
        resultGifImg.classList.add('hidden');
        tabShowStrip.className = "py-1.5 px-5 bg-white border-2 border-merdeka-navy rounded-full text-xs md:text-sm font-display font-extrabold shadow-pesta-sm text-merdeka-red cursor-pointer";
        tabShowGif.className = "py-1.5 px-5 bg-merdeka-surface-container border-2 border-merdeka-navy rounded-full text-xs md:text-sm font-display font-bold text-merdeka-on-surface-variant hover:bg-white transition-all cursor-pointer";
    }

    function showGifTab() {
        resultStripImg.classList.add('hidden');
        resultGifImg.classList.remove('hidden');
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
