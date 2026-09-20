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
    assert data.get("engine") == "invidious_api"

def test_api_config_update():
    res = client.post("/api/config", json={"target_clip_count": 4, "clip_mode": "montage"})
    assert res.status_code == 200
    assert state.config.target_clip_count == 4
    assert state.config.clip_mode == "montage"

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

def test_api_cache_clear():
    res = client.post("/api/cache/clear")
    assert res.status_code == 200
    assert res.json().get("status") == "ok"
    assert "Cache cleared" in res.json().get("message")

def test_static_index_html():
    res = client.get("/")
    assert res.status_code == 200
    assert "ClipMax Studio" in res.text
    assert "Invidious API Stream" in res.text
    assert "cookies.txt" not in res.text
    assert "Multi-Cut Montage" in res.text
    assert "Reset &amp; Clear Cache" in res.text or "Reset & Clear Cache" in res.text
