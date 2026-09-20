import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from clipmax.web.server import app, state
from clipmax.pipeline import ClipResult

client = TestClient(app)

def test_api_system():
    res = client.get("/api/system")
    assert res.status_code == 200
    data = res.json()
    assert "cuda_available" in data
    assert "device_name" in data
    assert "whisper_model" in data

def test_api_config():
    res = client.get("/api/config")
    assert res.status_code == 200
    data = res.json()
    assert "endpoint_url" in data
    assert "target_clip_count" in data
    assert "youtube_authenticated" in data

def test_api_config_update():
    res = client.post("/api/config", json={"target_clip_count": 4})
    assert res.status_code == 200
    assert state.config.target_clip_count == 4

def test_api_youtube_oauth_endpoints():
    # 1. Status endpoint
    with patch("clipmax.web.server.is_youtube_oauth_authenticated", return_value=True):
        res = client.get("/api/youtube/oauth/status")
        assert res.status_code == 200
        assert res.json()["authenticated"] is True

    # 2. Initiate endpoint
    with patch("clipmax.web.server.initiate_youtube_oauth", return_value={
        "verification_url": "https://www.google.com/device",
        "user_code": "TEST-123",
        "device_code": "dev-123"
    }):
        res = client.post("/api/youtube/oauth/initiate")
        assert res.status_code == 200
        assert res.json()["data"]["user_code"] == "TEST-123"

    # 3. Poll endpoint
    with patch("clipmax.web.server.poll_youtube_oauth_token", return_value={"status": "pending"}):
        res = client.post("/api/youtube/oauth/poll", json={"device_code": "dev-123"})
        assert res.status_code == 200
        assert res.json()["status"] == "pending"

def test_api_pipeline_status():
    res = client.get("/api/pipeline/status")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "progress" in data
    assert "message" in data

def test_api_models():
    res = client.get("/api/models")
    assert res.status_code == 200
    data = res.json()
    assert "models" in data
    assert isinstance(data["models"], list)

def test_static_index_html():
    res = client.get("/")
    assert res.status_code == 200
    assert "ClipMax Studio" in res.text
    assert "Hubungkan Akun YouTube (OAuth2)" in res.text
    assert "cookies.txt" not in res.text
