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

def test_pipeline_montage_mode_execution(tmp_path):
    from clipmax.ai_gateway import ViralClipCandidate, MontageCut
    from clipmax.transcriber import WordSegment
    from clipmax.reframe import SceneSegment

    cfg = AppConfig(temp_dir=str(tmp_path / "temp"), staging_dir=str(tmp_path / "staging"))
    orchestrator = PipelineOrchestrator(cfg)

    dummy_video = tmp_path / "input.mp4"
    dummy_video.touch()

    montage_candidate = ViralClipCandidate(
        title="Gaming Montage",
        hook="Epic play",
        start_time=10.0,
        end_time=50.0,
        virality_score=92,
        reasoning="Multi cut highlights",
        mode="montage",
        cuts=[
            MontageCut(start=10.0, end=25.0, event="First Blood"),
            MontageCut(start=35.0, end=50.0, event="Victory Push")
        ]
    )

    dummy_words = [
        WordSegment(word="First", start=11.0, end=11.5, probability=0.9),
        WordSegment(word="Blood", start=11.6, end=12.2, probability=0.9),
        WordSegment(word="Victory", start=36.0, end=36.8, probability=0.9),
    ]

    with patch("clipmax.pipeline.extract_audio") as mock_audio, \
         patch("clipmax.pipeline.transcribe_audio") as mock_transcribe, \
         patch("clipmax.pipeline.evaluate_viral_clips") as mock_eval, \
         patch("clipmax.pipeline.segment_clip_scenes") as mock_scenes, \
         patch("clipmax.pipeline.render_clip") as mock_render, \
         patch("clipmax.pipeline.generate_kinetic_ass") as mock_ass, \
         patch("clipmax.pipeline.generate_thumbnail") as mock_thumb, \
         patch("subprocess.run") as mock_subproc, \
         patch("shutil.copy2") as mock_copy:

        mock_audio.return_value = str(tmp_path / "temp" / "audio.wav")
        mock_transcribe.return_value = (dummy_words, "Full transcript")
        mock_eval.return_value = [montage_candidate]
        mock_scenes.return_value = [
            SceneSegment(start_time=10.0, end_time=25.0, mode="CROP_TRACKING", crop_x="500")
        ]
        mock_thumb.return_value = "thumb.jpg"
        mock_subproc.return_value = MagicMock(returncode=0)

        results = orchestrator.run(
            input_source=str(dummy_video),
            clip_mode="montage"
        )

        assert len(results) == 1
        res = results[0]
        assert res.title == "Gaming Montage"
        assert res.reframe_mode == "MONTAGE"
        assert res.virality_score == 92
        # Verify render_clip called once per cut (2 cuts = 2 calls)
        assert mock_render.call_count == 2
        # Verify generate_kinetic_ass called
        assert mock_ass.call_count == 1

def test_pipeline_audio_language_passed(tmp_path):
    from clipmax.ai_gateway import ViralClipCandidate
    from clipmax.transcriber import WordSegment, TranscriptionResult
    from clipmax.reframe import SceneSegment

    cfg = AppConfig(temp_dir=str(tmp_path / "temp"), staging_dir=str(tmp_path / "staging"))
    orchestrator = PipelineOrchestrator(cfg)

    dummy_video = tmp_path / "input.mp4"
    dummy_video.touch()

    candidate = ViralClipCandidate(
        title="Klip Bahasa Indonesia",
        hook="Hook menarik",
        start_time=0.0,
        end_time=15.0,
        virality_score=95,
        reasoning="Alasan viral",
        mode="single"
    )

    with patch("clipmax.pipeline.extract_audio"), \
         patch("clipmax.pipeline.transcribe_audio") as mock_transcribe, \
         patch("clipmax.pipeline.evaluate_viral_clips") as mock_eval, \
         patch("clipmax.pipeline.segment_clip_scenes") as mock_scenes, \
         patch("clipmax.pipeline.render_clip"), \
         patch("clipmax.pipeline.generate_kinetic_ass"), \
         patch("clipmax.pipeline.generate_thumbnail"), \
         patch("subprocess.run"):

        mock_transcribe.return_value = TranscriptionResult([], "Transkrip Indonesia", language="id")
        mock_eval.return_value = [candidate]
        mock_scenes.return_value = [SceneSegment(start_time=0.0, end_time=15.0, mode="BLURRED_BACKGROUND", crop_x="0")]

        orchestrator.run(
            input_source=str(dummy_video),
            audio_language="id"
        )

        # Ensure language was passed to transcribe_audio
        assert mock_transcribe.call_args.kwargs.get("language") == "id"
        # Ensure detected_language passed to evaluate_viral_clips is "id"
        assert mock_eval.call_args.kwargs.get("detected_language") == "id"

