import pytest
from unittest.mock import patch, MagicMock
from clipmax.reframe import (
    calculate_crop_box,
    smooth_ema_series,
    ReframeStrategy,
    detect_face_centers,
    build_dynamic_crop_expression,
    merge_scene_intervals,
    segment_clip_scenes,
    SceneSegment,
    ActiveSpeakerTracker,
    cluster_face_anchors,
    get_face_landmarker
)

def test_cluster_face_anchors():
    # 2 persons: left sitting at ~440-460, right sitting at ~1460-1490
    cxs = [440.0, 450.0, 460.0, 445.0, 455.0] * 10 + [1460.0, 1475.0, 1490.0, 1480.0] * 10
    anchors = cluster_face_anchors(cxs, min_dist=250.0)
    assert len(anchors) == 2
    assert abs(anchors[0] - 450.0) < 10.0
    assert abs(anchors[1] - 1476.0) < 15.0

def test_active_speaker_tracker_multi_face_hysteresis():
    tracker = ActiveSpeakerTracker(switch_threshold_sec=1.0, window_sec=1.0, min_hold_sec=2.5)
    # Person 1 (cx=400, left), Person 2 (cx=1500, right)

    # 0s to 3s: Person 1 speaking (MAR varying 0.15 - 0.45), Person 2 silent (MAR=0.15)
    for step in range(15):
        t = step * 0.2
        mar_p1 = 0.3 + 0.15 * (1 if step % 2 == 0 else -1)
        faces = [(400.0, mar_p1), (1500.0, 0.15)]
        cx = tracker.update(t, faces)
        assert cx == 400.0
    assert tracker.active_person_id == "person_0"

    # 3.0s to 3.4s: Person 2 smiles / reacts briefly (< 1.0s)
    for step in range(15, 18):
        t = step * 0.2
        faces = [(400.0, 0.15), (1500.0, 0.35)]
        cx = tracker.update(t, faces)
        # Hysteresis prevents switching
        assert cx == 400.0
    assert tracker.active_person_id == "person_0"

    # 3.4s to 5.0s: Person 2 speaks continuously for > 1.0s
    for step in range(18, 26):
        t = step * 0.2
        mar_p2 = 0.35 + 0.15 * (1 if step % 2 == 0 else -1)
        faces = [(400.0, 0.15), (1500.0, mar_p2)]
        cx = tracker.update(t, faces)

    # Now camera switched to Person 2
    assert tracker.active_person_id == "person_1"
    assert cx == 1500.0

def test_active_speaker_cooldown_locking():
    # Once locked to Person 0, camera CANNOT switch to Person 1 for at least 2.5s
    tracker = ActiveSpeakerTracker(min_hold_sec=2.5, switch_threshold_sec=0.8)
    for step in range(25):  # 0.0s to 5.0s in 0.2s steps
        t = step * 0.2
        # Person 0 active for 0.4s
        mar_0 = 0.35 if t < 0.4 else 0.15
        # Person 1 active starting at t=0.6s
        mar_1 = 0.15 if t < 0.6 else (0.35 + 0.15 * (1 if step % 2 == 0 else -1))
        cx = tracker.update(t, [(400.0, mar_0), (1500.0, mar_1)])
        if t < 2.5:
            # During the 2.5s cooldown period, camera MUST stay locked on Person 0
            assert cx == 400.0
        elif t >= 2.6:
            # Cooldown passed and Person 1 spoke consistently -> hard switch
            assert cx == 1500.0

def test_active_speaker_tracker_single_person():
    tracker = ActiveSpeakerTracker()
    cx = tracker.update(1.0, [(600.0, 0.25)])
    assert cx == 600.0

def test_calculate_crop_box_center():
    x_crop, crop_w, crop_h = calculate_crop_box(
        frame_width=1920,
        frame_height=1080,
        face_center_x=960
    )
    assert crop_h == 1080
    assert round(crop_w) == 608
    assert x_crop >= 0
    assert x_crop + crop_w <= 1920

def test_calculate_crop_box_boundary_clamping():
    x_crop, crop_w, _ = calculate_crop_box(
        frame_width=1920,
        frame_height=1080,
        face_center_x=50
    )
    assert x_crop == 0

    x_crop_right, crop_w, _ = calculate_crop_box(
        frame_width=1920,
        frame_height=1080,
        face_center_x=1900
    )
    assert x_crop_right + crop_w == 1920

def test_smooth_ema_series():
    raw_series = [100.0, 100.0, 500.0, 500.0]
    smoothed = smooth_ema_series(raw_series, alpha=0.1)
    assert len(smoothed) == len(raw_series)
    assert smoothed[0] == 100.0
    assert abs(smoothed[2] - 140.0) < 1.0

def test_build_dynamic_crop_expression_static():
    points = [650.0, 652.0, 651.0, 650.0]
    times = [0.0, 1.0, 2.0, 3.0]
    expr = build_dynamic_crop_expression(points, times)
    assert expr == "650"

def test_build_dynamic_crop_expression_moving():
    points = [200.0, 400.0, 800.0]
    times = [0.0, 1.0, 2.0]
    expr = build_dynamic_crop_expression(points, times)
    assert "if(lt(t,1.00)" in expr
    assert "if(lt(t,2.00)" in expr
    assert "max(0,min(1312" in expr

def test_build_dynamic_crop_expression_discrete_hard_cut():
    # Discrete multi-person switcher: must create a step function (Hard Cut), no linear pan
    vals = [146.0, 146.0, 146.0, 1176.0, 1176.0, 1176.0]
    times = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
    cuts = [2.9]
    expr = build_dynamic_crop_expression(vals, times, discrete=True, visual_cuts=cuts)
    # Snapped to cut at 2.90s
    assert "if(lt(t,2.90),146,1176)" in expr
    # No linear interpolator term
    assert "(t-" not in expr

def test_merge_scene_intervals_anti_micro_cut():
    samples = []
    for s in range(21):
        if s == 10:
            samples.append((float(s), False, 960.0))
        else:
            samples.append((float(s), True, 600.0))

    segments = merge_scene_intervals(samples, min_scene_sec=1.8, clip_duration=20.0, padding_sec=0.0)
    assert len(segments) == 1
    assert segments[0]["mode"] == "CROP_TRACKING"
    assert segments[0]["start"] == 0.0
    assert segments[0]["end"] == 20.0

def test_merge_scene_intervals_visual_cut_snapping_and_padding():
    samples = []
    for s in range(31):
        if 0 <= s < 10 or 25 <= s <= 30:
            samples.append((float(s), True, 600.0))
        else:
            samples.append((float(s), False, 960.0))

    visual_cuts = [9.8, 24.9]
    segments = merge_scene_intervals(
        samples,
        min_scene_sec=2.0,
        clip_duration=30.0,
        visual_cuts=visual_cuts,
        padding_sec=0.2
    )
    assert len(segments) == 3
    assert segments[0]["mode"] == "CROP_TRACKING"
    assert abs(segments[0]["end"] - 10.00) < 0.05
    assert segments[1]["mode"] == "BLURRED_BACKGROUND"
    assert abs(segments[1]["end"] - 24.70) < 0.05
    assert segments[2]["mode"] == "CROP_TRACKING"
    assert abs(segments[2]["start"] - 24.70) < 0.05
    assert segments[2]["end"] == 30.0

def test_segment_clip_scenes_file_not_found():
    scenes = segment_clip_scenes("non_existent_video.mp4", 0.0, 10.0)
    assert len(scenes) == 1
    assert scenes[0].mode == "BLURRED_BACKGROUND"
    assert scenes[0].end_time == 10.0

def test_detect_face_centers_file_not_found():
    centers, strategy = detect_face_centers("non_existent_video.mp4", 0.0, 5.0)
    assert centers == [960.0]
    assert strategy == ReframeStrategy.BLURRED_BACKGROUND

def test_segment_clip_scenes_execution_no_nameerror(tmp_path):
    import subprocess
    vid_file = tmp_path / "test_run.mp4"
    subprocess.run([
        "./bin/ffmpeg.exe", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=2:size=640x360:rate=30",
        "-c:v", "h264_nvenc", str(vid_file)
    ], capture_output=True)

    scenes = segment_clip_scenes(str(vid_file), 0.0, 2.0)
    assert len(scenes) >= 1
    assert scenes[0].mode in ("CROP_TRACKING", "BLURRED_BACKGROUND")

def test_reframe_strategies_enum():
    assert ReframeStrategy.CROP_TRACKING.value == "CROP_TRACKING"
    assert ReframeStrategy.BLURRED_BACKGROUND.value == "BLURRED_BACKGROUND"
