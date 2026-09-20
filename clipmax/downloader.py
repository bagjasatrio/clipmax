import os
import re
import subprocess
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List, Tuple
from clipmax.config import get_ffmpeg_bin

def clean_error_message(text: str) -> str:
    """Removes raw terminal ANSI escape sequences, color codes, and bracketed escapes."""
    if not text:
        return ""
    # Remove standard ANSI escape sequences \x1b[...]
    cleaned = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)
    # Remove raw bracket escapes like []0;31m or \x1b[0;31m or [0;31m or [0m
    cleaned = re.sub(r'(?:\[\]|\[)[0-9;]+m', '', cleaned)
    cleaned = re.sub(r'\[0m', '', cleaned)
    # Remove terminal control characters
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', cleaned)
    return cleaned.strip()

def auto_update_ytdlp() -> bool:
    """Updates yt-dlp to the latest version to maintain extraction compatibility against YouTube changes."""
    try:
        res = subprocess.run(
            ["uv", "pip", "install", "-U", "yt-dlp"],
            capture_output=True,
            text=True,
            timeout=8
        )
        return res.returncode == 0
    except Exception:
        return False

def is_valid_video_url(url: str) -> bool:
    if not isinstance(url, str):
        return False
    u = url.strip().lower()
    return u.startswith("http://") or u.startswith("https://")

def find_manual_cookie_file() -> Optional[str]:
    """Finds a manual cookies.txt in project root, temp, or bin folder."""
    project_root = Path(__file__).resolve().parent.parent
    candidates = [
        project_root / "cookies.txt",
        project_root / "temp" / "cookies.txt",
        project_root / "bin" / "cookies.txt",
        Path.home() / "cookies.txt"
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            return str(p.resolve())
    return None

def get_ydl_options(output_path: str, active_cookie_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns yt-dlp options using login-free android_vr / android clients.
    Does not include cookiefile for android/android_vr clients to avoid skipping warnings.
    """
    ydl_opts: Dict[str, Any] = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": output_path,
        "extractor_args": {
            "youtube": {
                "player_client": ["android_vr", "android"],
                "player_skip": ["webpage", "configs"]
            }
        },
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Referer": "https://www.google.com/"
        },
        "nocheckcertificate": True,
        "no_warnings": True,
        "quiet": False
    }

    return ydl_opts

def download_video(
    url: str,
    output_dir: str,
    cookie_file: Optional[str] = None,
    cancel_event: Optional[threading.Event] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> str:
    """
    Downloads video using manual cookies.txt (if loaded) or mobile client anti-bot extraction.
    Never calls cookiesfrombrowser to eliminate DPAPI decryption or database lock errors.
    """
    import yt_dlp

    if not is_valid_video_url(url):
        raise ValueError(f"Invalid URL: '{url}'. Harap masukkan URL http:// atau https://")

    # Ensure latest yt-dlp release
    auto_update_ytdlp()

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

    active_cookie = cookie_file or find_manual_cookie_file()

    # Build strategies without cookiesfrombrowser:
    strategies: List[Tuple[str, Dict[str, Any]]] = []

    # 1. If cookies.txt is provided, prioritize Web Client with cookies
    if active_cookie and os.path.isfile(active_cookie):
        opts_cookie: Dict[str, Any] = {
            "outtmpl": out_template,
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
            "ffmpeg_location": ffmpeg_bin,
            "cookiefile": active_cookie,
            "nocheckcertificate": True,
            "no_warnings": True,
            "quiet": False,
            "progress_hooks": [progress_hook],
            "ignoreerrors": False,
            "extract_flat": False,
        }
        strategies.append(("Web Client (dengan cookies.txt)", opts_cookie))

    # 2. Login-free android_vr / android Strategy (NO GVS PO Token required, NO error 152)
    # Never include cookiefile with android/android_vr to avoid skipping warnings
    opts_android_vr: Dict[str, Any] = {
        "outtmpl": out_template,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "ffmpeg_location": ffmpeg_bin,
        "extractor_args": {
            "youtube": {
                "player_client": ["android_vr", "android"],
                "player_skip": ["webpage", "configs"]
            }
        },
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Referer": "https://www.google.com/"
        },
        "nocheckcertificate": True,
        "no_warnings": True,
        "quiet": False,
        "progress_hooks": [progress_hook],
        "ignoreerrors": False,
        "extract_flat": False,
    }
    strategies.append(("Android VR / Android (Bebas Login)", opts_android_vr))

    # 3. Android + Web Client fallback
    opts_web: Dict[str, Any] = {
        "outtmpl": out_template,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "ffmpeg_location": ffmpeg_bin,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"]
            }
        },
        "nocheckcertificate": True,
        "no_warnings": True,
        "quiet": False,
        "progress_hooks": [progress_hook],
        "ignoreerrors": False,
        "extract_flat": False,
    }
    strategies.append(("Android/Web Client", opts_web))

    last_error: Optional[Exception] = None

    for strategy_name, opts in strategies:
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("Download dibatalkan oleh pengguna.")

        if progress_callback:
            progress_callback(0, f"Menghubungkan ({strategy_name})...")

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url.strip(), download=True)
                if not info:
                    continue

                filename = ydl.prepare_filename(info)
                mp4_filename = str(Path(filename).with_suffix(".mp4"))
                if os.path.exists(mp4_filename):
                    return str(Path(mp4_filename).resolve())
                if os.path.exists(filename):
                    return str(Path(filename).resolve())

                vid_id = info.get("id", "")
                matches = list(out_dir_path.glob(f"yt_download_{vid_id}.*"))
                if matches:
                    return str(matches[0].resolve())
        except Exception as e:
            last_error = e
            if cancel_event and cancel_event.is_set():
                raise RuntimeError("Download dibatalkan oleh pengguna.") from e
            continue

    bot_msg = (
        "YouTube meminta verifikasi bot. Silakan ekspor cookies YouTube dari browser "
        "menggunakan ekstensi 'Get cookies.txt LOCALLY' lalu muat lewat tombol 'Import cookies.txt'."
    )
    if last_error:
        cleaned_err = clean_error_message(str(last_error))
        raise RuntimeError(f"Gagal mengunduh video: {cleaned_err}\n{bot_msg}") from last_error
    raise RuntimeError(f"Gagal mengunduh video setelah mencoba seluruh strategi yt-dlp.\n{bot_msg}")
