import pytest
from pathlib import Path
from clipmax.transcriber import WordSegment
from clipmax.subtitle import generate_kinetic_ass, format_ass_time

def test_format_ass_time():
    assert format_ass_time(0.0) == "0:00:00.00"
    assert format_ass_time(65.25) == "0:01:05.25"
    assert format_ass_time(3661.12) == "1:01:01.12"

def test_generate_kinetic_ass(tmp_path):
    words = [
        WordSegment(word="Kunci", start=10.0, end=10.4, probability=0.99),
        WordSegment(word="sukses", start=10.4, end=10.8, probability=0.99),
        WordSegment(word="AI", start=10.8, end=11.2, probability=0.99),
    ]
    out_file = tmp_path / "sub.ass"
    generate_kinetic_ass(words, clip_start=10.0, clip_end=15.0, output_ass_path=str(out_file))

    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "[Script Info]" in content
    assert "[V4+ Styles]" in content
    assert "Style: Kinetic" in content
    assert "Dialogue:" in content
    assert "{\\c&H002BF7&" in content
