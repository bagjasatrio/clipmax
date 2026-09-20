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

def format_ts(sec: float) -> str:
    m = int(sec // 60)
    s = int(sec % 60)
    return f"{m:02d}:{s:02d}"

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

def normalize_sample_to_frame(
    item: Any,
    frame_width: int = 1920,
    frame_height: int = 1080
) -> List[Dict[str, float]]:
    """
    Normalizes a sampled frame record into valid face dicts.
    Filters out faces with height < 12% frame height or confidence < 0.55.
    """
    if isinstance(item, list):
        frame_faces = []
        for face in item:
            if isinstance(face, dict):
                score = face.get("score", 1.0)
                # Height check: height >= 12% total video height
                h_norm = face.get("h_norm", None)
                if h_norm is None:
                    h_val = face.get("h", 0.0)
                    h_norm = (h_val / float(frame_height)) if h_val > 1.0 else float(h_val)
                if h_norm <= 0.0:
                    h_norm = 0.15

                if score >= 0.55 and h_norm >= 0.12:
                    xc = face.get("x_center", face.get("cx", 0.5))
                    norm_xc = (xc / float(frame_width)) if xc > 1.0 else float(xc)
                    frame_faces.append({
                        "x_center": norm_xc,
                        "cx_px": face.get("cx_px", norm_xc * frame_width),
                        "h_norm": h_norm,
                        "score": score
                    })
            elif isinstance(face, (int, float)):
                norm_xc = (face / float(frame_width)) if face > 1.0 else float(face)
                frame_faces.append({
                    "x_center": norm_xc,
                    "cx_px": norm_xc * frame_width,
                    "h_norm": 0.15,
                    "score": 1.0
                })
        return frame_faces

    elif isinstance(item, tuple):
        if len(item) == 3:
            _, ind, cx = item
        elif len(item) == 2:
            ind, cx = item
        else:
            ind, cx = item[0], None

        if isinstance(ind, list):
            return normalize_sample_to_frame(ind, frame_width, frame_height)

        if isinstance(ind, bool):
            fc = 1 if ind else 0
        else:
            fc = int(ind) if ind is not None else 0

        if fc == 0 or cx is None:
            return []

        norm_xc = (cx / float(frame_width)) if cx > 1.0 else float(cx)
        if fc == 1:
            return [{
                "x_center": norm_xc,
                "cx_px": norm_xc * frame_width,
                "h_norm": 0.15,
                "score": 1.0
            }]
        else:
            return [{
                "x_center": norm_xc,
                "cx_px": norm_xc * frame_width,
                "h_norm": 0.15,
                "score": 1.0
            }] * fc

    elif isinstance(item, dict):
        fc = item.get("face_count", item.get("faces", 0))
        cx = item.get("cx", item.get("x_center", None))
        if fc == 0 or cx is None:
            return []
        norm_xc = (cx / float(frame_width)) if cx > 1.0 else float(cx)
        return [{
            "x_center": norm_xc,
            "cx_px": norm_xc * frame_width,
            "h_norm": 0.15,
            "score": 1.0
        }] * int(fc)

    return []

def determine_segment_layout(
    detected_faces_list: List[Any],
    frame_width: int = 1920,
    frame_height: int = 1080
) -> str:
    """
    Robust Segment Layout Evaluator with Confidence & Size Filtering and Voting:
    1. Filter faces: score >= 0.55, height >= 12% frame height (ignoring small icons/logos/slide photos).
    2. face_ratio = (frames with valid faces) / total_samples.
    3. If face_ratio < 0.35:
       -> Pasti Slide / Layar / Presentasi -> BLURRED_BACKGROUND.
    4. If face_ratio >= 0.35:
       - Multi-person check: If multi-person frames >= 15% -> BLURRED_BACKGROUND.
       - Single person check:
         * 0.35 <= avg_x <= 0.65 (centered) -> CROP_9_16.
         * avg_x < 0.35 or avg_x > 0.65 (edge anchor) -> BLURRED_BACKGROUND.
    """
    if not detected_faces_list:
        return "BLURRED_BACKGROUND"

    normalized_frames = [
        normalize_sample_to_frame(item, frame_width, frame_height)
        for item in detected_faces_list
    ]
    total_samples = len(normalized_frames)
    if total_samples == 0:
        return "BLURRED_BACKGROUND"

    valid_frames = [f for f in normalized_frames if len(f) > 0]
    face_ratio = len(valid_frames) / float(total_samples)

    # Condition 1: Slide / Presentation / B-Roll
    if face_ratio < 0.35:
        return "BLURRED_BACKGROUND"

    # Condition 2: Multi-person (>= 2 faces in >= 15% of frames)
    multi_frames = [f for f in normalized_frames if len(f) >= 2]
    multi_ratio = len(multi_frames) / float(total_samples)
    if multi_ratio >= 0.15:
        return "BLURRED_BACKGROUND"

    # Condition 3: Single Talking Head
    x_centers = [f[0]["x_center"] for f in valid_frames]
    avg_x = sum(x_centers) / float(len(x_centers))

    if 0.35 <= avg_x <= 0.65:
        return "CROP_9_16"
    else:
        return "BLURRED_BACKGROUND"

def detect_visual_shots(
    video_path: str,
    clip_start: float,
    clip_end: float,
    min_scene_sec: float = 1.5
) -> List[Tuple[float, float]]:
    """
    Detects scene cuts using PySceneDetect (ContentDetector).
    Returns list of relative shot timestamps [(s_start, s_end), ...] within [0.0, clip_dur].
    """
    clip_dur = max(0.1, clip_end - clip_start)
    try:
        from scenedetect import SceneManager, open_video, ContentDetector
        v = open_video(video_path)
        v.seek(clip_start)
        sm = SceneManager()
        sm.add_detector(ContentDetector(threshold=25.0))
        sm.detect_scenes(v, end_time=clip_end)
        scene_list = sm.get_scene_list()

        if not scene_list:
            return [(0.0, clip_dur)]

        raw_shots = []
        for s in scene_list:
            s_rel = max(0.0, min(clip_dur, s[0].seconds - clip_start))
            e_rel = max(0.0, min(clip_dur, s[1].seconds - clip_start))
            if e_rel - s_rel >= 0.1:
                raw_shots.append((s_rel, e_rel))

        if not raw_shots:
            return [(0.0, clip_dur)]

        shots = [list(raw_shots[0])]
        shots[0][0] = 0.0
        for s_r, e_r in raw_shots[1:]:
            if (e_r - shots[-1][1]) < min_scene_sec or (shots[-1][1] - shots[-1][0]) < min_scene_sec:
                shots[-1][1] = e_r
            else:
                shots.append([s_r, e_r])
        shots[-1][1] = clip_dur
        return [(round(float(s), 3), round(float(e), 3)) for s, e in shots if e > s]
    except Exception:
        return [(0.0, clip_dur)]

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
    Maintained for backward compatibility with existing tests and fine-grained visual cut pipelines.
    """
    if not raw_samples:
        return []

    if padding_sec is None:
        padding_sec = 0.2

    final_end = clip_duration if clip_duration > 0 else raw_samples[-1][0]

    def to_state(s):
        ind = s[1] if isinstance(s, tuple) and len(s) > 1 else s
        if isinstance(ind, list):
            return 2 if len(ind) >= 2 else (1 if len(ind) == 1 else 0)
        if isinstance(ind, bool):
            return 1 if ind else 0
        return 2 if ind >= 2 else (1 if ind == 1 else 0)

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

    if visual_cuts:
        for i in range(len(merged) - 1):
            b = merged[i]["end"]
            nearby_cuts = [c for c in visual_cuts if abs(c - b) <= 0.8]
            if nearby_cuts:
                best_cut = min(nearby_cuts, key=lambda c: abs(c - b))
                if merged[i]["start"] + 0.8 < best_cut < merged[i + 1]["end"] - 0.8:
                    merged[i]["end"] = best_cut
                    merged[i + 1]["start"] = best_cut

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
    sample_step: Optional[int] = None,
    detect_width: int = 640,
    min_scene_sec: float = 1.5,
    padding_sec: float = 0.2
) -> List[SceneSegment]:
    """
    Per-Shot Scene Classifier using PySceneDetect + Confidence & Size Filtering:
    1. Scene Cut Detection: Detects visual shot boundaries via PySceneDetect.
    2. Face Validation: score >= 0.55, height >= 12% total frame height.
    3. Sampling: Samples frames every 0.25s along each shot.
    4. Robust Voting:
       - face_ratio < 0.35 -> BLURRED_BACKGROUND (Slide)
       - multi_ratio >= 0.15 -> BLURRED_BACKGROUND (Multi-person)
       - 0.35 <= avg_x <= 0.65 -> CROP_9_16 (Solo)
       - avg_x < 0.35 or avg_x > 0.65 -> BLURRED_BACKGROUND (Edge Anchor)
    5. Visual Debug Log printed for every evaluated scene.
    """
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

    # Detect visual shot boundaries using PySceneDetect
    visual_shots = detect_visual_shots(video_path, clip_start, clip_end, min_scene_sec=min_scene_sec)

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
                score_threshold=0.55,
                nms_threshold=0.3
            )
        except Exception:
            detector = None

    default_center = width / 2.0
    # 0.25s sampling interval
    step_frames = max(1, int(round(fps * 0.25))) if (sample_step is None or sample_step <= 0) else sample_step

    # Minimum face bounding box height: >= 12% of total height
    min_face_h = 0.12 * detect_h

    scenes: List[SceneSegment] = []

    for idx, (s_start, s_end) in enumerate(visual_shots, start=1):
        shot_dur = s_end - s_start
        if shot_dur < 0.1:
            continue

        shot_start_frame = int((clip_start + s_start) * fps)
        shot_end_frame = int((clip_start + s_end) * fps)

        cap.set(cv2.CAP_PROP_POS_FRAMES, shot_start_frame)
        cur_frame = shot_start_frame

        shot_frame_faces: List[List[Dict[str, Any]]] = []

        while cur_frame <= shot_end_frame:
            if not cap.grab():
                break

            if (cur_frame - shot_start_frame) % step_frames == 0:
                ret, frame = cap.retrieve()
                valid_faces = []
                if ret and frame is not None:
                    small_frame = cv2.resize(frame, (detect_w, detect_h))
                    if detector is not None:
                        try:
                            _, faces = detector.detect(small_frame)
                            if faces is not None and len(faces) > 0:
                                for f in faces:
                                    w_f, h_f = float(f[2]), float(f[3])
                                    score = float(f[14]) if len(f) > 14 else 1.0
                                    # Strict validation: score >= 0.55 and height >= 12% total height
                                    if score >= 0.55 and h_f >= min_face_h:
                                        cx_small = float(f[0] + f[2] / 2.0)
                                        norm_x = cx_small / float(detect_w)
                                        valid_faces.append({
                                            "x_center": norm_x,
                                            "cx_px": cx_small * scale_x,
                                            "h": h_f,
                                            "score": score
                                        })
                        except Exception:
                            valid_faces = []

                shot_frame_faces.append(valid_faces)

            cur_frame += 1

        total_samples = len(shot_frame_faces)
        valid_frames = [f for f in shot_frame_faces if len(f) > 0]
        face_ratio = (len(valid_frames) / float(total_samples)) if total_samples > 0 else 0.0

        # Robust Voting Rules
        if face_ratio < 0.35:
            # Rule A: Slide / Presentation / Screen Share
            mode = "BLURRED_BACKGROUND"
            crop_x = "0"
            label = "Slide"
            log_str = f"[Scene {idx}: {format_ts(s_start)}-{format_ts(s_end)}] Faces: 0 | Ratio: {face_ratio:.2f} -> BLURRED_BACKGROUND ({label})"
        else:
            multi_frames = [f for f in shot_frame_faces if len(f) >= 2]
            multi_ratio = (len(multi_frames) / float(total_samples)) if total_samples > 0 else 0.0

            if multi_ratio >= 0.15:
                # Rule B: Multi-person Podcast
                mode = "BLURRED_BACKGROUND"
                crop_x = "0"
                label = "Multi-person"
                log_str = f"[Scene {idx}: {format_ts(s_start)}-{format_ts(s_end)}] Faces: 2 | Ratio: {face_ratio:.2f} | Multi: {multi_ratio:.2f} -> BLURRED_BACKGROUND ({label})"
            else:
                # Rule C: Single Talking Head
                x_centers = [f[0]["x_center"] for f in valid_frames]
                avg_x = sum(x_centers) / float(len(x_centers))

                if 0.35 <= avg_x <= 0.65:
                    # Centered Solo Presenter
                    mode = "CROP_TRACKING"
                    label = "Solo"
                    median_cx = float(np.median([f[0]["cx_px"] for f in valid_frames]))
                    fixed_crop_x, _, _ = calculate_crop_box(width, height, median_cx)
                    crop_x = str(fixed_crop_x)
                    log_str = f"[Scene {idx}: {format_ts(s_start)}-{format_ts(s_end)}] Faces: 1 | Ratio: {face_ratio:.2f} | X: {avg_x:.2f} -> CROP_9_16 ({label})"
                else:
                    # Edge Anchor (Podcast wide two-shot)
                    mode = "BLURRED_BACKGROUND"
                    crop_x = "0"
                    label = "Edge Anchor"
                    log_str = f"[Scene {idx}: {format_ts(s_start)}-{format_ts(s_end)}] Faces: 1 | Ratio: {face_ratio:.2f} | X: {avg_x:.2f} -> BLURRED_BACKGROUND ({label})"

        print(log_str)

        scenes.append(
            SceneSegment(
                start_time=s_start,
                end_time=s_end,
                mode=mode,
                crop_x=crop_x
            )
        )

    cap.release()

    # Merge consecutive scenes with identical mode
    if len(scenes) > 1:
        merged_scenes: List[SceneSegment] = [scenes[0]]
        for sc in scenes[1:]:
            last = merged_scenes[-1]
            if last.mode == sc.mode and (last.mode == "BLURRED_BACKGROUND" or abs(int(last.crop_x) - int(sc.crop_x)) < 30):
                last.end_time = sc.end_time
            else:
                merged_scenes.append(sc)
        scenes = merged_scenes

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
    has_crop = any(sc.mode in ("CROP_TRACKING", "CROP_9_16") for sc in scenes)
    strategy = ReframeStrategy.CROP_TRACKING if has_crop else ReframeStrategy.BLURRED_BACKGROUND

    centers = [960.0]
    return centers, strategy
