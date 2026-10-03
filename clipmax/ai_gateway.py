import json
import re
from typing import List, Dict, Any, Optional
import requests
from pydantic import BaseModel
from openai import OpenAI
from clipmax.config import parse_to_seconds

class MontageCut(BaseModel):
    start: float
    end: float
    event: str = ""

class ViralClipCandidate(BaseModel):
    title: str
    hook: str = ""
    start_time: float
    end_time: float
    virality_score: int
    reasoning: str = ""
    mode: str = "single"  # "single" or "montage"
    cuts: Optional[List[MontageCut]] = None

def safe_extract_json(text: str) -> Any:
    # 1. Direct parse
    clean = text.strip()
    try:
        return json.loads(clean)
    except Exception:
        pass

    # 2. Markdown code block ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except Exception:
            pass

    # 3. Find first outer bracket/brace
    first_brace = text.find('{')
    first_bracket = text.find('[')

    candidates = []
    if first_brace != -1:
        last_brace = text.rfind('}')
        if last_brace > first_brace:
            candidates.append((first_brace, text[first_brace:last_brace + 1]))
    if first_bracket != -1:
        last_bracket = text.rfind(']')
        if last_bracket > first_bracket:
            candidates.append((first_bracket, text[first_bracket:last_bracket + 1]))

    # Sort by appearance in text
    candidates.sort(key=lambda x: x[0])
    for _, snippet in candidates:
        try:
            return json.loads(snippet)
        except Exception:
            pass

    raise ValueError(f"Failed to parse valid JSON from LLM output: {text[:200]}...")

def discover_models(endpoint_url: str, api_key: str = "") -> List[str]:
    url = endpoint_url.rstrip("/")
    if not url.endswith("/models"):
        url = f"{url}/models"

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    resp = requests.get(url, headers=headers, timeout=10)
    if resp.status_code != 200:
        raise RuntimeError(f"Model discovery failed HTTP {resp.status_code}: {resp.text}")

    data = resp.json()
    model_ids: List[str] = []
    if "data" in data and isinstance(data["data"], list):
        for item in data["data"]:
            if isinstance(item, dict) and "id" in item:
                model_ids.append(item["id"])
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "id" in item:
                model_ids.append(item["id"])
            elif isinstance(item, str):
                model_ids.append(item)

    return model_ids or ["default"]

SYSTEM_PROMPT = """Anda adalah kurator video viral profesional untuk TikTok, Instagram Reels, dan YouTube Shorts.
Analisis transkrip dan pilih segmen klip terbaik berdasarkan kriteria dan instruksi khusus.

ATURAN KESELARASAN BAHASA (STRICT LANGUAGE ALIGNMENT - WAJIB):
1. Periksa bahasa utama dari teks transkrip audio sumber:
   - JIKA TRANSKRIP BERBAHASA INGGRIS (ENGLISH): Seluruh teks output: 'title', 'hook', dan 'reasoning' WAJIB DITULIS DALAM BAHASA INGGRIS (English) yang tajam, punchy, viral, dan natural! JANGAN PERNAH menerjemahkan ke bahasa Indonesia!
   - JIKA TRANSKRIP BERBAHASA INDONESIA: Seluruh teks output: 'title', 'hook', dan 'reasoning' WAJIB DITULIS DALAM BAHASA INDONESIA yang menarik dan natural.
2. Selalu gunakan bahasa yang sama persis dengan bahasa asli pembicara pada transkrip sumber!

ATURAN UTAMA (ENFORCE MANDATORY CONSTRAINTS):
Periksa 'Campaign Brief & Custom Rules'. Jika ada syarat akhir spesifik (seperti diakhiri kemenangan/victory/end-game):
1. Cari segmen transkrip paling relevan di bagian akhir sesi pertandingan (analisis kata penutup, seruan 'menang', 'kelar', 'push base', 'GG', atau segmen audio intens di menit-menit akhir).
2. Jadikan titik tersebut sebagai END_TIME (Anchor Akhir).
3. Tentukan START_TIME dengan menghitung mundur dari END_TIME sesuai durasi preset (misal 30-60 detik sebelumnya) sehingga momen setup war, wipeout, dan selebrasi kemenangan masuk ke dalam satu klip utuh.
4. Jika dalam transkrip tidak ada teks kata 'victory', cari stempel waktu di mana terdengar teriakan puncak terakhir sebelum video berakhir atau sebelum gameplay terhenti.
5. PENALTI: Berikan skor viral_score = 0 jika klip melanggar instruksi mandatory ending yang diberikan pengguna di Custom Rules!

Kriteria seleksi umum:
1. Memiliki Hook kuat di 3 detik pertama.
2. Memiliki narasi yang utuh atau poin klimaks yang berbobot.
3. Beri skor viralitas (1-100) dan alasan.

Format output WAJIB berupa JSON array murni tanpa markdown wrapper:
[
  {
    "title": "Short punchy title (match transcript language)",
    "hook": "Attention-grabbing opening hook (match transcript language)",
    "start_time": 754.20,
    "end_time": 784.50,
    "virality_score": 95,
    "reasoning": "Explanation why this clip is viral (match transcript language)"
  }
]
PENTING: Gunakan stempel waktu 'start_time' dan 'end_time' presisi angka float detik dari penanda waktu transkrip (contoh: 754.20), JANGAN membulatkan ke integer agar pemotongan FFmpeg presisi frame-accurate."""

MONTAGE_SYSTEM_PROMPT = """Anda adalah editor dan kurator video montage profesional untuk TikTok, Instagram Reels, dan YouTube Shorts.
Tugas Anda adalah merangkai video Multi-Cut Montage dengan menggabungkan beberapa momen penting atau klimaks berbeda dari transkrip video.

ATURAN KESELARASAN BAHASA (STRICT LANGUAGE ALIGNMENT - WAJIB):
1. Periksa bahasa utama dari teks transkrip audio sumber:
   - JIKA TRANSKRIP BERBAHASA INGGRIS (ENGLISH): Seluruh teks output: 'title', 'hook', 'reasoning', serta label deskripsi 'event' pada cuts WAJIB DITULIS DALAM BAHASA INGGRIS (English) yang tajam, punchy, viral, dan natural! JANGAN PERNAH menerjemahkan ke bahasa Indonesia!
   - JIKA TRANSKRIP BERBAHASA INDONESIA: Seluruh teks output: 'title', 'hook', 'reasoning', dan label 'event' WAJIB DITULIS DALAM BAHASA INDONESIA.
2. Selalu gunakan bahasa yang sama persis dengan bahasa asli pembicara pada transkrip sumber!

ATURAN UTAMA (ENFORCE MANDATORY CONSTRAINTS):
Periksa 'Campaign Brief & Custom Rules'. Jika ada syarat akhir spesifik (seperti diakhiri kemenangan/victory/end-game):
1. Cut terakhir (ending cut) WAJIB berupa segmen penutup/kemenangan pertandingan (analisis kata penutup, seruan 'menang', 'kelar', 'push base', 'GG', atau segmen puncak di menit-menit akhir).
2. Jika dalam transkrip tidak ada teks kata 'victory', cari stempel waktu di mana terdengar teriakan puncak terakhir sebelum video berakhir atau sebelum gameplay terhenti.
3. Rangkai cuts sebelumnya sebagai setup menuju cut klimaks akhir tersebut.
4. PENALTI: Berikan skor viral_score = 0 jika rangkaian cuts melanggar instruksi mandatory ending yang diberikan pengguna di Custom Rules!

Kriteria seleksi montage:
1. Pilih 2 sampai 5 potongan momen penting/menarik (cuts) dari bagian video yang berbeda.
2. Setiap cut memiliki deskripsi event/momen singkat (misal: "First Blood / War Turtle", "Lord Steal", "Wipeout & Base Push").
3. TOTAL akumulasi durasi dari seluruh cuts dalam satu montage HARUS berada di dalam rentang durasi yang diminta.
4. Beri skor viralitas (1-100).

Format output WAJIB berupa JSON array murni tanpa markdown wrapper:
[
  {
    "title": "Epic War & Comeback",
    "viral_score": 95,
    "mode": "montage",
    "cuts": [
      {"start": 124.0, "end": 139.5, "event": "First Blood / War Turtle"},
      {"start": 350.2, "end": 368.0, "event": "Lord Steal"},
      {"start": 520.0, "end": 542.5, "event": "Wipeout & Base Push"}
    ]
  }
]"""

def evaluate_viral_clips(
    endpoint_url: str,
    api_key: str,
    model: str,
    transcript: str,
    target_clip_count: int = 3,
    min_duration: float = 30.0,
    max_duration: float = 60.0,
    campaign_rules: str = "",
    clip_mode: str = "single",
    detected_language: Optional[str] = None
) -> List[ViralClipCandidate]:
    client = OpenAI(
        base_url=endpoint_url,
        api_key=api_key or "no-key-required"
    )

    lang_section = ""
    if detected_language:
        if detected_language.lower().startswith("en"):
            lang_section = (
                "\n[LANGUAGE MANDATE: SOURCE IS IN ENGLISH]\n"
                "The source video audio and transcript are in ENGLISH.\n"
                "All output fields ('title', 'hook', 'reasoning', and 'event') MUST BE WRITTEN IN PUNCHY, VIRAL ENGLISH.\n"
                "DO NOT translate into Indonesian!\n"
            )
        elif detected_language.lower().startswith("id"):
            lang_section = (
                "\n[LANGUAGE MANDATE: AUDIO BERBAHASA INDONESIA]\n"
                "Transkrip audio video sumber dalam BAHASA INDONESIA.\n"
                "Seluruh output ('title', 'hook', 'reasoning', dan 'event') WAJIB DITULIS DALAM BAHASA INDONESIA.\n"
            )

    rules_section = ""
    if campaign_rules and campaign_rules.strip():
        rules_section = f"""
CRITICAL CAMPAIGN RULES (User Guidelines):
{campaign_rules.strip()}

ATURAN UTAMA (ENFORCE MANDATORY CONSTRAINTS):
Periksa 'Campaign Brief & Custom Rules' di atas! Jika ada syarat akhir spesifik (seperti diakhiri kemenangan/victory/end-game):
1. Cari segmen transkrip paling relevan di bagian akhir sesi pertandingan (analisis kata penutup, seruan 'menang', 'kelar', 'push base', 'GG', atau segmen audio intens di menit-menit akhir).
2. Jadikan titik tersebut sebagai END_TIME (Anchor Akhir).
3. Tentukan START_TIME dengan menghitung mundur dari END_TIME sesuai durasi preset ({int(min_duration)} sampai {int(max_duration)} detik sebelumnya) sehingga momen setup war, wipeout, dan selebrasi kemenangan masuk ke dalam satu klip utuh.
4. Jika dalam transkrip tidak ada teks kata 'victory', cari stempel waktu di mana terdengar teriakan puncak terakhir sebelum video berakhir atau sebelum gameplay terhenti.
5. PENALTI KERAS: Berikan skor virality_score = 0 (atau viral_score = 0) jika segmen melanggar instruksi mandatory ending di atas!
Kamu WAJIB memilih dan memotong klip yang memenuhi aturan di atas.
"""

    is_montage = (clip_mode == "montage")

    if is_montage:
        system_content = MONTAGE_SYSTEM_PROMPT
        prompt = f"""Instruksi Pemilihan Multi-Cut Montage:
- Hasilkan tepat {target_clip_count} montage terbaik.
- Setiap montage menggabungkan beberapa momen (cuts) berbeda.
- Pastikan TOTAL akumulasi durasi dari seluruh cuts di setiap montage berada di dalam rentang {int(min_duration)} sampai {int(max_duration)} detik.{lang_section}{rules_section}

Transkrip Video:

{transcript}

PENGINGAT AKHIR (RECENCY BIAS):
Wajib patuhi ATURAN BAHASA: Jika transkrip berbahasa Inggris, tulis title/hook/reasoning/event dalam BAHASA INGGRIS. Jika bahasa Indonesia, tulis dalam BAHASA INDONESIA.
Patuhi CRITICAL CAMPAIGN RULES dan ATURAN UTAMA di atas jika ada syarat kemenangan/ending wajib."""
    else:
        system_content = SYSTEM_PROMPT
        prompt = f"""Instruksi Pemilihan Klip:
- Hasilkan tepat {target_clip_count} klip terbaik.
- Pastikan durasi setiap klip berada di dalam rentang {int(min_duration)} sampai {int(max_duration)} detik.{lang_section}{rules_section}

Transkrip Video:

{transcript}

PENGINGAT AKHIR (RECENCY BIAS):
Wajib patuhi ATURAN BAHASA: Jika transkrip berbahasa Inggris, tulis title/hook/reasoning dalam BAHASA INGGRIS. Jika bahasa Indonesia, tulis dalam BAHASA INDONESIA.
Patuhi CRITICAL CAMPAIGN RULES dan ATURAN UTAMA di atas jika ada syarat kemenangan/ending wajib."""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    content = response.choices[0].message.content or ""
    parsed = safe_extract_json(content)

    items = parsed.get("clips", parsed) if isinstance(parsed, dict) else parsed
    if not isinstance(items, list):
        items = [items]

    results: List[ViralClipCandidate] = []
    relaxed_results: List[ViralClipCandidate] = []

    lower_bound = max(5.0, min_duration - 5.0)
    upper_bound = max_duration + 5.0

    for item in items:
        if not isinstance(item, dict):
            continue

        v_score = int(item.get("viral_score", item.get("virality_score", 50)))
        if v_score <= 0:
            # Penalized candidate (score = 0), skip
            continue

        if is_montage or item.get("mode") == "montage" or "cuts" in item:
            cuts_raw = item.get("cuts", [])
            valid_cuts: List[MontageCut] = []
            for c in cuts_raw:
                if not isinstance(c, dict):
                    continue
                c_start = round(parse_to_seconds(c.get("start", c.get("start_time", 0))), 2)
                c_end = round(parse_to_seconds(c.get("end", c.get("end_time", 0))), 2)
                c_ev = str(c.get("event", c.get("title", "")))
                if c_end > c_start and (c_end - c_start) >= 2.0:
                    valid_cuts.append(MontageCut(start=c_start, end=c_end, event=c_ev))

            if len(valid_cuts) >= 2:
                total_dur = sum(c.end - c.start for c in valid_cuts)
                candidate = ViralClipCandidate(
                    title=str(item.get("title", "Montage Clip")),
                    hook=valid_cuts[0].event or str(item.get("hook", "")),
                    start_time=valid_cuts[0].start,
                    end_time=valid_cuts[-1].end,
                    virality_score=v_score,
                    reasoning=" | ".join(c.event for c in valid_cuts if c.event),
                    mode="montage",
                    cuts=valid_cuts
                )
                relaxed_results.append(candidate)
                if lower_bound <= total_dur <= upper_bound:
                    results.append(candidate)
                continue

        # Single clip processing (Default)
        start_sec = round(parse_to_seconds(item.get("start_time", 0)), 2)
        end_sec = round(parse_to_seconds(item.get("end_time", 0)), 2)
        dur = end_sec - start_sec

        if end_sec <= start_sec or dur < 5.0:
            continue

        candidate = ViralClipCandidate(
            title=str(item.get("title", "Untitled Clip")),
            hook=str(item.get("hook", "")),
            start_time=start_sec,
            end_time=end_sec,
            virality_score=v_score,
            reasoning=str(item.get("reasoning", "")),
            mode="single"
        )
        relaxed_results.append(candidate)

        # Enforce duration bounds
        if lower_bound <= dur <= upper_bound:
            results.append(candidate)

    # If strict filter eliminated everything, fallback to relaxed results
    final_list = results if results else relaxed_results
    final_list.sort(key=lambda x: x.virality_score, reverse=True)
    return final_list[:target_clip_count]
