from pathlib import Path
from typing import List, Optional, Dict, Any
from clipmax.transcriber import WordSegment

def to_ass_color(hex_color: str, alpha: float = 1.0) -> str:
    """Converts HEX color (#RRGGBB, #AARRGGBB, #RGB) or passes through ASS color (&HAABBGGRR&)."""
    if not hex_color:
        return "&H00FFFFFF&"
    if hex_color.startswith("&H") or hex_color.startswith("&h"):
        return hex_color
    hex_clean = hex_color.lstrip('#')
    ass_alpha = int(round((1.0 - max(0.0, min(1.0, alpha))) * 255))
    if len(hex_clean) == 8:
        # User passed 8-digit hex #RRGGBBAA
        r, g, b, a_hex = hex_clean[0:2], hex_clean[2:4], hex_clean[4:6], hex_clean[6:8]
        css_a = int(a_hex, 16) / 255.0
        ass_alpha = int(round((1.0 - css_a) * 255))
        return f"&H{ass_alpha:02X}{b.upper()}{g.upper()}{r.upper()}&"
    if len(hex_clean) == 3:
        hex_clean = "".join([c * 2 for c in hex_clean])
    if len(hex_clean) == 6:
        r, g, b = hex_clean[0:2], hex_clean[2:4], hex_clean[4:6]
        return f"&H{ass_alpha:02X}{b.upper()}{g.upper()}{r.upper()}&"
    return f"&H{ass_alpha:02X}FFFFFF&"

def build_ass_header(
    base_ass_color: str = "&H00FFFFFF&",
    font_name: str = "Impact",
    font_size: int = 58,
    border_style: int = 1,
    outline: int = 6,
    shadow: int = 2,
    margin_v: int = 280,
    alignment: int = 2
) -> str:
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Kinetic,{font_name},{font_size},{base_ass_color},&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,{border_style},{outline},{shadow},{alignment},40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

ASS_HEADER = build_ass_header("&H00FFFFFF&")

SUBTITLE_PRESETS: Dict[str, Dict[str, Any]] = {
    "classic_red": {
        "name": "Classic Red",
        "label": "Klasik Merah - Putih",
        "base_color": "#FFFFFF",
        "highlight_color": "#FF2A2A",
        "font_name": "Impact",
        "font_size": 58,
        "outline": 6,
        "shadow": 2,
        "border_style": 1
    },
    "viral_pop": {
        "name": "VIRAL POP",
        "label": "VIRAL POP (Hormozi Yellow Glow)",
        "base_color": "#FFFFFF",
        "highlight_color": "#FFE81F",
        "font_name": "Impact",
        "font_size": 58,
        "outline": 6,
        "shadow": 2,
        "border_style": 1
    },
    "beast_punch": {
        "name": "BEAST PUNCH",
        "label": "BEAST PUNCH (High Impact Green)",
        "base_color": "#FFFFFF",
        "highlight_color": "#39FF14",
        "font_name": "Impact",
        "font_size": 58,
        "outline": 6,
        "shadow": 2,
        "border_style": 1
    },
    "cyber_violet": {
        "name": "CYBER VIOLET",
        "label": "CYBER VIOLET (Neon Purple Glow)",
        "base_color": "#FFFFFF",
        "highlight_color": "#B026FF",
        "font_name": "Montserrat",
        "font_size": 56,
        "outline": 6,
        "shadow": 2,
        "border_style": 1
    },
    "fire_crimson": {
        "name": "FIRE CRIMSON",
        "label": "FIRE CRIMSON (High Energy Red)",
        "base_color": "#FFFFFF",
        "highlight_color": "#FF2A2A",
        "font_name": "Impact",
        "font_size": 58,
        "outline": 6,
        "shadow": 2,
        "border_style": 1
    },
    "electric_cyan": {
        "name": "ELECTRIC CYAN",
        "label": "ELECTRIC CYAN (Ice Blue Glow)",
        "base_color": "#FFFFFF",
        "highlight_color": "#00F0FF",
        "font_name": "Montserrat",
        "font_size": 56,
        "outline": 6,
        "shadow": 2,
        "border_style": 1
    },
    "golden_aura": {
        "name": "GOLDEN AURA",
        "label": "GOLDEN AURA (Luxury Warm Gold)",
        "base_color": "#FFFFFF",
        "highlight_color": "#FFD700",
        "font_name": "Montserrat",
        "font_size": 56,
        "outline": 5,
        "shadow": 2,
        "border_style": 1
    },
    "clean_minimal": {
        "name": "Clean Minimal",
        "label": "Clean Minimal (Soft Dark Box)",
        "base_color": "#FFFFFF",
        "highlight_color": "#00F0FF",
        "font_name": "Montserrat",
        "font_size": 52,
        "outline": 8,
        "shadow": 0,
        "border_style": 3
    },
    "none": {
        "name": "NONE",
        "label": "NONE (Tanpa Subtitle)",
        "base_color": "#FFFFFF",
        "highlight_color": "#FFFFFF",
        "font_name": "Impact",
        "font_size": 58,
        "outline": 0,
        "shadow": 0,
        "border_style": 1
    }
}

def format_word_case(text: str, case_mode: str = "upper") -> str:
    if case_mode == "lower":
        return text.lower()
    elif case_mode == "title":
        return text.title()
    return text.upper()

def format_ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

def format_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000:
        ms = 999
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def generate_srt(
    words: List[WordSegment],
    clip_start: float,
    clip_end: float,
    output_srt_path: str,
    chunk_size: int = 4,
    case_mode: str = "upper"
) -> str:
    scoped_words = [
        w for w in words
        if w.start >= (clip_start - 0.2) and w.end <= (clip_end + 0.2)
    ]
    lines = []
    srt_idx = 1
    for i in range(0, len(scoped_words), chunk_size):
        chunk = scoped_words[i:i + chunk_size]
        if not chunk:
            continue
        c_start = max(0.0, chunk[0].start - clip_start)
        c_end = max(c_start + 0.3, chunk[-1].end - clip_start)
        words_text = " ".join(format_word_case(w.word, case_mode) for w in chunk)
        lines.append(f"{srt_idx}\n{format_srt_time(c_start)} --> {format_srt_time(c_end)}\n{words_text}\n")
        srt_idx += 1

    out_p = Path(output_srt_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return str(out_p.resolve())

def generate_youtube_chapters(clips: list) -> str:
    lines = ["00:00 Intro"]
    for c in sorted(clips, key=lambda x: getattr(x, "start_time", 0)):
        st = getattr(c, "start_time", 0)
        title = getattr(c, "title", "Clip")
        m = int(st // 60)
        s = int(st % 60)
        lines.append(f"{m:02d}:{s:02d} {title}")
    return "\n".join(lines)

def generate_markdown_summary(clips: list) -> str:
    md = ["# Generated Viral Clips Summary\n"]
    md.append("| # | Title | Hook | Virality Score | Start - End | Hook Timestamp |")
    md.append("|---|---|---|---|---|---|")
    for c in sorted(clips, key=lambda x: getattr(x, "clip_id", 0)):
        cid = getattr(c, "clip_id", 0)
        title = getattr(c, "title", "Untitled")
        hook = getattr(c, "hook", "")
        score = getattr(c, "virality_score", 0)
        st = getattr(c, "start_time", 0)
        et = getattr(c, "end_time", 0)
        hts = getattr(c, "hook_timestamp", None)
        hts_str = f"{hts:.2f}s" if hts is not None else "-"
        md.append(f"| {cid} | **{title}** | {hook} | {score}/100 | {st:.1f}s - {et:.1f}s | {hts_str} |")

    md.append("\n## Social Captions & Hashtags\n")
    for c in sorted(clips, key=lambda x: getattr(x, "clip_id", 0)):
        cid = getattr(c, "clip_id", 0)
        title = getattr(c, "title", "Untitled")
        caption = getattr(c, "social_caption", "")
        reason = getattr(c, "reasoning", "")
        md.append(f"### Clip {cid}: {title}\n")
        if reason:
            md.append(f"*Viral Reasoning:* {reason}\n")
        if caption:
            md.append(f"```text\n{caption}\n```\n")
    return "\n".join(md)

def generate_kinetic_ass(
    words: List[WordSegment],
    clip_start: float,
    clip_end: float,
    output_ass_path: str,
    max_words_per_line: int = 3,
    highlight_color: str = "#FF2A2A",
    base_color: str = "#FFFFFF",
    preset: Optional[str] = None,
    font_name: Optional[str] = None,
    font_size: Optional[int] = None,
    case_mode: str = "upper",
    strictly_one_line: bool = False,
    bottom_offset_pct: Optional[int] = None
) -> str:
    border_style = 1
    outline = 6
    shadow = 2

    if preset and preset in SUBTITLE_PRESETS:
        p_info = SUBTITLE_PRESETS[preset]
        if preset == "none":
            out_p = Path(output_ass_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            with open(out_p, "w", encoding="utf-8") as f:
                f.write(build_ass_header())
            return str(out_p.resolve())

        if highlight_color == "#FF2A2A" and "highlight_color" in p_info:
            highlight_color = p_info["highlight_color"]
        if base_color == "#FFFFFF" and "base_color" in p_info:
            base_color = p_info["base_color"]
        if font_name is None and "font_name" in p_info:
            font_name = p_info["font_name"]
        if font_size is None and "font_size" in p_info:
            font_size = p_info["font_size"]
        border_style = p_info.get("border_style", 1)
        outline = p_info.get("outline", 6)
        shadow = p_info.get("shadow", 2)

    font_name = font_name or "Impact"
    font_size = font_size or 58

    if bottom_offset_pct is not None:
        margin_v = int(round(1920 * (max(5, min(60, bottom_offset_pct)) / 100.0)))
    else:
        margin_v = 280

    scoped_words = [
        w for w in words
        if w.start >= (clip_start - 0.2) and w.end <= (clip_end + 0.2)
    ]

    base_ass = to_ass_color(base_color)
    highlight_ass = to_ass_color(highlight_color)

    events = []
    chunk_size = 2 if strictly_one_line else max_words_per_line

    for i in range(0, len(scoped_words), chunk_size):
        chunk = scoped_words[i:i + chunk_size]
        if not chunk:
            continue

        group_start = max(0.0, chunk[0].start - clip_start)
        group_end = max(group_start + 0.3, chunk[-1].end - clip_start)

        for current_idx, active_word in enumerate(chunk):
            w_start = max(group_start, active_word.start - clip_start)
            w_end = min(group_end, active_word.end - clip_start)
            if w_end <= w_start:
                w_end = w_start + 0.25

            line_parts = []
            for other_idx, other_word in enumerate(chunk):
                w_text = format_word_case(other_word.word, case_mode)
                if other_idx == current_idx:
                    line_parts.append(f"{{\\c{highlight_ass}\\fscx110\\fscy110}}{w_text}{{\\c{base_ass}\\r}}")
                else:
                    line_parts.append(w_text)

            line_text = " ".join(line_parts)
            start_str = format_ass_time(w_start)
            end_str = format_ass_time(w_end)
            events.append(f"Dialogue: 0,{start_str},{end_str},Kinetic,,0,0,0,,{line_text}")

    out_p = Path(output_ass_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    header = build_ass_header(
        base_ass_color=base_ass,
        font_name=font_name,
        font_size=font_size,
        border_style=border_style,
        outline=outline,
        shadow=shadow,
        margin_v=margin_v
    )
    with open(out_p, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(events))
        f.write("\n")

    return str(out_p.resolve())

def generate_overlay_ass(
    text: str,
    duration: float,
    output_ass_path: str,
    font_name: str = "Impact",
    font_size: int = 56,
    text_color: str = "#FFFFFF",
    bg_color: str = "#000000",
    has_bg: bool = True,
    bg_alpha: float = 1.0,
    position: str = "top",
    x_pct: Optional[float] = None,
    y_pct: Optional[float] = None
) -> str:
    """Generates an ASS subtitle file for burning a custom text/title overlay."""
    out_p = Path(output_ass_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    t_ass = to_ass_color(text_color, alpha=1.0)
    bg_ass = to_ass_color(bg_color, alpha=bg_alpha)
    border_style = 3 if has_bg else 1
    outline_pad = 10 if has_bg else 4
    shadow_depth = 0 if has_bg else 2

    # Free roam positioning or preset alignment
    if x_pct is not None and y_pct is not None:
        align = 5  # center anchor
        margin_v = 0
        px = int(round((x_pct / 100.0) * 1080))
        py = int(round((y_pct / 100.0) * 1920))
        pos_tag = f"{{\\an5\\pos({px},{py})}}"
    else:
        align = 8 if position == "top" else (5 if position == "center" else 2)
        margin_v = 160 if position == "top" else (0 if position == "center" else 480)
        pos_tag = ""

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: OverlayText,{font_name},{font_size},{t_ass},{t_ass},{bg_ass},{bg_ass},-1,0,0,0,100,100,1,0,{border_style},{outline_pad},{shadow_depth},{align},50,50,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    # Clean text and preserve user's explicit lines verbatim
    clean_raw = text.strip().replace("\r", "")
    if r"\N" in clean_raw:
        lines = [l.strip() for l in clean_raw.split(r"\N") if l.strip()]
    else:
        lines = [l.strip() for l in clean_raw.split("\n") if l.strip()]

    # If the text has only 1 long line without explicit line breaks, apply smart wrap:
    if len(lines) == 1 and len(lines[0]) > 22:
        max_c = max(14, int(1000 / max(20, font_size)))
        import textwrap
        lines = textwrap.wrap(lines[0], width=max_c, break_long_words=False)

    clean_text = r"\N".join(lines) if lines else clean_raw

    end_str = format_ass_time(max(0.1, duration))
    event_line = f"Dialogue: 2,0:00:00.00,{end_str},OverlayText,,0,0,0,,{pos_tag}{clean_text}\n"

    with open(out_p, "w", encoding="utf-8") as f:
        f.write(header)
        f.write(event_line)

    return str(out_p.resolve())
