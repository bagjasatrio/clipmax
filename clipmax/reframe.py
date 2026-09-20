import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any, Union
from enum import Enum
from pydantic import BaseModel

class ReframeStrategy(str, Enum):
    CROP_TRACKING = "CROP_TRACKING"
    BLURRED_BACKGROUND = "BLURRED_BACKGROUND"
    CROP_9_16 = "CROP_TRACKING"
    BLURRED_BG = "BLURRED_BACKGROUND"
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

    if max(values) - min(values) < 2.0 or len(values) == 1:
        return str(int(round(values[0])))

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

def normalize_sample_to_frame(item: Any, frame_width: int = 1920) -> List[Dict[str, float]]:
    if isinstance(item, list):
        frame_faces = []
        for face in item:
            if isinstance(face, dict):
                xc = face.get("x_center", face.get("cx", 0.5))
                norm_xc = xc / float(frame_width) if xc > 1.0 else float(xc)
                frame_faces.append({"x_center": norm_xc})
            elif isinstance(face, (int, float)):
                norm_xc = face / float(frame_width) if face > 1.0 else float(face)
                frame_faces.append({"x_center": norm_xc})
        return frame_faces
    elif isinstance(item, tuple):
        if len(item) == 3:
            _, ind, cx = item
        elif len(item) == 2:
            ind, cx = item
        else:
            ind, cx = item[0], None

        if isinstance(ind, list):
            return normalize_sample_to_frame(ind, frame_width)
        if isinstance(ind, bool):
            fc = 1 if ind else 0
        else:
            fc = int(ind) if ind is not None else 0

        if fc == 0 or cx is None:
            return []
        norm_xc = cx / float(frame_width) if cx > 1.0 else float(cx)
        if fc == 1:
            return [{"x_center": norm_xc}]
        else:
            return [{"x_center": norm_xc}] * fc
    elif isinstance(item, dict):
        fc = item.get("face_count", item.get("faces", 0))
        cx = item.get("cx", item.get("x_center", None))
        if fc == 0 or cx is None:
            return []
        norm_xc = cx / float(frame_width) if cx > 1.0 else float(cx)
        return [{"x_center": norm_xc}] * int(fc)
    return []

def determine_segment_layout(
    detected_faces_list: List[Any],
    frame_width: int = 1920
) -> str:
    """
    Evaluasi layout per segmen:
    - detected_faces_list: list hasil deteksi wajah per frame sampel di segmen tersebut
    
    1. KASUS A: Layar / Slide / B-Roll (Tidak ada wajah sama sekali)
       -> "BLURRED_BACKGROUND"
    2. KASUS B: Multi-orang (Ada 2 wajah atau lebih dalam frame)
       -> "BLURRED_BACKGROUND"
    3. KASUS C: 1 Wajah (Single Talking Head)
       - Jika posisi rata-rata X di tengah (0.35 <= avg_x <= 0.65) -> "CROP_9_16" (WAJIB FULL CROP 9:16)
       - Jika posisi wajah di pinggir layar (avg_x < 0.35 atau avg_x > 0.65) -> "BLURRED_BACKGROUND"
    """
    if not detected_faces_list:
        return "BLURRED_BACKGROUND"

    normalized_frames = [normalize_sample_to_frame(item, frame_width) for item in detected_faces_list]

    # 1. Hitung frame yang memiliki wajah
    valid_frames = [f for f in normalized_frames if len(f) > 0]

    # KASUS A: Layar / Slide / B-Roll (Tidak ada wajah sama sekali)
    if len(valid_frames) == 0:
        return "BLURRED_BACKGROUND"

    # KASUS B: Multi-orang (Ada 2 wajah atau lebih dalam frame)
    max_faces = max([len(f) for f in normalized_frames])
    if max_faces >= 2:
        return "BLURRED_BACKGROUND"

    # KASUS C: 1 Wajah (Single Talking Head)
    # Ambil rata-rata posisi X wajah
    x_centers = [f[0]["x_center"] for f in valid_frames]
    avg_x = sum(x_centers) / len(x_centers)

    # Jika posisi wajah wajar di tengah (antara 35% sampai 65% lebar layar)
    if 0.35 <= avg_x <= 0.65:
        return "CROP_9_16"  # WAJIB FULL CROP 9:16
    else:
        # Wajah terlalu di pinggir (indikasi wide podcast 2 orang)
        return "BLURRED_BACKGROUND"

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

    def to_state(s):
        ind = s[1] if isinstance(s, tuple) and len(s) > 1 else s
        if isinstance(ind, list):
            return 2 if len(ind) >= 2 else (1 if len(ind) == 1 else 0)
        if isinstance(ind, bool):
            return 1 if ind else 0
        return 2 if ind >= 2 else (1 if ind == 1 else 0)

    # 1. Group contiguous raw samples into candidate blocks
    chunks: List[Dict[str, Any]] = []
    cur_state = to_state(raw_samples[0])
    cur_start = raw_samples[0][0]
    cur_chunk_samples = [raw_samples[0]]

    for s in raw_samples[1:]:
        state = to_state(s)
        if state == cur_state:
            cur_chunk_samples.append(s)
        else:
            chunks.append({
                "start": cur_start,
                "end": s[0],
                "samples": cur_chunk_samples
            })
            cur_state = state
            cur_start = s[0]
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

    # 3. Classify each chunk using determine_segment_layout
    classified: List[Dict[str, Any]] = []
    for c in chunks:
        layout = determine_segment_layout(c["samples"], frame_width=frame_width)
        mode = "CROP_TRACKING" if layout == "CROP_9_16" else "BLURRED_BACKGROUND"
        faces = [s[2] for s in c["samples"] if len(s) > 2 and s[2] is not None]
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
      * CROP_9_16: Locked static crop 9:16 on median X position (0.35 <= avg_x <= 0.65).
      * BLURRED_BACKGROUND: 16:9 full view fit in center with blurred background (>= 2 faces, 0 faces, or edge anchor).
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
    raw_samples: List[Tuple[float, Any, float]] = []
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
            frame_faces = []

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
                            for f in faces:
                                w_f, h_f = float(f[2]), float(f[3])
                                area = w_f * h_f
                                score = float(f[14]) if len(f) > 14 else 1.0
                                if score >= 0.6 and area >= min_face_area:
                                    cx_small = float(f[0] + f[2] / 2.0)
                                    norm_x = cx_small / float(detect_w)
                                    frame_faces.append({
                                        "x_center": norm_x,
                                        "cx_px": cx_small * scale_x,
                                        "box": (float(f[0]), float(f[1]), w_f, h_f),
                                        "score": score
                                    })
                    except Exception:
                        frame_faces = []

            if len(frame_faces) == 1:
                last_center = frame_faces[0]["cx_px"]

            raw_samples.append((t_rel, frame_faces, last_center))

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

        seg_samples = c.get("samples", [])
        layout = determine_segment_layout(seg_samples, frame_width=width)

        if layout == "CROP_9_16":
            # Extract valid pixel centers from detected face dicts
            cx_vals = []
            for s in seg_samples:
                item = s[1] if len(s) > 1 else None
                if isinstance(item, list):
                    for f in item:
                        if isinstance(f, dict) and "cx_px" in f:
                            cx_vals.append(f["cx_px"])
                elif len(s) > 2 and s[2] is not None:
                    cx_vals.append(float(s[2]))

            median_cx = float(np.median(cx_vals)) if cx_vals else default_center
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
