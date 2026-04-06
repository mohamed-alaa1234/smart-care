import cv2
import mediapipe as mp
import time
from ultralytics import YOLO

class FallDetectorCV:
    """
    Improved fall detection logic combining YOLOv8 and MediaPipe.
    Relies on body keypoints and velocity of coordinate changes to reduce false alarms.
    """
    def __init__(self, y_threshold=0.6, yolo_model_path='yolov8n.pt'):
        try:
            # Prevents overwhelming system logs, runs silently
            self.yolo_model = YOLO(yolo_model_path) 
        except Exception as e:
            print(f"Failed to load YOLOv8 weights ({e}). Operating in MediaPipe-only mode.")
            self.yolo_model = None
            
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)
        self.mp_draw = mp.solutions.drawing_utils
        self.prev_y = None
        self.prev_time = time.time()
        self.y_threshold = y_threshold 

    def detect(self, frame):
        """Processes frame, returning drawn data, boolean state, and text updates."""
        if frame is None:
            return frame, False, "Camera Signal Lost"
            
        # 1. Performance optimization: Quick exit using YOLO if no person
        if self.yolo_model:
            results = self.yolo_model(frame, classes=[0], verbose=False)
            if not results or len(results[0].boxes) == 0:
                self.prev_y = None # Reset state history to prevent sudden jumps
                return frame, False, "No Person Detected"
                
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Wrapped for camera/driver corrupt frame errors
        try:
            pose_results = self.pose.process(rgb_frame)
        except Exception as e:
            print(f"MediaPipe Processing Exception: {e}")
            return frame, False, "Error Processing Frame"
        
        is_fall = False
        message = "Normal"
        
        if pose_results and pose_results.pose_landmarks:
            self.mp_draw.draw_landmarks(frame, pose_results.pose_landmarks, self.mp_pose.POSE_CONNECTIONS)
            
            landmarks = pose_results.pose_landmarks.landmark
            left_hip = landmarks[self.mp_pose.PoseLandmark.LEFT_HIP]
            right_hip = landmarks[self.mp_pose.PoseLandmark.RIGHT_HIP]
            current_y = (left_hip.y + right_hip.y) / 2.0
            current_time = time.time()
            
            if self.prev_y is not None:
                dy = current_y - self.prev_y
                dt = current_time - self.prev_time
                
                # Prevent mathematical DivisionByZero or micro-stutters
                if dt > 0.01:
                    velocity = dy / dt 
                    
                    if velocity > self.y_threshold:
                        left_s = landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER]
                        right_s = landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER]
                        shoulder_y = (left_s.y + right_s.y) / 2.0
                        
                        # Guard mechanism against 'Sitting down' false-positives
                        # Verifies shoulders dropped to horizontal symmetry with hips
                        if abs(shoulder_y - current_y) < 0.15:
                            is_fall = True
                            message = "Emergency: Fall Detected!"
            
            self.prev_y = current_y
            self.prev_time = current_time
        else:
            self.prev_y = None
            
        return frame, is_fall, message

    def close_resources(self):
        """Safely destructs underlying GC variables to prevent memory leaks."""
        if self.pose:
            self.pose.close()
