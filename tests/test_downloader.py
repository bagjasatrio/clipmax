import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from clipmax.downloader import (
    download_video,
    is_valid_video_url,
    auto_update_ytdlp,
    get_ydl_options,
    clean_error_message,
    extract_video_id,
    download_via_invidious
)

def test_download_video_invalid_url():
    with pytest.raises(ValueError, match="Invalid URL"):
        download_video("ftp://not-a-valid-url.com", "temp/downloads")

def test_auto_update_ytdlp():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        assert auto_update_ytdlp() is True

def test_extract_video_id():
    assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("https://invalid-url.com") is None

def test_get_ydl_options_structure():
    opts = get_ydl_options("temp/out.mp4")
    assert "bestvideo" in opts["format"]
    assert "bestaudio" in opts["format"]
    assert opts["outtmpl"] == "temp/out.mp4"
    assert opts["nocheckcertificate"] is True
    assert opts["no_warnings"] is True
    assert opts["quiet"] is False
    assert "tv_embedded" in opts["extractor_args"]["youtube"]["player_client"]

def test_clean_error_message():
    raw = "\x1b[0;31mERROR:\x1b[0m []0;31mERROR:[]0m [youtube] UCCZ-F2bidU: This video is unavailable."
    cleaned = clean_error_message(raw)
    assert "[]0;31m" not in cleaned
    assert "\x1b" not in cleaned
    assert "This video is unavailable." in cleaned

def test_download_via_invidious_success(tmp_path):
    out_file = tmp_path / "invidious_out.mp4"

    mock_resp_meta = MagicMock()
    mock_resp_meta.status_code = 200
    mock_resp_meta.json.return_value = {
        "formatStreams": [
            {"qualityLabel": "360p", "url": "https://stream.example/360.mp4"},
            {"qualityLabel": "720p", "url": "https://stream.example/720.mp4"}
        ]
    }

    mock_resp_stream = MagicMock()
    mock_resp_stream.status_code = 200
    mock_resp_stream.headers = {"content-length": "1024"}
    mock_resp_stream.iter_content.return_value = [b"video_content_chunk"]
    mock_resp_stream.__enter__.return_value = mock_resp_stream
    mock_resp_stream.__exit__.return_value = False

    def fake_get(url, **kwargs):
        if "api/v1/videos" in url:
            return mock_resp_meta
        return mock_resp_stream

    with patch("requests.get", side_effect=fake_get):
        ok = download_via_invidious("https://www.youtube.com/watch?v=dQw4w9WgXcQ", str(out_file))
        assert ok is True
        assert out_file.exists()
        assert out_file.read_bytes() == b"video_content_chunk"

def test_download_via_invidious_failure():
    with patch("requests.get", side_effect=RuntimeError("Connection refused")):
        ok = download_via_invidious("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dummy.mp4")
        assert ok is False

def test_download_video_invidious_primary_success(tmp_path):
    fake_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    out_dir = tmp_path / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)

    def fake_invidious(youtube_url, output_path, **kwargs):
        p = Path(output_path)
        p.write_bytes(b"x" * 2000)
        return True

    with patch("clipmax.downloader.download_via_invidious", side_effect=fake_invidious):
        res = download_video(fake_url, str(out_dir))
        assert Path(res).exists()
        assert "dQw4w9WgXcQ" in res

def test_download_video_ytdlp_fallback(tmp_path):
    fake_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    out_dir = tmp_path / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)
    simulated_file = out_dir / "yt_download_dQw4w9WgXcQ.mp4"
    simulated_file.touch()

    with patch("clipmax.downloader.download_via_invidious", return_value=False), \
         patch("yt_dlp.YoutubeDL") as mock_ydl_cls, \
         patch("clipmax.downloader.auto_update_ytdlp"):
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

    with patch("clipmax.downloader.download_via_invidious", return_value=False), \
         patch("yt_dlp.YoutubeDL") as mock_ydl_cls, \
         patch("clipmax.downloader.auto_update_ytdlp"):
        mock_ydl_cls.return_value.__enter__.side_effect = RuntimeError("\x1b[0;31mERROR:\x1b[0m Video unavailable")
        with pytest.raises(RuntimeError) as excinfo:
            download_video(fake_url, str(out_dir))
        assert "Video unavailable" in str(excinfo.value)
        assert "cookies" not in str(excinfo.value).lower()

def test_probe_youtube_audio_tracks_mocked():
    from clipmax.downloader import probe_youtube_audio_tracks
    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = {
            "formats": [
                {"vcodec": "avc1", "acodec": "none", "height": 1080},
                {"vcodec": "none", "acodec": "opus", "language": "en", "format_note": "English - original (default)"},
                {"vcodec": "none", "acodec": "opus", "language": "id", "format_note": "Indonesia - dubbed"},
                {"vcodec": "none", "acodec": "opus", "language": "es", "format_note": "Español - dubbed"},
            ]
        }
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

        tracks = probe_youtube_audio_tracks("https://www.youtube.com/watch?v=kX3nB4PpJko")
        assert len(tracks) == 3
        # Original should be first
        assert tracks[0]["code"] == "en"
        assert tracks[0]["is_original"] is True
        assert "Original" in tracks[0]["label"]

        # Indonesian dubbed track
        assert tracks[1]["code"] == "id"
        assert "Indonesia" in tracks[1]["label"]
        assert "Dubbed" in tracks[1]["label"]

def test_get_ydl_options_with_audio_lang():
    from clipmax.downloader import get_ydl_options
    opts_id = get_ydl_options("out.mp4", audio_lang="id")
    assert "bestaudio[language=id]" in opts_id["format"]
    # Multi-track dubbing must not use tv_embedded extractor or PS4 headers
    assert "extractor_args" not in opts_id
    assert "http_headers" not in opts_id

    opts_default = get_ydl_options("out.mp4", audio_lang="default")
    assert "bestaudio[ext=m4a]" in opts_default["format"]
    assert "tv_embedded" in opts_default["extractor_args"]["youtube"]["player_client"]


