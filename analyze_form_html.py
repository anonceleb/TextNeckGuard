#!/usr/bin/env python3
"""
Running Form Analysis Tool - HTML Report Generator
---------------------------------------------------
Creates a presentable HTML report with embedded video and analysis feedback.
"""

import argparse
import base64
import math
import sys
from pathlib import Path
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from datetime import datetime

import cv2
import mediapipe as mp
import numpy as np


# MediaPipe Pose landmark indices
class Landmarks:
    NOSE = 0
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_HEEL = 29
    RIGHT_HEEL = 30
    LEFT_FOOT_INDEX = 31
    RIGHT_FOOT_INDEX = 32


@dataclass
class GaitMetrics:
    """Stores calculated gait metrics from analysis."""
    cadence: float = 0.0
    avg_knee_angle_at_contact: float = 0.0
    avg_hip_drop: float = 0.0
    avg_forward_lean: float = 0.0
    avg_vertical_oscillation: float = 0.0
    overstriding_detected: bool = False
    step_count: int = 0
    analysis_duration: float = 0.0
    
    knee_angles: list = field(default_factory=list)
    hip_drops: list = field(default_factory=list)
    forward_leans: list = field(default_factory=list)
    vertical_positions: list = field(default_factory=list)
    
    # Quality indicators
    confidence_scores: list = field(default_factory=list)
    avg_confidence: float = 0.0
    data_quality: str = "Unknown"


def calculate_angle(a: tuple, b: tuple, c: tuple) -> float:
    """Calculate angle at point b given three points."""
    ba = np.array([a[0] - b[0], a[1] - b[1]])
    bc = np.array([c[0] - b[0], c[1] - b[1]])
    
    cosine = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    cosine = np.clip(cosine, -1.0, 1.0)
    return np.degrees(np.arccos(cosine))


def calculate_angle_from_vertical(point1: tuple, point2: tuple) -> float:
    """Calculate angle of line from vertical."""
    dx = point2[0] - point1[0]
    dy = point1[1] - point2[1]  # Adjust for image coordinates where y increases downwards
    return math.degrees(math.atan2(dx, dy))


def get_landmark_coords(landmarks, idx, frame_width, frame_height):
    """Extract x, y coordinates from landmark."""
    lm = landmarks.landmark[idx]
    return (int(lm.x * frame_width), int(lm.y * frame_height))


def get_landmark_visibility(landmarks, idx) -> float:
    """Get visibility score for a landmark."""
    return landmarks.landmark[idx].visibility


class RunningFormAnalyzer:
    """Analyzes running form from video using MediaPipe pose estimation."""
    
    def __init__(self, video_path: str):
        self.video_path = Path(video_path)
        if not self.video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")
        
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=2,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        self.cap = cv2.VideoCapture(str(self.video_path))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        self.metrics = GaitMetrics()
        self.step_frames = []
        self.hip_y_positions = []
        self.left_ankle_history = []
        self.right_ankle_history = []
        
    def analyze(self, output_path: Optional[str] = None) -> GaitMetrics:
        """Analyze the video and return gait metrics."""
        writer = None
        if output_path:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(
                output_path, fourcc, self.fps, 
                (self.frame_width, self.frame_height)
            )
        
        frame_count = 0
        
        print(f"Analyzing video: {self.video_path.name}")
        print(f"Resolution: {self.frame_width}x{self.frame_height}, FPS: {self.fps:.1f}")
        print()
        
        while self.cap.isOpened():
            success, frame = self.cap.read()
            if not success:
                break
            
            frame_count += 1
            
            if frame_count % 30 == 0:
                progress = (frame_count / self.total_frames) * 100
                print(f"\rProcessing: {progress:.1f}%", end="", flush=True)
            
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.pose.process(frame_rgb)
            
            if results.pose_landmarks:
                landmarks = results.pose_landmarks
                
                # Track confidence
                avg_vis = np.mean([landmarks.landmark[i].visibility for i in 
                                   [Landmarks.LEFT_HIP, Landmarks.RIGHT_HIP,
                                    Landmarks.LEFT_KNEE, Landmarks.RIGHT_KNEE,
                                    Landmarks.LEFT_ANKLE, Landmarks.RIGHT_ANKLE]])
                self.metrics.confidence_scores.append(avg_vis)
                
                # Extract key points
                left_hip = get_landmark_coords(landmarks, Landmarks.LEFT_HIP, 
                                                self.frame_width, self.frame_height)
                right_hip = get_landmark_coords(landmarks, Landmarks.RIGHT_HIP,
                                                 self.frame_width, self.frame_height)
                left_knee = get_landmark_coords(landmarks, Landmarks.LEFT_KNEE,
                                                 self.frame_width, self.frame_height)
                right_knee = get_landmark_coords(landmarks, Landmarks.RIGHT_KNEE,
                                                  self.frame_width, self.frame_height)
                left_ankle = get_landmark_coords(landmarks, Landmarks.LEFT_ANKLE,
                                                  self.frame_width, self.frame_height)
                right_ankle = get_landmark_coords(landmarks, Landmarks.RIGHT_ANKLE,
                                                   self.frame_width, self.frame_height)
                left_shoulder = get_landmark_coords(landmarks, Landmarks.LEFT_SHOULDER,
                                                     self.frame_width, self.frame_height)
                right_shoulder = get_landmark_coords(landmarks, Landmarks.RIGHT_SHOULDER,
                                                      self.frame_width, self.frame_height)
                
                mid_hip = ((left_hip[0] + right_hip[0]) // 2, 
                           (left_hip[1] + right_hip[1]) // 2)
                mid_shoulder = ((left_shoulder[0] + right_shoulder[0]) // 2,
                                (left_shoulder[1] + right_shoulder[1]) // 2)
                
                self.hip_y_positions.append(mid_hip[1])
                self.left_ankle_history.append(left_ankle[1])
                self.right_ankle_history.append(right_ankle[1])
                
                # Calculate metrics
                left_knee_angle = calculate_angle(left_hip, left_knee, left_ankle)
                right_knee_angle = calculate_angle(right_hip, right_knee, right_ankle)
                self.metrics.knee_angles.append((left_knee_angle, right_knee_angle))
                
                hip_drop = abs(left_hip[1] - right_hip[1])
                hip_drop_degrees = math.degrees(math.atan2(hip_drop, 
                                                           abs(left_hip[0] - right_hip[0]) + 1))
                self.metrics.hip_drops.append(hip_drop_degrees)
                
                forward_lean = calculate_angle_from_vertical(mid_hip, mid_shoulder)
                self.metrics.forward_leans.append(forward_lean)
                
                # Draw on frame
                self.mp_drawing.draw_landmarks(
                    frame, landmarks, self.mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=self.mp_drawing_styles.get_default_pose_landmarks_style()
                )
                
                self._draw_metrics_overlay(frame, left_knee_angle, right_knee_angle,
                                           hip_drop_degrees, forward_lean, frame_count)
            
            if writer:
                writer.write(frame)
        
        print("\rProcessing: 100.0%")
        print()
        
        self.cap.release()
        if writer:
            writer.release()
        self.pose.close()
        
        self._calculate_final_metrics(frame_count)
        self._detect_steps_improved()
        
        return self.metrics
    
    def _draw_metrics_overlay(self, frame, left_knee_angle, right_knee_angle,
                               hip_drop, forward_lean, frame_count):
        """Draw real-time metrics on the frame."""
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (350, 150), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        color = (255, 255, 255)
        
        y_offset = 35
        cv2.putText(frame, f"Frame: {frame_count}", (20, y_offset), font, 0.6, color, 1)
        y_offset += 25
        cv2.putText(frame, f"L Knee: {left_knee_angle:.1f} deg", (20, y_offset), font, 0.6, color, 1)
        y_offset += 25
        cv2.putText(frame, f"R Knee: {right_knee_angle:.1f} deg", (20, y_offset), font, 0.6, color, 1)
        y_offset += 25
        cv2.putText(frame, f"Hip Drop: {hip_drop:.1f} deg", (20, y_offset), font, 0.6, color, 1)
        y_offset += 25
        cv2.putText(frame, f"Forward Lean: {forward_lean:.1f} deg", (20, y_offset), font, 0.6, color, 1)
    
    def _detect_steps_improved(self):
        """Improved step detection using ankle position oscillation."""
        if len(self.left_ankle_history) < 10:
            return
            
        # Use signal processing to count oscillations
        left_signal = np.array(self.left_ankle_history)
        right_signal = np.array(self.right_ankle_history)
        
        # Simple zero-crossing detection on detrended signal
        left_detrended = left_signal - np.mean(left_signal)
        right_detrended = right_signal - np.mean(right_signal)
        
        left_crossings = np.where(np.diff(np.sign(left_detrended)))[0]
        right_crossings = np.where(np.diff(np.sign(right_detrended)))[0]
        
        # Each leg completes one stride per 2 zero crossings
        left_steps = len(left_crossings) // 2
        right_steps = len(right_crossings) // 2
        
        self.metrics.step_count = left_steps + right_steps
        
        if self.metrics.analysis_duration > 0:
            self.metrics.cadence = (self.metrics.step_count / self.metrics.analysis_duration) * 60
    
    def _calculate_final_metrics(self, total_frames: int):
        """Calculate summary metrics."""
        self.metrics.analysis_duration = total_frames / self.fps
        
        if self.metrics.confidence_scores:
            self.metrics.avg_confidence = np.mean(self.metrics.confidence_scores)
            if self.metrics.avg_confidence > 0.8:
                self.metrics.data_quality = "High"
            elif self.metrics.avg_confidence > 0.5:
                self.metrics.data_quality = "Medium"
            else:
                self.metrics.data_quality = "Low"
        
        if self.metrics.knee_angles:
            all_angles = [a for pair in self.metrics.knee_angles for a in pair]
            self.metrics.avg_knee_angle_at_contact = np.mean(all_angles)
        
        if self.metrics.hip_drops:
            self.metrics.avg_hip_drop = np.mean(self.metrics.hip_drops)
        
        if self.metrics.forward_leans:
            self.metrics.avg_forward_lean = np.mean(self.metrics.forward_leans)
        
        if self.hip_y_positions:
            oscillation = np.max(self.hip_y_positions) - np.min(self.hip_y_positions)
            estimated_height = self.frame_height * 0.5
            self.metrics.avg_vertical_oscillation = (oscillation / estimated_height) * 100


def generate_html_report(metrics: GaitMetrics, video_path: str, analyzed_video_path: str) -> str:
    """Generate an HTML report with embedded video and analysis."""
    
    # Read and encode the analyzed video as base64 for embedding
    video_base64 = ""
    try:
        with open(analyzed_video_path, 'rb') as f:
            video_base64 = base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        print(f"Warning: Could not embed video: {e}")
    
    # Determine status for each metric
    def get_cadence_status(cadence):
        if 165 <= cadence <= 185:
            return ("good", "✅", "Your cadence is in the optimal range for efficient running.")
        elif 155 <= cadence < 165:
            return ("warning", "📊", "Slightly below optimal. Consider increasing by 5-10 spm.")
        elif cadence > 185:
            return ("warning", "📊", "High cadence - ensure you're not shuffling.")
        else:
            return ("alert", "⚠️", "Low cadence often indicates overstriding. Target 175-180 spm.")
    
    def get_hip_drop_status(hip_drop):
        if hip_drop < 5:
            return ("good", "✅", "Excellent hip stability - strong glutes!")
        elif hip_drop < 10:
            return ("warning", "📊", "Mild hip drop - some room for improvement.")
        else:
            return ("alert", "⚠️", "Significant hip drop - indicates weak glutes/hip abductors.")
    
    def get_lean_status(lean):
        if 3 <= lean <= 15:
            return ("good", "✅", "Good forward lean from ankles.")
        elif lean < 0:
            return ("alert", "⚠️", "Leaning backward - increases braking forces.")
        elif lean > 20:
            return ("alert", "⚠️", "Excessive forward lean - may strain lower back.")
        else:
            return ("warning", "📊", "Slight lean - generally acceptable.")
    
    def get_oscillation_status(osc):
        if osc < 6:
            return ("good", "✅", "Efficient - minimal wasted vertical energy.")
        elif osc < 10:
            return ("warning", "📊", "Moderate bounce - could improve efficiency.")
        else:
            return ("alert", "⚠️", "High bounce - wasting energy going up and down.")
    
    cadence_status = get_cadence_status(metrics.cadence)
    hip_status = get_hip_drop_status(metrics.avg_hip_drop)
    lean_status = get_lean_status(metrics.avg_forward_lean)
    osc_status = get_oscillation_status(metrics.avg_vertical_oscillation)
    
    # Count issues for priority
    issues = []
    if cadence_status[0] == "alert":
        issues.append("cadence")
    if hip_status[0] == "alert":
        issues.append("hip stability")
    if lean_status[0] == "alert":
        issues.append("posture")
    if osc_status[0] == "alert":
        issues.append("vertical bounce")
    
    exercises = []
    if hip_status[0] in ["alert", "warning"]:
        exercises.extend([
            ("Single-leg Glute Bridges", "3 sets × 15 reps each side", "Strengthens glutes for better hip stability"),
            ("Clamshells with Resistance Band", "3 sets × 20 reps each side", "Targets hip abductors"),
            ("Side-lying Leg Raises", "3 sets × 15 reps each side", "Builds lateral hip strength")
        ])
    if osc_status[0] in ["alert", "warning"]:
        exercises.extend([
            ("Running with Metronome", "5 minutes at target cadence", "Use a metronome app at 175-180 bpm"),
            ("Ankle Hops", "3 sets × 30 seconds", "Improves ground contact efficiency")
        ])
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Running Form Analysis Report</title>
    <style>
        :root {{
            --good: #10b981;
            --warning: #f59e0b;
            --alert: #ef4444;
            --bg-dark: #1f2937;
            --bg-card: #374151;
            --text-primary: #f9fafb;
            --text-secondary: #9ca3af;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 2rem;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        header {{
            text-align: center;
            margin-bottom: 3rem;
        }}
        
        h1 {{
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }}
        
        .subtitle {{
            color: var(--text-secondary);
            font-size: 1.1rem;
        }}
        
        .video-section {{
            background: var(--bg-card);
            border-radius: 1rem;
            padding: 1.5rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }}
        
        .video-section h2 {{
            margin-bottom: 1rem;
            font-size: 1.3rem;
        }}
        
        video {{
            width: 100%;
            border-radius: 0.5rem;
            max-height: 500px;
            object-fit: contain;
            background: #000;
        }}
        
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}
        
        .metric-card {{
            background: var(--bg-card);
            border-radius: 1rem;
            padding: 1.5rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
            border-left: 4px solid var(--good);
        }}
        
        .metric-card.warning {{
            border-left-color: var(--warning);
        }}
        
        .metric-card.alert {{
            border-left-color: var(--alert);
        }}
        
        .metric-header {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.5rem;
        }}
        
        .metric-icon {{
            font-size: 1.5rem;
        }}
        
        .metric-title {{
            font-size: 1rem;
            color: var(--text-secondary);
        }}
        
        .metric-value {{
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }}
        
        .metric-unit {{
            font-size: 1rem;
            color: var(--text-secondary);
            font-weight: 400;
        }}
        
        .metric-description {{
            color: var(--text-secondary);
            font-size: 0.9rem;
            line-height: 1.5;
        }}
        
        .summary-section {{
            background: var(--bg-card);
            border-radius: 1rem;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }}
        
        .summary-section h2 {{
            margin-bottom: 1.5rem;
            font-size: 1.5rem;
        }}
        
        .priority-list {{
            list-style: none;
        }}
        
        .priority-list li {{
            padding: 1rem;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 0.5rem;
            margin-bottom: 0.75rem;
            display: flex;
            align-items: center;
            gap: 1rem;
        }}
        
        .priority-number {{
            background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
            color: white;
            width: 2rem;
            height: 2rem;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            flex-shrink: 0;
        }}
        
        .exercises-section {{
            background: var(--bg-card);
            border-radius: 1rem;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }}
        
        .exercise-card {{
            background: rgba(255, 255, 255, 0.05);
            border-radius: 0.5rem;
            padding: 1rem;
            margin-bottom: 1rem;
        }}
        
        .exercise-name {{
            font-weight: 600;
            margin-bottom: 0.25rem;
        }}
        
        .exercise-reps {{
            color: #60a5fa;
            font-size: 0.9rem;
            margin-bottom: 0.25rem;
        }}
        
        .exercise-desc {{
            color: var(--text-secondary);
            font-size: 0.85rem;
        }}
        
        .quality-badge {{
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }}
        
        .quality-high {{
            background: rgba(16, 185, 129, 0.2);
            color: var(--good);
        }}
        
        .quality-medium {{
            background: rgba(245, 158, 11, 0.2);
            color: var(--warning);
        }}
        
        .quality-low {{
            background: rgba(239, 68, 68, 0.2);
            color: var(--alert);
        }}
        
        footer {{
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.85rem;
            padding-top: 2rem;
        }}
        
        .meta-info {{
            display: flex;
            gap: 2rem;
            flex-wrap: wrap;
            margin-bottom: 1rem;
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🏃 Running Form Analysis</h1>
            <p class="subtitle">AI-powered gait analysis using pose estimation</p>
        </header>
        
        <div class="video-section">
            <h2>📹 Analyzed Video</h2>
            <div class="meta-info">
                <span>Duration: {metrics.analysis_duration:.1f}s</span>
                <span>Steps detected: {metrics.step_count}</span>
                <span class="quality-badge quality-{metrics.data_quality.lower()}">
                    Data Quality: {metrics.data_quality}
                </span>
            </div>
            {"<video controls><source src='data:video/mp4;base64," + video_base64 + "' type='video/mp4'>Your browser does not support video.</video>" if video_base64 else "<p>Video file: " + analyzed_video_path + "</p>"}
        </div>
        
        <div class="metrics-grid">
            <div class="metric-card {cadence_status[0]}">
                <div class="metric-header">
                    <span class="metric-icon">{cadence_status[1]}</span>
                    <span class="metric-title">Cadence</span>
                </div>
                <div class="metric-value">{metrics.cadence:.0f} <span class="metric-unit">spm</span></div>
                <p class="metric-description">{cadence_status[2]}</p>
            </div>
            
            <div class="metric-card {hip_status[0]}">
                <div class="metric-header">
                    <span class="metric-icon">{hip_status[1]}</span>
                    <span class="metric-title">Hip Stability</span>
                </div>
                <div class="metric-value">{metrics.avg_hip_drop:.1f}<span class="metric-unit">°</span></div>
                <p class="metric-description">{hip_status[2]}</p>
            </div>
            
            <div class="metric-card {lean_status[0]}">
                <div class="metric-header">
                    <span class="metric-icon">{lean_status[1]}</span>
                    <span class="metric-title">Forward Lean</span>
                </div>
                <div class="metric-value">{metrics.avg_forward_lean:.1f}<span class="metric-unit">°</span></div>
                <p class="metric-description">{lean_status[2]}</p>
            </div>
            
            <div class="metric-card {osc_status[0]}">
                <div class="metric-header">
                    <span class="metric-icon">{osc_status[1]}</span>
                    <span class="metric-title">Vertical Bounce</span>
                </div>
                <div class="metric-value">{metrics.avg_vertical_oscillation:.1f}<span class="metric-unit">%</span></div>
                <p class="metric-description">{osc_status[2]}</p>
            </div>
        </div>
        
        <div class="summary-section">
            <h2>🎯 Priority Focus Areas</h2>
            <ol class="priority-list">
                {"".join(f'<li><span class="priority-number">{i+1}</span><span>Work on <strong>{issue}</strong></span></li>' for i, issue in enumerate(issues)) if issues else '<li><span class="priority-number">✓</span><span>Great form! Focus on consistency and gradual progression.</span></li>'}
            </ol>
        </div>
        
        {"<div class='exercises-section'><h2>💪 Recommended Exercises</h2>" + "".join(f'<div class="exercise-card"><div class="exercise-name">{ex[0]}</div><div class="exercise-reps">{ex[1]}</div><div class="exercise-desc">{ex[2]}</div></div>' for ex in exercises) + "</div>" if exercises else ""}
        
        <footer>
            <p>Generated on {datetime.now().strftime("%B %d, %Y at %H:%M")}</p>
            <p>Form Check Friday • Powered by MediaPipe Pose Estimation</p>
        </footer>
    </div>
</body>
</html>
"""
    return html


def main():
    parser = argparse.ArgumentParser(
        description="Analyze running form from video - generates HTML report",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("video", help="Path to input video file")
    parser.add_argument("-o", "--output", help="Path for output annotated video")
    parser.add_argument("-r", "--report", help="Path to save HTML report")
    
    args = parser.parse_args()
    
    video_path = Path(args.video)
    output_video = args.output or str(video_path.stem) + "_analyzed.mp4"
    report_path = args.report or str(video_path.stem) + "_report.html"
    
    try:
        analyzer = RunningFormAnalyzer(args.video)
        metrics = analyzer.analyze(output_path=output_video)
        
        # Generate HTML report
        html = generate_html_report(metrics, str(args.video), output_video)
        
        with open(report_path, 'w') as f:
            f.write(html)
        
        print(f"\n✅ Annotated video saved to: {output_video}")
        print(f"✅ HTML report saved to: {report_path}")
        print(f"\nOpen the HTML file in a browser to view your report!")
        
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error during analysis: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
