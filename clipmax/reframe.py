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

def smooth_ema_series(values: List[float], alpha: float = 0.1) -> List[float]:
    if not values:
        return []
    smoothed = [values[0]]
    for v in values[1:]:
        smoothed.append(alpha * v + (1.0 - alpha) * smoothed[-1])
    return smoothed

def build_dynamic_crop_expression(
    values: List[float],
    timestamps: List[float],
    max_x: int = 1312
) -> str:
    if not values:
        return str(max_x // 2)

    # If camera or presenter is static (variation across clip < 8px) or single sample
    if max(values) - min(values) < 8.0 or len(values) == 1:
        return str(int(round(values[0])))

    # Subsample to at most ~30 keypoints (~1 per second) for a concise, efficient FFmpeg expression
    if len(values) > 35:
        step = max(1, len(values) // 30)
        sub_values = values[::step]
        sub_times = timestamps[::step]
        if sub_times[-1] != timestamps[-1]:
            sub_values.append(values[-1])
            sub_times.append(timestamps[-1])
    else:
        sub_values = values
        sub_times = timestamps

    expr = str(int(round(sub_values[-1])))
    for i in range(len(sub_values) - 2, -1, -1):
        t_start = sub_times[i]
        t_end = sub_times[i + 1]
        x0 = int(round(sub_values[i]))
        x1 = int(round(sub_values[i + 1]))
        dt = max(0.01, t_end - t_start)
        piece = f"({x0}+({x1}-{x0})*(t-{t_start:.2f})/{dt:.2f})"
        expr = f"if(lt(t,{t_end:.2f}),{piece},{expr})"

    return f"max(0,min({max_x},{expr}))"

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
    first_face_detected = False
    frame_idx = 0
    current_frame = start_frame

    sampled_frames = 0
    valid_face_frames = 0
    min_face_area = 0.005 * (detect_w * detect_h)
    frame_interval_sec = sample_step / fps

    current_no_face_seconds = 0.0
    max_no_face_gap_seconds = 0.0

    while current_frame <= end_frame:
        # Fast grab packet without full decoding
        if not cap.grab():
            break

        # Only decode and run inference every sample_step frames (e.g. frame_idx % 6 == 0)
        if frame_idx % sample_step == 0:
            sampled_frames += 1
            ret, frame = cap.retrieve()
            face_found = False

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
                                face_found = True
                                valid_face_frames += 1
                                best_face = max(valid_faces, key=lambda x: x[0])[1]
                                cx_small = float(best_face[0] + best_face[2] / 2.0)
                                cx_orig = cx_small * scale_x

                                if not first_face_detected:
                                    first_face_detected = True
                                    # Backfill previous centers with first detected face location
                                    for k in range(len(centers)):
                                        centers[k] = cx_orig

                                last_center = cx_orig
                    except Exception:
                        pass

            if face_found:
                current_no_face_seconds = 0.0
            else:
                current_no_face_seconds += frame_interval_sec
                if current_no_face_seconds > max_no_face_gap_seconds:
                    max_no_face_gap_seconds = current_no_face_seconds

        # Use last known face center (sample-and-hold)
        centers.append(last_center)
        frame_idx += 1
        current_frame += 1

    cap.release()

    if current_no_face_seconds > max_no_face_gap_seconds:
        max_no_face_gap_seconds = current_no_face_seconds

    # Smart Fallback for Screen Recording / No Face:
    # If no face detected, or face missing for > 2.0 seconds (e.g. slide, browser demo), or low face presence:
    # Fallback to BLURRED_BACKGROUND (Fit Screen with Blurred Background)
    face_ratio = valid_face_frames / max(1, sampled_frames)
    has_dominant_face = (
        first_face_detected
        and valid_face_frames >= 3
        and max_no_face_gap_seconds <= 2.0
        and face_ratio >= 0.60
    )
    strategy = ReframeStrategy.CROP_TRACKING if has_dominant_face else ReframeStrategy.BLURRED_BACKGROUND

    return centers, strategy
