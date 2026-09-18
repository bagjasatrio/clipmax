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
