import os
import re
import subprocess
import threading
import requests
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from clipmax.config import get_ffmpeg_bin

def clean_error_message(text: str) -> str:
    """Removes raw terminal ANSI escape sequences, color codes, and bracketed escapes."""
    if not text:
        return ""
    cleaned = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)
    cleaned = re.sub(r'(?:\[\]|\[)[0-9;]+m', '', cleaned)
    cleaned = re.sub(r'\[0m', '', cleaned)
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', cleaned)
    return cleaned.strip()

def auto_update_ytdlp() -> bool:
    """Updates yt-dlp to maintain extraction compatibility against YouTube changes."""
    try:
        res = subprocess.run(
            ["uv", "pip", "install", "-U", "yt-dlp"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return res.returncode == 0
    except Exception:
        return False

def is_valid_video_url(url: str) -> bool:
    if not isinstance(url, str):
        return False
    u = url.strip().lower()
    return u.startswith("http://") or u.startswith("https://")

def extract_video_id(url: str) -> Optional[str]:
    """Extracts the 11-character YouTube video ID from URL string."""
    if not url or ("youtube.com" not in url and "youtu.be" not in url):
        return None
    match = re.search(r'(?:[?&]v=|\/embed\/|\/shorts\/|\/v\/|youtu\.be\/)([0-9A-Za-z_-]{11})', url)
    return match.group(1) if match else None

def download_via_invidious(
    youtube_url: str,
    output_path: str,
    cancel_event: Optional[threading.Event] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> bool:
    """
    Downloads YouTube video stream using public Invidious instances without requiring login or cookies.
    """
    video_id = extract_video_id(youtube_url)
    if not video_id:
        return False

    instances = [
        "https://invidious.nerdvpn.de",
        "https://inv.tux.pizza",
        "https://invidious.projectsegfau.lt",
        "https://vid.puffyan.us",
        "https://yewtu.be",
        "https://invidious.jing.rocks",
        "https://inv.nadeko.net",
        "https://invidious.f5.si"
    ]

    for base_url in instances:
        if cancel_event and cancel_event.is_set():
            return False

        try:
            api_url = f"{base_url}/api/v1/videos/{video_id}"
            resp = requests.get(api_url, timeout=8)
            if resp.status_code != 200:
                continue

            data = resp.json()
            format_streams = data.get("formatStreams", [])
            if not format_streams:
                continue

            # Sort by highest qualityLabel number
            best_stream = max(
                format_streams,
                key=lambda s: int(re.sub(r'\D', '', str(s.get("qualityLabel", "0"))) or 0)
            )
            direct_download_url = best_stream.get("url")

            if direct_download_url:
                with requests.get(direct_download_url, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    total_size = int(r.headers.get("content-length", 0))
                    downloaded = 0
                    with open(output_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=1024 * 1024):
                            if cancel_event and cancel_event.is_set():
                                return False
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if progress_callback and total_size > 0:
                                    pct = int((downloaded / total_size) * 100)
                                    progress_callback(pct, f"Mengunduh via Invidious: {pct}%")
                    return True
        except Exception as e:
            print(f"[Invidious] Error fetching from {base_url}: {e}")
            continue

    return False

def get_ydl_options(output_path: str, **kwargs) -> Dict[str, Any]:
    """
    Returns yt-dlp options configured for safe fallback without requiring login or cookies.
    """
    return {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": output_path,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios"],
                "player_skip": ["webpage", "configs"]
            }
        },
        "http_headers": {
            "User-Agent": "com.google.android.youtube/19.05.36 (Linux; U; Android 14; US) gzip"
        },
        "nocheckcertificate": True,
        "no_warnings": True,
        "quiet": False
    }

def download_video(
    url: str,
    output_dir: str,
    cancel_event: Optional[threading.Event] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None,
    **kwargs
) -> str:
    """
    Downloads video using Invidious API instance as primary engine,
    with yt-dlp as an optional fallback engine.
    """
    import yt_dlp

    if not is_valid_video_url(url):
        raise ValueError(f"Invalid URL: '{url}'. Harap masukkan URL http:// atau https://")

    out_dir_path = Path(output_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)

    # 1. Primary Engine: Invidious API stream download
    vid_id = extract_video_id(url)
    if vid_id:
        target_file = out_dir_path / f"yt_download_{vid_id}.mp4"
        if progress_callback:
            progress_callback(0, "Mengunduh via Invidious API instance...")

        try:
            invidious_ok = download_via_invidious(
                youtube_url=url,
                output_path=str(target_file),
                cancel_event=cancel_event,
                progress_callback=progress_callback
            )
            if invidious_ok and target_file.exists() and target_file.stat().st_size > 1000:
                return str(target_file.resolve())
        except Exception as e:
            print(f"[Invidious Engine Warning] Invidious download failed: {e}, falling back to yt-dlp")

    if cancel_event and cancel_event.is_set():
        raise RuntimeError("Download dibatalkan oleh pengguna.")

    # 2. Fallback Engine: yt-dlp
    auto_update_ytdlp()

    out_template = str(out_dir_path / "yt_download_%(id)s.%(ext)s")

    def progress_hook(d: Dict[str, Any]):
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("Download cancelled by user")
        if d.get("status") == "downloading" and progress_callback:
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            pct = int((downloaded / total) * 100) if total > 0 else 0
            progress_callback(pct, f"Mengunduh (yt-dlp): {pct}%")

    ffmpeg_bin = get_ffmpeg_bin()

    opts = get_ydl_options(out_template)
    opts.update({
        "merge_output_format": "mp4",
        "ffmpeg_location": ffmpeg_bin,
        "progress_hooks": [progress_hook],
        "ignoreerrors": False,
        "extract_flat": False,
    })

    if progress_callback:
        progress_callback(0, "Menghubungkan ke server video (yt-dlp fallback)...")

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url.strip(), download=True)
            if not info:
                raise RuntimeError("yt-dlp tidak menemukan stream video yang dapat diunduh.")

            filename = ydl.prepare_filename(info)
            mp4_filename = str(Path(filename).with_suffix(".mp4"))
            if os.path.exists(mp4_filename):
                return str(Path(mp4_filename).resolve())
            if os.path.exists(filename):
                return str(Path(filename).resolve())

            extracted_id = info.get("id", vid_id or "")
            matches = list(out_dir_path.glob(f"yt_download_{extracted_id}.*"))
            if matches:
                return str(matches[0].resolve())
            raise FileNotFoundError(f"File video unduhan tidak ditemukan di {output_dir}")
    except Exception as e:
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("Download dibatalkan oleh pengguna.") from e
        cleaned_err = clean_error_message(str(e))
        raise RuntimeError(f"Gagal mengunduh video: {cleaned_err}") from e
