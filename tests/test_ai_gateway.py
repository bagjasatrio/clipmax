import pytest
from unittest.mock import patch, MagicMock
from clipmax.ai_gateway import (
    discover_models,
    safe_extract_json,
    evaluate_viral_clips,
    ViralClipCandidate
)

def test_safe_extract_json_markdown_block():
    raw = 'Here is the result:\n```json\n[{"title": "Hook 1", "start_time": "00:10", "end_time": "00:45", "score": 90, "hook": "Awesome hook"}]\n```'
    parsed = safe_extract_json(raw)
    assert isinstance(parsed, list)
    assert parsed[0]["title"] == "Hook 1"

def test_safe_extract_json_raw_braces():
    raw = 'Some chatter {"clips": [{"title": "Clip A", "start_time": 10.0, "end_time": 40.0, "score": 85, "hook": "Watch this"}]}'
    parsed = safe_extract_json(raw)
    assert "clips" in parsed

def test_discover_models_mock():
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {"id": "gpt-4o-mini"},
                {"id": "deepseek-chat"}
            ]
        }
        mock_get.return_value = mock_resp

        models = discover_models("http://localhost:20128/v1")
        assert "gpt-4o-mini" in models
        assert "deepseek-chat" in models

def test_evaluate_viral_clips_mock():
    mock_json_response = '''
    [
      {
        "title": "Kunci Sukses AI",
        "hook": "Tahukah kamu rahasianya?",
        "start_time": "00:15",
        "end_time": "00:45",
        "virality_score": 95,
        "reasoning": "Strong hook"
      }
    ]
    '''
    with patch("clipmax.ai_gateway.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = mock_json_response
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
        mock_openai.return_value = mock_client

        clips = evaluate_viral_clips(
            transcript="Sample transcript text",
            endpoint_url="http://localhost:20128/v1",
            api_key="",
            model="gpt-4o-mini"
        )
        assert len(clips) == 1
        assert clips[0].start_time == 15.0
        assert clips[0].end_time == 45.0
        assert clips[0].virality_score == 95
