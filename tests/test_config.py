import pytest
from clipmax.config import sanitize_ffmpeg_path, parse_to_seconds, AppConfig, get_ffmpeg_bin

def test_sanitize_ffmpeg_path_windows():
    raw = r"C:\project\clipmax\output\sub.ass"
    sanitized = sanitize_ffmpeg_path(raw)
    assert sanitized == "C\\:/project/clipmax/output/sub.ass"

def test_sanitize_ffmpeg_path_relative():
    raw = r"output\sub.ass"
    assert sanitize_ffmpeg_path(raw) == "output/sub.ass"

def test_parse_to_seconds_float_int():
    assert parse_to_seconds(45.5) == 45.5
    assert parse_to_seconds(60) == 60.0

def test_parse_to_seconds_mmss():
    assert parse_to_seconds("01:23") == 83.0
    assert parse_to_seconds("00:30") == 30.0

def test_parse_to_seconds_hhmmss():
    assert parse_to_seconds("01:02:03") == 3723.0
    assert parse_to_seconds("00:01:30.500") == 90.5

def test_parse_to_seconds_invalid():
    assert parse_to_seconds("invalid") == 0.0
    assert parse_to_seconds(None) == 0.0

def test_default_app_config():
    cfg = AppConfig()
    assert cfg.whisper_model == "small"
    assert cfg.device in ["cuda", "cpu"]
    assert cfg.endpoint_url == "http://localhost:20128/v1"

def test_clear_temp_cache(tmp_path):
    from clipmax.config import clear_temp_cache
    temp_dir = tmp_path / "temp_cache"
    temp_dir.mkdir(parents=True)
    (temp_dir / "temp_part_1.mp4").write_text("dummy")
    (temp_dir / "audio.wav").write_text("dummy")
    sub_folder = temp_dir / "old_subfolder"
    sub_folder.mkdir()
    (sub_folder / "file.txt").write_text("dummy")

    assert (temp_dir / "temp_part_1.mp4").exists()
    assert sub_folder.exists()

    removed = clear_temp_cache(str(temp_dir))
    assert removed >= 2
    assert not (temp_dir / "temp_part_1.mp4").exists()
    assert not sub_folder.exists()
    assert (temp_dir / "staging").exists()
    assert (temp_dir / "downloads").exists()

