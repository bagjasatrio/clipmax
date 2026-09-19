import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from clipmax.config import AppConfig
from clipmax.pipeline import PipelineOrchestrator, PipelineStatus, ClipResult
from clipmax.transcriber import WordSegment
from clipmax.ai_gateway import ViralClipCandidate

def test_full_pipeline_local_mocked(tmp_path):
    video_file = tmp_path / "test_video.mp4"
    video_file.touch()

    cfg = AppConfig(
        output_dir=str(tmp_path / "out"),
        temp_dir=str(tmp_path / "tmp")
    )
    orchestrator = PipelineOrchestrator(cfg)

    with patch("clipmax.pipeline.extract_audio") as mock_audio, \
         patch("clipmax.pipeline.transcribe_audio") as mock_transcribe, \
         patch("clipmax.pipeline.evaluate_viral_clips") as mock_llm, \
         patch("clipmax.pipeline.detect_face_centers") as mock_face, \
         patch("clipmax.pipeline.generate_kinetic_ass") as mock_sub, \
         patch("clipmax.pipeline.render_clip") as mock_render, \
         patch("clipmax.pipeline.generate_thumbnail") as mock_thumb:

        mock_transcribe.return_value = (
            [WordSegment(word="Tes", start=0.0, end=1.0, probability=0.99)],
            "Transkrip lengkap tes"
        )
        mock_llm.return_value = [
            ViralClipCandidate(
                title="Klip Viral 1",
                hook="Hook mantap",
                start_time=10.0,
                end_time=40.0,
                virality_score=90,
                reasoning="Bagus"
            )
        ]
        mock_face.return_value = ([960.0, 960.0], "single_speaker")

        progress_records = []
        def on_prog(status, pct, msg):
            progress_records.append((status, pct))

        results = orchestrator.run(str(video_file), on_prog)

        assert mock_audio.called
        assert mock_transcribe.called
        assert mock_llm.called
        assert mock_face.called
        assert mock_sub.called
        assert mock_render.called
        assert mock_thumb.called
        assert orchestrator.status == PipelineStatus.COMPLETED
        assert any(pct == 100 for _, pct in progress_records)
        assert len(results) == 1
        assert isinstance(results[0], ClipResult)
        assert "staging" in results[0].staging_path

def test_full_pipeline_url_ingestion_mocked(tmp_path):
    url_input = "https://www.youtube.com/watch?v=sample123"
    cfg = AppConfig(
        output_dir=str(tmp_path / "out"),
        temp_dir=str(tmp_path / "tmp")
    )
    orchestrator = PipelineOrchestrator(cfg)

    downloaded_video = tmp_path / "downloaded.mp4"
    downloaded_video.touch()

    with patch("clipmax.pipeline.download_video", return_value=str(downloaded_video)) as mock_dl, \
         patch("clipmax.pipeline.extract_audio") as mock_audio, \
         patch("clipmax.pipeline.transcribe_audio") as mock_transcribe, \
         patch("clipmax.pipeline.evaluate_viral_clips") as mock_llm, \
         patch("clipmax.pipeline.detect_face_centers") as mock_face, \
         patch("clipmax.pipeline.generate_kinetic_ass") as mock_sub, \
         patch("clipmax.pipeline.render_clip") as mock_render, \
         patch("clipmax.pipeline.generate_thumbnail") as mock_thumb:

        mock_transcribe.return_value = (
            [WordSegment(word="Tes", start=0.0, end=1.0, probability=0.99)],
            "Transkrip dari url video"
        )
        mock_llm.return_value = [
            ViralClipCandidate(
                title="Klip URL Viral",
                hook="Hook dari URL",
                start_time=5.0,
                end_time=35.0,
                virality_score=92,
                reasoning="Viral content"
            )
        ]
        mock_face.return_value = ([960.0, 960.0], "single_speaker")

        progress_records = []
        def on_prog(status, pct, msg):
            progress_records.append((status, pct))

        results = orchestrator.run(url_input, on_prog)

        assert mock_dl.called
        assert mock_audio.called
        assert orchestrator.status == PipelineStatus.COMPLETED
        assert any(status == PipelineStatus.DOWNLOADING for status, _ in progress_records)
        assert len(results) == 1
        assert results[0].title == "Klip URL Viral"
