import pytest
from unittest.mock import patch, MagicMock
from clipmax.transcriber import transcribe_audio, cleanup_vram, WordSegment

def test_transcribe_audio_mocked(tmp_path):
    wav_file = tmp_path / "fake.wav"
    wav_file.touch()

    mock_word = MagicMock()
    mock_word.word = "Halo"
    mock_word.start = 0.0
    mock_word.end = 0.5
    mock_word.probability = 0.95

    mock_segment = MagicMock()
    mock_segment.words = [mock_word]
    mock_segment.text = "Halo"

    with patch("faster_whisper.WhisperModel") as mock_model_cls, \
         patch("clipmax.transcriber.cleanup_vram") as mock_gc:

        instance = MagicMock()
        instance.transcribe.return_value = ([mock_segment], MagicMock())
        mock_model_cls.return_value = instance

        words, full_text = transcribe_audio(str(wav_file), model_size="small", device="cpu", compute_type="int8")

        assert len(words) == 1
        assert words[0].word == "Halo"
        assert words[0].start == 0.0
        assert full_text.strip() == "Halo"
        assert mock_gc.called

def test_transcribe_audio_cuda_fallback_on_dll_error(tmp_path):
    wav_file = tmp_path / "fake_cuda.wav"
    wav_file.touch()

    mock_word = MagicMock()
    mock_word.word = "Fallback"
    mock_word.start = 1.0
    mock_word.end = 1.5
    mock_word.probability = 0.98

    mock_segment = MagicMock()
    mock_segment.words = [mock_word]
    mock_segment.text = "Fallback"

    cuda_error = RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")
    cpu_instance = MagicMock()
    cpu_instance.transcribe.return_value = ([mock_segment], MagicMock())

    def side_effect(*args, **kwargs):
        if kwargs.get("device") == "cuda" or (len(args) > 1 and args[1] == "cuda"):
            raise cuda_error
        return cpu_instance

    with patch("faster_whisper.WhisperModel", side_effect=side_effect) as mock_model_cls, \
         patch("clipmax.transcriber.cleanup_vram") as mock_gc:

        words, full_text = transcribe_audio(str(wav_file), model_size="small", device="cuda", compute_type="float16")

        assert len(words) == 1
        assert words[0].word == "Fallback"
        assert full_text.strip() == "Fallback"
        # Verify it was called twice: first with cuda (failed), second with cpu
        assert mock_model_cls.call_count == 2
        second_call = mock_model_cls.call_args_list[1]
        assert second_call.kwargs.get("device") == "cpu"
        assert second_call.kwargs.get("compute_type") == "int8"
