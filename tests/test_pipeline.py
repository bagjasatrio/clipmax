import pytest
import threading
from unittest.mock import patch, MagicMock
from clipmax.pipeline import PipelineOrchestrator, PipelineStatus
from clipmax.config import AppConfig

def test_pipeline_status_enum():
    assert PipelineStatus.IDLE.value == "IDLE"
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
