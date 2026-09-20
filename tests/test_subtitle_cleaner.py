import pytest
from unittest.mock import patch, MagicMock
from clipmax.transcriber import WordSegment
from clipmax.subtitle_cleaner import (
    polish_transcript_lines,
    polish_subtitles_with_llm,
    format_time_label,
    SUBTITLE_POLISHER_PROMPT,
    LINE_PATTERN
)

def test_subtitle_polisher_prompt_content():
    assert "editor subtitle profesional" in SUBTITLE_POLISHER_PROMPT
    assert "Jangan ubah format baris" in SUBTITLE_POLISHER_PROMPT
    assert "Pertahankan istilah khas game" in SUBTITLE_POLISHER_PROMPT

def test_format_time_label():
    assert format_time_label(0.0) == "00:00.00"
    assert format_time_label(65.5) == "01:05.50"
    assert format_time_label(123.456) == "02:03.46"

def test_line_pattern_matching():
    sample1 = "1 | 00:01.20 - 00:03.50 | kita mau gank tortle di mid"
    m1 = LINE_PATTERN.match(sample1)
    assert m1 is not None
    assert m1.group(1) == "1"
    assert m1.group(2) == "kita mau gank tortle di mid"

    sample2 = "2. ulti ready bro by one"
    m2 = LINE_PATTERN.match(sample2)
    assert m2 is not None
    assert m2.group(1) == "2"
    assert m2.group(2) == "ulti ready bro by one"

def test_polish_transcript_lines_mock():
    mock_input = [
        "1 | 00:00.00 - 00:02.00 | gank tortle bro",
        "2 | 00:02.00 - 00:05.00 | awas lort di setil"
    ]
    mock_output = (
        "1 | 00:00.00 - 00:02.00 | gank turtle bro\n"
        "2 | 00:02.00 - 00:05.00 | awas lord di steal"
    )

    with patch("clipmax.subtitle_cleaner.OpenAI") as mock_openai:
        client = MagicMock()
        choice = MagicMock()
        choice.message.content = mock_output
        client.chat.completions.create.return_value = MagicMock(choices=[choice])
        mock_openai.return_value = client

        res = polish_transcript_lines(
            lines=mock_input,
            endpoint_url="http://localhost:20128/v1",
            api_key="test-key",
            model="gemini-flash"
        )
        assert len(res) == 2
        assert "turtle" in res[0]
        assert "steal" in res[1]

def test_polish_subtitles_with_llm_gaming_slang_preserves_timing():
    words = [
        WordSegment(word="gank", start=1.0, end=1.5, probability=0.9),
        WordSegment(word="tortle", start=1.5, end=2.0, probability=0.8),  # Typo fonetik
        WordSegment(word="bro", start=2.0, end=2.5, probability=0.9),
        WordSegment(word="cuy", start=2.5, end=3.0, probability=0.9),
    ]

    mock_llm_reply = "1 | 00:01.00 - 00:03.00 | gank turtle bro cuy"

    with patch("clipmax.subtitle_cleaner.OpenAI") as mock_openai:
        client = MagicMock()
        choice = MagicMock()
        choice.message.content = mock_llm_reply
        client.chat.completions.create.return_value = MagicMock(choices=[choice])
        mock_openai.return_value = client

        polished = polish_subtitles_with_llm(
            words=words,
            clip_start=1.0,
            clip_end=3.0,
            endpoint_url="http://localhost:20128/v1",
            api_key="test-key",
            model="gemini-flash"
        )

        assert len(polished) == 4
        # Verify phonetic mishear was fixed to gaming term
        assert polished[1].word == "turtle"
        # Verify exact timing preservation
        assert polished[1].start == 1.5
        assert polished[1].end == 2.0
        assert polished[0].word == "gank"
        assert polished[3].word == "cuy"

def test_polish_subtitles_with_llm_fallback_on_error():
    words = [
        WordSegment(word="rata", start=0.5, end=1.0, probability=0.9),
        WordSegment(word="semua", start=1.0, end=1.5, probability=0.9),
    ]

    with patch("clipmax.subtitle_cleaner.OpenAI", side_effect=RuntimeError("Connection timeout")):
        # Should gracefully return original words on exception
        result = polish_subtitles_with_llm(
            words=words,
            clip_start=0.5,
            clip_end=1.5,
            endpoint_url="http://localhost:20128/v1"
        )
        assert len(result) == 2
        assert result[0].word == "rata"
        assert result[1].word == "semua"
