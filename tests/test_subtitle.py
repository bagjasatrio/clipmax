import pytest
from pathlib import Path
from clipmax.transcriber import WordSegment
from clipmax.subtitle import generate_kinetic_ass, format_ass_time, to_ass_color

def test_format_ass_time():
    assert format_ass_time(0.0) == "0:00:00.00"
    assert format_ass_time(65.25) == "0:01:05.25"
    assert format_ass_time(3661.12) == "1:01:01.12"

def test_to_ass_color():
    assert to_ass_color("#FFFFFF") == "&H00FFFFFF&"
    assert to_ass_color("#FF2A2A") == "&H002A2AFF&"
    assert to_ass_color("#FFE81F") == "&H001FE8FF&"
    assert to_ass_color("#39FF14") == "&H0014FF39&"
    assert to_ass_color("#00F0FF") == "&H00FFF000&"
    assert to_ass_color("&H002BF7&") == "&H002BF7&"

def test_generate_kinetic_ass_default(tmp_path):
    words = [
        WordSegment(word="Kunci", start=10.0, end=10.4, probability=0.99),
        WordSegment(word="sukses", start=10.4, end=10.8, probability=0.99),
        WordSegment(word="AI", start=10.8, end=11.2, probability=0.99),
    ]
    out_file = tmp_path / "sub_default.ass"
    generate_kinetic_ass(words, clip_start=10.0, clip_end=15.0, output_ass_path=str(out_file))

    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "[Script Info]" in content
    assert "[V4+ Styles]" in content
    assert "Style: Kinetic" in content
    assert "&H00FFFFFF&" in content  # Base white
    assert "&H002A2AFF&" in content  # Default red highlight

def test_generate_kinetic_ass_custom_colors(tmp_path):
    words = [
        WordSegment(word="Gaming", start=5.0, end=6.0, probability=0.99),
        WordSegment(word="Stream", start=6.0, end=7.0, probability=0.99),
    ]
    out_file = tmp_path / "sub_custom.ass"
    # TikTok yellow highlight (#FFE81F -> &H001FE8FF&), base white (#FFFFFF)
    generate_kinetic_ass(
        words,
        clip_start=5.0,
        clip_end=8.0,
        output_ass_path=str(out_file),
        highlight_color="#FFE81F",
        base_color="#FFFFFF"
    )

    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "&H001FE8FF&" in content
    assert "&H00FFFFFF&" in content

def test_generate_overlay_ass(tmp_path):
    from clipmax.subtitle import generate_overlay_ass

    out_file = tmp_path / "overlay_test.ass"
    res = generate_overlay_ass(
        text="FAKTA MENARIK!\nTONTON SAMPAI HABIS",
        duration=20.5,
        output_ass_path=str(out_file),
        font_name="Impact",
        font_size=56,
        text_color="#FFE81F",
        bg_color="#000000",
        has_bg=True,
        position="top"
    )

    assert Path(res).exists()
    content = out_file.read_text(encoding="utf-8")
    assert "Style: OverlayText,Impact,56" in content
    # BorderStyle=3 for background box
    assert ",3,10,0,8,50,50,160,1" in content
    # Text in dialogue event with \N for newline
    assert r"Dialogue: 2,0:00:00.00,0:00:20.50,OverlayText,,0,0,0,,FAKTA MENARIK!\NTONTON SAMPAI HABIS" in content


