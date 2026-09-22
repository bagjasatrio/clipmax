import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from clipmax.web.server import app, state
from clipmax.pipeline import ClipResult

client = TestClient(app)

def test_api_system():
    res = client.get("/api/system")
    assert res.status_code == 200
    data = res.json()
    assert "cuda_available" in data
    assert "device_name" in data
    assert "whisper_model" in data

def test_api_config():
    res = client.get("/api/config")
    assert res.status_code == 200
    data = res.json()
    assert "endpoint_url" in data
    assert "target_clip_count" in data
    assert data.get("engine") == "invidious_api"

def test_api_config_update():
    res = client.post("/api/config", json={
        "target_clip_count": 4,
        "clip_mode": "montage",
        "subtitle_base_color": "#EEEEEE",
        "subtitle_highlight_color": "#FFE81F",
        "subtitle_color_preset": "tiktok_yellow"
    })
    assert res.status_code == 200
    assert state.config.target_clip_count == 4
    assert state.config.clip_mode == "montage"
    assert state.config.subtitle_highlight_color == "#FFE81F"
    assert state.config.subtitle_color_preset == "tiktok_yellow"

def test_api_pipeline_status():
    res = client.get("/api/pipeline/status")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "progress" in data
    assert "message" in data

def test_api_models():
    res = client.get("/api/models")
    assert res.status_code == 200
    data = res.json()
    assert "models" in data
    assert isinstance(data["models"], list)

def test_api_cache_clear():
    res = client.post("/api/cache/clear")
    assert res.status_code == 200
    assert res.json().get("status") == "ok"
    assert "Cache cleared" in res.json().get("message")

def test_static_index_html():
    res = client.get("/")
    assert res.status_code == 200
    assert "ClipMax Studio" in res.text
    assert "Invidious API Stream" in res.text
    assert "cookies.txt" not in res.text
    assert "Multi-Cut Montage" in res.text
    assert "Reset &amp; Clear Cache" in res.text or "Reset & Clear Cache" in res.text
    assert "Subtitle Style" in res.text
    assert "inputHighlightColor" in res.text

def test_api_export_direct_download(tmp_path):
    clip_file = tmp_path / "clipmax_1_10.mp4"
    clip_file.write_text("dummy video content")

    dummy_clip = ClipResult(
        clip_id=1,
        title="Test Clip",
        hook="Awesome",
        virality_score=95,
        reasoning="Good",
        start_time=10.0,
        end_time=30.0,
        staging_path=str(clip_file)
    )
    state.clips = [dummy_clip]

    res = client.get("/api/export/1")
    assert res.status_code == 200
    assert res.headers["content-type"] == "video/mp4"
    assert "clipmax_1_10.mp4" in res.headers.get("content-disposition", "")

def test_export_single_clip_tuple_safety(tmp_path):
    source_file = tmp_path / "source.mp4"
    source_file.write_text("source content")
    dest_file = tmp_path / "saved.mp4"

    dummy_clip = ClipResult(
        clip_id=2,
        title="Clip 2",
        hook="Hook",
        virality_score=80,
        reasoning="Ok",
        start_time=0.0,
        end_time=10.0,
        staging_path=str(source_file)
    )
    state.clips = [dummy_clip]

    # Test with string path
    res = client.post("/api/clips/export-single", json={"clip_id": 2, "dest_path": str(dest_file)})
    assert res.status_code == 200
    assert dest_file.exists()

def test_desktop_js_api_tuple_handling(tmp_path):
    from desktop_app import DesktopJsApi
    source_file = tmp_path / "source_desktop.mp4"
    source_file.write_text("source desktop")
    dest_file = tmp_path / "saved_desktop.mp4"

    dummy_clip = ClipResult(
        clip_id=3,
        title="Clip 3",
        hook="Hook 3",
        virality_score=90,
        reasoning="Ok",
        start_time=0.0,
        end_time=15.0,
        staging_path=str(source_file)
    )
    state.clips = [dummy_clip]

    mock_window = MagicMock()
    # Mock create_file_dialog returning a tuple ('C:/path/file.mp4',) as pywebview does
    mock_window.create_file_dialog.return_value = (str(dest_file),)

    api = DesktopJsApi({"window": mock_window})
    saved = api.save_clip_dialog(3, "clipmax_3_0.mp4")

    assert saved == str(dest_file)
    assert dest_file.exists()

def test_api_clip_overlay_and_remove(tmp_path):
    clip_file = tmp_path / "clipmax_4_0.mp4"
    clip_file.write_text("dummy mp4 video bytes")

    dummy_clip = ClipResult(
        clip_id=4,
        title="Clip 4 Viral",
        hook="Hook 4",
        virality_score=95,
        reasoning="Ok",
        start_time=0.0,
        end_time=20.0,
        staging_path=str(clip_file)
    )
    state.clips = [dummy_clip]

    with patch("clipmax.web.server.apply_ass_overlay") as mock_apply:
        # Mock apply_ass_overlay creating the output video file
        def fake_apply(input_video, output_video, ass_path, use_gpu):
            Path(output_video).write_text("rendered mp4 with overlay")
            return output_video
        mock_apply.side_effect = fake_apply

        res = client.post("/api/clips/overlay", json={
            "clip_id": 4,
            "text": "TOP HEADLINE!",
            "font_name": "Impact",
            "text_color": "#FFE81F",
            "bg_color": "#000000",
            "has_bg": True,
            "position": "top"
        })

        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["clip_id"] == 4
        assert clip_file.read_text() == "rendered mp4 with overlay"

        # Check backup base file exists
        backup_file = tmp_path / "clipmax_4_0_base.mp4"
        assert backup_file.exists()
        assert backup_file.read_text() == "dummy mp4 video bytes"

        # Test remove overlay
        res_remove = client.post("/api/clips/remove-overlay", json={"clip_id": 4})
        assert res_remove.status_code == 200
        assert clip_file.read_text() == "dummy mp4 video bytes"


