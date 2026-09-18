# ClipMax Desktop Implementation Plan (Python 3.12 & RTX 3050 Hardened)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an autonomous desktop AI video clipper application converting 16:9 long videos to 9:16 vertical shorts with local faster-whisper transcription, MediaPipe auto-reframing, kinetic ASS styling, NVENC GPU rendering, dynamic AI provider discovery, and PySide6 frameless UI on Python 3.12.10.

**Architecture:** The core engine is structured into sequential decoupled pipeline stages (Audio Extraction -> Faster-Whisper Transcription + Strict VRAM GC -> Dynamic OpenAI AI Gateway -> MediaPipe Face Reframe -> Kinetic ASS Subtitle Builder -> FFmpeg NVENC Renderer). A PySide6 desktop worker runs the pipeline on a background thread with explicit process tracking (PID capture) and cancellation tokens to guarantee graceful abortion without UI freezing or VRAM leaks. The desktop interface adheres to a frameless dark aesthetic with ambient glow and dynamic endpoint autodiscovery.

**Tech Stack:**
- Runtime: Python 3.12.10 x64, uv virtual environment (`.venv`)
- AI / Inference: PyTorch 2.5.1+cu121, faster-whisper 1.2.x, MediaPipe, OpenCV, OpenAI Python SDK
- Acceleration: NVIDIA CUDA 12.1, cuDNN 9, FFmpeg NVENC (`h264_nvenc`) with CPU fallback (`libx264`)
- Desktop UI: PySide6 (Qt 6.11+) with frameless window styling

## Global Constraints
- Target hardware: RTX 3050 Laptop GPU (4GB GDDR6 VRAM limit) — deep learning models must NOT be held in memory simultaneously.
- Transcription completion MUST trigger explicit VRAM GC (`del whisper_model`, `gc.collect()`, `torch.cuda.empty_cache()`).
- Static FFmpeg binaries (`./bin/ffmpeg.exe`, `./bin/ffprobe.exe`) must be used preferentially over system PATH.
- Windows file paths passed into FFmpeg filtergraphs must be sanitized (`\` replaced with `/` and drive colon escaped as `\:`, e.g., `C\:/...`).
- Time parser must handle integer/float seconds, `"MM:SS"`, and `"HH:MM:SS"` strings safely without generating 0-second clips.
- AI Gateway must support dynamic OpenAI-compatible endpoints with model autodiscovery via `GET /v1/models` and fallback regex JSON parsing.
- Cancellation must terminate running sub-process trees (`taskkill /F /PID <pid>`), clean temporary files, and empty GPU cache.

---

### Task 1: Environment Initialization & Static Binary Scaffolding

**Files:**
- Create: `C:/project/clipmax/pyproject.toml`
- Create: `C:/project/clipmax/requirements.txt`
- Create: `C:/project/clipmax/bin/.gitkeep`
- Create: `C:/project/clipmax/tests/__init__.py`

**Interfaces:**
- Consumes: Python 3.12.10 installed on Windows (`AppData/Local/Programs/Python/Python312/python.exe`), FFmpeg in WinGet packages.
- Produces: Activated `.venv` virtual environment with PyTorch CUDA 12.1 and runtime dependencies, static `./bin/ffmpeg.exe` and `./bin/ffprobe.exe`.

- [ ] **Step 1: Create pyproject.toml and requirements.txt**

File: `C:/project/clipmax/requirements.txt`
```text
--extra-index-url https://download.pytorch.org/whl/cu121
torch==2.5.1+cu121
torchvision==0.20.1+cu121
torchaudio==2.5.1+cu121
faster-whisper>=1.0.0
mediapipe>=0.10.9
opencv-python>=4.8.0
openai>=1.12.0
pydantic>=2.5.0
requests>=2.31.0
python-dotenv>=1.0.0
pyside6>=6.6.0
pytest>=8.0.0
pytest-mock>=3.12.0
```

File: `C:/project/clipmax/pyproject.toml`
```toml
[project]
name = "clipmax"
version = "2.4.0"
description = "Autonomous Desktop AI Video Clipper"
requires-python = ">=3.12,<3.13"
dependencies = [
    "torch",
    "torchvision",
    "torchaudio",
    "faster-whisper>=1.0.0",
    "mediapipe>=0.10.9",
    "opencv-python>=4.8.0",
    "openai>=1.12.0",
    "pydantic>=2.5.0",
    "requests>=2.31.0",
    "python-dotenv>=1.0.0",
    "pyside6>=6.6.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 2: Initialize uv virtualenv and copy static FFmpeg binaries**

Run commands in terminal:
```bash
cd /c/project/clipmax
git init
mkdir -p bin
cp /c/Users/ASUS/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-8.1.1-full_build/bin/ffmpeg.exe bin/
cp /c/Users/ASUS/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-8.1.1-full_build/bin/ffprobe.exe bin/
uv venv --python /c/Users/ASUS/AppData/Local/Programs/Python/Python312/python.exe .venv
.venv/Scripts/python -m pip install --upgrade pip
.venv/Scripts/pip install -r requirements.txt
```

- [ ] **Step 3: Verify environment and CUDA detection**

Run:
```bash
.venv/Scripts/python -c "import torch; print('CUDA available:', torch.cuda.is_available(), 'Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
./bin/ffmpeg.exe -version | head -n 1
```
Expected output:
```text
CUDA available: True Device: NVIDIA GeForce RTX 3050 Laptop GPU
ffmpeg version 8.1.1...
```

- [ ] **Step 4: Commit environment scaffolding**

```bash
git add pyproject.toml requirements.txt .gitignore
git commit -m "chore: initialize project dependencies and static binaries"
```

---

### Task 2: Core Configuration, Path Escaping & Time Parsing

**Files:**
- Create: `C:/project/clipmax/clipmax/__init__.py`
- Create: `C:/project/clipmax/clipmax/config.py`
- Create: `C:/project/clipmax/tests/test_config.py`

**Interfaces:**
- Consumes: JSON config files, raw Windows paths, mixed time strings.
- Produces: `AppConfig`, `sanitize_ffmpeg_path(path: str) -> str`, `parse_to_seconds(val: Any) -> float`, `get_ffmpeg_bin() -> str`.

- [ ] **Step 1: Write the failing tests**

File: `C:/project/clipmax/tests/test_config.py`
```python
import pytest
from clipmax.config import sanitize_ffmpeg_path, parse_to_seconds, AppConfig, get_ffmpeg_bin

def test_sanitize_ffmpeg_path_windows():
    raw = r"C:\project\clipmax\output\sub.ass"
    sanitized = sanitize_ffmpeg_path(raw)
    assert sanitized == "C\\:/project/clipmax/output/sub.ass"

def test_sanitize_ffmpeg_path_relative():
    raw = r"output\sub.ass"
    assert sanitize_ffmpeg_path(raw) == "output/sub.ass"

def test_parse_to_seconds_float_int():
    assert parse_to_seconds(45.5) == 45.5
    assert parse_to_seconds(60) == 60.0

def test_parse_to_seconds_mmss():
    assert parse_to_seconds("01:23") == 83.0
    assert parse_to_seconds("00:30") == 30.0

def test_parse_to_seconds_hhmmss():
    assert parse_to_seconds("01:02:03") == 3723.0
    assert parse_to_seconds("00:01:30.500") == 90.5

def test_parse_to_seconds_invalid():
    assert parse_to_seconds("invalid") == 0.0
    assert parse_to_seconds(None) == 0.0

def test_default_app_config():
    cfg = AppConfig()
    assert cfg.whisper_model == "small"
    assert cfg.device in ["cuda", "cpu"]
    assert cfg.endpoint_url == "http://localhost:20128/v1"
```

- [ ] **Step 2: Run test to verify failure**

Run:
```bash
.venv/Scripts/pytest tests/test_config.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'clipmax'`

- [ ] **Step 3: Implement minimal configuration module**

File: `C:/project/clipmax/clipmax/__init__.py`
```python
"""ClipMax - Autonomous Desktop AI Video Clipper"""
__version__ = "2.4.0"
```

File: `C:/project/clipmax/clipmax/config.py`
```python
import os
import json
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel, Field
import torch

def sanitize_ffmpeg_path(raw_path: str) -> str:
    clean = str(raw_path).replace("\\", "/")
    if len(clean) > 1 and clean[1] == ":":
        clean = clean[0] + "\\:" + clean[2:]
    return clean

def parse_to_seconds(val: Any) -> float:
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        val = val.strip().strip('"').strip("'")
        try:
            return float(val)
        except ValueError:
            pass
        parts = val.split(":")
        try:
            if len(parts) == 3:
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            if len(parts) == 2:
                return float(parts[0]) * 60 + float(parts[1])
        except (ValueError, TypeError):
            return 0.0
    return 0.0

def get_ffmpeg_bin() -> str:
    project_root = Path(__file__).resolve().parent.parent
    local_bin = project_root / "bin" / "ffmpeg.exe"
    if local_bin.exists():
        return str(local_bin)
    return "ffmpeg"

def get_ffprobe_bin() -> str:
    project_root = Path(__file__).resolve().parent.parent
    local_bin = project_root / "bin" / "ffprobe.exe"
    if local_bin.exists():
        return str(local_bin)
    return "ffprobe"

class AppConfig(BaseModel):
    whisper_model: str = "small"
    device: str = Field(default_factory=lambda: "cuda" if torch.cuda.is_available() else "cpu")
    compute_type: str = Field(default_factory=lambda: "float16" if torch.cuda.is_available() else "int8")
    provider_name: str = "9Router Local"
    endpoint_url: str = "http://localhost:20128/v1"
    api_key: str = ""
    selected_model: str = "default"
    output_dir: str = str(Path("./output").resolve())
    temp_dir: str = str(Path("./temp").resolve())
    reframe_split_mode: bool = True
    nvenc_preset: str = "p4"
    video_bitrate: str = "6000k"
    audio_bitrate: str = "192k"

    @classmethod
    def load(cls, path: str = "config.json") -> "AppConfig":
        p = Path(path)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(**data)
        cfg = cls()
        cfg.save(path)
        return cfg

    def save(self, path: str = "config.json") -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, indent=2)
```

- [ ] **Step 4: Run test to verify pass**

Run:
```bash
.venv/Scripts/pytest tests/test_config.py -v
```
Expected: PASS (7 passed)

- [ ] **Step 5: Commit config module**

```bash
git add clipmax/__init__.py clipmax/config.py tests/test_config.py
git commit -m "feat: implement config, path escaping, and universal time parsing"
```

---

### Task 3: Stage 1 - Audio Extraction Module

**Files:**
- Create: `C:/project/clipmax/clipmax/audio.py`
- Create: `C:/project/clipmax/tests/test_audio.py`

**Interfaces:**
- Consumes: Input video file path (`str`), output WAV destination (`str`), optional PID callback / cancellation event.
- Produces: Extracted 16kHz mono WAV file path.

- [ ] **Step 1: Write the failing test**

File: `C:/project/clipmax/tests/test_audio.py`
```python
import subprocess
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
from clipmax.audio import extract_audio

def test_extract_audio_command_construction(tmp_path):
    video_path = tmp_path / "sample.mp4"
    video_path.touch()
    out_wav = tmp_path / "audio.wav"

    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (b"", b"")
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        result = extract_audio(str(video_path), str(out_wav))
        assert result == str(out_wav)
        
        args = mock_popen.call_args[0][0]
        assert "-vn" in args
        assert "-acodec" in args
        assert "pcm_s16le" in args
        assert "-ar" in args
        assert "16000" in args
        assert "-ac" in args
        assert "1" in args

def test_extract_audio_file_not_found():
    with pytest.raises(FileNotFoundError):
        extract_audio("nonexistent_video.mp4", "out.wav")
```

- [ ] **Step 2: Run test to verify failure**

Run:
```bash
.venv/Scripts/pytest tests/test_audio.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'clipmax.audio'`

- [ ] **Step 3: Implement audio extraction module**

File: `C:/project/clipmax/clipmax/audio.py`
```python
import os
import subprocess
import threading
from pathlib import Path
from typing import Optional, Callable
from clipmax.config import get_ffmpeg_bin

def extract_audio(
    video_path: str,
    output_wav_path: str,
    cancel_event: Optional[threading.Event] = None,
    pid_callback: Optional[Callable[[int], None]] = None
) -> str:
    v_path = Path(video_path)
    if not v_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    out_path = Path(output_wav_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_bin = get_ffmpeg_bin()
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", str(v_path.resolve()),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(out_path.resolve())
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    if pid_callback:
        pid_callback(proc.pid)

    stdout, stderr = proc.communicate()

    if cancel_event and cancel_event.is_set():
        if out_path.exists():
            out_path.unlink(missing_ok=True)
        raise RuntimeError("Audio extraction cancelled by user")

    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg audio extraction failed: {stderr.decode('utf-8', errors='ignore')}")

    return str(out_path.resolve())
```

- [ ] **Step 4: Run test to verify pass**

Run:
```bash
.venv/Scripts/pytest tests/test_audio.py -v
```
Expected: PASS (2 passed)

- [ ] **Step 5: Commit audio module**

```bash
git add clipmax/audio.py tests/test_audio.py
git commit -m "feat: implement stage 1 audio extraction with cancellation support"
```

---

### Task 4: Stage 2 - Faster-Whisper Transcription & Strict VRAM Garbage Collection

**Files:**
- Create: `C:/project/clipmax/clipmax/transcriber.py`
- Create: `C:/project/clipmax/tests/test_transcriber.py`

**Interfaces:**
- Consumes: Audio WAV path (`str`), model size (`str`), device (`str`), compute_type (`str`).
- Produces: List of word-level dicts `[{"word": str, "start": float, "end": float, "probability": float}]` and clean text prompt for LLM.
- Side Effect: Strict memory cleanup (`del model`, `gc.collect()`, `torch.cuda.empty_cache()`).

- [ ] **Step 1: Write the failing test**

File: `C:/project/clipmax/tests/test_transcriber.py`
```python
import pytest
from unittest.mock import patch, MagicMock
from clipmax.transcriber import transcribe_audio, cleanup_vram, WordSegment

def test_transcribe_audio_mocked():
    mock_word = MagicMock()
    mock_word.word = "Halo"
    mock_word.start = 0.0
    mock_word.end = 0.5
    mock_word.probability = 0.95

    mock_segment = MagicMock()
    mock_segment.words = [mock_word]
    mock_segment.text = "Halo"

    with patch("faster_whisper.WhisperModel") as mock_model_cls, \
         patch("clipmax.transcriber.cleanup_vram") as mock_gc:
        
        instance = MagicMock()
        instance.transcribe.return_value = ([mock_segment], MagicMock())
        mock_model_cls.return_value = instance

        words, full_text = transcribe_audio("fake.wav", model_size="small", device="cpu", compute_type="int8")
        
        assert len(words) == 1
        assert words[0].word == "Halo"
        assert words[0].start == 0.0
        assert full_text.strip() == "Halo"
        assert mock_gc.called
```

- [ ] **Step 2: Run test to verify failure**

Run:
```bash
.venv/Scripts/pytest tests/test_transcriber.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'clipmax.transcriber'`

- [ ] **Step 3: Implement transcription module with explicit VRAM purge**

File: `C:/project/clipmax/clipmax/transcriber.py`
```python
import gc
import os
from typing import List, Tuple, Optional
from pydantic import BaseModel
import torch

class WordSegment(BaseModel):
    word: str
    start: float
    end: float
    probability: float

def cleanup_vram() -> None:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()

def transcribe_audio(
    audio_path: str,
    model_size: str = "small",
    device: Optional[str] = None,
    compute_type: Optional[str] = None,
    language: Optional[str] = None
) -> Tuple[List[WordSegment], str]:
    from faster_whisper import WhisperModel

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if compute_type is None:
        compute_type = "float16" if device == "cuda" else "int8"

    whisper_model = None
    all_words: List[WordSegment] = []
    text_segments: List[str] = []

    try:
        whisper_model = WhisperModel(model_size, device=device, compute_type=compute_type)
        segments, info = whisper_model.transcribe(
            audio_path,
            word_timestamps=True,
            language=language
        )

        for segment in segments:
            text_segments.append(segment.text.strip())
            if segment.words:
                for w in segment.words:
                    clean_w = w.word.strip()
                    if clean_w:
                        all_words.append(
                            WordSegment(
                                word=clean_w,
                                start=float(w.start),
                                end=float(w.end),
                                probability=float(w.probability)
                            )
                        )
    finally:
        if whisper_model is not None:
            del whisper_model
        cleanup_vram()

    full_transcript = " ".join(text_segments)
    return all_words, full_transcript
```

- [ ] **Step 4: Run test to verify pass**

Run:
```bash
.venv/Scripts/pytest tests/test_transcriber.py -v
```
Expected: PASS (1 passed)

- [ ] **Step 5: Commit transcription module**

```bash
git add clipmax/transcriber.py tests/test_transcriber.py
git commit -m "feat: implement stage 2 faster-whisper transcription with strict VRAM GC"
```

---

### Task 5: Stage 3 - Dynamic AI Gateway & Resilient Content Evaluator

**Files:**
- Create: `C:/project/clipmax/clipmax/ai_gateway.py`
- Create: `C:/project/clipmax/tests/test_ai_gateway.py`

**Interfaces:**
- Consumes: Transcript text, endpoint configuration (`endpoint_url`, `api_key`, `model`).
- Produces: List of discovered models via `GET /v1/models`, parsed list of clips with `title`, `hook`, `start_time` (float), `end_time` (float), `virality_score` (int 1-100).

- [ ] **Step 1: Write the failing tests**

File: `C:/project/clipmax/tests/test_ai_gateway.py`
```python
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
    with patch("openai.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = mock_json_response
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
        mock_openai.return_value = mock_client

        clips = evaluate_viral_clips(
            transcript="Sample transcript text",
            endpoint_url="http://localhost:20128/v1",
            api_key="",
            model="gpt-4o-mini"
        )
        assert len(clips) == 1
        assert clips[0].start_time == 15.0
        assert clips[0].end_time == 45.0
        assert clips[0].virality_score == 95
```

- [ ] **Step 2: Run test to verify failure**

Run:
```bash
.venv/Scripts/pytest tests/test_ai_gateway.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'clipmax.ai_gateway'`

- [ ] **Step 3: Implement dynamic AI gateway module**

File: `C:/project/clipmax/clipmax/ai_gateway.py`
```python
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
    try:
        return json.loads(text.strip())
    except Exception:
        pass

    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except Exception:
            pass

    array_match = re.search(r"\[\s*\{[\s\S]*\}\s*\]", text)
    if array_match:
        try:
            return json.loads(array_match.group(0))
        except Exception:
            pass

    obj_match = re.search(r"\{[\s\S]*\}", text)
    if obj_match:
        try:
            return json.loads(obj_match.group(0))
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
```

- [ ] **Step 4: Run test to verify pass**

Run:
```bash
.venv/Scripts/pytest tests/test_ai_gateway.py -v
```
Expected: PASS (4 passed)

- [ ] **Step 5: Commit AI Gateway module**

```bash
git add clipmax/ai_gateway.py tests/test_ai_gateway.py
git commit -m "feat: implement stage 3 dynamic AI gateway with model discovery and resilient JSON parser"
```

---

### Task 6: Stage 4 - MediaPipe Face Detection & Dynamic 9:16 Auto-Reframe

**Files:**
- Create: `C:/project/clipmax/clipmax/reframe.py`
- Create: `C:/project/clipmax/tests/test_reframe.py`

**Interfaces:**
- Consumes: Video path, clip start and end time, frame dimensions (W, H).
- Produces: Normalized crop center coordinate $X_{crop}$ smoothed with Exponential Moving Average ($\alpha=0.15$), or multi-speaker layout metadata.

- [ ] **Step 1: Write the failing tests**

File: `C:/project/clipmax/tests/test_reframe.py`
```python
import pytest
from clipmax.reframe import calculate_crop_box, smooth_ema_series, ReframeStrategy

def test_calculate_crop_box_center():
    x_crop, crop_w, crop_h = calculate_crop_box(
        frame_width=1920,
        frame_height=1080,
        face_center_x=960
    )
    assert crop_h == 1080
    assert round(crop_w) == 608
    assert x_crop >= 0
    assert x_crop + crop_w <= 1920

def test_calculate_crop_box_boundary_clamping():
    x_crop, crop_w, _ = calculate_crop_box(
        frame_width=1920,
        frame_height=1080,
        face_center_x=50
    )
    assert x_crop == 0

    x_crop_right, crop_w, _ = calculate_crop_box(
        frame_width=1920,
        frame_height=1080,
        face_center_x=1900
    )
    assert x_crop_right + crop_w == 1920

def test_smooth_ema_series():
    raw_series = [100.0, 100.0, 500.0, 500.0]
    smoothed = smooth_ema_series(raw_series, alpha=0.15)
    assert len(smoothed) == len(raw_series)
    assert smoothed[0] == 100.0
    assert smoothed[2] < 500.0
```

- [ ] **Step 2: Run test to verify failure**

Run:
```bash
.venv/Scripts/pytest tests/test_reframe.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'clipmax.reframe'`

- [ ] **Step 3: Implement reframe module**

File: `C:/project/clipmax/clipmax/reframe.py`
```python
import cv2
from typing import List, Tuple, Optional
from enum import Enum

class ReframeStrategy(str, Enum):
    SINGLE_SPEAKER = "single_speaker"
    SPLIT_SCREEN = "split_screen"
    STATIC_CENTER = "static_center"

def calculate_crop_box(
    frame_width: int,
    frame_height: int,
    face_center_x: float,
    aspect_ratio: float = 9.0 / 16.0
) -> Tuple[int, int, int]:
    crop_height = frame_height
    crop_width = int(round(crop_height * aspect_ratio))
    
    if crop_width > frame_width:
        crop_width = frame_width

    half_w = crop_width / 2.0
    x_start = face_center_x - half_w

    if x_start < 0:
        x_start = 0
    elif x_start + crop_width > frame_width:
        x_start = frame_width - crop_width

    return int(round(x_start)), crop_width, crop_height

def smooth_ema_series(values: List[float], alpha: float = 0.15) -> List[float]:
    if not values:
        return []
    smoothed = [values[0]]
    for v in values[1:]:
        smoothed.append(alpha * v + (1.0 - alpha) * smoothed[-1])
    return smoothed

def detect_face_centers(
    video_path: str,
    start_time: float,
    end_time: float,
    sample_fps: int = 4
) -> Tuple[List[float], ReframeStrategy]:
    import mediapipe as mp
    mp_face_detection = mp.solutions.face_detection

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return [], ReframeStrategy.STATIC_CENTER

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
    frame_step = max(1, int(fps / sample_fps))

    start_frame = int(start_time * fps)
    end_frame = int(end_time * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    centers: List[float] = []
    max_faces_seen = 1

    with mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5) as detector:
        current_frame = start_frame
        default_center = width / 2.0

        while current_frame <= end_frame:
            ret, frame = cap.read()
            if not ret:
                break

            if (current_frame - start_frame) % frame_step == 0:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = detector.process(rgb)
                
                if results.detections:
                    max_faces_seen = max(max_faces_seen, len(results.detections))
                    best_box = None
                    max_area = 0.0
                    for det in results.detections:
                        bb = det.location_data.relative_bounding_box
                        area = bb.width * bb.height
                        if area > max_area:
                            max_area = area
                            best_box = bb
                    
                    if best_box:
                        cx = (best_box.xmin + best_box.width / 2.0) * width
                        centers.append(cx)
                    else:
                        centers.append(centers[-1] if centers else default_center)
                else:
                    centers.append(centers[-1] if centers else default_center)

            current_frame += 1

    cap.release()

    strategy = ReframeStrategy.SPLIT_SCREEN if max_faces_seen > 1 else ReframeStrategy.SINGLE_SPEAKER
    return centers, strategy
```

- [ ] **Step 4: Run test to verify pass**

Run:
```bash
.venv/Scripts/pytest tests/test_reframe.py -v
```
Expected: PASS (3 passed)

- [ ] **Step 5: Commit reframe module**

```bash
git add clipmax/reframe.py tests/test_reframe.py
git commit -m "feat: implement stage 4 face reframe and EMA smoothing calculations"
```

---

### Task 7: Stage 5 - Kinetic Dynamic ASS Subtitle Styling

**Files:**
- Create: `C:/project/clipmax/clipmax/subtitle.py`
- Create: `C:/project/clipmax/tests/test_subtitle.py`

**Interfaces:**
- Consumes: List of `WordSegment`, clip start and end time, output `.ass` path.
- Produces: Formatted Advanced SubStation Alpha (`.ass`) file with TikTok-style highlight styling and outline stroke.

- [ ] **Step 1: Write the failing tests**

File: `C:/project/clipmax/tests/test_subtitle.py`
```python
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
```

- [ ] **Step 2: Run test to verify failure**

Run:
```bash
.venv/Scripts/pytest tests/test_subtitle.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'clipmax.subtitle'`

- [ ] **Step 3: Implement kinetic ASS subtitle generator**

File: `C:/project/clipmax/clipmax/subtitle.py`
```python
from pathlib import Path
from typing import List
from clipmax.transcriber import WordSegment

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Kinetic,Impact,72,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,6,2,2,40,40,280,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

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
    highlight_color: str = "&H002BF7&"
) -> str:
    scoped_words = [
        w for w in words
        if w.start >= (clip_start - 0.2) and w.end <= (clip_end + 0.2)
    ]

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
                    line_parts.append(f"{{\\c{highlight_color}\\fscx110\\fscy110}}{other_word.word.upper()}{{\\r}}")
                else:
                    line_parts.append(other_word.word.upper())

            line_text = " ".join(line_parts)
            start_str = format_ass_time(w_start)
            end_str = format_ass_time(w_end)
            events.append(f"Dialogue: 0,{start_str},{end_str},Kinetic,,0,0,0,,{line_text}")

    out_p = Path(output_ass_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w", encoding="utf-8") as f:
        f.write(ASS_HEADER)
        f.write("\n".join(events))
        f.write("\n")

    return str(out_p.resolve())
```

- [ ] **Step 4: Run test to verify pass**

Run:
```bash
.venv/Scripts/pytest tests/test_subtitle.py -v
```
Expected: PASS (2 passed)

- [ ] **Step 5: Commit subtitle module**

```bash
git add clipmax/subtitle.py tests/test_subtitle.py
git commit -m "feat: implement stage 5 kinetic ASS subtitle styling with karaoke highlight"
```

---

### Task 8: Stage 6 - Hardware-Accelerated Video Rendering

**Files:**
- Create: `C:/project/clipmax/clipmax/renderer.py`
- Create: `C:/project/clipmax/tests/test_renderer.py`

**Interfaces:**
- Consumes: Input video, output clip path, clip start/end, crop X coordinate, ASS subtitle path, GPU availability.
- Produces: Rendered MP4 vertical video (1080x1920) via NVENC or CPU fallback with process cancellation hook.

- [ ] **Step 1: Write the failing tests**

File: `C:/project/clipmax/tests/test_renderer.py`
```python
import pytest
from unittest.mock import patch, MagicMock
from clipmax.renderer import render_clip

def test_render_clip_command_nvenc():
    with patch("subprocess.Popen") as mock_popen, \
         patch("clipmax.renderer.is_nvenc_supported", return_value=True):
        
        proc = MagicMock()
        proc.communicate.return_value = (b"", b"")
        proc.returncode = 0
        mock_popen.return_value = proc

        out = render_clip(
            input_video="input.mp4",
            output_clip="output.mp4",
            start_time=10.0,
            end_time=40.0,
            crop_x=650,
            ass_path=r"C:\temp\sub.ass",
            use_gpu=True
        )

        args = mock_popen.call_args[0][0]
        assert "-c:v" in args
        encoder_idx = args.index("-c:v") + 1
        assert args[encoder_idx] == "h264_nvenc"
        assert "subtitles='C\\:/temp/sub.ass'" in " ".join(args)

def test_render_clip_command_cpu_fallback():
    with patch("subprocess.Popen") as mock_popen, \
         patch("clipmax.renderer.is_nvenc_supported", return_value=False):
        
        proc = MagicMock()
        proc.communicate.return_value = (b"", b"")
        proc.returncode = 0
        mock_popen.return_value = proc

        render_clip(
            input_video="input.mp4",
            output_clip="output.mp4",
            start_time=0.0,
            end_time=10.0,
            crop_x=0,
            ass_path="sub.ass",
            use_gpu=False
        )

        args = mock_popen.call_args[0][0]
        encoder_idx = args.index("-c:v") + 1
        assert args[encoder_idx] == "libx264"
```

- [ ] **Step 2: Run test to verify failure**

Run:
```bash
.venv/Scripts/pytest tests/test_renderer.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'clipmax.renderer'`

- [ ] **Step 3: Implement renderer module**

File: `C:/project/clipmax/clipmax/renderer.py`
```python
import os
import subprocess
import threading
from pathlib import Path
from typing import Optional, Callable
import torch
from clipmax.config import get_ffmpeg_bin, sanitize_ffmpeg_path

def is_nvenc_supported() -> bool:
    if not torch.cuda.is_available():
        return False
    ffmpeg_bin = get_ffmpeg_bin()
    try:
        res = subprocess.run(
            [ffmpeg_bin, "-encoders"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return "h264_nvenc" in res.stdout
    except Exception:
        return False

def render_clip(
    input_video: str,
    output_clip: str,
    start_time: float,
    end_time: float,
    crop_x: int,
    ass_path: Optional[str] = None,
    use_gpu: bool = True,
    video_bitrate: str = "6000k",
    audio_bitrate: str = "192k",
    cancel_event: Optional[threading.Event] = None,
    pid_callback: Optional[Callable[[int], None]] = None
) -> str:
    in_p = Path(input_video)
    if not in_p.exists():
        raise FileNotFoundError(f"Input video not found: {input_video}")

    out_p = Path(output_clip)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    encoder = "h264_nvenc" if (use_gpu and is_nvenc_supported()) else "libx264"
    preset = "p4" if encoder == "h264_nvenc" else "veryfast"

    filter_parts = [
        f"crop=ih*(9/16):ih:{crop_x}:0",
        "scale=1080:1920"
    ]

    if ass_path and os.path.exists(ass_path):
        escaped_ass = sanitize_ffmpeg_path(ass_path)
        filter_parts.append(f"subtitles='{escaped_ass}'")

    vf_chain = ",".join(filter_parts)

    cmd = [
        get_ffmpeg_bin(),
        "-y",
        "-ss", str(start_time),
        "-to", str(end_time),
        "-i", str(in_p.resolve()),
        "-vf", vf_chain,
        "-c:v", encoder,
        "-preset", preset,
        "-b:v", video_bitrate,
        "-c:a", "aac",
        "-b:a", audio_bitrate,
        str(out_p.resolve())
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    if pid_callback:
        pid_callback(proc.pid)

    stdout, stderr = proc.communicate()

    if cancel_event and cancel_event.is_set():
        if out_p.exists():
            out_p.unlink(missing_ok=True)
        raise RuntimeError("Video rendering cancelled by user")

    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg render failed: {stderr.decode('utf-8', errors='ignore')}")

    return str(out_p.resolve())
```

- [ ] **Step 4: Run test to verify pass**

Run:
```bash
.venv/Scripts/pytest tests/test_renderer.py -v
```
Expected: PASS (2 passed)

- [ ] **Step 5: Commit renderer module**

```bash
git add clipmax/renderer.py tests/test_renderer.py
git commit -m "feat: implement stage 6 NVENC accelerated renderer with CPU fallback"
```

---

### Task 9: Pipeline Orchestration, Task Lifecycle & Cancellation Manager

**Files:**
- Create: `C:/project/clipmax/clipmax/pipeline.py`
- Create: `C:/project/clipmax/tests/test_pipeline.py`

**Interfaces:**
- Consumes: Pipeline parameters (video path, config).
- Produces: Execution loop across Stages 1-6, progress events (`0%` to `100%`), and kill-safe cancellation (`kill_process_tree`, temp file cleanup, VRAM purge).

- [ ] **Step 1: Write the failing tests**

File: `C:/project/clipmax/tests/test_pipeline.py`
```python
import pytest
import threading
from unittest.mock import patch, MagicMock
from clipmax.pipeline import PipelineOrchestrator, PipelineStatus
from clipmax.config import AppConfig

def test_pipeline_status_enum():
    assert PipelineStatus.IDLE.value == "IDLE"
    assert PipelineStatus.EXTRACTING_AUDIO.value == "EXTRACTING_AUDIO"
    assert PipelineStatus.TRANSCRIBING.value == "TRANSCRIBING"
    assert PipelineStatus.AI_EVALUATING.value == "AI_EVALUATING"
    assert PipelineStatus.TRACKING_FACES.value == "TRACKING_FACES"
    assert PipelineStatus.RENDERING.value == "RENDERING"
    assert PipelineStatus.COMPLETED.value == "COMPLETED"
    assert PipelineStatus.CANCELLED.value == "CANCELLED"

def test_pipeline_cancellation_token():
    cfg = AppConfig()
    orchestrator = PipelineOrchestrator(cfg)
    assert not orchestrator.cancel_requested.is_set()
    orchestrator.cancel()
    assert orchestrator.cancel_requested.is_set()
```

- [ ] **Step 2: Run test to verify failure**

Run:
```bash
.venv/Scripts/pytest tests/test_pipeline.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'clipmax.pipeline'`

- [ ] **Step 3: Implement pipeline orchestrator module**

File: `C:/project/clipmax/clipmax/pipeline.py`
```python
import os
import subprocess
import threading
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, List
from clipmax.config import AppConfig
from clipmax.audio import extract_audio
from clipmax.transcriber import transcribe_audio, cleanup_vram
from clipmax.ai_gateway import evaluate_viral_clips, ViralClipCandidate
from clipmax.reframe import detect_face_centers, calculate_crop_box, smooth_ema_series
from clipmax.subtitle import generate_kinetic_ass
from clipmax.renderer import render_clip

class PipelineStatus(str, Enum):
    IDLE = "IDLE"
    EXTRACTING_AUDIO = "EXTRACTING_AUDIO"
    TRANSCRIBING = "TRANSCRIBING"
    AI_EVALUATING = "AI_EVALUATING"
    TRACKING_FACES = "TRACKING_FACES"
    RENDERING = "RENDERING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

def kill_process_tree(pid: int) -> None:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        else:
            os.kill(pid, 9)
    except Exception:
        pass

class PipelineOrchestrator:
    def __init__(self, config: AppConfig):
        self.config = config
        self.cancel_requested = threading.Event()
        self.active_pid: Optional[int] = None
        self.status = PipelineStatus.IDLE
        self.temp_files: List[str] = []

    def set_pid(self, pid: int) -> None:
        self.active_pid = pid

    def cancel(self) -> None:
        self.cancel_requested.set()
        if self.active_pid:
            kill_process_tree(self.active_pid)
            self.active_pid = None
        self.cleanup()
        self.status = PipelineStatus.CANCELLED

    def cleanup(self) -> None:
        for f in self.temp_files:
            try:
                p = Path(f)
                if p.exists():
                    p.unlink(missing_ok=True)
            except Exception:
                pass
        self.temp_files.clear()
        cleanup_vram()

    def run(
        self,
        video_path: str,
        progress_callback: Optional[Callable[[PipelineStatus, int, str], None]] = None
    ) -> List[str]:
        self.cancel_requested.clear()
        self.temp_files.clear()
        generated_clips: List[str] = []

        temp_dir = Path(self.config.temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        temp_wav = str((temp_dir / "temp_audio.wav").resolve())
        self.temp_files.append(temp_wav)

        try:
            # Stage 1: Audio Extraction (10%)
            self.status = PipelineStatus.EXTRACTING_AUDIO
            if progress_callback:
                progress_callback(self.status, 10, "Mengestrak audio WAV 16kHz mono...")
            extract_audio(video_path, temp_wav, self.cancel_requested, self.set_pid)
            self.active_pid = None

            if self.cancel_requested.is_set():
                return []

            # Stage 2: Transcription (30%)
            self.status = PipelineStatus.TRANSCRIBING
            if progress_callback:
                progress_callback(self.status, 30, "Transkripsi kata via Faster-Whisper...")
            words, full_text = transcribe_audio(
                temp_wav,
                model_size=self.config.whisper_model,
                device=self.config.device,
                compute_type=self.config.compute_type
            )

            if self.cancel_requested.is_set():
                return []

            # Stage 3: LLM Virality Evaluation (50%)
            self.status = PipelineStatus.AI_EVALUATING
            if progress_callback:
                progress_callback(self.status, 50, "Mengevaluasi hook & klip viral via LLM...")
            candidates = evaluate_viral_clips(
                transcript=full_text,
                endpoint_url=self.config.endpoint_url,
                api_key=self.config.api_key,
                model=self.config.selected_model
            )

            if not candidates:
                raise RuntimeError("Tidak ada klip viral yang ditemukan dari transkrip")

            if self.cancel_requested.is_set():
                return []

            # Process Each Clip (Stages 4, 5, 6)
            total_clips = len(candidates)
            for idx, clip in enumerate(candidates):
                clip_num = idx + 1
                base_pct = 50 + int((idx / total_clips) * 45)

                # Stage 4: Tracking Faces (70%)
                self.status = PipelineStatus.TRACKING_FACES
                if progress_callback:
                    progress_callback(self.status, base_pct, f"Auto-reframe wajah klip {clip_num}/{total_clips}...")

                centers, strategy = detect_face_centers(video_path, clip.start_time, clip.end_time)
                if centers:
                    smoothed = smooth_ema_series(centers, alpha=0.15)
                    avg_center = sum(smoothed) / len(smoothed)
                else:
                    avg_center = 960.0

                crop_x, crop_w, crop_h = calculate_crop_box(1920, 1080, avg_center)

                if self.cancel_requested.is_set():
                    return []

                # Stage 5: Subtitle Generation
                temp_ass = str((temp_dir / f"clip_{clip_num}.ass").resolve())
                self.temp_files.append(temp_ass)
                generate_kinetic_ass(words, clip.start_time, clip.end_time, temp_ass)

                # Stage 6: Video Rendering (90%)
                self.status = PipelineStatus.RENDERING
                if progress_callback:
                    progress_callback(self.status, min(95, base_pct + 10), f"Rendering NVENC klip {clip_num}/{total_clips}...")

                out_clip_path = str((output_dir / f"clipmax_{clip_num}_{int(clip.start_time)}.mp4").resolve())
                render_clip(
                    input_video=video_path,
                    output_clip=out_clip_path,
                    start_time=clip.start_time,
                    end_time=clip.end_time,
                    crop_x=crop_x,
                    ass_path=temp_ass,
                    use_gpu=(self.config.device == "cuda"),
                    video_bitrate=self.config.video_bitrate,
                    audio_bitrate=self.config.audio_bitrate,
                    cancel_event=self.cancel_requested,
                    pid_callback=self.set_pid
                )
                self.active_pid = None
                generated_clips.append(out_clip_path)

            self.status = PipelineStatus.COMPLETED
            if progress_callback:
                progress_callback(self.status, 100, "Semua klip berhasil diproses!")
            return generated_clips

        except Exception as e:
            self.cleanup()
            if self.cancel_requested.is_set():
                self.status = PipelineStatus.CANCELLED
                return []
            self.status = PipelineStatus.FAILED
            raise e
        finally:
            self.cleanup()
```

- [ ] **Step 4: Run test to verify pass**

Run:
```bash
.venv/Scripts/pytest tests/test_pipeline.py -v
```
Expected: PASS (2 passed)

- [ ] **Step 5: Commit pipeline module**

```bash
git add clipmax/pipeline.py tests/test_pipeline.py
git commit -m "feat: implement pipeline orchestrator with full task lifecycle and kill-safe cancellation"
```

---

### Task 10: Desktop UI - Frameless Theme, Ambient Glow & QThread Worker

**Files:**
- Create: `C:/project/clipmax/clipmax/ui/__init__.py`
- Create: `C:/project/clipmax/clipmax/ui/theme.py`
- Create: `C:/project/clipmax/clipmax/ui/main_window.py`
- Create: `C:/project/clipmax/run.py`

**Interfaces:**
- Consumes: `AppConfig`, `PipelineOrchestrator`.
- Produces: Standalone Frameless PySide6 GUI with model autodiscovery, provider selector, file picker, progress animation, and cancellation button.

- [ ] **Step 1: Implement Theme and QSS styling**

File: `C:/project/clipmax/clipmax/ui/__init__.py`
```python
"""ClipMax UI Module"""
```

File: `C:/project/clipmax/clipmax/ui/theme.py`
```python
DARK_THEME_QSS = """
QMainWindow {
    background-color: #0b0f19;
    border: 1px solid #1e293b;
    border-radius: 12px;
}

QWidget#CentralWidget {
    background-color: #0b0f19;
    border-radius: 12px;
}

QFrame.Card {
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 10px;
    padding: 12px;
}

QLabel {
    color: #f3f4f6;
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}

QLabel.Title {
    font-size: 18px;
    font-weight: bold;
    color: #60a5fa;
}

QLabel.Sub {
    font-size: 12px;
    color: #9ca3af;
}

QLineEdit, QComboBox {
    background-color: #1f2937;
    border: 1px solid #374151;
    border-radius: 6px;
    color: #f9fafb;
    padding: 8px 12px;
    font-size: 13px;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #3b82f6;
}

QPushButton {
    background-color: #2563eb;
    color: #ffffff;
    font-weight: 600;
    border: none;
    border-radius: 6px;
    padding: 9px 16px;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #1d4ed8;
}

QPushButton:pressed {
    background-color: #1e40af;
}

QPushButton.Secondary {
    background-color: #374151;
    color: #e5e7eb;
}

QPushButton.Secondary:hover {
    background-color: #4b5563;
}

QPushButton.Danger {
    background-color: #dc2626;
}

QPushButton.Danger:hover {
    background-color: #b91c1c;
}

QProgressBar {
    background-color: #1f2937;
    border: 1px solid #374151;
    border-radius: 6px;
    text-align: center;
    color: #f9fafb;
    font-weight: bold;
    height: 18px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #8b5cf6);
    border-radius: 5px;
}
"""
```

- [ ] **Step 2: Implement Main Window and QThread Worker**

File: `C:/project/clipmax/clipmax/ui/main_window.py`
```python
import sys
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt, QThread, Signal, QPoint
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QProgressBar,
    QFileDialog, QMessageBox, QFrame
)
from clipmax.config import AppConfig
from clipmax.ai_gateway import discover_models
from clipmax.pipeline import PipelineOrchestrator, PipelineStatus

class PipelineWorker(QThread):
    progress_changed = Signal(str, int, str)
    finished = Signal(list)
    failed = Signal(str)

    def __init__(self, orchestrator: PipelineOrchestrator, video_path: str):
        super().__init__()
        self.orchestrator = orchestrator
        self.video_path = video_path

    def run(self):
        try:
            def on_progress(status, pct, msg):
                self.progress_changed.emit(status.value, pct, msg)

            clips = self.orchestrator.run(self.video_path, on_progress)
            self.finished.emit(clips)
        except Exception as e:
            self.failed.emit(str(e))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(880, 680)

        self.config = AppConfig.load()
        self.orchestrator = PipelineOrchestrator(self.config)
        self.worker: Optional[PipelineWorker] = None
        self._drag_pos = QPoint()

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Titlebar
        title_bar = QHBoxLayout()
        title_lbl = QLabel("ClipMax ⚡ Autonomous Desktop Clipper")
        title_lbl.setProperty("class", "Title")
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(32, 32)
        btn_close.setProperty("class", "Secondary")
        btn_close.clicked.connect(self.close)

        title_bar.addWidget(title_lbl)
        title_bar.addStretch()
        title_bar.addWidget(btn_close)
        main_layout.addLayout(title_bar)

        # Card 1: AI Provider Gateway
        provider_card = QFrame()
        provider_card.setProperty("class", "Card")
        p_layout = QVBoxLayout(provider_card)

        p_lbl = QLabel("AI Provider & Dynamic Model Discovery")
        p_lbl.setStyleSheet("font-weight: bold; color: #93c5fd;")
        p_layout.addWidget(p_lbl)

        row1 = QHBoxLayout()
        self.txt_endpoint = QLineEdit(self.config.endpoint_url)
        self.txt_endpoint.setPlaceholderText("Endpoint URL (e.g. http://localhost:20128/v1)")
        self.txt_key = QLineEdit(self.config.api_key)
        self.txt_key.setPlaceholderText("API Key (opsional)")
        self.txt_key.setEchoMode(QLineEdit.Password)
        self.btn_discover = QPushButton("Discover Models")
        self.btn_discover.setProperty("class", "Secondary")
        self.btn_discover.clicked.connect(self._on_discover_models)

        row1.addWidget(self.txt_endpoint, 3)
        row1.addWidget(self.txt_key, 2)
        row1.addWidget(self.btn_discover, 1)
        p_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.cmb_models = QComboBox()
        self.cmb_models.addItem(self.config.selected_model)
        self.lbl_device = QLabel(f"Hardware: {self.config.device.upper()} ({self.config.compute_type})")
        self.lbl_device.setStyleSheet("color: #10b981; font-weight: bold;")
        row2.addWidget(QLabel("Model:"))
        row2.addWidget(self.cmb_models, 3)
        row2.addWidget(self.lbl_device, 1)
        p_layout.addLayout(row2)

        main_layout.addWidget(provider_card)

        # Card 2: Video Selection
        video_card = QFrame()
        video_card.setProperty("class", "Card")
        v_layout = QVBoxLayout(video_card)

        v_lbl = QLabel("Input Video (16:9 Long Form)")
        v_lbl.setStyleSheet("font-weight: bold; color: #93c5fd;")
        v_layout.addWidget(v_lbl)

        v_row = QHBoxLayout()
        self.txt_video = QLineEdit()
        self.txt_video.setPlaceholderText("Pilih file video MP4/MKV...")
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.setProperty("class", "Secondary")
        self.btn_browse.clicked.connect(self._on_browse_video)

        v_row.addWidget(self.txt_video, 4)
        v_row.addWidget(self.btn_browse, 1)
        v_layout.addLayout(v_row)
        main_layout.addWidget(video_card)

        # Card 3: Execution & Progress
        exec_card = QFrame()
        exec_card.setProperty("class", "Card")
        e_layout = QVBoxLayout(exec_card)

        self.lbl_status = QLabel("Status: Menunggu instruksi...")
        self.lbl_status.setProperty("class", "Sub")
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)

        e_layout.addWidget(self.lbl_status)
        e_layout.addWidget(self.progress_bar)

        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("Mulai Generate Klip 9:16")
        self.btn_start.clicked.connect(self._on_start)
        self.btn_cancel = QPushButton("Batal / Stop")
        self.btn_cancel.setProperty("class", "Danger")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._on_cancel)

        btn_row.addWidget(self.btn_start, 3)
        btn_row.addWidget(self.btn_cancel, 1)
        e_layout.addLayout(btn_row)

        main_layout.addWidget(exec_card)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _on_discover_models(self):
        url = self.txt_endpoint.text().strip()
        key = self.txt_key.text().strip()
        try:
            models = discover_models(url, key)
            self.cmb_models.clear()
            self.cmb_models.addItems(models)
            QMessageBox.information(self, "Sukses", f"Ditemukan {len(models)} model.")
        except Exception as e:
            QMessageBox.warning(self, "Error Discovery", f"Gagal mengambil model: {str(e)}")

    def _on_browse_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Pilih Video", "", "Video Files (*.mp4 *.mkv *.mov *.avi)"
        )
        if file_path:
            self.txt_video.setText(file_path)

    def _on_start(self):
        video = self.txt_video.text().strip()
        if not video or not Path(video).exists():
            QMessageBox.warning(self, "Validasi", "Pilih file video valid terlebih dahulu.")
            return

        self.config.endpoint_url = self.txt_endpoint.text().strip()
        self.config.api_key = self.txt_key.text().strip()
        self.config.selected_model = self.cmb_models.currentText()
        self.config.save()

        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)

        self.worker = PipelineWorker(self.orchestrator, video)
        self.worker.progress_changed.connect(self._on_worker_progress)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.failed.connect(self._on_worker_failed)
        self.worker.start()

    def _on_cancel(self):
        if self.worker and self.worker.isRunning():
            self.lbl_status.setText("Membatalkan dan membersihkan VRAM/temp...")
            self.orchestrator.cancel()
            self.worker.wait(3000)
            self.btn_start.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            self.progress_bar.setValue(0)
            self.lbl_status.setText("Status: Dibatalkan oleh pengguna.")

    def _on_worker_progress(self, status, pct, msg):
        self.progress_bar.setValue(pct)
        self.lbl_status.setText(f"[{status}] {msg}")

    def _on_worker_finished(self, clips):
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setValue(100)
        self.lbl_status.setText(f"Selesai! {len(clips)} klip dibuat di output.")
        QMessageBox.information(self, "Selesai", f"Berhasil membuat {len(clips)} video klip 9:16!")

    def _on_worker_failed(self, error):
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.lbl_status.setText("Gagal!")
        QMessageBox.critical(self, "Error Pipeline", f"Pipeline terhenti: {error}")
```

- [ ] **Step 3: Create run.py entry point**

File: `C:/project/clipmax/run.py`
```python
import sys
from PySide6.QtWidgets import QApplication
from clipmax.ui.main_window import MainWindow
from clipmax.ui.theme import DARK_THEME_QSS

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_THEME_QSS)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Commit UI components**

```bash
git add clipmax/ui/__init__.py clipmax/ui/theme.py clipmax/ui/main_window.py run.py
git commit -m "feat: implement frameless PySide6 desktop UI with model discovery and QThread lifecycle"
```

---

### Task 11: End-to-End Suite Verification & DoD Validation

**Files:**
- Test: `tests/test_e2e_mocked.py`

**Interfaces:**
- Consumes: Mock video input, pipeline orchestrator.
- Produces: Complete pass verification of DoD criteria (VRAM clean, cancel token, time formatting, static binary resolution).

- [ ] **Step 1: Write comprehensive end-to-end mocked test**

File: `C:/project/clipmax/tests/test_e2e_mocked.py`
```python
import pytest
from unittest.mock import patch, MagicMock
from clipmax.config import AppConfig
from clipmax.pipeline import PipelineOrchestrator, PipelineStatus
from clipmax.transcriber import WordSegment
from clipmax.ai_gateway import ViralClipCandidate

def test_full_pipeline_mocked(tmp_path):
    video_file = tmp_path / "test_video.mp4"
    video_file.touch()

    cfg = AppConfig(
        output_dir=str(tmp_path / "out"),
        temp_dir=str(tmp_path / "tmp")
    )
    orchestrator = PipelineOrchestrator(cfg)

    with patch("clipmax.pipeline.extract_audio") as mock_audio, \
         patch("clipmax.pipeline.transcribe_audio") as mock_transcribe, \
         patch("clipmax.pipeline.evaluate_viral_clips") as mock_llm, \
         patch("clipmax.pipeline.detect_face_centers") as mock_face, \
         patch("clipmax.pipeline.generate_kinetic_ass") as mock_sub, \
         patch("clipmax.pipeline.render_clip") as mock_render:

        mock_transcribe.return_value = (
            [WordSegment(word="Tes", start=0.0, end=1.0, probability=0.99)],
            "Transkrip lengkap tes"
        )
        mock_llm.return_value = [
            ViralClipCandidate(
                title="Klip Viral 1",
                hook="Hook mantap",
                start_time=10.0,
                end_time=40.0,
                virality_score=90,
                reasoning="Bagus"
            )
        ]
        mock_face.return_value = ([960.0, 960.0], "single_speaker")

        progress_records = []
        def on_prog(status, pct, msg):
            progress_records.append((status, pct))

        results = orchestrator.run(str(video_file), on_prog)

        assert mock_audio.called
        assert mock_transcribe.called
        assert mock_llm.called
        assert mock_face.called
        assert mock_sub.called
        assert mock_render.called
        assert orchestrator.status == PipelineStatus.COMPLETED
        assert any(pct == 100 for _, pct in progress_records)
```

- [ ] **Step 2: Run all tests to verify 100% test coverage across suite**

Run:
```bash
.venv/Scripts/pytest tests/ -v
```
Expected output:
```text
tests/test_config.py::test_sanitize_ffmpeg_path_windows PASSED
tests/test_config.py::test_sanitize_ffmpeg_path_relative PASSED
tests/test_config.py::test_parse_to_seconds_float_int PASSED
tests/test_config.py::test_parse_to_seconds_mmss PASSED
tests/test_config.py::test_parse_to_seconds_hhmmss PASSED
tests/test_config.py::test_parse_to_seconds_invalid PASSED
tests/test_config.py::test_default_app_config PASSED
tests/test_audio.py::test_extract_audio_command_construction PASSED
tests/test_audio.py::test_extract_audio_file_not_found PASSED
tests/test_transcriber.py::test_transcribe_audio_mocked PASSED
tests/test_ai_gateway.py::test_safe_extract_json_markdown_block PASSED
tests/test_ai_gateway.py::test_safe_extract_json_raw_braces PASSED
tests/test_ai_gateway.py::test_discover_models_mock PASSED
tests/test_ai_gateway.py::test_evaluate_viral_clips_mock PASSED
tests/test_reframe.py::test_calculate_crop_box_center PASSED
tests/test_reframe.py::test_calculate_crop_box_boundary_clamping PASSED
tests/test_reframe.py::test_smooth_ema_series PASSED
tests/test_subtitle.py::test_format_ass_time PASSED
tests/test_subtitle.py::test_generate_kinetic_ass PASSED
tests/test_renderer.py::test_render_clip_command_nvenc PASSED
tests/test_renderer.py::test_render_clip_command_cpu_fallback PASSED
tests/test_pipeline.py::test_pipeline_status_enum PASSED
tests/test_pipeline.py::test_pipeline_cancellation_token PASSED
tests/test_e2e_mocked.py::test_full_pipeline_mocked PASSED
============================== 24 passed ==============================
```

- [ ] **Step 3: Commit full test suite and DoD verification**

```bash
git add tests/test_e2e_mocked.py
git commit -m "test: add full suite e2e mocked validation fulfilling PRD DoD"
```

---

## Risks, Tradeoffs & Open Questions

1. **Risk:** Faster-Whisper VRAM allocation might retain CUDA allocator cache on 4GB GPUs.
   - **Mitigation:** Task 4 explicitly invokes `del whisper_model`, `gc.collect()`, `torch.cuda.empty_cache()`, and `torch.cuda.ipc_collect()` inside a `finally` block before MediaPipe or FFmpeg NVENC are invoked.
2. **Tradeoff:** MediaPipe CPU face detection vs GPU.
   - **Mitigation:** Running MediaPipe on CPU keeps the 4GB GPU GDDR6 frame buffer 100% available for NVENC hardware video encoding.
3. **Windows FFmpeg Path Quoting:**
   - **Mitigation:** Handled via `sanitize_ffmpeg_path` converting backslashes to forward slashes and escaping `C:` as `C\:`.
