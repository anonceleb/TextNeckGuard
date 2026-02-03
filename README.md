# Text Neck Haptic Guard 🛡️

A "Sophisticated" Utility that runs quietly in the background (or as an active "Reading Mode") to protect your neck posture.

**Target**: Commuters, Heavy phone users.  
**The Tech**: MediaPipe Pose (Neck/Shoulder landmarks) running entirely in the browser (PWA).

## The Problem
Looking down at a phone at 60° puts **60lbs of force** on the neck ("Text Neck"). This leads to pain, strain, and long-term spinal issues.

## The Solution
When your neck angle exceeds a safe threshold (e.g. 45°) for more than a set time, the phone **gently vibrates** or **blurs the text**. It forces you to lift the phone to eye level to read clearly.

**Why it works**: Immediate, physical feedback loop. No charts, no doctors, just "Fix your posture to continue reading."

## Features

- **Reading Mode**: Distraction-free dark mode reader.
- **Real-time Monitoring**: Uses front-facing camera to detect neck flexion.
- **Privacy First**: All processing happens locally on your device. No video is uploaded.
- **Calibration**: "Zero" the sensor to your comfortable reading position.
- **Custom Content**: Paste your own articles or books to read.
- **Installable**: Works as a Progressive Web App (PWA) on iOS and Android.

## Quick Start (Local)

This is a static web app. To test it locally:

1.  Clone this repo.
2.  Navigate to the `pwa` folder:
    ```bash
    cd pwa
    ```
3.  Start a local HTTP server:
    ```bash
    # Python 3
    python3 -m http.server 8000
    ```
4.  Open `http://localhost:8000` in your browser.

> **Note**: For Haptics (vibration) to work on mobile, the site must be served over **HTTPS** (or localhost). 

## Deployment

Deploy the `pwa` directory to any static host (Netlify, Vercel, GitHub Pages).

### Netlify
1.  Drag the `pwa` folder to Netlify Drop.
2.  That's it!

## License
MIT License.
