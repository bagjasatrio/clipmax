import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional
from enum import Enum

class ReframeStrategy(str, Enum):
    CROP_TRACKING = "CROP_TRACKING"
    BLURRED_BACKGROUND = "BLURRED_BACKGROUND"
    SINGLE_SPEAKER = "CROP_TRACKING"
    STATIC_CENTER = "BLURRED_BACKGROUND"
    SPLIT_SCREEN = "CROP_TRACKING"

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
        return [], ReframeStrategy.BLURRED_BACKGROUND

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
    default_center = width / 2.0
    last_center = default_center
    frame_idx = 0
    current_frame = start_frame

    sampled_frames = 0
    valid_face_frames = 0
    min_face_area = 0.005 * (detect_w * detect_h)

    while current_frame <= end_frame:
        # Fast grab packet without full decoding
        if not cap.grab():
            break

        # Only decode and run inference every sample_step frames (e.g. frame_idx % 6 == 0)
        if frame_idx % sample_step == 0:
            sampled_frames += 1
            ret, frame = cap.retrieve()
            if ret and frame is not None:
                small_frame = cv2.resize(frame, (detect_w, detect_h))
                if detector is not None:
                    try:
                        _, faces = detector.detect(small_frame)
                        if faces is not None and len(faces) > 0:
                            valid_faces = []
                            for f in faces:
                                w_f, h_f = float(f[2]), float(f[3])
                                area = w_f * h_f
                                score = float(f[14]) if len(f) > 14 else 1.0
                                if score >= 0.6 and area >= min_face_area:
                                    valid_faces.append((area, f))

                            if valid_faces:
                                valid_face_frames += 1
                                best_face = max(valid_faces, key=lambda x: x[0])[1]
                                cx_small = float(best_face[0] + best_face[2] / 2.0)
                                last_center = cx_small * scale_x
                    except Exception:
                        pass

        # Use last known face center (sample-and-hold)
        centers.append(last_center)
        frame_idx += 1
        current_frame += 1

    cap.release()

    # Scene & content aware decision:
    # If a clear dominant face was present in >= 15% of sampled frames (and at least 2 frames), use CROP_TRACKING
    # Otherwise, this is a non-face / B-Roll / slide / screen record -> fallback to BLURRED_BACKGROUND
    has_dominant_face = (valid_face_frames >= 2) and (valid_face_frames / max(1, sampled_frames) >= 0.15)
    strategy = ReframeStrategy.CROP_TRACKING if has_dominant_face else ReframeStrategy.BLURRED_BACKGROUND

    return centers, strategy
