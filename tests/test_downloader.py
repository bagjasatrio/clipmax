import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from clipmax.downloader import download_video, is_valid_video_url, auto_update_ytdlp

def test_download_video_invalid_url():
    with pytest.raises(ValueError, match="Invalid URL"):
        download_video("ftp://not-a-valid-url.com", "temp/downloads")

def test_auto_update_ytdlp():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        assert auto_update_ytdlp() is True

def test_download_video_browser_cookie_and_fallback(tmp_path):
    fake_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    out_dir = tmp_path / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)
    simulated_file = out_dir / "yt_download_dQw4w9WgXcQ.mp4"
    simulated_file.touch()

    # Simulate: first 2 attempts (browser cookies) throw "Database locked" / DPAPI error,
    # then 3rd attempt (Android/Web client fallback) succeeds
    call_count = [0]

    def fake_ydl_enter(self):
        call_count[0] += 1
        if call_count[0] <= 2:
            raise RuntimeError("Database locked by running browser")
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = {
            "id": "dQw4w9WgXcQ",
            "ext": "mp4"
        }
        mock_ydl.prepare_filename.return_value = str(simulated_file)
        return mock_ydl

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls, patch("clipmax.downloader.auto_update_ytdlp"):
        mock_ydl_cls.return_value.__enter__ = fake_ydl_enter
        mock_ydl_cls.return_value.__exit__ = MagicMock()

        result = download_video(fake_url, str(out_dir))
        assert Path(result).exists()
        assert "dQw4w9WgXcQ" in result
        assert call_count[0] >= 3
