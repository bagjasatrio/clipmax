import os
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from clipmax.config import get_ffmpeg_bin

def is_valid_video_url(url: str) -> bool:
    if not isinstance(url, str):
        return False
    u = url.strip().lower()
    return u.startswith("http://") or u.startswith("https://")

def download_video(
    url: str,
    output_dir: str,
    cancel_event: Optional[threading.Event] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> str:
    import yt_dlp

    if not is_valid_video_url(url):
        raise ValueError(f"Invalid URL: '{url}'. Harap masukkan URL http:// atau https://")

    out_dir_path = Path(output_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)
    out_template = str(out_dir_path / "yt_download_%(id)s.%(ext)s")

    def progress_hook(d: Dict[str, Any]):
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("Download cancelled by user")
        if d.get("status") == "downloading" and progress_callback:
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            pct = int((downloaded / total) * 100) if total > 0 else 0
            progress_callback(pct, f"Mengunduh video: {pct}%")

    ffmpeg_bin = get_ffmpeg_bin()

    ydl_opts = {
        "outtmpl": out_template,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "ffmpeg_location": ffmpeg_bin,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [progress_hook],
        "nocheckcertificate": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url.strip(), download=True)
            if not info:
                raise RuntimeError("Gagal mengekstrak informasi video dari URL.")

            # Resolve output file path
            filename = ydl.prepare_filename(info)
            # Check if merged to .mp4
            mp4_filename = str(Path(filename).with_suffix(".mp4"))
            if os.path.exists(mp4_filename):
                return str(Path(mp4_filename).resolve())
            if os.path.exists(filename):
                return str(Path(filename).resolve())

            # Fallback search in out_dir_path
            vid_id = info.get("id", "")
            matches = list(out_dir_path.glob(f"yt_download_{vid_id}.*"))
            if matches:
                return str(matches[0].resolve())

            raise FileNotFoundError(f"Hasil download video tidak ditemukan: {filename}")
    except Exception as e:
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("Download dibatalkan oleh pengguna.") from e
        raise e
