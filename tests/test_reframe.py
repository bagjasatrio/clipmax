import pytest
from unittest.mock import patch, MagicMock
from clipmax.reframe import calculate_crop_box, smooth_ema_series, ReframeStrategy, detect_face_centers

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
    smoothed = smooth_ema_series(raw_series, alpha=0.15)
    assert len(smoothed) == len(raw_series)
    assert smoothed[0] == 100.0
    assert smoothed[2] < 500.0

def test_detect_face_centers_file_not_found():
    centers, strategy = detect_face_centers("non_existent_video.mp4", 0.0, 5.0)
    assert centers == []
    assert strategy == ReframeStrategy.BLURRED_BACKGROUND

def test_reframe_strategies_enum():
    assert ReframeStrategy.CROP_TRACKING.value == "CROP_TRACKING"
    assert ReframeStrategy.BLURRED_BACKGROUND.value == "BLURRED_BACKGROUND"
