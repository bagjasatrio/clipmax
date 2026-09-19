import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from clipmax.downloader import download_video

def test_download_video_invalid_url():
    with pytest.raises(ValueError, match="Invalid URL"):
        download_video("ftp://not-a-valid-url.com", "temp/downloads")

def test_download_video_mocked(tmp_path):
    fake_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    out_dir = tmp_path / "downloads"

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            "id": "dQw4w9WgXcQ",
            "ext": "mp4",
        }

        # Create the simulated downloaded file
        out_dir.mkdir(parents=True, exist_ok=True)
        simulated_file = out_dir / "yt_download_dQw4w9WgXcQ.mp4"
        simulated_file.touch()
        mock_ydl.prepare_filename.return_value = str(simulated_file)

        result = download_video(fake_url, str(out_dir))
        assert Path(result).exists()
        assert "dQw4w9WgXcQ" in result
