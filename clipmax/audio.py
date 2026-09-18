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
