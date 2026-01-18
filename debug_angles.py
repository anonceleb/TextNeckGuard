#!/usr/bin/env python3
"""
Debug script to visualize and verify angle calculations.
Extracts a few frames and shows the calculated angles visually.
"""

import sys
import math
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np


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


def get_landmark_coords(landmarks, idx, frame_width, frame_height):
    lm = landmarks.landmark[idx]
    return (int(lm.x * frame_width), int(lm.y * frame_height))


def calculate_angle_from_vertical_v1(point1, point2):
    """Original calculation - angle from vertical (y-axis pointing down)."""
    dx = point2[0] - point1[0]
    dy = point2[1] - point1[1]
    # This gives angle from positive Y (downward) axis
    angle = math.degrees(math.atan2(dx, dy))
    return angle


def calculate_angle_from_vertical_v2(hip, shoulder):
    """
    Corrected: Forward lean angle from vertical.
    In image coords: y increases downward, x increases rightward.
    Vertical line would be hip straight up (dy positive, dx zero).
    Forward lean = how much the shoulder is in front of (to the left of) the hip
    when runner is facing right, or to the right when facing left.
    """
    dx = shoulder[0] - hip[0]  # positive if shoulder is to the right of hip
    dy = hip[1] - shoulder[1]  # positive if shoulder is above hip (normal)
    
    # Angle from vertical: atan2(horizontal, vertical)
    # This gives angle in degrees where:
    # 0° = perfectly vertical (shoulder directly above hip)
    # positive = leaning to the right
    # negative = leaning to the left
    angle = math.degrees(math.atan2(dx, dy))
    return angle


def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_angles.py <video_file>")
        sys.exit(1)
    
    video_path = sys.argv[1]
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"Video: {video_path}")
    print(f"Resolution: {frame_width}x{frame_height}")
    print(f"Orientation: {'Portrait' if frame_height > frame_width else 'Landscape'}")
    print(f"FPS: {fps:.1f}, Total frames: {total_frames}")
    print()
    
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(
        static_image_mode=False,
        model_complexity=2,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )
    
    # Sample frames at different points
    sample_frames = [
        int(total_frames * 0.25),
        int(total_frames * 0.5),
        int(total_frames * 0.75)
    ]
    
    for target_frame in sample_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        success, frame = cap.read()
        if not success:
            continue
        
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(frame_rgb)
        
        if results.pose_landmarks:
            landmarks = results.pose_landmarks
            
            # Get key points
            left_hip = get_landmark_coords(landmarks, Landmarks.LEFT_HIP, frame_width, frame_height)
            right_hip = get_landmark_coords(landmarks, Landmarks.RIGHT_HIP, frame_width, frame_height)
            left_shoulder = get_landmark_coords(landmarks, Landmarks.LEFT_SHOULDER, frame_width, frame_height)
            right_shoulder = get_landmark_coords(landmarks, Landmarks.RIGHT_SHOULDER, frame_width, frame_height)
            
            mid_hip = ((left_hip[0] + right_hip[0]) // 2, (left_hip[1] + right_hip[1]) // 2)
            mid_shoulder = ((left_shoulder[0] + right_shoulder[0]) // 2, (left_shoulder[1] + right_shoulder[1]) // 2)
            
            # Calculate both versions
            angle_v1 = calculate_angle_from_vertical_v1(mid_hip, mid_shoulder)
            angle_v2 = calculate_angle_from_vertical_v2(mid_hip, mid_shoulder)
            
            print(f"=== Frame {target_frame} ===")
            print(f"Mid Hip:      {mid_hip}")
            print(f"Mid Shoulder: {mid_shoulder}")
            print(f"Shoulder is {'RIGHT of' if mid_shoulder[0] > mid_hip[0] else 'LEFT of'} hip by {abs(mid_shoulder[0] - mid_hip[0])}px")
            print(f"Shoulder is {'ABOVE' if mid_shoulder[1] < mid_hip[1] else 'BELOW'} hip by {abs(mid_shoulder[1] - mid_hip[1])}px")
            print(f"Original calc (v1): {angle_v1:.1f}°")
            print(f"Corrected calc (v2): {angle_v2:.1f}°")
            print()
            
            # Draw visualization
            vis_frame = frame.copy()
            
            # Draw points
            cv2.circle(vis_frame, mid_hip, 10, (0, 255, 0), -1)  # Green = hip
            cv2.circle(vis_frame, mid_shoulder, 10, (255, 0, 0), -1)  # Blue = shoulder
            
            # Draw trunk line
            cv2.line(vis_frame, mid_hip, mid_shoulder, (0, 255, 255), 3)  # Yellow trunk
            
            # Draw vertical reference line from hip
            vertical_top = (mid_hip[0], mid_hip[1] - 200)
            cv2.line(vis_frame, mid_hip, vertical_top, (255, 255, 255), 2)  # White vertical
            
            # Add text
            cv2.putText(vis_frame, f"Original: {angle_v1:.1f} deg", (30, 50), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(vis_frame, f"Corrected: {angle_v2:.1f} deg", (30, 90),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(vis_frame, "Hip (green), Shoulder (blue)", (30, 130),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
            cv2.putText(vis_frame, "Yellow=trunk, White=vertical", (30, 160),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
            
            # Save debug frame
            output_path = f"debug_frame_{target_frame}.jpg"
            cv2.imwrite(output_path, vis_frame)
            print(f"Saved: {output_path}")
            print()
    
    cap.release()
    pose.close()
    
    print("Debug complete! Check the saved images to verify angles.")


if __name__ == "__main__":
    main()
