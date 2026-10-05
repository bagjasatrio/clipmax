from pathlib import Path
from typing import List, Optional
from clipmax.transcriber import WordSegment

def to_ass_color(hex_color: str) -> str:
    """Converts HEX color (#RRGGBB, RRGGBB, #RGB) or passes through ASS color (&H00BBGGRR&)."""
    if not hex_color:
        return "&H00FFFFFF&"
    if hex_color.startswith("&H") or hex_color.startswith("&h"):
        return hex_color
    hex_clean = hex_color.lstrip('#')
    if len(hex_clean) == 3:
        hex_clean = "".join([c * 2 for c in hex_clean])
    if len(hex_clean) != 6:
        return "&H00FFFFFF&"
    r, g, b = hex_clean[0:2], hex_clean[2:4], hex_clean[4:6]
    return f"&H00{b.upper()}{g.upper()}{r.upper()}&"

def build_ass_header(base_ass_color: str = "&H00FFFFFF&") -> str:
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Kinetic,Impact,58,{base_ass_color},&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,6,2,2,40,40,280,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

ASS_HEADER = build_ass_header("&H00FFFFFF&")

def format_ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

def generate_kinetic_ass(
    words: List[WordSegment],
    clip_start: float,
    clip_end: float,
    output_ass_path: str,
    max_words_per_line: int = 3,
    highlight_color: str = "#FF2A2A",
    base_color: str = "#FFFFFF"
) -> str:
    scoped_words = [
        w for w in words
        if w.start >= (clip_start - 0.2) and w.end <= (clip_end + 0.2)
    ]

    base_ass = to_ass_color(base_color)
    highlight_ass = to_ass_color(highlight_color)

    events = []
    chunk_size = max_words_per_line

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
                if other_idx == current_idx:
                    line_parts.append(f"{{\\c{highlight_ass}\\fscx110\\fscy110}}{other_word.word.upper()}{{\\c{base_ass}\\r}}")
                else:
                    line_parts.append(other_word.word.upper())

            line_text = " ".join(line_parts)
            start_str = format_ass_time(w_start)
            end_str = format_ass_time(w_end)
            events.append(f"Dialogue: 0,{start_str},{end_str},Kinetic,,0,0,0,,{line_text}")

    out_p = Path(output_ass_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w", encoding="utf-8") as f:
        f.write(build_ass_header(base_ass))
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
    position: str = "top",
    x_pct: Optional[float] = None,
    y_pct: Optional[float] = None
) -> str:
    """Generates an ASS subtitle file for burning a custom text/title overlay."""
    out_p = Path(output_ass_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    t_ass = to_ass_color(text_color)
    bg_ass = to_ass_color(bg_color)
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
    clean_text = text.strip().replace("\r", "").replace("\n", r"\N")
    # Smart line-wrapping for long titles without manual line-breaks
    max_c = max(14, int(1200 / max(20, font_size)))
    raw_lines = text.strip().splitlines()
    wrapped_lines = []
    for line in raw_lines:
        line_clean = line.strip()
        if not line_clean:
            continue
        if len(line_clean) > max_c:
            import textwrap
            wrapped_lines.extend(textwrap.wrap(line_clean, width=max_c, break_long_words=False))
        else:
            wrapped_lines.append(line_clean)
    if wrapped_lines:
        clean_text = r"\N".join(wrapped_lines)

    end_str = format_ass_time(max(0.1, duration))
    event_line = f"Dialogue: 2,0:00:00.00,{end_str},OverlayText,,0,0,0,,{pos_tag}{clean_text}\n"

    with open(out_p, "w", encoding="utf-8") as f:
        f.write(header)
        f.write(event_line)

    return str(out_p.resolve())
