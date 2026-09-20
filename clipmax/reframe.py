import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any, Union
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
    Builds fixed crop expression. In fixed-scene mode, returns a single fixed X coordinate string.
    """
    if not values:
        return str(max_x // 2)

    # In fixed scene mode, values in a segment are identical or median-centered
    if max(values) - min(values) < 2.0 or len(values) == 1:
        return str(int(round(values[0])))

    # Discrete step function (Hard Cuts between scenes)
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

def determine_segment_layout(
    segment_frames: List[Any],
    frame_width: int = 1920
) -> str:
    """
    Universal Standalone Segment Layout Evaluator:
    
    A. BLURRED_BG (16:9 Fit in center + blurred background):
       - If in this segment max_detected_faces >= 2 (even if only in a few sample frames).
       - OR if 0 faces are detected throughout the segment (screen share / slide / presentation / B-roll).
       - OR if only 1 face detected, but average/median X-center is on screen edge (X < 0.38 or X > 0.62),
         indicating a two-person podcast shot where the partner is sitting on the opposite side.
    
    B. CROP_9_16:
       - ONLY if throughout the segment consistently max_detected_faces <= 1 (and at least 1 valid face),
         AND median X-center is in the centered region (0.38 <= X <= 0.62).
    
    Returns: 'CROP_9_16' or 'BLURRED_BG'.
    """
    if not segment_frames:
        return "BLURRED_BG"

    face_counts: List[int] = []
    face_xs: List[float] = []

    for item in segment_frames:
        # Support various formats: (t, fc, cx) or (fc, cx) or dict or raw int
        if isinstance(item, (tuple, list)):
            if len(item) == 3:
                fc, cx = item[1], item[2]
            elif len(item) == 2:
                fc, cx = item[0], item[1]
            else:
                fc, cx = item[0], None
        elif isinstance(item, dict):
            fc = item.get("face_count", item.get("faces", 0))
            cx = item.get("cx", item.get("center_x", None))
        elif isinstance(item, (int, float)):
            fc, cx = int(item), None
        else:
            fc, cx = 0, None

        if isinstance(fc, bool):
            fc = 1 if fc else 0
        face_counts.append(int(fc))
        if int(fc) == 1 and cx is not None:
            face_xs.append(float(cx))

    max_detected_faces = max(face_counts) if face_counts else 0

    # Condition A1: Multi-person frame detected (max_detected_faces >= 2)
    if max_detected_faces >= 2:
        return "BLURRED_BG"

    # Condition A2: No face detected throughout the segment
    if not face_xs:
        return "BLURRED_BG"

    median_x = float(np.median(face_xs))
    x_norm = median_x / float(frame_width)

    # Condition A3: Asymmetric edge position (X < 0.38 or X > 0.62)
    if x_norm < 0.38 or x_norm > 0.62:
        return "BLURRED_BG"

    # Condition B: Centered single talking head (0.38 <= X <= 0.62)
    return "CROP_9_16"

def merge_scene_intervals(
    raw_samples: List[Tuple[float, Any, float]],
    min_scene_sec: float = 2.0,
    clip_duration: float = 0.0,
    visual_cuts: Optional[List[float]] = None,
    padding_sec: float = 0.2,
    frame_width: int = 1920
) -> List[Dict[str, Any]]:
    """
    Evaluates segment candidate intervals using determine_segment_layout.
    Absorbs micro-flickers, snaps cuts to visual changes, and pads transitions.
    """
    if not raw_samples:
        return []

    if padding_sec is None:
        padding_sec = 0.2

    if visual_cuts is None:
        visual_cuts = []

    final_end = clip_duration if clip_duration > 0 else raw_samples[-1][0]

    def to_state(ind):
        if isinstance(ind, bool):
            return 1 if ind else 0
        return 2 if ind >= 2 else (1 if ind == 1 else 0)

    # 1. Group contiguous raw samples into candidate blocks
    chunks: List[Dict[str, Any]] = []
    cur_state = to_state(raw_samples[0][1])
    cur_start = raw_samples[0][0]
    cur_chunk_samples = [raw_samples[0]]

    for s in raw_samples[1:]:
        t, ind, fx = s
        state = to_state(ind)
        if state == cur_state:
            cur_chunk_samples.append(s)
        else:
            chunks.append({
                "start": cur_start,
                "end": t,
                "samples": cur_chunk_samples
            })
            cur_state = state
            cur_start = t
            cur_chunk_samples = [s]

    chunks.append({
        "start": cur_start,
        "end": final_end,
        "samples": cur_chunk_samples
    })

    # 2. Absorb micro-flickers (< min_scene_sec)
    changed = True
    while changed and len(chunks) > 1:
        changed = False
        for i in range(len(chunks)):
            dur = chunks[i]["end"] - chunks[i]["start"]
            if dur < min_scene_sec:
                if i == 0:
                    chunks[1]["start"] = chunks[0]["start"]
                    chunks[1]["samples"] = chunks[0]["samples"] + chunks[1]["samples"]
                    chunks.pop(0)
                else:
                    chunks[i - 1]["end"] = chunks[i]["end"]
                    chunks[i - 1]["samples"] = chunks[i - 1]["samples"] + chunks[i]["samples"]
                    chunks.pop(i)
                changed = True
                break

    # 3. Classify each chunk using the standalone determine_segment_layout evaluator
    classified: List[Dict[str, Any]] = []
    for c in chunks:
        layout = determine_segment_layout(c["samples"], frame_width=frame_width)
        mode = "CROP_TRACKING" if layout == "CROP_9_16" else "BLURRED_BACKGROUND"
        faces = [s[2] for s in c["samples"] if (s[1] == 1 or s[1] is True) and s[2] is not None]
        classified.append({
            "start": c["start"],
            "end": c["end"],
            "mode": mode,
            "faces": faces,
            "samples": c["samples"]
        })

    # 4. Merge adjacent chunks with identical mode
    merged: List[Dict[str, Any]] = []
    for c in classified:
        if merged and merged[-1]["mode"] == c["mode"]:
            merged[-1]["end"] = c["end"]
            if c.get("faces"):
                merged[-1].setdefault("faces", []).extend(c["faces"])
            if c.get("samples"):
                merged[-1].setdefault("samples", []).extend(c["samples"])
        else:
            merged.append(c)

    # 5. Snap boundaries to closest visual cut within +/- 0.8s
    for i in range(len(merged) - 1):
        b = merged[i]["end"]
        nearby_cuts = [c for c in visual_cuts if abs(c - b) <= 0.8]
        if nearby_cuts:
            best_cut = min(nearby_cuts, key=lambda c: abs(c - b))
            if merged[i]["start"] + 0.8 < best_cut < merged[i + 1]["end"] - 0.8:
                merged[i]["end"] = best_cut
                merged[i + 1]["start"] = best_cut

    # 6. Apply padding (+/- 0.2s) for CROP_TRACKING (Talking Head)
    for i in range(len(merged) - 1):
        curr_mode = merged[i]["mode"]
        next_mode = merged[i + 1]["mode"]
        b = merged[i]["end"]

        if curr_mode == "CROP_TRACKING" and next_mode == "BLURRED_BACKGROUND":
            new_b = min(final_end, b + padding_sec)
            merged[i]["end"] = new_b
            merged[i + 1]["start"] = new_b
        elif curr_mode == "BLURRED_BACKGROUND" and next_mode == "CROP_TRACKING":
            new_b = max(0.0, b - padding_sec)
            merged[i]["end"] = new_b
            merged[i + 1]["start"] = new_b

    return merged

def segment_clip_scenes(
    video_path: str,
    clip_start: float,
    clip_end: float,
    sample_step: int = 15,
    detect_width: int = 640,
    min_scene_sec: float = 2.0,
    padding_sec: float = 0.2
) -> List[SceneSegment]:
    """
    Universal Video Segmenter:
    - Samples frames periodically (~0.5s interval).
    - Runs Face Detection on each sample.
    - Evaluates every segment with determine_segment_layout:
      * CROP_9_16: Locked static crop 9:16 on median X position (0.38 <= X <= 0.62).
      * BLURRED_BG: 16:9 full view fit in center with blurred background (>= 2 faces, 0 faces, or edge anchor).
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

    # 0.5s periodic sampling interval
    step = max(1, int(round(fps * 0.5))) if sample_step is None or sample_step <= 0 else sample_step

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
    raw_samples: List[Tuple[float, int, float]] = []
    visual_cuts: List[float] = []
    prev_gray = None
    cut_diff_threshold = 28.0

    min_face_area = 0.015 * (detect_w * detect_h)  # >= 1.5% frame area

    frame_idx = 0
    current_frame = start_frame

    while current_frame <= end_frame:
        if not cap.grab():
            break

        if frame_idx % step == 0:
            t_rel = (current_frame - start_frame) / fps
            ret, frame = cap.retrieve()
            face_count = 0

            if ret and frame is not None:
                small_frame = cv2.resize(frame, (detect_w, detect_h))

                # Visual scene boundary cut detection
                gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
                if prev_gray is not None:
                    diff_val = float(np.mean(cv2.absdiff(gray, prev_gray)))
                    if diff_val >= cut_diff_threshold:
                        visual_cuts.append(t_rel)
                prev_gray = gray

                # Evaluate face count
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

                            face_count = len(valid_faces)
                            if face_count == 1:
                                best_face = valid_faces[0][1]
                                cx_small = float(best_face[0] + best_face[2] / 2.0)
                                last_center = cx_small * scale_x
                    except Exception:
                        face_count = 0

            raw_samples.append((t_rel, face_count, last_center))

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

    # Merge into stable scene intervals using determine_segment_layout
    chunks = merge_scene_intervals(
        raw_samples,
        min_scene_sec=min_scene_sec,
        clip_duration=clip_dur,
        visual_cuts=visual_cuts,
        padding_sec=padding_sec,
        frame_width=width
    )
    scenes: List[SceneSegment] = []

    for c in chunks:
        s_start = max(0.0, float(c["start"]))
        s_end = min(clip_dur, float(c["end"]))
        if s_end <= s_start:
            continue

        # Universal evaluator called on every segment
        seg_samples = c.get("samples", [])
        layout = determine_segment_layout(seg_samples, frame_width=width)

        if layout == "CROP_9_16":
            faces = [s[2] for s in seg_samples if (s[1] == 1 or s[1] is True) and s[2] is not None]
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
    sample_step: int = 15,
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

    centers = [960.0]
    return centers, strategy
