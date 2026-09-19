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
            model="gpt-4o-mini",
            target_clip_count=1,
            min_duration=20.0,
            max_duration=50.0
        )
        assert len(clips) == 1
        assert clips[0].start_time == 15.0
        assert clips[0].end_time == 45.0
        assert clips[0].virality_score == 95

def test_evaluate_viral_clips_campaign_rules_and_count():
    mock_json_response = '''
    [
      {
        "title": "Klip 1",
        "hook": "Hook 1",
        "start_time": "00:10",
        "end_time": "00:40",
        "virality_score": 99,
        "reasoning": "Fits campaign"
      },
      {
        "title": "Klip 2",
        "hook": "Hook 2",
        "start_time": "00:50",
        "end_time": "01:20",
        "virality_score": 85,
        "reasoning": "Fits campaign"
      },
      {
        "title": "Klip 3",
        "hook": "Hook 3",
        "start_time": "02:00",
        "end_time": "02:30",
        "virality_score": 70,
        "reasoning": "Extra clip"
      }
    ]
    '''
    with patch("clipmax.ai_gateway.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = mock_json_response
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
        mock_openai.return_value = mock_client

        campaign_rules = "Fokus pada call to action produk X"
        clips = evaluate_viral_clips(
            transcript="Transkrip tentang produk X",
            endpoint_url="http://localhost:20128/v1",
            api_key="test-key",
            model="test-model",
            target_clip_count=2,
            min_duration=25.0,
            max_duration=35.0,
            campaign_rules=campaign_rules
        )

        # Check prompt injection
        create_kwargs = mock_client.chat.completions.create.call_args.kwargs
        user_message = create_kwargs["messages"][1]["content"]
        assert "CRITICAL CAMPAIGN RULES" in user_message
        assert "Fokus pada call to action produk X" in user_message
        assert "Hasilkan tepat 2 klip terbaik" in user_message
        assert "rentang 25 sampai 35 detik" in user_message

        # Check target clip count enforced
        assert len(clips) == 2
        assert clips[0].virality_score == 99
        assert clips[1].virality_score == 85
