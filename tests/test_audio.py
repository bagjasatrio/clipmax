import subprocess
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
from clipmax.audio import extract_audio

def test_extract_audio_command_construction(tmp_path):
    video_path = tmp_path / "sample.mp4"
    video_path.touch()
    out_wav = tmp_path / "audio.wav"

    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (b"", b"")
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        result = extract_audio(str(video_path), str(out_wav))
        assert result == str(out_wav.resolve())
        
        args = mock_popen.call_args[0][0]
        assert "-vn" in args
        assert "-acodec" in args
        assert "pcm_s16le" in args
        assert "-ar" in args
        assert "16000" in args
        assert "-ac" in args
        assert "1" in args

def test_extract_audio_file_not_found():
    with pytest.raises(FileNotFoundError):
        extract_audio("nonexistent_video.mp4", "out.wav")
