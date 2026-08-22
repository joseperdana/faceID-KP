// --- Nusantara Festive Light Photo Strip & Animated GIF Engine ---
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
    const interposeOverlay = document.getElementById('interpose-overlay');
    const interposeTitle = document.getElementById('interpose-title');
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
        // Synthesize mechanical paper dispenser whir
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
        timer3sBtn.className = "px-3 py-1 text-xs font-mono font-extrabold rounded-xl bg-paper-900 text-white border-2 border-paper-900 shadow-tactile-sm transition-all";
        timer5sBtn.className = "px-3 py-1 text-xs font-mono font-extrabold rounded-xl bg-white text-slate-600 border-2 border-paper-900 hover:bg-paper-100 transition-all";
    });

    timer5sBtn.addEventListener('click', () => {
        timerDuration = 5;
        timer5sBtn.className = "px-3 py-1 text-xs font-mono font-extrabold rounded-xl bg-paper-900 text-white border-2 border-paper-900 shadow-tactile-sm transition-all";
        timer3sBtn.className = "px-3 py-1 text-xs font-mono font-extrabold rounded-xl bg-white text-slate-600 border-2 border-paper-900 hover:bg-paper-100 transition-all";
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
                background: '#FAF7F2',
                color: '#1E1B18',
                confirmButtonColor: '#DC2626'
            });
        }
    }

    // --- 3. Stage Navigation & Burst Capture Loop ---
    btnStartSession.addEventListener('click', async () => {
        welcomeStage.classList.add('hidden');
        cameraStage.classList.remove('hidden');
        renderPoseDots();
        await startCamera();
        // Small delay to let camera warm up, then launch multi-pose burst
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
        interposeOverlay.classList.add('hidden');
    }

    function renderPoseDots() {
        poseDotsContainer.innerHTML = '';
        for (let i = 0; i < targetPoses; i++) {
            const dot = document.createElement('span');
            dot.id = `dot-pose-${i}`;
            dot.className = "w-7 h-2 rounded-full bg-paper-300 border border-paper-900/30 transition-all";
            poseDotsContainer.appendChild(dot);
        }
    }

    function updatePoseDot(index, state) {
        const dot = document.getElementById(`dot-pose-${index}`);
        if (!dot) return;
        if (state === 'active') {
            dot.className = "w-9 h-2 rounded-full bg-festive-crimson shadow-tactile-sm transition-all border border-paper-900";
        } else if (state === 'done') {
            dot.className = "w-7 h-2 rounded-full bg-festive-sage shadow-tactile-sm transition-all border border-paper-900";
        }
    }

    async function runMultiPoseCaptureSequence() {
        if (isSessionRunning) return;
        isSessionRunning = true;
        capturedPoses = [];

        const posePrompts = [
            { text: "Pose 1: Senyum Manis!", next: "Siapkan Gaya 2!" },
            { text: "Pose 2: Gaya Lucu / Bebas!", next: "Siapkan Gaya 3!" },
            { text: "Pose 3: Gaya Terbaik!", next: "Pose Terakhir! Paling Heboh!" },
            { text: "Pose 4: Gaya Paling Heboh!", next: "Selesai! Merangkai Foto..." }
        ];

        for (let i = 0; i < targetPoses; i++) {
            const promptObj = posePrompts[Math.min(i, posePrompts.length - 1)];
            poseIndicatorText.innerText = `Pose ${i + 1} dari ${targetPoses}: ${promptObj.text}`;
            updatePoseDot(i, 'active');

            // 1. Floating Non-Intrusive Countdown (VIEWFINDER 100% CLEAR)
            await runFloatingCountdown(timerDuration);

            // 2. Flash & Mechanical Shutter
            triggerFlash();
            playShutterSound();
            const poseCanvas = captureSingleFrame();
            capturedPoses.push(poseCanvas);
            updatePoseDot(i, 'done');

            // 3. Inter-pose Break
            if (i < targetPoses - 1) {
                interposeTitle.innerText = promptObj.next;
                interposeOverlay.classList.remove('hidden');
                await new Promise(r => setTimeout(r, 2200));
                interposeOverlay.classList.add('hidden');
            }
        }

        poseIndicatorText.innerText = "Merangkai Foto & Animasi GIF...";
        await new Promise(r => setTimeout(r, 500));

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

        return frameCanvas;
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
        ctx.lineWidth = 3.5;
        ctx.strokeStyle = '#1E1B18';
        ctx.stroke();
        ctx.restore();
    }

    // --- 4. High-Res Canvas Compositor for 4 Layouts ---
    function renderCompositeStripCanvas() {
        const stripCanvas = document.createElement('canvas');
        const customCaption = (customCaptionInput.value || '').trim();
        const todayStr = new Intl.DateTimeFormat('id-ID', { day: 'numeric', month: 'long', year: 'numeric' }).format(new Date());

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

        // Render Background (Warm Paper)
        ctx.fillStyle = '#FFFDF7';
        ctx.fillRect(0, 0, STRIP_W, STRIP_H);

        // Chunky Terracotta & Crimson Outer Border
        ctx.fillStyle = '#DC2626';
        ctx.fillRect(0, 0, STRIP_W, 34);
        ctx.fillRect(0, STRIP_H - 34, STRIP_W, 34);
        ctx.fillRect(0, 0, 34, STRIP_H);
        ctx.fillRect(STRIP_W - 34, 0, 34, STRIP_H);

        if (selectedLayout === '3-strip' || selectedLayout === '4-strip') {
            renderVerticalStripLayout(ctx, STRIP_W, STRIP_H, capturedPoses, customCaption, todayStr);
        } else if (selectedLayout === '2x2-grid') {
            renderBentoGridLayout(ctx, STRIP_W, STRIP_H, capturedPoses, customCaption, todayStr);
        } else {
            renderSingleWideLayout(ctx, STRIP_W, STRIP_H, capturedPoses[0], customCaption, todayStr);
        }

        return stripCanvas;
    }

    function renderVerticalStripLayout(ctx, W, H, poses, caption, dateStr) {
        // Top Header Badge
        ctx.save();
        ctx.fillStyle = '#1E1B18';
        ctx.beginPath();
        ctx.roundRect(76, 76, W - 140, 150, 24);
        ctx.fill();

        ctx.fillStyle = '#DC2626';
        ctx.beginPath();
        ctx.roundRect(70, 70, W - 140, 150, 24);
        ctx.fill();
        ctx.lineWidth = 4;
        ctx.strokeStyle = '#1E1B18';
        ctx.stroke();

        ctx.fillStyle = '#FFFFFF';
        ctx.font = '900 42px "Space Grotesk", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('DIRGAHAYU INDONESIA', W / 2, 135);

        ctx.fillStyle = '#FEF08A';
        ctx.font = '800 22px "JetBrains Mono", monospace';
        ctx.fillText('KOMISI PEMUDA GKI BROMO MALANG', W / 2, 180);
        ctx.restore();

        const count = poses.length;
        const photoW = 840;
        const photoH = count === 3 ? 630 : 540;
        const photoX = (W - photoW) / 2;
        const startY = 265;
        const gapY = count === 3 ? 55 : 45;

        poses.forEach((pose, idx) => {
            const posY = startY + idx * (photoH + gapY);

            // Drop shadow
            ctx.fillStyle = '#1E1B18';
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
            ctx.strokeStyle = '#1E1B18';
            ctx.strokeRect(photoX, posY, photoW, photoH);

            // Numbered Tab
            ctx.save();
            ctx.fillStyle = '#1E1B18';
            ctx.beginPath();
            ctx.roundRect(photoX + 24, posY + 24, 64, 40, 10);
            ctx.fill();

            ctx.fillStyle = '#DC2626';
            ctx.beginPath();
            ctx.roundRect(photoX + 20, posY + 20, 64, 40, 10);
            ctx.fill();
            ctx.lineWidth = 3;
            ctx.strokeStyle = '#1E1B18';
            ctx.stroke();

            ctx.fillStyle = '#FFFFFF';
            ctx.font = '900 22px "Space Grotesk", sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(`0${idx + 1}`, photoX + 52, posY + 48);
            ctx.restore();

            // Decorative Corner Stars
            if (idx === 0) drawStar(ctx, photoX + photoW - 32, posY + 32, 5, 24, 11, '#F59E0B');
            if (idx === count - 1) drawStar(ctx, photoX + photoW - 32, posY + photoH - 32, 5, 24, 11, '#C2410C');
        });

        // Bottom Footer
        const footerY = startY + count * (photoH + gapY) + 30;
        
        ctx.fillStyle = '#1E1B18';
        ctx.font = '900 38px "Space Grotesk", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(caption || 'Komisi Pemuda GKI Bromo', W / 2, footerY + 55);

        ctx.fillStyle = '#C2410C';
        ctx.font = '700 22px "JetBrains Mono", monospace';
        ctx.fillText(`Saturday Fellowship • ${dateStr}`, W / 2, footerY + 105);

        ctx.fillStyle = '#DC2626';
        ctx.font = '900 26px "Space Grotesk", sans-serif';
        ctx.fillText('YOUTH ON FIRE FOR CHRIST', W / 2, footerY + 155);
    }

    function renderBentoGridLayout(ctx, W, H, poses, caption, dateStr) {
        // Header
        ctx.fillStyle = '#DC2626';
        ctx.beginPath();
        ctx.roundRect(80, 80, W - 160, 160, 24);
        ctx.fill();
        ctx.lineWidth = 4;
        ctx.strokeStyle = '#1E1B18';
        ctx.stroke();

        ctx.fillStyle = '#FFFFFF';
        ctx.font = '900 56px "Space Grotesk", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('DIRGAHAYU REPUBLIK INDONESIA', W / 2, 160);

        ctx.fillStyle = '#FEF08A';
        ctx.font = '800 28px "JetBrains Mono", monospace';
        ctx.fillText('EDISI 17 AGUSTUS • KP BROMO MALANG', W / 2, 210);

        // 2x2 Bento Photo Layout
        const photoW = 860;
        const photoH = 645;
        const gap = 60;
        const startX = (W - (photoW * 2 + gap)) / 2;
        const startY = 290;

        poses.forEach((pose, idx) => {
            const col = idx % 2;
            const row = Math.floor(idx / 2);
            const pX = startX + col * (photoW + gap);
            const pY = startY + row * (photoH + gap);

            ctx.fillStyle = '#1E1B18';
            ctx.beginPath();
            ctx.roundRect(pX + 8, pY + 8, photoW, photoH, 20);
            ctx.fill();

            ctx.save();
            ctx.beginPath();
            ctx.roundRect(pX, pY, photoW, photoH, 20);
            ctx.clip();
            ctx.drawImage(pose, pX, pY, photoW, photoH);
            ctx.restore();

            ctx.lineWidth = 4;
            ctx.strokeStyle = '#1E1B18';
            ctx.strokeRect(pX, pY, photoW, photoH);
        });

        // Bottom Banner
        const footerY = H - 240;
        ctx.fillStyle = '#1E1B18';
        ctx.font = '900 48px "Space Grotesk", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(caption || 'Komisi Pemuda GKI Bromo', W / 2, footerY + 60);

        ctx.fillStyle = '#DC2626';
        ctx.font = '800 30px "JetBrains Mono", monospace';
        ctx.fillText(`Saturday Fellowship • ${dateStr}`, W / 2, footerY + 120);
    }

    function renderSingleWideLayout(ctx, W, H, pose, caption, dateStr) {
        // Top Header
        ctx.fillStyle = '#DC2626';
        ctx.beginPath();
        ctx.roundRect(80, 80, W - 160, 140, 24);
        ctx.fill();
        ctx.lineWidth = 4;
        ctx.strokeStyle = '#1E1B18';
        ctx.stroke();

        ctx.fillStyle = '#FFFFFF';
        ctx.font = '900 46px "Space Grotesk", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('DIRGAHAYU REPUBLIK INDONESIA', W / 2, 155);

        ctx.fillStyle = '#FEF08A';
        ctx.font = '700 24px "JetBrains Mono", monospace';
        ctx.fillText('EDISI 17 AGUSTUS • KP BROMO', W / 2, 195);

        // 1 Large Wide Photo (4:3)
        const photoW = 1400;
        const photoH = 1050;
        const photoX = (W - photoW) / 2;
        const photoY = 270;

        ctx.fillStyle = '#1E1B18';
        ctx.beginPath();
        ctx.roundRect(photoX + 10, photoY + 10, photoW, photoH, 24);
        ctx.fill();

        ctx.save();
        ctx.beginPath();
        ctx.roundRect(photoX, photoY, photoW, photoH, 24);
        ctx.clip();
        ctx.drawImage(pose, photoX, photoY, photoW, photoH);
        ctx.restore();

        ctx.lineWidth = 4;
        ctx.strokeStyle = '#1E1B18';
        ctx.strokeRect(photoX, photoY, photoW, photoH);

        // Polaroid Footnote
        const footerY = photoY + photoH + 70;
        ctx.fillStyle = '#1E1B18';
        ctx.font = '900 52px "Space Grotesk", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(caption || 'Komisi Pemuda GKI Bromo', W / 2, footerY + 50);

        ctx.fillStyle = '#C2410C';
        ctx.font = '700 30px "JetBrains Mono", monospace';
        ctx.fillText(`Saturday Fellowship • ${dateStr}`, W / 2, footerY + 120);
    }

    // --- 5. Animated Looping GIF Generator ---
    function generateAnimatedGif(poses) {
        return new Promise((resolve) => {
            if (typeof gifshot === 'undefined' || poses.length === 0) {
                resolve(null);
                return;
            }

            // Convert canvases to lightweight image data URLs
            const frameImages = poses.map(c => c.toDataURL('image/jpeg', 0.85));

            gifshot.createGIF({
                images: frameImages,
                interval: 0.45, // 450ms per frame
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
            title: 'Mencetak Foto & Animasi GIF...',
            text: 'Merangkai strip foto beresolusi tinggi...',
            allowOutsideClick: false,
            background: '#FAF7F2',
            color: '#1E1B18',
            didOpen: () => { Swal.showLoading(); }
        });

        // 1. Render Composite Strip
        const stripCanvas = renderCompositeStripCanvas();
        const base64Strip = stripCanvas.toDataURL('image/jpeg', 0.92);

        // 2. Generate Animated GIF
        const base64Gif = await generateAnimatedGif(capturedPoses);

        const customCaption = (customCaptionInput.value || '').trim();

        // 3. Upload to Backend
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
        btnDownloadStrip.download = `KP_Bromo_PhotoStrip_${uploadData.photo_id || 'strip'}.jpg`;

        if (localGif || uploadData.gif_download_url) {
            resultGifImg.src = uploadData.gif_download_url || localGif;
            btnDownloadGif.href = uploadData.gif_download_url || localGif;
            btnDownloadGif.download = `KP_Bromo_Animated_${uploadData.photo_id || 'gif'}.gif`;
            btnDownloadGif.classList.remove('opacity-50', 'pointer-events-none');
            tabShowGif.classList.remove('hidden');
        } else {
            btnDownloadGif.classList.add('opacity-50', 'pointer-events-none');
            tabShowGif.classList.add('hidden');
        }

        // Default to Photo Strip Tab
        showStripTab();

        // Trigger Dispenser Printing Animation
        resultStripImg.classList.remove('animate-print-slide');
        void resultStripImg.offsetWidth; // trigger reflow
        resultStripImg.classList.add('animate-print-slide');

        // Render QR Code
        qrCodeContainer.innerHTML = '';
        const qrTargetUrl = uploadData.qr_url || window.location.href;
        
        qrCodeInstance = new QRCode(qrCodeContainer, {
            text: qrTargetUrl,
            width: 175,
            height: 175,
            colorDark: "#1E1B18",
            colorLight: "#FFFFFF",
            correctLevel: QRCode.CorrectLevel.M
        });

        resultModal.classList.remove('hidden');

        // Confetti Celebration
        try {
            confetti({
                particleCount: 85,
                spread: 80,
                origin: { y: 0.6 }
            });
        } catch(e) {}

        // Start 45s Auto-Reset Countdown
        startAutoResetTimer(45);
    }

    function showStripTab() {
        resultStripImg.classList.remove('hidden');
        resultGifImg.classList.add('hidden');
        tabShowStrip.className = "py-1.5 px-4 bg-white border-2 border-paper-900 rounded-xl text-xs font-display font-black shadow-tactile-sm text-festive-crimson cursor-pointer";
        tabShowGif.className = "py-1.5 px-4 bg-paper-200 border-2 border-paper-900 rounded-xl text-xs font-display font-bold text-slate-600 hover:bg-white transition-all cursor-pointer";
    }

    function showGifTab() {
        resultStripImg.classList.add('hidden');
        resultGifImg.classList.remove('hidden');
        tabShowGif.className = "py-1.5 px-4 bg-white border-2 border-paper-900 rounded-xl text-xs font-display font-black shadow-tactile-sm text-festive-indigo cursor-pointer";
        tabShowStrip.className = "py-1.5 px-4 bg-paper-200 border-2 border-paper-900 rounded-xl text-xs font-display font-bold text-slate-600 hover:bg-white transition-all cursor-pointer";
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
