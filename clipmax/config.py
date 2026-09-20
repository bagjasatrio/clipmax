import os
import json
import shutil
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel, Field
import torch

def is_cuda_available() -> bool:
    if torch.cuda.is_available():
        return True
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return True
    except Exception:
        pass
    return False

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
    device: str = Field(default_factory=lambda: "cuda" if is_cuda_available() else "cpu")
    compute_type: str = Field(default_factory=lambda: "float16" if is_cuda_available() else "int8")
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
    target_clip_count: int = 3
    duration_preset: str = "Auto / Optimal (30-60s)"
    min_duration: float = 30.0
    max_duration: float = 60.0
    campaign_rules: str = ""
    cookie_file: Optional[str] = None
    clip_mode: str = "single"

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

def clear_temp_cache(temp_dir_path: Optional[str] = None) -> int:
    """Removes all temporary cache files, subclips, wav chunks, and directories."""
    target = Path(temp_dir_path or AppConfig().temp_dir).resolve()
    removed_count = 0
    if target.exists():
        for item in target.iterdir():
            try:
                if item.is_file():
                    item.unlink()
                    removed_count += 1
                elif item.is_dir():
                    shutil.rmtree(item)
                    removed_count += 1
            except Exception as e:
                print(f"[Cleanup Warning] Gagal hapus {item}: {e}")
        (target / "staging").mkdir(parents=True, exist_ok=True)
        (target / "downloads").mkdir(parents=True, exist_ok=True)
    return removed_count
