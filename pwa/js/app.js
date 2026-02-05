/**
 * Spine Shine - app.js
 * Uses MediaPipe Pose to detect neck flexion and triggered haptic feedback.
 */

// DOM Elements
const videoElement = document.getElementById('input-video');
const canvasElement = document.getElementById('output-canvas');
const canvasCtx = canvasElement.getContext('2d');
const toggleBtn = document.getElementById('toggle-guard-btn');
const statusIndicator = document.getElementById('status-indicator');
const statusText = document.getElementById('status-text');
const readingContainer = document.getElementById('reading-container');
const debugInfo = document.getElementById('debug-info');
const cameraPreview = document.getElementById('camera-preview');
const closePreviewBtn = document.getElementById('close-preview');

// Settings DOM
const settingsBtn = document.getElementById('settings-btn');
const settingsModal = document.getElementById('settings-modal');
const closeSettingsBtn = document.getElementById('close-settings');
const calibrateBtn = document.getElementById('calibrate-btn');
const calibStatus = document.getElementById('calibration-status');
const sensitivitySlider = document.getElementById('sensitivity-slider');
const sensitivityVal = document.getElementById('sensitivity-val');
const customInput = document.getElementById('custom-text-input');
const loadTextBtn = document.getElementById('load-text-btn');
const toggleDebugBtn = document.getElementById('toggle-debug-btn');
const articleContent = document.getElementById('sample-article');
const timerSlider = document.getElementById('timer-slider');
const timerVal = document.getElementById('timer-val');
const pipBtn = document.getElementById('pip-btn');

// PiP State
let pipWindow = null;
let pipStatusIndicator = null;
let pipStatusText = null;

// State
let isGuardActive = false;
let isCameraRunning = false;
let badPostureStartTime = null;
let lastFeedbackTime = 0;
let camera = null;
let pose = null;

// Config / Calibration
let baselineRatio = 0.95; // Default "good" ratio (approx)
let sensitivity = 0.85; // Multiplier. Threshold = Baseline * Sensitivity
let badPostureThreshold = baselineRatio * sensitivity;
let latestRatio = 0; // Current live ratio

// const TIME_LIMIT_MS = 2 * 60 * 1000;
let timeLimitMs = 5000; // Default 5s
const FEEDBACK_COOLDOWN = 5000;

// --- Initialization ---

function init() {
    loadSettings();
    setupEventListeners();
    initMediaPipe();
    updateThreshold();
    checkPiPSupport();
}

function checkPiPSupport() {
    if ('documentPictureInPicture' in window) {
        pipBtn.classList.remove('hidden');
    }
}

function loadSettings() {
    // Load from LocalStorage
    const savedBaseline = localStorage.getItem('textNeck_baseline');
    const savedSens = localStorage.getItem('textNeck_sensitivity');
    const savedText = localStorage.getItem('textNeck_customText');
    const savedTimer = localStorage.getItem('textNeck_timer');

    if (savedBaseline) {
        baselineRatio = parseFloat(savedBaseline);
        calibStatus.innerText = `Saved (Baseline: ${baselineRatio.toFixed(2)})`;
    }

    if (savedSens) {
        sensitivity = parseFloat(savedSens);
        sensitivitySlider.value = sensitivity;
        sensitivityVal.innerText = sensitivity;
    }

    if (savedText) {
        updateArticle(savedText);
    }

    if (savedTimer) {
        timeLimitMs = parseInt(savedTimer, 10);
        timerSlider.value = timeLimitMs / 1000;
        timerVal.innerText = (timeLimitMs / 1000) + 's';
    }
}

function setupEventListeners() {
    toggleBtn.addEventListener('click', toggleGuard);
    pipBtn.addEventListener('click', togglePiP);

    // Settings Modal

    // Settings Modal
    settingsBtn.addEventListener('click', () => {
        settingsModal.classList.remove('hidden');
    });

    closeSettingsBtn.addEventListener('click', () => {
        settingsModal.classList.add('hidden');
    });

    // Calibration
    calibrateBtn.addEventListener('click', performCalibration);

    // Sensitivity
    sensitivitySlider.addEventListener('input', (e) => {
        sensitivity = parseFloat(e.target.value);
        sensitivityVal.innerText = sensitivity;
        localStorage.setItem('textNeck_sensitivity', sensitivity);
        localStorage.setItem('textNeck_sensitivity', sensitivity);
        updateThreshold();
    });

    // Timer
    timerSlider.addEventListener('input', (e) => {
        const seconds = parseInt(e.target.value, 10);
        timeLimitMs = seconds * 1000;
        timerVal.innerText = seconds + 's';
        localStorage.setItem('textNeck_timer', timeLimitMs);
    });

    // Custom Text
    loadTextBtn.addEventListener('click', () => {
        const text = customInput.value;
        if (text.trim().length > 0) {
            updateArticle(text);
            localStorage.setItem('textNeck_customText', text);
            customInput.value = '';
            settingsModal.classList.add('hidden');
        }
    });

    // Debug
    toggleDebugBtn.addEventListener('click', () => {
        cameraPreview.classList.toggle('hidden');
    });

    closePreviewBtn.addEventListener('click', () => {
        cameraPreview.classList.add('hidden');
    });
}

function updateThreshold() {
    badPostureThreshold = baselineRatio * sensitivity;
    // sanity check
    if (badPostureThreshold < 0.1) badPostureThreshold = 0.1;
}

function updateArticle(text) {
    // Simple parser: Split by double newline for paragraphs
    const paragraphs = text.split(/\n\s*\n/);
    let html = '<h2>My Reading List</h2>';
    paragraphs.forEach(p => {
        if (p.trim().length > 0) {
            html += `<p>${p.trim()}</p>`;
        }
    });
    articleContent.innerHTML = html;
}

function performCalibration() {
    // We assume the user is sitting straight NOW.
    // We take the 'latestRatio' as the new baseline.
    if (latestRatio > 0) {
        baselineRatio = latestRatio;
        updateThreshold();
        localStorage.setItem('textNeck_baseline', baselineRatio);

        calibStatus.innerText = `Calibrated! (Baseline: ${baselineRatio.toFixed(2)})`;
        calibStatus.style.color = '#10b981';

        // Flash success
        calibrateBtn.textContent = 'Success!';
        setTimeout(() => calibrateBtn.textContent = 'Set Healthy Posture (Zero)', 2000);
    } else {
        calibStatus.innerText = 'Error: No camera data. Start Guard first?';
        calibStatus.style.color = '#ef4444';
    }
}

function initMediaPipe() {
    pose = new Pose({
        locateFile: (file) => {
            return `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`;
        }
    });

    pose.setOptions({
        modelComplexity: 1,
        smoothLandmarks: true,
        enableSegmentation: false,
        minDetectionConfidence: 0.5,
        minTrackingConfidence: 0.5
    });

    pose.onResults(onPoseResults);

    camera = new Camera(videoElement, {
        onFrame: async () => {
            if (isGuardActive || !settingsModal.classList.contains('hidden')) {
                // Run pose detection if Active OR if Settings are open (for calibration)
                // Note: We need to start the camera stream if it's not started.
                await pose.send({ image: videoElement });
            }
        },
        width: 640,
        height: 480,
        facingMode: 'user'
    });
}

async function toggleGuard() {
    isGuardActive = !isGuardActive;

    if (isGuardActive) {
        toggleBtn.textContent = '⏹ Stop Guard';
        toggleBtn.classList.add('active');
        statusIndicator.classList.remove('warning');
        statusIndicator.classList.add('active');
        statusText.textContent = 'Monitoring...';

        if (!isCameraRunning) {
            await camera.start();
            isCameraRunning = true;
        }
    } else {
        toggleBtn.textContent = '🛡️ Activate';
        toggleBtn.classList.remove('active');
        statusIndicator.classList.remove('active', 'warning');
        statusText.textContent = 'Inactive';

        disablePenalty();
        badPostureStartTime = null;
    }
    updateStatusUI();
}

async function togglePiP() {
    if (!pipWindow) {
        // Open PiP
        try {
            pipWindow = await documentPictureInPicture.requestWindow({
                width: 300,
                height: 150,
            });

            // Add Class for styling
            pipWindow.document.body.classList.add('pip-mode');

            // Copy Styles
            // 1. Main Styles
            const mainStyleLink = document.createElement('link');
            mainStyleLink.rel = 'stylesheet';
            mainStyleLink.href = 'css/style.css';
            pipWindow.document.head.appendChild(mainStyleLink);

            // 2. PiP Specific Styles
            const pipStyleLink = document.createElement('link');
            pipStyleLink.rel = 'stylesheet';
            pipStyleLink.href = 'css/pip.css';
            pipWindow.document.head.appendChild(pipStyleLink);

            // Construct Content
            const container = document.createElement('div');
            container.innerHTML = `
                <div class="status-indicator" id="pip-status-indicator">
                    <span id="pip-status-text">Great Posture</span>
                </div>
                <div class="pip-controls">
                     <button id="pip-close-btn" style="padding: 4px 8px; font-size: 0.8rem;">Stop</button>
                </div>
            `;
            pipWindow.document.body.appendChild(container);

            // Init PiP Refs
            pipStatusIndicator = pipWindow.document.getElementById('pip-status-indicator');
            pipStatusText = pipWindow.document.getElementById('pip-status-text');

            // Event Listeners
            pipWindow.document.getElementById('pip-close-btn').addEventListener('click', () => {
                pipWindow.close();
            });

            // Handle Closing
            pipWindow.addEventListener('pagehide', () => {
                pipWindow = null;
                pipStatusIndicator = null;
                pipStatusText = null;
                pipBtn.classList.remove('active'); // Optional visual state
            });

            updateStatusUI(); // Sync immediate state

        } catch (err) {
            console.error("Failed to open PiP:", err);
        }
    } else {
        // Close PiP
        pipWindow.close();
    }
}

function updateStatusUI(reason = 'GOOD') {
    // Determine current state text/class
    let text = 'Inactive';
    let isWarning = false;
    let isActive = isGuardActive;
    let emoji = '😴'; // Default Sleep

    if (isGuardActive) {
        if (reason === 'IDLE') {
            // User left the frame - reset timer and show idle
            badPostureStartTime = null;
            text = 'Away / Idle';
            emoji = '😴';
            isWarning = false;
        } else if (badPostureStartTime) {
            const duration = Date.now() - badPostureStartTime;
            let type = 'Bad Posture';

            if (reason === 'TILT') type = 'Tilting!';
            else if (reason === 'SHRUG') type = 'Shrugging!';
            else type = 'Slouching!';

            text = `${type} (${Math.floor(duration / 1000)}s)`;
            isWarning = true;

            // Avatar Logic
            if (reason === 'TILT') emoji = '📐'; // Ruler
            else if (reason === 'SHRUG') emoji = '💪'; // Flexed bicep
            else emoji = '🐢'; // Turtle (Slouch)

        } else {
            text = 'Great Posture';
            emoji = '🦒'; // Giraffe (Tall/Good)
        }
    }

    // Update Main UI
    statusText.textContent = text;
    if (isActive) {
        statusIndicator.classList.add('active');
        if (isWarning) statusIndicator.classList.add('warning');
        else statusIndicator.classList.remove('warning');
    } else {
        statusIndicator.classList.remove('active', 'warning');
    }

    // Update PiP UI if exists
    if (pipWindow && pipStatusIndicator && pipStatusText) {
        pipStatusText.textContent = text;

        if (isActive) {
            pipStatusIndicator.classList.add('active');
            if (isWarning) pipStatusIndicator.classList.add('warning');
            else pipStatusIndicator.classList.remove('warning');
        } else {
            pipStatusIndicator.classList.remove('active', 'warning');
        }
    }
}

function onPoseResults(results) {
    if (!results.poseLandmarks) {
        // No user detected -> IDLE
        updateStatusUI('IDLE');
        return;
    }

    drawDebug(results);

    // Analyze Posture
    const landmarks = results.poseLandmarks;
    const leftEar = landmarks[7];
    const rightEar = landmarks[8];
    const leftMouth = landmarks[9];
    const rightMouth = landmarks[10];
    const leftShoulder = landmarks[11];
    const rightShoulder = landmarks[12];

    const mouthX = (leftMouth.x + rightMouth.x) / 2;
    const mouthY = (leftMouth.y + rightMouth.y) / 2;
    const shoulderX = (leftShoulder.x + rightShoulder.x) / 2;
    const shoulderY = (leftShoulder.y + rightShoulder.y) / 2;

    const distMouthToShoulder = Math.hypot(mouthX - shoulderX, mouthY - shoulderY);
    const distEarToEar = Math.hypot(leftEar.x - rightEar.x, leftEar.y - rightEar.y);

    if (distEarToEar < 0.01) return;

    // Store latest for calibration
    latestRatio = distMouthToShoulder / distEarToEar;

    // Debug Visualization
    const leftEarY = leftEar.y;
    const rightEarY = rightEar.y;
    const avgEarY = (leftEarY + rightEarY) / 2;
    const leftShoulderY = leftShoulder.y;
    const rightShoulderY = rightShoulder.y;
    const avgShoulderY = (leftShoulderY + rightShoulderY) / 2;
    const earToShoulderDist = avgShoulderY - avgEarY;

    // Expose for calibration wizard
    window.latestEarToShoulderDist = earToShoulderDist;

    debugInfo.innerHTML = `Curr: ${latestRatio.toFixed(2)} <br> Thresh: ${badPostureThreshold.toFixed(2)} (Base:${baselineRatio.toFixed(2)}) <br> Ear-Shoulder: ${earToShoulderDist.toFixed(3)}`;

    if (!isGuardActive) return; // Only trigger if active

    // Check Thresholds
    let postureState = 'GOOD'; // GOOD, SLOUCH, TILT, SHRUG

    // 1. Check Shoulder Shrug FIRST (before slouch check)
    // When shrugging, shoulders rise and ear-to-shoulder distance decreases
    const shrugThreshold = 0.38; // Calibrated: normal ~0.48, full shrug ~0.39

    if (earToShoulderDist < shrugThreshold) {
        postureState = 'SHRUG';
    }

    // 2. Check Forward Head (Slouch) - only if not shrugging
    if (postureState === 'GOOD' && latestRatio < badPostureThreshold) {
        postureState = 'SLOUCH';
    }

    // 3. Check Lateral Tilt (Side Bending)
    const earYDiff = Math.abs(leftEar.y - rightEar.y);
    const tiltThreshold = distEarToEar * 0.35; // Approx 20 degrees tilt tolerance

    // Expose for calibration wizard
    window.latestEarYDiff = earYDiff;

    if (earYDiff > tiltThreshold && postureState === 'GOOD') {
        postureState = 'TILT';
    }

    if (postureState !== 'GOOD') {
        handleBadPosture(true, postureState);
    } else {
        handleBadPosture(false);
    }
}

function handleBadPosture(isBad, reason = 'BAD') {
    if (isBad) {
        if (!badPostureStartTime) {
            badPostureStartTime = Date.now();
        }

        const duration = Date.now() - badPostureStartTime;
        // statusText.textContent = `Bad Posture (${Math.floor(duration / 1000)}s)`;
        // statusIndicator.classList.add('warning');
        updateStatusUI(reason); // Pass reason to UI

        if (duration > timeLimitMs) {
            triggerPenalty();
        }

    } else {
        badPostureStartTime = null;
        // statusText.textContent = 'Posture: Good';
        // statusIndicator.classList.remove('warning');
        // statusIndicator.classList.add('active');
        updateStatusUI('GOOD');
        disablePenalty();
    }
}

function triggerPenalty() {
    document.body.classList.add('blur-mode');

    const now = Date.now();
    if (now - lastFeedbackTime > FEEDBACK_COOLDOWN) {
        if (navigator.vibrate) {
            navigator.vibrate([200, 100, 200]);
        }
        lastFeedbackTime = now;
    }
}

function disablePenalty() {
    document.body.classList.remove('blur-mode');
}

function drawDebug(results) {
    if (cameraPreview.classList.contains('hidden')) return;

    canvasCtx.save();
    canvasCtx.clearRect(0, 0, canvasElement.width, canvasElement.height);
    canvasElement.width = videoElement.videoWidth;
    canvasElement.height = videoElement.videoHeight;

    if (results.poseLandmarks) {
        drawConnectors(canvasCtx, results.poseLandmarks, POSE_CONNECTIONS,
            { color: '#00FF00', lineWidth: 2 });
        drawLandmarks(canvasCtx, results.poseLandmarks,
            { color: '#FF0000', lineWidth: 1 });
    }
    canvasCtx.restore();
}

init();
