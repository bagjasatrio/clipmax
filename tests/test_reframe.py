import pytest
import numpy as np
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
    determine_segment_layout
)

def test_determine_segment_layout_rules():
    # User's exact signature with list of detected face dicts:
    # KASUS A: Layar / Slide / B-Roll (0 wajah sama sekali) -> BLURRED_BACKGROUND
    assert determine_segment_layout([[] for _ in range(5)]) == "BLURRED_BACKGROUND"

    # KASUS B: Multi-orang (>= 2 wajah) -> BLURRED_BACKGROUND
    assert determine_segment_layout([[{"x_center": 0.25}, {"x_center": 0.75}]] * 5) == "BLURRED_BACKGROUND"

    # KASUS C1: 1 Wajah di tengah (0.35 <= avg_x <= 0.65) -> CROP_9_16 (WAJIB FULL CROP 9:16)
    assert determine_segment_layout([[{"x_center": 0.50}]] * 5) == "CROP_9_16"
    assert determine_segment_layout([[{"x_center": 0.40}]] * 5) == "CROP_9_16"
    assert determine_segment_layout([[{"x_center": 0.60}]] * 5) == "CROP_9_16"

    # KASUS C2: 1 Wajah di pinggir (indikasi wide podcast 2 orang) -> BLURRED_BACKGROUND
    assert determine_segment_layout([[{"x_center": 0.20}]] * 5) == "BLURRED_BACKGROUND"
    assert determine_segment_layout([[{"x_center": 0.80}]] * 5) == "BLURRED_BACKGROUND"

    # Backward-compatible tuple inputs:
    frames_multi = [(1, 450.0)] * 10 + [(2, 450.0)] * 2
    assert determine_segment_layout(frames_multi) == "BLURRED_BACKGROUND"

    frames_zero = [(0, None)] * 15
    assert determine_segment_layout(frames_zero) == "BLURRED_BACKGROUND"

    frames_left_edge = [(1, 450.0)] * 20
    assert determine_segment_layout(frames_left_edge, frame_width=1920) == "BLURRED_BACKGROUND"

    frames_centered = [(1, 960.0)] * 20
    assert determine_segment_layout(frames_centered, frame_width=1920) == "CROP_9_16"

def test_fixed_scene_crop_median_calculation():
    detected_faces = [940.0, 960.0, 950.0, 980.0, 955.0]
    median_val = float(np.median(detected_faces))
    crop_x, crop_w, crop_h = calculate_crop_box(1920, 1080, median_val)
    assert crop_x == int(round(median_val - crop_w / 2.0))
    assert str(crop_x).isdigit()

def test_aggregated_face_voting_podcast_partial_turn():
    # User's podcast case:
    # 0s - 15s: 1 person detected (partner turned head 90 deg)
    # 15s - 30s: 2 people detected
    # Aggregated face voting MUST lock the ENTIRE 30-second scene to BLURRED_BACKGROUND
    samples = [(i * 0.2, 1, 450.0) for i in range(75)] + [(15.0 + i * 0.2, 2, 450.0) for i in range(75)]
    segments = merge_scene_intervals(samples, min_scene_sec=2.0, clip_duration=30.0)
    assert len(segments) == 1
    assert segments[0]["mode"] == "BLURRED_BACKGROUND"
    assert segments[0]["start"] == 0.0
    assert segments[0]["end"] == 30.0

def test_asymmetric_edge_anchor_blurred_bg():
    samples_left = [(i * 0.2, 1, 450.0) for i in range(50)]
    seg_left = merge_scene_intervals(samples_left, min_scene_sec=2.0, clip_duration=10.0, frame_width=1920)
    assert len(seg_left) == 1
    assert seg_left[0]["mode"] == "BLURRED_BACKGROUND"

    samples_right = [(i * 0.2, 1, 1500.0) for i in range(50)]
    seg_right = merge_scene_intervals(samples_right, min_scene_sec=2.0, clip_duration=10.0, frame_width=1920)
    assert len(seg_right) == 1
    assert seg_right[0]["mode"] == "BLURRED_BACKGROUND"

def test_face_count_rule_single_face_centered_crop_916():
    samples = [(i * 0.2, 1, 960.0 + (i % 3) * 5) for i in range(50)]
    segments = merge_scene_intervals(samples, min_scene_sec=2.0, clip_duration=10.0, frame_width=1920)
    assert len(segments) == 1
    assert segments[0]["mode"] == "CROP_TRACKING"
    assert segments[0]["start"] == 0.0
    assert segments[0]["end"] == 10.0

def test_face_count_rule_multi_person_blurred_bg():
    samples = [(i * 0.2, 2, 500.0) for i in range(50)]
    segments = merge_scene_intervals(samples, min_scene_sec=2.0, clip_duration=10.0)
    assert len(segments) == 1
    assert segments[0]["mode"] == "BLURRED_BACKGROUND"
    assert segments[0]["start"] == 0.0
    assert segments[0]["end"] == 10.0

def test_face_count_rule_zero_face_blurred_bg():
    samples = [(i * 0.2, 0, None) for i in range(50)]
    segments = merge_scene_intervals(samples, min_scene_sec=2.0, clip_duration=10.0)
    assert len(segments) == 1
    assert segments[0]["mode"] == "BLURRED_BACKGROUND"
    assert segments[0]["start"] == 0.0
    assert segments[0]["end"] == 10.0

def test_face_count_rule_mixed_timeline():
    samples = (
        [(i * 0.2, 1, 960.0) for i in range(30)] +
        [(6.0 + i * 0.2, 2, 800.0) for i in range(30)] +
        [(12.0 + i * 0.2, 0, None) for i in range(20)] +
        [(16.0 + i * 0.2, 1, 960.0) for i in range(20)]
    )
    segments = merge_scene_intervals(samples, min_scene_sec=2.0, clip_duration=20.0, padding_sec=0.0, frame_width=1920)
    assert len(segments) == 3
    assert segments[0]["mode"] == "CROP_TRACKING"
    assert segments[0]["start"] == 0.0
    assert segments[0]["end"] == 6.0

    assert segments[1]["mode"] == "BLURRED_BACKGROUND"
    assert segments[1]["start"] == 6.0
    assert segments[1]["end"] == 16.0

    assert segments[2]["mode"] == "CROP_TRACKING"
    assert segments[2]["start"] == 16.0
    assert segments[2]["end"] == 20.0

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
    points = [650.0, 650.0, 650.0]
    times = [0.0, 1.0, 2.0]
    expr = build_dynamic_crop_expression(points, times)
    assert expr == "650"

def test_build_dynamic_crop_expression_discrete():
    vals = [146.0, 146.0, 1176.0, 1176.0]
    times = [0.0, 1.0, 3.0, 4.0]
    cuts = [2.9]
    expr = build_dynamic_crop_expression(vals, times, discrete=True, visual_cuts=cuts)
    assert "if(lt(t,2.90),146,1176)" in expr

def test_merge_scene_intervals_anti_micro_cut():
    samples = []
    for s in range(21):
        if s == 10:
            samples.append((float(s), False, 960.0))
        else:
            samples.append((float(s), True, 960.0))

    segments = merge_scene_intervals(samples, min_scene_sec=1.8, clip_duration=20.0, padding_sec=0.0)
    assert len(segments) == 1
    assert segments[0]["mode"] == "CROP_TRACKING"
    assert segments[0]["start"] == 0.0
    assert segments[0]["end"] == 20.0

def test_merge_scene_intervals_visual_cut_snapping_and_padding():
    samples = []
    for s in range(31):
        if 0 <= s < 10 or 25 <= s <= 30:
            samples.append((float(s), True, 960.0))
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
    assert str(scenes[0].crop_x).isdigit()

def test_reframe_strategies_enum():
    assert ReframeStrategy.CROP_TRACKING.value == "CROP_TRACKING"
    assert ReframeStrategy.BLURRED_BACKGROUND.value == "BLURRED_BACKGROUND"

def test_face_validation_size_and_confidence_filter():
    # Icons / logos on slide with h_norm < 0.12 (8% screen height) or low confidence must be ignored
    slide_icons = [[{"x_center": 0.50, "h_norm": 0.08, "score": 0.90}]] * 10
    assert determine_segment_layout(slide_icons) == "BLURRED_BACKGROUND"

    low_conf = [[{"x_center": 0.50, "h_norm": 0.20, "score": 0.40}]] * 10
    assert determine_segment_layout(low_conf) == "BLURRED_BACKGROUND"

    # Valid solo face with h_norm >= 0.12 and score >= 0.55
    valid_solo = [[{"x_center": 0.50, "h_norm": 0.20, "score": 0.85}]] * 10
    assert determine_segment_layout(valid_solo) == "CROP_9_16"

def test_robust_scene_ratio_voting_slide():
    # When faces are only detected in 2 out of 10 sampled frames (face_ratio = 0.20 < 0.35)
    # the system recognizes it as a slide / screen share and locks to BLURRED_BACKGROUND
    sparse_faces = (
        [[{"x_center": 0.50, "h_norm": 0.20, "score": 0.80}]] * 2 +
        [[]] * 8
    )
    assert determine_segment_layout(sparse_faces) == "BLURRED_BACKGROUND"

def test_detect_visual_shots_py_scenedetect():
    from clipmax.reframe import detect_visual_shots
    # Test with non-existent or synthetic video
    shots = detect_visual_shots("non_existent.mp4", 0.0, 10.0)
    assert len(shots) == 1
    assert shots[0] == (0.0, 10.0)
