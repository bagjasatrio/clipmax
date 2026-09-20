import re
from typing import List, Optional, Dict
from openai import OpenAI
from clipmax.transcriber import WordSegment

SUBTITLE_POLISHER_PROMPT = """Kamu adalah editor subtitle profesional untuk konten gaming & vlog. Perbaiki typo, salah dengar fonetik, dan ejaan slang (baik bahasa Indonesia, Inggris, maupun Indoglish) agar natural dan tepat konteks.
Aturan:
- Jangan ubah format baris, nomor urut, atau stempel waktu.
- Pertahankan istilah khas game.
- Kembalikan hanya teks hasil koreksi."""

LINE_PATTERN = re.compile(
    r"^(\d+)\s*[\|\.\:\-]\s*(?:(?:\d+:\d+(?:\.\d+)?\s*[\-\–]\s*\d+:\d+(?:\.\d+)?)\s*[\|\:\-\s]+)?(.+)$"
)

def format_time_label(seconds: float) -> str:
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m:02d}:{s:05.2f}"

def polish_transcript_lines(
    lines: List[str],
    endpoint_url: str,
    api_key: str = "",
    model: str = "default"
) -> List[str]:
    """Sends numbered lines of transcript to LLM for typo, phonetic, and slang polishing."""
    if not lines:
        return []

    try:
        client = OpenAI(
            base_url=endpoint_url,
            api_key=api_key or "no-key-required"
        )
        prompt = "\n".join(lines)
        response = client.chat.completions.create(
            model=model or "default",
            messages=[
                {"role": "system", "content": SUBTITLE_POLISHER_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        content = response.choices[0].message.content or ""
        raw_lines = [l.strip() for l in content.strip().splitlines() if l.strip()]
        return raw_lines if raw_lines else lines
    except Exception as e:
        print(f"[Subtitle Cleaner Warning] Failed to polish lines via LLM: {e}")
        return lines

def polish_subtitles_with_llm(
    words: List[WordSegment],
    clip_start: float,
    clip_end: float,
    endpoint_url: str,
    api_key: str = "",
    model: str = "default",
    chunk_size: int = 4
) -> List[WordSegment]:
    """Polishes words within clip timeframe for gaming slang, phonetic typos, and Indoglish while preserving timestamps."""
    scoped_indices = [
        i for i, w in enumerate(words)
        if w.start >= (clip_start - 0.2) and w.end <= (clip_end + 0.2)
    ]
    if not scoped_indices:
        return words

    scoped_words = [words[i] for i in scoped_indices]

    # Chunk into 3-5 word groups
    chunks: List[List[WordSegment]] = [
        scoped_words[i:i + chunk_size]
        for i in range(0, len(scoped_words), chunk_size)
    ]

    prompt_lines: List[str] = []
    for idx, chunk in enumerate(chunks):
        c_start = max(0.0, chunk[0].start - clip_start)
        c_end = max(c_start + 0.2, chunk[-1].end - clip_start)
        c_text = " ".join(w.word for w in chunk)
        prompt_lines.append(f"{idx + 1} | {format_time_label(c_start)} - {format_time_label(c_end)} | {c_text}")

    try:
        client = OpenAI(
            base_url=endpoint_url,
            api_key=api_key or "no-key-required"
        )
        response = client.chat.completions.create(
            model=model or "default",
            messages=[
                {"role": "system", "content": SUBTITLE_POLISHER_PROMPT},
                {"role": "user", "content": "\n".join(prompt_lines)}
            ],
            temperature=0.2
        )
        content = response.choices[0].message.content or ""

        line_map: Dict[int, str] = {}
        for line in content.strip().splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            m = LINE_PATTERN.match(line_str)
            if m:
                lid = int(m.group(1))
                corr = m.group(2).strip()
                line_map[lid] = corr

        polished_scoped: List[WordSegment] = []
        for idx, chunk in enumerate(chunks):
            lid = idx + 1
            corr_text = line_map.get(lid)
            if corr_text:
                new_tokens = corr_text.split()
                if len(new_tokens) == len(chunk):
                    for orig_w, n_token in zip(chunk, new_tokens):
                        polished_scoped.append(
                            WordSegment(
                                word=n_token,
                                start=orig_w.start,
                                end=orig_w.end,
                                probability=orig_w.probability
                            )
                        )
                elif new_tokens:
                    c_start = chunk[0].start
                    c_end = chunk[-1].end
                    tot_dur = max(0.2, c_end - c_start)
                    w_dur = tot_dur / len(new_tokens)
                    for iw, n_token in enumerate(new_tokens):
                        polished_scoped.append(
                            WordSegment(
                                word=n_token,
                                start=c_start + iw * w_dur,
                                end=c_start + (iw + 1) * w_dur,
                                probability=0.95
                            )
                        )
                else:
                    polished_scoped.extend(chunk)
            else:
                polished_scoped.extend(chunk)

        # Replace scoped range in words list
        new_words = list(words)
        # Clear out original scoped elements
        min_idx = scoped_indices[0]
        max_idx = scoped_indices[-1]
        return new_words[:min_idx] + polished_scoped + new_words[max_idx + 1:]

    except Exception as e:
        print(f"[Subtitle Cleaner Warning] Subtitle LLM polish fallback: {e}")
        return words
