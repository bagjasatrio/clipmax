import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional
from enum import Enum

class ReframeStrategy(str, Enum):
    SINGLE_SPEAKER = "single_speaker"
    SPLIT_SCREEN = "split_screen"
    STATIC_CENTER = "static_center"

def calculate_crop_box(
    frame_width: int,
    frame_height: int,
    face_center_x: float,
    aspect_ratio: float = 9.0 / 16.0
) -> Tuple[int, int, int]:
    crop_height = frame_height
    crop_width = int(round(crop_height * aspect_ratio))
    
    if crop_width > frame_width:
        crop_width = frame_width

    half_w = crop_width / 2.0
    x_start = face_center_x - half_w

    if x_start < 0:
        x_start = 0
    elif x_start + crop_width > frame_width:
        x_start = frame_width - crop_width

    return int(round(x_start)), crop_width, crop_height

def smooth_ema_series(values: List[float], alpha: float = 0.15) -> List[float]:
    if not values:
        return []
    smoothed = [values[0]]
    for v in values[1:]:
        smoothed.append(alpha * v + (1.0 - alpha) * smoothed[-1])
    return smoothed

def get_face_detector_model() -> Optional[str]:
    project_root = Path(__file__).resolve().parent.parent
    model_p = project_root / "bin" / "face_detection_yunet_2023mar.onnx"
    if model_p.exists():
        return str(model_p)
    return None

def detect_face_centers(
    video_path: str,
    start_time: float,
    end_time: float,
    sample_step: int = 6,
    detect_width: int = 640
) -> Tuple[List[float], ReframeStrategy]:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return [], ReframeStrategy.STATIC_CENTER

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080

    start_frame = int(start_time * fps)
    end_frame = int(end_time * fps)
    if end_frame < start_frame:
        end_frame = start_frame
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    # Calculate resized dimensions for ultra-fast CPU face inference (e.g. 640x360)
    detect_w = min(width, detect_width)
    detect_h = int(round(height * (detect_w / float(width)))) if width > 0 else 360
    scale_x = (width / float(detect_w)) if detect_w > 0 else 1.0

    model_path = get_face_detector_model()
    detector = None
    if model_path:
        try:
            detector = cv2.FaceDetectorYN_create(
                model_path,
                "",
                (detect_w, detect_h),
                score_threshold=0.6,
                nms_threshold=0.3
            )
        except Exception:
            detector = None

    centers: List[float] = []
    max_faces_seen = 1
    default_center = width / 2.0
    last_center = default_center
    frame_idx = 0
    current_frame = start_frame

    while current_frame <= end_frame:
        # Fast grab packet without full decoding
        if not cap.grab():
            break

        # Only decode and run inference every sample_step frames (e.g. frame_idx % 6 == 0)
        if frame_idx % sample_step == 0:
            ret, frame = cap.retrieve()
            if ret and frame is not None:
                small_frame = cv2.resize(frame, (detect_w, detect_h))
                if detector is not None:
                    try:
                        _, faces = detector.detect(small_frame)
                        if faces is not None and len(faces) > 0:
                            max_faces_seen = max(max_faces_seen, len(faces))
                            best_face = max(faces, key=lambda f: f[2] * f[3])
                            cx_small = float(best_face[0] + best_face[2] / 2.0)
                            last_center = cx_small * scale_x
                    except Exception:
                        pass

        # Use last known face center (hold / sample-and-hold)
        centers.append(last_center)
        frame_idx += 1
        current_frame += 1

    cap.release()

    strategy = ReframeStrategy.SPLIT_SCREEN if max_faces_seen > 1 else ReframeStrategy.SINGLE_SPEAKER
    return centers, strategy
