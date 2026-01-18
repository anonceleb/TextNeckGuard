# Running Form Analysis Tool

A Python tool that analyzes running gait from video using MediaPipe pose estimation. Outputs an annotated video with skeleton overlay and detailed text feedback on your running form.

## Features

- **Pose Estimation**: Uses Google MediaPipe for accurate body tracking
- **Gait Metrics**:
  - Cadence (steps per minute)
  - Knee angle at ground contact
  - Hip drop (pelvic stability)
  - Forward lean (trunk angle)
  - Vertical oscillation
- **Visual Output**: Annotated video with skeleton overlay and real-time metrics
- **Text Report**: Detailed feedback with recommendations

## Installation

```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Basic usage
```bash
python analyze_form.py your_video.mp4
```

This will create:
- `your_video_analyzed.mp4` - Annotated video with skeleton overlay
- `your_video_report.txt` - Text report with feedback

### Custom output paths
```bash
python analyze_form.py runner.mp4 --output analyzed.mp4 --report report.txt
```

### Help
```bash
python analyze_form.py --help
```

## Recording Tips

For best results:

1. **Camera Position**: 
   - Side view (perpendicular to running direction)
   - About 3-5 meters away
   - Camera at hip height

2. **Lighting**:
   - Good, even lighting
   - Avoid backlighting/silhouettes

3. **Clothing**:
   - Fitted clothes work better than baggy
   - Contrasting colors from background help

4. **Duration**:
   - 10-30 seconds is sufficient
   - Steady-state running (not accelerating/decelerating)

5. **Surface**:
   - Flat ground preferred
   - Treadmill works well

## Understanding the Output

### Cadence
- **Optimal Range**: 170-180 steps/minute
- Low cadence often indicates overstriding

### Knee Angle
- **At Contact**: Should be slightly bent (160-170°)
- Very straight knee may indicate overstriding

### Hip Drop
- **Ideal**: Minimal (<5°)
- Excessive drop indicates weak glutes/hip abductors

### Forward Lean
- **Optimal**: 5-12° forward
- Should come from ankles, not waist

### Vertical Oscillation
- **Efficient**: Minimal bounce
- High oscillation wastes energy

## Limitations

- Works best with side-view video
- Single runner in frame
- Consistent pace during recording
- Not a replacement for professional gait analysis

## Example Output

```
============================================================
RUNNING FORM ANALYSIS REPORT
============================================================

Analysis Duration: 15.2 seconds
Steps Detected: 42

----------------------------------------
CADENCE
----------------------------------------
Your cadence: 166 steps/minute
📊 Cadence is slightly below optimal
   Target: 175-180 for efficient running

----------------------------------------
HIP STABILITY (Pelvic Drop)
----------------------------------------
Average hip drop: 7.2°
📊 Mild hip drop - some room for improvement
   Consider adding hip strengthening exercises

...
```

## Tech Stack

- **MediaPipe**: Pose estimation (33 keypoints)
- **OpenCV**: Video processing
- **NumPy**: Calculations

## Contributing

This is a prototype for "Form Check Friday" content. Feedback welcome!

## License

MIT License - Use freely, attribution appreciated.
