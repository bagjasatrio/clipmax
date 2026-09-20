import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from clipmax.downloader import (
    download_video,
    is_valid_video_url,
    auto_update_ytdlp,
    get_ydl_options,
    clean_error_message,
    is_youtube_oauth_authenticated,
    initiate_youtube_oauth,
    poll_youtube_oauth_token
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
    assert opts["format"] == "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    assert opts["outtmpl"] == "temp/out.mp4"
    assert opts["username"] == "oauth2"
    assert opts["password"] == ""
    assert opts["nocheckcertificate"] is True
    assert opts["no_warnings"] is False
    assert opts["quiet"] is False

def test_clean_error_message():
    raw = "\x1b[0;31mERROR:\x1b[0m []0;31mERROR:[]0m [youtube] UCCZ-F2bidU: This video is unavailable."
    cleaned = clean_error_message(raw)
    assert "[]0;31m" not in cleaned
    assert "\x1b" not in cleaned
    assert "This video is unavailable." in cleaned

def test_is_youtube_oauth_authenticated():
    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_ydl = MagicMock()
        mock_ydl.cache.load.return_value = {"access_token": "valid_token"}
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        assert is_youtube_oauth_authenticated() is True

        mock_ydl.cache.load.return_value = None
        assert is_youtube_oauth_authenticated() is False

def test_initiate_youtube_oauth():
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "verification_url": "https://www.google.com/device",
            "user_code": "ABC-DEF-GHI",
            "device_code": "dev123"
        }
        data = initiate_youtube_oauth()
        assert data["verification_url"] == "https://www.google.com/device"
        assert data["user_code"] == "ABC-DEF-GHI"

def test_poll_youtube_oauth_token_success():
    with patch("requests.post") as mock_post, patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

        mock_post.return_value.json.return_value = {
            "access_token": "my_access_token",
            "expires_in": 3600,
            "refresh_token": "my_refresh_token"
        }
        res = poll_youtube_oauth_token("dev123")
        assert res["status"] == "success"
        mock_ydl.cache.store.assert_called_once()

def test_poll_youtube_oauth_token_pending():
    with patch("requests.post") as mock_post:
        mock_post.return_value.json.return_value = {
            "error": "authorization_pending"
        }
        res = poll_youtube_oauth_token("dev123")
        assert res["status"] == "pending"

def test_download_video_oauth2_success(tmp_path):
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

def test_download_video_failure_clean_error(tmp_path):
    fake_url = "https://www.youtube.com/watch?v=invalid_id"
    out_dir = tmp_path / "downloads"

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls, patch("clipmax.downloader.auto_update_ytdlp"):
        mock_ydl_cls.return_value.__enter__.side_effect = RuntimeError("\x1b[0;31mERROR:\x1b[0m Video unavailable")
        with pytest.raises(RuntimeError) as excinfo:
            download_video(fake_url, str(out_dir))
        assert "Video unavailable" in str(excinfo.value)
        # Verify no mention of cookies
        assert "cookies" not in str(excinfo.value).lower()
