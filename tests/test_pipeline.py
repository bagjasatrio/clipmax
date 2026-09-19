import pytest
import threading
from unittest.mock import patch, MagicMock
from clipmax.pipeline import PipelineOrchestrator, PipelineStatus, ClipResult, generate_thumbnail
from clipmax.config import AppConfig

def test_pipeline_status_enum():
    assert PipelineStatus.IDLE.value == "IDLE"
    assert PipelineStatus.DOWNLOADING.value == "DOWNLOADING"
    assert PipelineStatus.EXTRACTING_AUDIO.value == "EXTRACTING_AUDIO"
    assert PipelineStatus.TRANSCRIBING.value == "TRANSCRIBING"
    assert PipelineStatus.AI_EVALUATING.value == "AI_EVALUATING"
    assert PipelineStatus.TRACKING_FACES.value == "TRACKING_FACES"
    assert PipelineStatus.RENDERING.value == "RENDERING"
    assert PipelineStatus.COMPLETED.value == "COMPLETED"
    assert PipelineStatus.CANCELLED.value == "CANCELLED"

def test_pipeline_cancellation_token():
    cfg = AppConfig()
    orchestrator = PipelineOrchestrator(cfg)
    assert not orchestrator.cancel_requested.is_set()
    orchestrator.cancel()
    assert orchestrator.cancel_requested.is_set()

def test_generate_thumbnail_command(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.touch()
    thumb = tmp_path / "thumb.jpg"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        res = generate_thumbnail(str(clip), str(thumb))
        assert res == str(thumb.resolve())
        args = mock_run.call_args[0][0]
        assert "-ss" in args
        assert "-vframes" in args
        assert "1" in args
