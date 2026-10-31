import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from clipmax.config import AppConfig
from clipmax.pipeline import ClipResult
from clipmax.uploader.youtube import upload_youtube_short
from clipmax.uploader.tiktok import upload_tiktok_video
from clipmax.uploader.service import SocialUploaderManager


def test_youtube_missing_video_file():
    res = upload_youtube_short(
        video_path="non_existent_clip.mp4",
        title="Test Shorts",
        client_secrets_path="secrets.json",
        interactive=False,
    )
    assert res["success"] is False
    assert "File video tidak ditemukan" in res["error"]


def test_youtube_missing_credentials():
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        temp_path = f.name

    try:
        res = upload_youtube_short(
            video_path=temp_path,
            title="Test Shorts",
            client_secrets_path="non_existent_secrets.json",
            token_path="non_existent_token.json",
            interactive=False,
        )
        assert res["success"] is False
        assert "client secrets tidak ditemukan" in res["error"].lower() or "permissionerror" in res["error"].lower()
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@patch("clipmax.uploader.youtube.get_youtube_service")
@patch("clipmax.uploader.youtube.MediaFileUpload")
def test_youtube_upload_success_mock(mock_media, mock_get_service):
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        temp_path = f.name

    try:
        mock_youtube = MagicMock()
        mock_request = MagicMock()
        mock_request.next_chunk.return_value = (None, {"id": "yt_video_123"})
        mock_youtube.videos().insert.return_value = mock_request
        mock_get_service.return_value = mock_youtube

        res = upload_youtube_short(
            video_path=temp_path,
            title="Klip Juara",
            description="Deskripsi klip viral",
            privacy_status="unlisted",
            interactive=False,
        )

        assert res["success"] is True
        assert res["video_id"] == "yt_video_123"
        assert "https://www.youtube.com/shorts/yt_video_123" in res["url"]
        assert res["privacy"] == "unlisted"
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_tiktok_missing_video_file():
    res = upload_tiktok_video(
        video_path="non_existent_clip.mp4",
        description="Test TikTok",
    )
    assert res["success"] is False
    assert "File video tidak ditemukan" in res["error"]


def test_tiktok_missing_credentials():
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        temp_path = f.name

    try:
        res = upload_tiktok_video(
            video_path=temp_path,
            description="Test TikTok",
            cookies_path="non_existent_cookie_file.txt",
            session_id=None,
        )
        assert res["success"] is False
        assert "Kredensial TikTok tidak ditemukan" in res["error"]
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@patch("tiktok_uploader.upload.upload_video")
def test_tiktok_upload_success_mock(mock_upload_video):
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        temp_path = f.name

    try:
        mock_upload_video.return_value = []  # Empty failed list means success

        res = upload_tiktok_video(
            video_path=temp_path,
            description="Klip Viral TikTok #fyp",
            session_id="valid_session_id_mock",
            visibility="everyone",
            headless=True,
        )

        assert res["success"] is True
        assert res["platform"] == "tiktok"
        assert "berhasil diposting" in res["message"]
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_social_uploader_manager_job_lifecycle():
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        temp_path = f.name

    try:
        mgr = SocialUploaderManager()
        cfg = AppConfig()

        with patch("clipmax.uploader.service.upload_youtube_short") as mock_yt:
            mock_yt.return_value = {"success": True, "video_id": "test_id"}

            job_id = mgr.submit_upload_job(
                clip_id=1,
                video_path=temp_path,
                title="Judul Keren",
                caption="Caption Keren #shorts",
                platforms=["youtube"],
                config=cfg,
            )

            assert job_id is not None
            job = mgr.get_job(job_id)
            assert job is not None
            assert job.clip_id == 1

            # Wait for thread to finish
            import time
            for _ in range(50):
                if job.status in ("COMPLETED", "FAILED"):
                    break
                time.sleep(0.05)

            assert job.status == "COMPLETED"
            assert "youtube" in job.results
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
