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
    crop_x: str            # dynamic expression or static number

def cluster_face_anchors(all_cx: List[float], min_dist: float = 250.0) -> List[float]:
    """
    Groups face X-coordinates into discrete anchor clusters for multi-person podcasts.
    Returns the sorted average X position for each identified speaker.
    """
    if not all_cx:
        return []
    xs = sorted(all_cx)
    clusters = []
    current_cluster = [xs[0]]
    for x in xs[1:]:
        if x - np.mean(current_cluster) < min_dist:
            current_cluster.append(x)
        else:
            clusters.append(current_cluster)
            current_cluster = [x]
    clusters.append(current_cluster)

    min_count = max(3, int(0.04 * len(all_cx)))
    anchors = []
    for cl in clusters:
        if len(cl) >= min_count:
            anchors.append(float(np.mean(cl)))
    return sorted(anchors)

class ActiveSpeakerTracker:
    """
    Shot-Locking Switcher for multi-person podcast reframing (OpusClip style):
    - Clusters face positions into fixed anchor points (e.g. x1, x2).
    - Active speaker detected by Mouth Aspect Ratio (MAR) variation over a 1.5s sliding window.
    - Cooldown / Shot Hold Time: locks camera on current speaker for at least 2.5s (prevents jitter).
    - Discrete camera switching (Hard Cut) between fixed anchors.
    """
    def __init__(
        self,
        anchors: Optional[List[float]] = None,
        switch_threshold_sec: float = 1.0,
        window_sec: float = 1.5,
        min_hold_sec: float = 2.5,
        mar_threshold: float = 0.02
    ):
        self.anchors = sorted(anchors) if anchors else []
        self.switch_threshold_sec = switch_threshold_sec
        self.window_sec = window_sec
        self.min_hold_sec = min_hold_sec
        self.mar_threshold = mar_threshold

        self.history: Dict[str, List[Tuple[float, float, float]]] = {}  # pid -> [(timestamp, mar, cx)]
        self.anchor_points: Dict[str, float] = {}  # pid -> anchor cx
        self.active_person_id: Optional[str] = None
        self.last_switch_time: float = 0.0
        self.candidate_person_id: Optional[str] = None
        self.candidate_active_time: float = 0.0

    def match_person(self, cx: float, max_dist: float = 250.0) -> str:
        # Match to pre-defined anchors if available
        if self.anchors:
            dists = [abs(cx - a) for a in self.anchors]
            best_idx = int(np.argmin(dists))
            pid = f"person_{best_idx}"
            self.anchor_points[pid] = self.anchors[best_idx]
            if pid not in self.history:
                self.history[pid] = []
            return pid

        # Otherwise match to existing tracked person clusters
        best_id = None
        min_d = float("inf")
        for pid, records in self.history.items():
            if records:
                anchor = self.anchor_points.get(pid, records[-1][2])
                d = abs(cx - anchor)
                if d < min_d and d < max_dist:
                    min_d = d
                    best_id = pid

        if best_id is None:
            best_id = f"person_{len(self.history)}"
            self.history[best_id] = []
            self.anchor_points[best_id] = cx
        else:
            all_cxs = [r[2] for r in self.history[best_id]] + [cx]
            self.anchor_points[best_id] = float(np.mean(all_cxs))

        return best_id

    def update(self, timestamp: float, detected_faces: List[Tuple[float, float]]) -> Optional[float]:
        """
        detected_faces: List of tuples (cx, mar)
        Returns the discrete target X position of the active speaker.
        """
        if not detected_faces:
            return self.anchor_points.get(self.active_person_id) if self.active_person_id else None

        current_frame_pids = []
        for cx, mar in detected_faces:
            pid = self.match_person(cx)
            current_frame_pids.append(pid)
            self.history[pid].append((timestamp, mar, cx))

        # Prune history older than window_sec (1.5s)
        cutoff = timestamp - self.window_sec
        for pid in list(self.history.keys()):
            self.history[pid] = [r for r in self.history[pid] if r[0] >= cutoff]

        if self.active_person_id is None or self.active_person_id not in self.anchor_points:
            self.active_person_id = current_frame_pids[0]
            self.last_switch_time = timestamp

        # Single person observed
        if len(self.anchor_points) <= 1:
            self.active_person_id = current_frame_pids[0]
            self.candidate_person_id = None
            self.candidate_active_time = 0.0
            return self.anchor_points[self.active_person_id]

        # Multi-person: compute mouth activity (MAR variation / delta) over 1.5s window
        scores = {}
        for pid in self.anchor_points:
            records = self.history.get(pid, [])
            if len(records) >= 2:
                mars = [r[1] for r in records]
                scores[pid] = float(np.std(mars))
            else:
                scores[pid] = 0.0

        top_speaker_id = max(scores, key=scores.get)
        top_score = scores[top_speaker_id]
        current_score = scores.get(self.active_person_id, 0.0)

        time_since_switch = timestamp - self.last_switch_time

        # Cooldown / Shot-Locking rule:
        # Sekali kamera mengunci ke Orang A, kamera DILARANG berpindah selama minimal min_hold_sec (2.5s)
        if top_speaker_id != self.active_person_id and top_score >= self.mar_threshold:
            if top_speaker_id == self.candidate_person_id:
                dt = timestamp - (self.history[top_speaker_id][-2][0] if len(self.history[top_speaker_id]) >= 2 else timestamp)
                self.candidate_active_time += max(0.01, dt)
            else:
                self.candidate_person_id = top_speaker_id
                self.candidate_active_time = 0.0

            # Switch only if cooldown passed AND candidate has been speaking consistently
            if (time_since_switch >= self.min_hold_sec and
                self.candidate_active_time >= self.switch_threshold_sec and
                top_score > current_score + 0.005):
                self.active_person_id = top_speaker_id
                self.last_switch_time = timestamp
                self.candidate_person_id = None
                self.candidate_active_time = 0.0
        else:
            self.candidate_person_id = None
            self.candidate_active_time = 0.0

        return self.anchor_points[self.active_person_id]

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
    max_x: int = 1312,
    discrete: bool = False,
    visual_cuts: Optional[List[float]] = None
) -> str:
    """
    Builds FFmpeg crop X filter expression.
    - discrete=True: Generates discrete step function (HARD CUT) between speakers with no panning.
    - discrete=False: Generates piecewise linear continuous motion for single speakers.
    """
    if not values:
        return str(max_x // 2)

    # If camera or presenter is static (variation across clip < 8px) or single sample
    if max(values) - min(values) < 8.0 or len(values) == 1:
        return str(int(round(values[0])))

    if discrete:
        # Shot-Locking Switcher: discrete step function (Hard Cuts)
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
    else:
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

def get_face_landmarker():
    project_root = Path(__file__).resolve().parent.parent
    task_p = project_root / "bin" / "face_landmarker.task"
    if not task_p.exists():
        return None
    try:
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        base_options = python.BaseOptions(model_asset_path=str(task_p))
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=False,
            num_faces=4
        )
        return vision.FaceLandmarker.create_from_options(options)
    except Exception:
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
    crop_w = int(round(height * (9.0 / 16.0)))
    max_crop_x = width - crop_w

    start_frame = int(clip_start * fps)
    end_frame = int(clip_end * fps)
    if end_frame < start_frame:
        end_frame = start_frame
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    detect_w = min(width, detect_width)
    detect_h = int(round(height * (detect_w / float(width)))) if width > 0 else 360
    scale_x = (width / float(detect_w)) if detect_w > 0 else 1.0

    landmarker = get_face_landmarker()
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
    speaker_tracker = ActiveSpeakerTracker(
        window_sec=1.5,
        min_hold_sec=2.5,
        switch_threshold_sec=1.0
    )

    raw_samples: List[Tuple[float, bool, float]] = []
    all_detected_cx: List[float] = []
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

                # 1. MediaPipe FaceLandmarker for Multi-Face & Lip Movement (MAR)
                if landmarker is not None:
                    try:
                        import mediapipe as mp
                        rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
                        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                        res = landmarker.detect(mp_img)
                        if res.face_landmarks and len(res.face_landmarks) > 0:
                            face_candidates = []
                            for landmarks in res.face_landmarks:
                                lip_dist = abs(landmarks[14].y - landmarks[13].y)
                                lip_w = max(1e-5, abs(landmarks[291].x - landmarks[61].x))
                                mar = float(lip_dist / lip_w)
                                cx = float(np.mean([lm.x for lm in landmarks]) * width)
                                face_candidates.append((cx, mar))
                                all_detected_cx.append(cx)

                            if face_candidates:
                                face_found = True
                                active_cx = speaker_tracker.update(t_rel, face_candidates)
                                if active_cx is not None:
                                    last_center = active_cx
                    except Exception:
                        pass

                # 2. Fallback to YuNet if landmarker was unavailable / returned no detection
                if not face_found and detector is not None:
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
                                cand = []
                                for vf in valid_faces:
                                    fcx = float(vf[1][0] + vf[1][2] / 2.0) * scale_x
                                    cand.append((fcx, 0.0))
                                    all_detected_cx.append(fcx)
                                active_cx = speaker_tracker.update(t_rel, cand)
                                if active_cx is not None:
                                    last_center = active_cx
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

    # Detect if scene is multi-speaker podcast (>= 2 distinct face clusters)
    anchors = cluster_face_anchors(all_detected_cx, min_dist=250.0)
    is_multi_speaker = len(anchors) >= 2 or len(speaker_tracker.anchor_points) >= 2
    if is_multi_speaker and not anchors:
        anchors = sorted(speaker_tracker.anchor_points.values())

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
            faces = c["faces"] if c["faces"] else [default_center]
            dur_sc = max(0.01, s_end - s_start)

            if is_multi_speaker and len(anchors) >= 2:
                # Shot-Locking Switcher: Snap to discrete anchor points, Hard Cut transitions (no panning)
                discrete_faces = []
                for fx in faces:
                    best_a = min(anchors, key=lambda a: abs(fx - a))
                    discrete_faces.append(best_a)

                crop_positions = [float(calculate_crop_box(width, height, a)[0]) for a in discrete_faces]
                dt = dur_sc / max(1, len(crop_positions) - 1)
                timestamps = [k * dt for k in range(len(crop_positions))]
                crop_expr = build_dynamic_crop_expression(
                    crop_positions, timestamps, max_x=max_crop_x, discrete=True, visual_cuts=visual_cuts
                )
            else:
                # Single speaker: smooth EMA continuous tracking
                smoothed = smooth_ema_series(faces, alpha=0.1)
                crop_positions = [float(calculate_crop_box(width, height, fx)[0]) for fx in smoothed]
                dt = dur_sc / max(1, len(crop_positions) - 1)
                timestamps = [k * dt for k in range(len(crop_positions))]
                crop_expr = build_dynamic_crop_expression(
                    crop_positions, timestamps, max_x=max_crop_x, discrete=False
                )

            scenes.append(
                SceneSegment(
                    start_time=s_start,
                    end_time=s_end,
                    mode="CROP_TRACKING",
                    crop_x=crop_expr
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

    # Return default centers list for compatibility with older callers
    centers = [960.0]
    return centers, strategy
