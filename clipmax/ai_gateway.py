import json
import re
from typing import List, Dict, Any, Optional
import requests
from pydantic import BaseModel
from openai import OpenAI
from clipmax.config import parse_to_seconds

class ViralClipCandidate(BaseModel):
    title: str
    hook: str
    start_time: float
    end_time: float
    virality_score: int
    reasoning: str

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
Analisis transkrip berikut dan pilih segmen klip terbaik (durasi 30-60 detik).
Kriteria seleksi:
1. Memiliki Hook kuat di 3 detik pertama.
2. Memiliki narasi yang utuh atau poin klimaks yang berbobot.
3. Beri skor viralitas (1-100) dan alasan.

Format output WAJIB berupa JSON array murni tanpa markdown wrapper:
[
  {
    "title": "Judul singkat klip",
    "hook": "Kalimat pembuka pemikat perhatian",
    "start_time": "HH:MM:SS atau detik",
    "end_time": "HH:MM:SS atau detik",
    "virality_score": 95,
    "reasoning": "Penjelasan mengapa klip ini viral"
  }
]"""

def evaluate_viral_clips(
    transcript: str,
    endpoint_url: str,
    api_key: str = "",
    model: str = "default",
    max_clips: int = 5
) -> List[ViralClipCandidate]:
    client = OpenAI(
        base_url=endpoint_url,
        api_key=api_key or "no-key-required"
    )

    prompt = f"Transkrip Video:\n\n{transcript}\n\nPilih maksimal {max_clips} klip terbaik."

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
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
    for item in items:
        if not isinstance(item, dict):
            continue
        start_sec = parse_to_seconds(item.get("start_time", 0))
        end_sec = parse_to_seconds(item.get("end_time", 0))
        if end_sec <= start_sec or (end_sec - start_sec) < 5.0:
            continue
        results.append(
            ViralClipCandidate(
                title=str(item.get("title", "Untitled Clip")),
                hook=str(item.get("hook", "")),
                start_time=start_sec,
                end_time=end_sec,
                virality_score=int(item.get("virality_score", 50)),
                reasoning=str(item.get("reasoning", ""))
            )
        )

    results.sort(key=lambda x: x.virality_score, reverse=True)
    return results[:max_clips]
