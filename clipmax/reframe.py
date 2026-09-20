import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel

class ReframeStrategy(str, Enum):
    CROP_TRACKING = "CROP_TRACKING"
    BLURRED_BACKGROUND = "BLURRED_BACKGROUND"
    SINGLE_SPEAKER = "CROP_TRACKING"
    STATIC_CENTER = "BLURRED_BACKGROUND"
    SPLIT_SCREEN = "CROP_TRACKING"

class SceneSegment(BaseModel):
    start_time: float      # relative to clip start in seconds (e.g. 0.0)
    end_time: float        # relative to clip start in seconds (e.g. 15.0)
    mode: str              # "CROP_TRACKING" or "BLURRED_BACKGROUND"
    crop_x: str            # fixed integer string (e.g. "456") or "0"

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
    """Helper for exponential moving average smoothing."""
    if not values:
        return []
    smoothed = [values[0]]
    for v in values[1:]:
        smoothed.append(alpha * v + (1.0 - alpha) * smoothed[-1])
    return smoothed

def build_dynamic_crop_expression(
    values: List[float],
    timestamps: List[float],
    max_x: int = 1312,
    discrete: bool = True,
    visual_cuts: Optional[List[float]] = None
) -> str:
    """
    Builds fixed or discrete step expression without continuous panning.
    """
    if not values:
        return str(max_x // 2)

    # If single value or negligible variation across segment
    if max(values) - min(values) < 2.0 or len(values) == 1:
        return str(int(round(values[0])))

    # Discrete step function (Hard Cuts)
    blocks = []
    cur_val = values[0]
    cur_start = timestamps[0]
    for v, t in zip(values[1:], timestamps[1:]):
        if abs(v - cur_val) >= 2.0:
            t_cut = t
            if visual_cuts:
                nearby = [c for c in visual_cuts if abs(c - t) <= 0.6]
                if nearby:
                    t_cut = min(nearby, key=lambda c: abs(c - t))
            blocks.append((cur_start, t_cut, int(round(cur_val))))
            cur_val = v
            cur_start = t_cut
    blocks.append((cur_start, timestamps[-1], int(round(cur_val))))

    if len(blocks) == 1:
        return str(blocks[0][2])

    expr = str(blocks[-1][2])
    for i in range(len(blocks) - 2, -1, -1):
        t_end = blocks[i][1]
        val = blocks[i][2]
        expr = f"if(lt(t,{t_end:.2f}),{val},{expr})"
    return f"max(0,min({max_x},{expr}))"

def get_face_detector_model() -> Optional[str]:
    project_root = Path(__file__).resolve().parent.parent
    model_p = project_root / "bin" / "face_detection_yunet_2023mar.onnx"
    if model_p.exists():
        return str(model_p)
    return None

def merge_scene_intervals(
    raw_samples: List[Tuple[float, bool, float]],
    min_scene_sec: float = 2.0,
    clip_duration: float = 0.0,
    visual_cuts: Optional[List[float]] = None,
    padding_sec: float = 0.2
) -> List[Dict[str, Any]]:
    if not raw_samples:
        return []

    if padding_sec is None:
        padding_sec = 0.2

    if visual_cuts is None:
        visual_cuts = []

    # 1. Group contiguous identical states into raw chunks
    chunks: List[Dict[str, Any]] = []
    cur_is_face = raw_samples[0][1]
    cur_start = raw_samples[0][0]
    cur_faces = [raw_samples[0][2]] if cur_is_face else []

    for t, is_face, fx in raw_samples[1:]:
        if is_face == cur_is_face:
            if cur_is_face:
                cur_faces.append(fx)
        else:
            chunks.append({
                "start": cur_start,
                "end": t,
                "mode": "CROP_TRACKING" if cur_is_face else "BLURRED_BACKGROUND",
                "faces": cur_faces
            })
            cur_is_face = is_face
            cur_start = t
            cur_faces = [fx] if cur_is_face else []

    final_end = clip_duration if clip_duration > 0 else raw_samples[-1][0]
    chunks.append({
        "start": cur_start,
        "end": final_end,
        "mode": "CROP_TRACKING" if cur_is_face else "BLURRED_BACKGROUND",
        "faces": cur_faces
    })

    # 2. Iteratively merge short flickers (< min_scene_sec, anti-micro cut)
    changed = True
    while changed and len(chunks) > 1:
        changed = False
        for i in range(len(chunks)):
            dur = chunks[i]["end"] - chunks[i]["start"]
            if dur < min_scene_sec:
                if i == 0:
                    chunks[1]["start"] = chunks[0]["start"]
                    if chunks[0].get("faces"):
                        chunks[1].setdefault("faces", []).extend(chunks[0]["faces"])
                    chunks.pop(0)
                else:
                    chunks[i - 1]["end"] = chunks[i]["end"]
                    if chunks[i].get("faces"):
                        chunks[i - 1].setdefault("faces", []).extend(chunks[i]["faces"])
                    chunks.pop(i)
                changed = True
                break

    # 3. Merge adjacent chunks that have identical mode
    merged: List[Dict[str, Any]] = []
    for c in chunks:
        if merged and merged[-1]["mode"] == c["mode"]:
            merged[-1]["end"] = c["end"]
            if c.get("faces"):
                merged[-1].setdefault("faces", []).extend(c["faces"])
        else:
            merged.append(c)

    # 4. Snap boundaries to closest visual scene cut within +/- 0.8s
    for i in range(len(merged) - 1):
        b = merged[i]["end"]
        nearby_cuts = [c for c in visual_cuts if abs(c - b) <= 0.8]
        if nearby_cuts:
            best_cut = min(nearby_cuts, key=lambda c: abs(c - b))
            if merged[i]["start"] + 0.8 < best_cut < merged[i + 1]["end"] - 0.8:
                merged[i]["end"] = best_cut
                merged[i + 1]["start"] = best_cut

    # 5. Apply padding (+/- 0.2s) for CROP_TRACKING (Talking Head)
    for i in range(len(merged) - 1):
        curr_mode = merged[i]["mode"]
        next_mode = merged[i + 1]["mode"]
        b = merged[i]["end"]

        if curr_mode == "CROP_TRACKING" and next_mode == "BLURRED_BACKGROUND":
            # Extend talking head by +padding_sec
            new_b = min(final_end, b + padding_sec)
            merged[i]["end"] = new_b
            merged[i + 1]["start"] = new_b
        elif curr_mode == "BLURRED_BACKGROUND" and next_mode == "CROP_TRACKING":
            # Start talking head padding_sec earlier
            new_b = max(0.0, b - padding_sec)
            merged[i]["end"] = new_b
            merged[i + 1]["start"] = new_b

    return merged

def segment_clip_scenes(
    video_path: str,
    clip_start: float,
    clip_end: float,
    sample_step: int = 6,
    detect_width: int = 640,
    min_scene_sec: float = 2.0,
    padding_sec: float = 0.2
) -> List[SceneSegment]:
    """
    Segments video clip into distinct fixed scenes:
    - Talking Head: Locked static crop 9:16 using the MEDIAN dominant face X position (camera is completely stationary).
    - Screen Record / Non-Face: Full 16:9 view fit inside 1080x1920 canvas with blurred background.
    """
    if padding_sec is None:
        padding_sec = 0.2
    clip_dur = max(0.1, clip_end - clip_start)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return [
            SceneSegment(
                start_time=0.0,
                end_time=clip_dur,
                mode="BLURRED_BACKGROUND",
                crop_x="0"
            )
        ]

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080

    start_frame = int(clip_start * fps)
    end_frame = int(clip_end * fps)
    if end_frame < start_frame:
        end_frame = start_frame
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

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

    default_center = width / 2.0
    last_center = default_center
    raw_samples: List[Tuple[float, bool, float]] = []
    visual_cuts: List[float] = []
    prev_gray = None
    cut_diff_threshold = 28.0

    min_face_area = 0.015 * (detect_w * detect_h)  # >= 1.5% frame area

    frame_idx = 0
    current_frame = start_frame

    while current_frame <= end_frame:
        if not cap.grab():
            break

        if frame_idx % sample_step == 0:
            t_rel = (current_frame - start_frame) / fps
            ret, frame = cap.retrieve()
            face_found = False

            if ret and frame is not None:
                small_frame = cv2.resize(frame, (detect_w, detect_h))

                # Visual scene boundary cut detection
                gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
                if prev_gray is not None:
                    diff_val = float(np.mean(cv2.absdiff(gray, prev_gray)))
                    if diff_val >= cut_diff_threshold:
                        visual_cuts.append(t_rel)
                prev_gray = gray

                # Detect dominant face (largest bounding box area with score >= 0.6)
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
                                # Pick dominant face with largest area
                                best_face = max(valid_faces, key=lambda x: x[0])[1]
                                cx_small = float(best_face[0] + best_face[2] / 2.0)
                                last_center = cx_small * scale_x
                    except Exception:
                        pass

            raw_samples.append((t_rel, face_found, last_center))

        frame_idx += 1
        current_frame += 1

    cap.release()

    if not raw_samples:
        return [
            SceneSegment(
                start_time=0.0,
                end_time=clip_dur,
                mode="BLURRED_BACKGROUND",
                crop_x="0"
            )
        ]

    # Merge into stable scene intervals with visual cut snapping and padding
    chunks = merge_scene_intervals(
        raw_samples,
        min_scene_sec=min_scene_sec,
        clip_duration=clip_dur,
        visual_cuts=visual_cuts,
        padding_sec=padding_sec
    )
    scenes: List[SceneSegment] = []

    for c in chunks:
        s_start = max(0.0, float(c["start"]))
        s_end = min(clip_dur, float(c["end"]))
        if s_end <= s_start:
            continue

        if c["mode"] == "CROP_TRACKING":
            # Segmen Talking Head: Gunakan MEDIAN dari nilai X-center wajah sebagai satu-satunya titik crop (FIXED VALUE)
            faces = c.get("faces", [])
            if faces:
                median_cx = float(np.median(faces))
            else:
                median_cx = default_center

            fixed_crop_x, _, _ = calculate_crop_box(width, height, median_cx)
            scenes.append(
                SceneSegment(
                    start_time=s_start,
                    end_time=s_end,
                    mode="CROP_TRACKING",
                    crop_x=str(fixed_crop_x)
                )
            )
        else:
            # Segmen Non-Face / Screen Record: Fit 16:9 di tengah dengan latar buram
            scenes.append(
                SceneSegment(
                    start_time=s_start,
                    end_time=s_end,
                    mode="BLURRED_BACKGROUND",
                    crop_x="0"
                )
            )

    return scenes or [
        SceneSegment(
            start_time=0.0,
            end_time=clip_dur,
            mode="BLURRED_BACKGROUND",
            crop_x="0"
        )
    ]

def detect_face_centers(
    video_path: str,
    start_time: float,
    end_time: float,
    sample_step: int = 6,
    detect_width: int = 640
) -> Tuple[List[float], ReframeStrategy]:
    scenes = segment_clip_scenes(
        video_path,
        start_time,
        end_time,
        sample_step=sample_step,
        detect_width=detect_width
    )
    has_crop = any(sc.mode == "CROP_TRACKING" for sc in scenes)
    strategy = ReframeStrategy.CROP_TRACKING if has_crop else ReframeStrategy.BLURRED_BACKGROUND

    # Return default centers list for compatibility with callers
    centers = [960.0]
    return centers, strategy
