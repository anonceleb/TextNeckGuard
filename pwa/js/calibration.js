/**
 * Calibration Wizard Logic
 * Handles step-by-step calibration flow and threshold calculation
 */

// Calibration State
const calibrationState = {
    currentStep: 0,
    samples: {
        goodPosture: [],
        slouch: [],
        tilt: [],
        shrug: []
    },
    thresholds: null
};

// DOM Elements
const calModal = document.getElementById('calibration-modal');
const calSteps = document.querySelectorAll('.calibration-step');
const calProgressDots = document.querySelectorAll('.progress-dot');

// Button Elements
const calCancelBtn = document.getElementById('cal-cancel');
const calStartBtn = document.getElementById('cal-start');
const calCollectGoodBtn = document.getElementById('cal-collect-good');
const calCollectSlouchBtn = document.getElementById('cal-collect-slouch');
const calCollectTiltBtn = document.getElementById('cal-collect-tilt');
const calCollectShrugBtn = document.getElementById('cal-collect-shrug');
const calRecalibrateBtn = document.getElementById('cal-recalibrate');
const calFinishBtn = document.getElementById('cal-finish');

// Progress Elements
const calGoodCount = document.getElementById('cal-good-count');
const calGoodProgress = document.getElementById('cal-good-progress');
const calSlouchCount = document.getElementById('cal-slouch-count');
const calSlouchProgress = document.getElementById('cal-slouch-progress');
const calTiltCount = document.getElementById('cal-tilt-count');
const calTiltProgress = document.getElementById('cal-tilt-progress');
const calShrugCount = document.getElementById('cal-shrug-count');
const calShrugProgress = document.getElementById('cal-shrug-progress');
const calSummary = document.getElementById('cal-summary');

function openCalibrationWizard() {
    // Reset state
    calibrationState.currentStep = 0;
    calibrationState.samples = {
        goodPosture: [],
        slouch: [],
        tilt: [],
        shrug: []
    };

    // Show modal
    calModal.classList.remove('hidden');
    goToCalibrationStep(0);

    // Ensure camera is running
    if (!isCameraRunning) {
        camera.start();
        isCameraRunning = true;
    }
}

function closeCalibrationWizard() {
    calModal.classList.add('hidden');
}

function goToCalibrationStep(step) {
    calibrationState.currentStep = step;

    // Update step visibility
    calSteps.forEach((stepEl, idx) => {
        if (idx === step) {
            stepEl.classList.add('active');
        } else {
            stepEl.classList.remove('active');
        }
    });

    // Update progress dots
    calProgressDots.forEach((dot, idx) => {
        if (idx < step) {
            dot.classList.add('completed');
            dot.classList.remove('active');
        } else if (idx === step) {
            dot.classList.add('active');
            dot.classList.remove('completed');
        } else {
            dot.classList.remove('active', 'completed');
        }
    });
}

function collectSample(type) {
    // Get current pose data
    if (!latestRatio || latestRatio === 0) {
        alert('No pose detected. Please ensure you are visible to the camera.');
        return;
    }

    // Get current measurements
    const sample = {
        ratio: latestRatio,
        earToShoulderDist: window.latestEarToShoulderDist || 0,
        earYDiff: window.latestEarYDiff || 0
    };

    calibrationState.samples[type].push(sample);

    // Update UI
    const count = calibrationState.samples[type].length;
    const progress = (count / 3) * 100;

    switch (type) {
        case 'goodPosture':
            calGoodCount.textContent = count;
            calGoodProgress.style.width = progress + '%';
            if (count >= 3) {
                setTimeout(() => goToCalibrationStep(2), 500);
            }
            break;
        case 'slouch':
            calSlouchCount.textContent = count;
            calSlouchProgress.style.width = progress + '%';
            if (count >= 3) {
                setTimeout(() => goToCalibrationStep(3), 500);
            }
            break;
        case 'tilt':
            calTiltCount.textContent = count;
            calTiltProgress.style.width = progress + '%';
            if (count >= 3) {
                setTimeout(() => goToCalibrationStep(4), 500);
            }
            break;
        case 'shrug':
            calShrugCount.textContent = count;
            calShrugProgress.style.width = progress + '%';
            if (count >= 3) {
                calculateThresholds();
                setTimeout(() => goToCalibrationStep(5), 500);
            }
            break;
    }
}

function calculateThresholds() {
    const { goodPosture, slouch, tilt, shrug } = calibrationState.samples;

    // Calculate averages
    const avgGoodRatio = average(goodPosture.map(s => s.ratio));
    const avgSlouchRatio = average(slouch.map(s => s.ratio));
    const avgTiltEarYDiff = average(tilt.map(s => s.earYDiff));
    const avgShrugDist = average(shrug.map(s => s.earToShoulderDist));

    // Calculate thresholds (midpoint between good and bad)
    const slouchThreshold = (avgGoodRatio + avgSlouchRatio) / 2;
    const tiltThreshold = avgTiltEarYDiff * 0.8; // 80% of tilt value
    const shrugThreshold = (avgGoodRatio + avgShrugDist) / 2;

    calibrationState.thresholds = {
        baselineRatio: avgGoodRatio,
        slouchThreshold: slouchThreshold,
        tiltThreshold: tiltThreshold,
        shrugThreshold: shrugThreshold,
        calibrationDate: Date.now()
    };

    // Display summary
    calSummary.innerHTML = `
        <div class="summary-item">
            <span class="summary-label">Good Posture Baseline:</span>
            <span class="summary-value">${avgGoodRatio.toFixed(3)}</span>
        </div>
        <div class="summary-item">
            <span class="summary-label">Slouch Threshold:</span>
            <span class="summary-value">${slouchThreshold.toFixed(3)}</span>
        </div>
        <div class="summary-item">
            <span class="summary-label">Tilt Threshold:</span>
            <span class="summary-value">${tiltThreshold.toFixed(3)}</span>
        </div>
        <div class="summary-item">
            <span class="summary-label">Shrug Threshold:</span>
            <span class="summary-value">${shrugThreshold.toFixed(3)}</span>
        </div>
    `;
}

function average(arr) {
    return arr.reduce((sum, val) => sum + val, 0) / arr.length;
}

function saveCalibration() {
    if (!calibrationState.thresholds) return;

    // Save to localStorage
    localStorage.setItem('textNeck_calibration', JSON.stringify(calibrationState.thresholds));

    // Apply to current session
    baselineRatio = calibrationState.thresholds.baselineRatio;
    badPostureThreshold = calibrationState.thresholds.slouchThreshold;

    // Update UI
    calibStatus.innerText = `Calibrated (${new Date(calibrationState.thresholds.calibrationDate).toLocaleDateString()})`;
    calibStatus.style.color = '#10b981';

    closeCalibrationWizard();
}

function loadCalibration() {
    const saved = localStorage.getItem('textNeck_calibration');
    if (saved) {
        const cal = JSON.parse(saved);
        baselineRatio = cal.baselineRatio;
        badPostureThreshold = cal.slouchThreshold;

        calibStatus.innerText = `Calibrated (${new Date(cal.calibrationDate).toLocaleDateString()})`;
        calibStatus.style.color = '#10b981';
    }
}

// Event Listeners
calCancelBtn.addEventListener('click', closeCalibrationWizard);
calStartBtn.addEventListener('click', () => goToCalibrationStep(1));
calCollectGoodBtn.addEventListener('click', () => collectSample('goodPosture'));
calCollectSlouchBtn.addEventListener('click', () => collectSample('slouch'));
calCollectTiltBtn.addEventListener('click', () => collectSample('tilt'));
calCollectShrugBtn.addEventListener('click', () => collectSample('shrug'));
calRecalibrateBtn.addEventListener('click', () => {
    goToCalibrationStep(0);
    calibrationState.samples = {
        goodPosture: [],
        slouch: [],
        tilt: [],
        shrug: []
    };
});
calFinishBtn.addEventListener('click', saveCalibration);

// Add button to open wizard from settings
const openCalWizardBtn = document.createElement('button');
openCalWizardBtn.textContent = 'Start Calibration Wizard';
openCalWizardBtn.className = 'btn-secondary';
openCalWizardBtn.style.marginTop = '10px';
openCalWizardBtn.addEventListener('click', openCalibrationWizard);
calibrateBtn.parentElement.appendChild(openCalWizardBtn);
