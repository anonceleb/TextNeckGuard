#!/usr/bin/env python3
"""
Running Form Analysis Tool
--------------------------
Analyzes running gait from video using MediaPipe pose estimation.
Outputs annotated video with skeleton overlay and text feedback.

Usage:
    python analyze_form.py <video_file> [--output <output_file>]

Example:
    python analyze_form.py runner_side_view.mp4 --output analyzed.mp4
"""

import argparse
import math
import sys
from pathlib import Path
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

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
    cadence: float = 0.0  # steps per minute
    avg_knee_angle_at_contact: float = 0.0  # degrees
    avg_hip_drop: float = 0.0  # degrees
    avg_forward_lean: float = 0.0  # degrees (trunk angle from vertical)
    avg_vertical_oscillation: float = 0.0  # as percentage of height
    overstriding_detected: bool = False
    step_count: int = 0
    analysis_duration: float = 0.0  # seconds
    
    # Raw data for detailed analysis
    knee_angles: list = field(default_factory=list)
    hip_drops: list = field(default_factory=list)
    forward_leans: list = field(default_factory=list)
    vertical_positions: list = field(default_factory=list)


def calculate_angle(a: tuple, b: tuple, c: tuple) -> float:
    """
    Calculate angle at point b given three points a, b, c.
    Returns angle in degrees.
    """
    ba = np.array([a[0] - b[0], a[1] - b[1]])
    bc = np.array([c[0] - b[0], c[1] - b[1]])
    
    cosine = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    cosine = np.clip(cosine, -1.0, 1.0)
    angle = np.degrees(np.arccos(cosine))
    
    return angle


def calculate_angle_from_vertical(point1: tuple, point2: tuple) -> float:
    """
    Calculate angle of line from point1 to point2 relative to vertical.
    Returns angle in degrees (positive = leaning forward).
    """
    dx = point2[0] - point1[0]
    dy = point2[1] - point1[1]
    
    # Angle from vertical (note: in image coords, y increases downward)
    angle = math.degrees(math.atan2(dx, dy))
    return angle


def get_landmark_coords(landmarks, idx, frame_width, frame_height):
    """Extract x, y coordinates from landmark."""
    lm = landmarks.landmark[idx]
    return (int(lm.x * frame_width), int(lm.y * frame_height))


def detect_foot_strike(prev_ankle_y: float, curr_ankle_y: float, 
                       prev_velocity: float, threshold: float = 2.0) -> bool:
    """
    Detect foot strike by looking for when ankle stops descending.
    Returns True if foot strike detected.
    """
    curr_velocity = curr_ankle_y - prev_ankle_y
    
    # Foot strike when ankle was descending (positive velocity in image coords)
    # and now slows down or starts ascending
    if prev_velocity > threshold and curr_velocity < prev_velocity * 0.5:
        return True
    return False


class RunningFormAnalyzer:
    """Analyzes running form from video using MediaPipe pose estimation."""
    
    def __init__(self, video_path: str):
        self.video_path = Path(video_path)
        if not self.video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")
        
        # Initialize MediaPipe Pose
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=2,  # Higher accuracy
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # Video capture
        self.cap = cv2.VideoCapture(str(self.video_path))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Metrics storage
        self.metrics = GaitMetrics()
        
        # Step detection state
        self.ankle_history = deque(maxlen=5)
        self.velocity_history = deque(maxlen=5)
        self.step_frames = []
        
        # Hip position tracking for vertical oscillation
        self.hip_y_positions = []
        
    def analyze(self, output_path: Optional[str] = None) -> GaitMetrics:
        """
        Analyze the video and return gait metrics.
        If output_path provided, saves annotated video.
        """
        # Setup video writer if output requested
        writer = None
        if output_path:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(
                output_path, fourcc, self.fps, 
                (self.frame_width, self.frame_height)
            )
        
        frame_count = 0
        prev_ankle_y = None
        prev_velocity = 0
        
        print(f"Analyzing video: {self.video_path.name}")
        print(f"Resolution: {self.frame_width}x{self.frame_height}, FPS: {self.fps:.1f}")
        print(f"Total frames: {self.total_frames}")
        print()
        
        while self.cap.isOpened():
            success, frame = self.cap.read()
            if not success:
                break
            
            frame_count += 1
            
            # Progress indicator
            if frame_count % 30 == 0:
                progress = (frame_count / self.total_frames) * 100
                print(f"\rProcessing: {progress:.1f}%", end="", flush=True)
            
            # Convert to RGB for MediaPipe
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.pose.process(frame_rgb)
            
            if results.pose_landmarks:
                landmarks = results.pose_landmarks
                
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
                
                # Calculate midpoints
                mid_hip = ((left_hip[0] + right_hip[0]) // 2, 
                           (left_hip[1] + right_hip[1]) // 2)
                mid_shoulder = ((left_shoulder[0] + right_shoulder[0]) // 2,
                                (left_shoulder[1] + right_shoulder[1]) // 2)
                
                # Track hip position for vertical oscillation
                self.hip_y_positions.append(mid_hip[1])
                
                # Calculate knee angles (hip-knee-ankle)
                left_knee_angle = calculate_angle(left_hip, left_knee, left_ankle)
                right_knee_angle = calculate_angle(right_hip, right_knee, right_ankle)
                self.metrics.knee_angles.append((left_knee_angle, right_knee_angle))
                
                # Calculate hip drop (difference in hip heights)
                hip_drop = abs(left_hip[1] - right_hip[1])
                hip_drop_degrees = math.degrees(math.atan2(hip_drop, 
                                                           abs(left_hip[0] - right_hip[0]) + 1))
                self.metrics.hip_drops.append(hip_drop_degrees)
                
                # Calculate forward lean (trunk angle from vertical)
                forward_lean = calculate_angle_from_vertical(mid_hip, mid_shoulder)
                self.metrics.forward_leans.append(forward_lean)
                
                # Step detection using lower ankle
                lower_ankle_y = max(left_ankle[1], right_ankle[1])
                
                if prev_ankle_y is not None:
                    curr_velocity = lower_ankle_y - prev_ankle_y
                    
                    if detect_foot_strike(prev_ankle_y, lower_ankle_y, 
                                          prev_velocity, threshold=1.0):
                        self.step_frames.append(frame_count)
                    
                    prev_velocity = curr_velocity
                
                prev_ankle_y = lower_ankle_y
                
                # Draw skeleton on frame
                self.mp_drawing.draw_landmarks(
                    frame,
                    landmarks,
                    self.mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=self.mp_drawing_styles.get_default_pose_landmarks_style()
                )
                
                # Add metrics overlay
                self._draw_metrics_overlay(frame, left_knee_angle, right_knee_angle,
                                           hip_drop_degrees, forward_lean, frame_count)
            
            if writer:
                writer.write(frame)
        
        print("\rProcessing: 100.0%")
        print()
        
        # Cleanup
        self.cap.release()
        if writer:
            writer.release()
        self.pose.close()
        
        # Calculate final metrics
        self._calculate_final_metrics(frame_count)
        
        return self.metrics
    
    def _draw_metrics_overlay(self, frame, left_knee_angle, right_knee_angle,
                               hip_drop, forward_lean, frame_count):
        """Draw real-time metrics on the frame."""
        # Semi-transparent background
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (350, 150), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
        
        # Text settings
        font = cv2.FONT_HERSHEY_SIMPLEX
        color = (255, 255, 255)
        
        # Display metrics
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
    
    def _calculate_final_metrics(self, total_frames: int):
        """Calculate summary metrics from collected data."""
        # Duration
        self.metrics.analysis_duration = total_frames / self.fps
        
        # Cadence (steps per minute)
        self.metrics.step_count = len(self.step_frames)
        if self.metrics.analysis_duration > 0:
            self.metrics.cadence = (self.metrics.step_count / 
                                     self.metrics.analysis_duration) * 60
        
        # Average knee angle
        if self.metrics.knee_angles:
            all_angles = [a for pair in self.metrics.knee_angles for a in pair]
            self.metrics.avg_knee_angle_at_contact = np.mean(all_angles)
        
        # Average hip drop
        if self.metrics.hip_drops:
            self.metrics.avg_hip_drop = np.mean(self.metrics.hip_drops)
        
        # Average forward lean
        if self.metrics.forward_leans:
            self.metrics.avg_forward_lean = np.mean(self.metrics.forward_leans)
        
        # Vertical oscillation (as percentage of estimated height)
        if self.hip_y_positions:
            oscillation = np.max(self.hip_y_positions) - np.min(self.hip_y_positions)
            estimated_height = self.frame_height * 0.5  # Rough estimate
            self.metrics.avg_vertical_oscillation = (oscillation / estimated_height) * 100


def generate_feedback(metrics: GaitMetrics) -> str:
    """Generate text feedback based on gait metrics."""
    feedback = []
    feedback.append("=" * 60)
    feedback.append("RUNNING FORM ANALYSIS REPORT")
    feedback.append("=" * 60)
    feedback.append("")
    
    # Duration and steps
    feedback.append(f"Analysis Duration: {metrics.analysis_duration:.1f} seconds")
    feedback.append(f"Steps Detected: {metrics.step_count}")
    feedback.append("")
    
    # Cadence
    feedback.append("-" * 40)
    feedback.append("CADENCE")
    feedback.append("-" * 40)
    feedback.append(f"Your cadence: {metrics.cadence:.0f} steps/minute")
    
    if metrics.cadence < 160:
        feedback.append("⚠️  LOW CADENCE detected")
        feedback.append("   Target: 170-180 steps/minute for most runners")
        feedback.append("   Tip: Try running to a metronome app at 175 bpm")
        feedback.append("   Lower cadence often means overstriding")
    elif metrics.cadence < 170:
        feedback.append("📊 Cadence is slightly below optimal")
        feedback.append("   Target: 175-180 for efficient running")
    elif metrics.cadence <= 185:
        feedback.append("✅ Good cadence! This is in the optimal range")
    else:
        feedback.append("📊 High cadence - make sure you're not shuffling")
    feedback.append("")
    
    # Knee angle
    feedback.append("-" * 40)
    feedback.append("KNEE ANGLE")
    feedback.append("-" * 40)
    feedback.append(f"Average knee angle: {metrics.avg_knee_angle_at_contact:.1f}°")
    
    if metrics.avg_knee_angle_at_contact < 150:
        feedback.append("⚠️  Knee appears quite bent")
        feedback.append("   This could indicate excessive knee drive or measurement angle")
    elif metrics.avg_knee_angle_at_contact > 175:
        feedback.append("⚠️  Very straight knee at contact")
        feedback.append("   This may indicate overstriding (landing ahead of body)")
        feedback.append("   Tip: Focus on landing with foot under your hips")
    else:
        feedback.append("✅ Knee angle looks reasonable")
    feedback.append("")
    
    # Hip drop
    feedback.append("-" * 40)
    feedback.append("HIP STABILITY (Pelvic Drop)")
    feedback.append("-" * 40)
    feedback.append(f"Average hip drop: {metrics.avg_hip_drop:.1f}°")
    
    if metrics.avg_hip_drop > 10:
        feedback.append("⚠️  Significant hip drop detected")
        feedback.append("   This often indicates weak glutes/hip abductors")
        feedback.append("   Exercises to help:")
        feedback.append("   - Single-leg glute bridges: 3x15 each side")
        feedback.append("   - Clamshells with band: 3x20 each side")
        feedback.append("   - Side-lying leg raises: 3x15 each side")
    elif metrics.avg_hip_drop > 5:
        feedback.append("📊 Mild hip drop - some room for improvement")
        feedback.append("   Consider adding hip strengthening exercises")
    else:
        feedback.append("✅ Good hip stability!")
    feedback.append("")
    
    # Forward lean
    feedback.append("-" * 40)
    feedback.append("TRUNK POSITION (Forward Lean)")
    feedback.append("-" * 40)
    feedback.append(f"Average forward lean: {metrics.avg_forward_lean:.1f}°")
    
    if metrics.avg_forward_lean < -5:
        feedback.append("⚠️  Leaning backward detected")
        feedback.append("   This can increase braking forces")
        feedback.append("   Tip: Imagine a slight forward fall from the ankles")
    elif metrics.avg_forward_lean > 15:
        feedback.append("⚠️  Excessive forward lean")
        feedback.append("   This can strain lower back and hamstrings")
        feedback.append("   Tip: Run tall, lead with your chest")
    elif 5 <= metrics.avg_forward_lean <= 12:
        feedback.append("✅ Good forward lean for running")
    else:
        feedback.append("📊 Slight forward lean - generally acceptable")
    feedback.append("")
    
    # Vertical oscillation
    feedback.append("-" * 40)
    feedback.append("VERTICAL OSCILLATION")
    feedback.append("-" * 40)
    feedback.append(f"Estimated bounce: {metrics.avg_vertical_oscillation:.1f}% of height")
    
    if metrics.avg_vertical_oscillation > 8:
        feedback.append("⚠️  High vertical movement detected")
        feedback.append("   Wasted energy going up and down")
        feedback.append("   Tips:")
        feedback.append("   - Think 'glide' not 'bounce'")
        feedback.append("   - Increase cadence to reduce bounce")
        feedback.append("   - Avoid pushing off too hard")
    else:
        feedback.append("✅ Vertical oscillation looks efficient")
    feedback.append("")
    
    # Summary
    feedback.append("=" * 60)
    feedback.append("SUMMARY & NEXT STEPS")
    feedback.append("=" * 60)
    
    issues = []
    if metrics.cadence < 165:
        issues.append("low cadence")
    if metrics.avg_hip_drop > 8:
        issues.append("hip drop")
    if metrics.avg_forward_lean < 0 or metrics.avg_forward_lean > 15:
        issues.append("trunk position")
    if metrics.avg_vertical_oscillation > 8:
        issues.append("excessive bounce")
    
    if not issues:
        feedback.append("Great form! Keep up the good work.")
        feedback.append("Focus on consistency and gradual progression.")
    else:
        feedback.append(f"Areas to focus on: {', '.join(issues)}")
        feedback.append("")
        feedback.append("Recommended priority:")
        feedback.append("1. Work on one thing at a time")
        feedback.append("2. Start with short drills (30-60 seconds)")
        feedback.append("3. Re-record in 4-6 weeks to track progress")
    
    feedback.append("")
    feedback.append("=" * 60)
    feedback.append("Note: This analysis works best with a side-view video")
    feedback.append("of running at steady pace on flat ground.")
    feedback.append("=" * 60)
    
    return "\n".join(feedback)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze running form from video using pose estimation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python analyze_form.py runner.mp4
    python analyze_form.py runner.mp4 --output analyzed.mp4
    python analyze_form.py runner.mp4 -o analyzed.mp4 --report report.txt
        """
    )
    
    parser.add_argument("video", help="Path to input video file")
    parser.add_argument("-o", "--output", help="Path for output annotated video")
    parser.add_argument("-r", "--report", help="Path to save text report")
    
    args = parser.parse_args()
    
    # Default output paths
    video_path = Path(args.video)
    output_video = args.output or str(video_path.stem) + "_analyzed.mp4"
    report_path = args.report or str(video_path.stem) + "_report.txt"
    
    try:
        # Run analysis
        analyzer = RunningFormAnalyzer(args.video)
        metrics = analyzer.analyze(output_path=output_video)
        
        # Generate feedback
        feedback = generate_feedback(metrics)
        print(feedback)
        
        # Save report
        with open(report_path, 'w') as f:
            f.write(feedback)
        
        print(f"\n✅ Annotated video saved to: {output_video}")
        print(f"✅ Text report saved to: {report_path}")
        
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error during analysis: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
