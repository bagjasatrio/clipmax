import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from clipmax.downloader import (
    download_video,
    is_valid_video_url,
    auto_update_ytdlp,
    get_ydl_options,
    find_manual_cookie_file
)

def test_download_video_invalid_url():
    with pytest.raises(ValueError, match="Invalid URL"):
        download_video("ftp://not-a-valid-url.com", "temp/downloads")

def test_auto_update_ytdlp():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        assert auto_update_ytdlp() is True

def test_get_ydl_options_structure():
    opts = get_ydl_options("temp/out.mp4")
    assert "format" in opts
    assert "outtmpl" in opts
    assert "cookiesfrombrowser" not in opts
    assert opts["extractor_args"]["youtube"]["player_client"] == ["android", "ios"]
    assert "com.google.android.youtube" in opts["http_headers"]["User-Agent"]

def test_find_manual_cookie_file(tmp_path):
    cookie_txt = tmp_path / "cookies.txt"
    cookie_txt.write_text("# Netscape HTTP Cookie File\n")
    with patch("clipmax.downloader.Path.home", return_value=tmp_path):
        found = find_manual_cookie_file()
        assert found is not None
        assert "cookies.txt" in found

def test_download_video_mobile_client_success(tmp_path):
    fake_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    out_dir = tmp_path / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)
    simulated_file = out_dir / "yt_download_dQw4w9WgXcQ.mp4"
    simulated_file.touch()

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls, patch("clipmax.downloader.auto_update_ytdlp"):
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = {
            "id": "dQw4w9WgXcQ",
            "ext": "mp4"
        }
        mock_ydl.prepare_filename.return_value = str(simulated_file)
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

        result = download_video(fake_url, str(out_dir))
        assert Path(result).exists()
        assert "dQw4w9WgXcQ" in result

def test_download_video_failure_includes_tips(tmp_path):
    fake_url = "https://www.youtube.com/watch?v=invalid_id"
    out_dir = tmp_path / "downloads"

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls, patch("clipmax.downloader.auto_update_ytdlp"):
        mock_ydl_cls.return_value.__enter__.side_effect = RuntimeError("Sign in to confirm you're not a bot")
        with pytest.raises(RuntimeError) as excinfo:
            download_video(fake_url, str(out_dir))
        assert "YouTube meminta verifikasi bot" in str(excinfo.value)
        assert "Import cookies.txt" in str(excinfo.value)

def test_download_video_with_active_cookie(tmp_path):
    fake_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    out_dir = tmp_path / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)
    simulated_file = out_dir / "yt_download_dQw4w9WgXcQ.mp4"
    simulated_file.touch()

    cookie_file = tmp_path / "my_cookies.txt"
    cookie_file.write_text("# Netscape HTTP Cookie File\n")

    captured_opts = []

    def fake_ydl_init(opts):
        captured_opts.append(opts)
        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value = mock_ydl
        mock_ydl.__exit__.return_value = False
        mock_ydl.extract_info.return_value = {"id": "dQw4w9WgXcQ", "ext": "mp4"}
        mock_ydl.prepare_filename.return_value = str(simulated_file)
        return mock_ydl

    with patch("yt_dlp.YoutubeDL", side_effect=fake_ydl_init), patch("clipmax.downloader.auto_update_ytdlp"):
        result = download_video(fake_url, str(out_dir), cookie_file=str(cookie_file))
        assert Path(result).exists()
        assert any(opt.get("cookiefile") == str(cookie_file) for opt in captured_opts)
