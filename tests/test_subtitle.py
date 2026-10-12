import pytest
from pathlib import Path
from clipmax.transcriber import WordSegment
from clipmax.subtitle import generate_kinetic_ass, format_ass_time, to_ass_color, generate_overlay_ass

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

def test_generate_overlay_ass_free_roam(tmp_path):
    from clipmax.subtitle import generate_overlay_ass

    out_file = tmp_path / "overlay_freeroam.ass"
    res = generate_overlay_ass(
        text="FREE ROAM TITLE",
        duration=10.0,
        output_ass_path=str(out_file),
        font_name="Montserrat",
        font_size=50,
        text_color="#FFFFFF",
        has_bg=False,
        x_pct=40.0,
        y_pct=65.0
    )

    assert Path(res).exists()
    content = out_file.read_text(encoding="utf-8")
    assert "Style: OverlayText,Montserrat,50" in content
    # Pos tag at 40% of 1080 = 432, 65% of 1920 = 1248
    assert r"{\an5\pos(432,1248)}FREE ROAM TITLE" in content

def test_generate_overlay_ass_smart_wrapping(tmp_path):
    out_file = tmp_path / "wrapped_overlay.ass"
    # Long text exceeding character width limit
    long_text = "Aaron Rodgers Fiance Wild Ultimatum"
    res = generate_overlay_ass(
        text=long_text,
        duration=5.0,
        output_ass_path=str(out_file),
        font_name="Montserrat",
        font_size=56,
        x_pct=50.0,
        y_pct=12.0
    )
    assert Path(res).exists()
    content = out_file.read_text(encoding="utf-8")
    # Must be wrapped with \N rather than spanning on single giant line
    assert r"\N" in content
    assert "Aaron Rodgers" in content
    assert "Ultimatum" in content

    # Test preserving explicit user lines
    out_file2 = tmp_path / "explicit_overlay.ass"
    generate_overlay_ass(
        text="Custom Line 1\nCustom Line 2",
        duration=5.0,
        output_ass_path=str(out_file2),
        font_name="Montserrat",
        font_size=56,
        x_pct=50.0,
        y_pct=12.0
    )
    content2 = out_file2.read_text(encoding="utf-8")
    assert r"Custom Line 1\NCustom Line 2" in content2

def test_generate_srt(tmp_path):
    from clipmax.subtitle import generate_srt
    words = [
        WordSegment(word="Ini", start=1.0, end=1.4, probability=0.99),
        WordSegment(word="adalah", start=1.4, end=1.8, probability=0.99),
        WordSegment(word="video", start=1.8, end=2.2, probability=0.99),
        WordSegment(word="viral", start=2.2, end=2.8, probability=0.99),
    ]
    srt_out = tmp_path / "test.srt"
    res = generate_srt(words, clip_start=1.0, clip_end=3.0, output_srt_path=str(srt_out), chunk_size=2, case_mode="upper")
    assert Path(res).exists()
    content = srt_out.read_text(encoding="utf-8")
    assert "00:00:00,000 --> " in content
    assert "INI ADALAH" in content
    assert "VIDEO VIRAL" in content

def test_generate_youtube_chapters_and_summary():
    from clipmax.subtitle import generate_youtube_chapters, generate_markdown_summary
    from clipmax.pipeline import ClipResult
    clips = [
        ClipResult(
            clip_id=1,
            title="Momen Juara",
            hook="Gila banget!",
            virality_score=95,
            reasoning="Keren",
            start_time=15.0,
            end_time=45.0,
            staging_path="",
            social_caption="Momen juara seru #viral #shorts",
            hook_timestamp=17.5
        ),
        ClipResult(
            clip_id=2,
            title="Strategi Akhir",
            hook="Tonton sampai habis",
            virality_score=88,
            reasoning="Penuh taktik",
            start_time=80.0,
            end_time=110.0,
            staging_path="",
            social_caption="Strategi jitu #tips #shorts"
        )
    ]
    chapters = generate_youtube_chapters(clips)
    assert "00:00 Intro" in chapters
    assert "00:15 Momen Juara" in chapters
    assert "01:20 Strategi Akhir" in chapters

    summary = generate_markdown_summary(clips)
    assert "# Generated Viral Clips Summary" in summary
    assert "Momen Juara" in summary
    assert "95/100" in summary
    assert "17.50s" in summary
    assert "Momen juara seru #viral #shorts" in summary

def test_subtitle_presets_and_options(tmp_path):
    from clipmax.subtitle import SUBTITLE_PRESETS, generate_kinetic_ass
    assert "viral_pop" in SUBTITLE_PRESETS
    assert "beast_punch" in SUBTITLE_PRESETS
    assert "cyber_violet" in SUBTITLE_PRESETS

    words = [
        WordSegment(word="halo", start=2.0, end=2.5, probability=0.99),
        WordSegment(word="dunia", start=2.5, end=3.0, probability=0.99),
    ]
    out_ass = tmp_path / "preset_test.ass"
    res = generate_kinetic_ass(
        words=words,
        clip_start=2.0,
        clip_end=4.0,
        output_ass_path=str(out_ass),
        preset="viral_pop",
        case_mode="title",
        strictly_one_line=True,
        bottom_offset_pct=25
    )
    assert Path(res).exists()
    content = out_ass.read_text(encoding="utf-8")
    assert "Style: Kinetic" in content
    # MarginV at 25% of 1920 = 480
    assert ",480,1" in content
    # Title case format
    assert "Halo" in content or "Dunia" in content




