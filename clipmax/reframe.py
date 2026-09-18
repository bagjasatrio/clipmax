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
    sample_fps: int = 4
) -> Tuple[List[float], ReframeStrategy]:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return [], ReframeStrategy.STATIC_CENTER

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080
    frame_step = max(1, int(fps / sample_fps))

    start_frame = int(start_time * fps)
    end_frame = int(end_time * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    model_path = get_face_detector_model()
    detector = None
    if model_path:
        try:
            detector = cv2.FaceDetectorYN_create(
                model_path,
                "",
                (width, height),
                score_threshold=0.6,
                nms_threshold=0.3
            )
        except Exception:
            detector = None

    centers: List[float] = []
    max_faces_seen = 1
    default_center = width / 2.0
    current_frame = start_frame

    while current_frame <= end_frame:
        ret, frame = cap.read()
        if not ret:
            break

        if (current_frame - start_frame) % frame_step == 0:
            best_cx = None
            if detector is not None:
                try:
                    _, faces = detector.detect(frame)
                    if faces is not None and len(faces) > 0:
                        max_faces_seen = max(max_faces_seen, len(faces))
                        # Face format: [x, y, w, h, x_re, y_re, x_le, y_le, x_nt, y_nt, x_rc, y_rc, x_lc, y_lc, score]
                        # Choose largest face
                        best_face = max(faces, key=lambda f: f[2] * f[3])
                        best_cx = float(best_face[0] + best_face[2] / 2.0)
                except Exception:
                    best_cx = None

            if best_cx is not None:
                centers.append(best_cx)
            else:
                centers.append(centers[-1] if centers else default_center)

        current_frame += 1

    cap.release()

    strategy = ReframeStrategy.SPLIT_SCREEN if max_faces_seen > 1 else ReframeStrategy.SINGLE_SPEAKER
    return centers, strategy
