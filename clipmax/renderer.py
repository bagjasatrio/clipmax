import os
import subprocess
import threading
from pathlib import Path
from typing import Optional, Callable
from clipmax.config import get_ffmpeg_bin, sanitize_ffmpeg_path, is_cuda_available

def is_nvenc_supported() -> bool:
    if not is_cuda_available():
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
    if not os.path.exists(str(in_p)):
        raise FileNotFoundError(f"Input video not found: {input_video}")

    out_p = Path(output_clip)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    encoder = "h264_nvenc" if (use_gpu and is_nvenc_supported()) else "libx264"
    preset = "p4" if encoder == "h264_nvenc" else "veryfast"

    # Filter string: 9:16 crop + scale to 1080x1920 + optional subtitles
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
