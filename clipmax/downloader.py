import os
import subprocess
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List, Tuple
from clipmax.config import get_ffmpeg_bin

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

def get_ydl_options(output_path: str) -> Dict[str, Any]:
    """
    Returns robust yt-dlp options using Android & iOS clients and custom mobile user agent,
    completely eliminating dependency on local browser cookie extraction (DPAPI/DB lock).
    """
    opts: Dict[str, Any] = {
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
        "ignoreerrors": False,
        "quiet": True,
        "no_warnings": True,
    }

    cookie_file = find_manual_cookie_file()
    if cookie_file:
        opts["cookiefile"] = cookie_file

    return opts

def download_video(
    url: str,
    output_dir: str,
    cancel_event: Optional[threading.Event] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> str:
    """
    Downloads video with safe mobile client extraction (Android + iOS player) and manual cookie fallback.
    Avoids cookiesfrombrowser to prevent DPAPI / database lock errors.
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

    base_shared: Dict[str, Any] = {
        "outtmpl": out_template,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "ffmpeg_location": ffmpeg_bin,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [progress_hook],
        "nocheckcertificate": True,
        "ignoreerrors": False,
        "extract_flat": False,
    }

    cookie_file = find_manual_cookie_file()
    if cookie_file:
        base_shared["cookiefile"] = cookie_file

    # Build reliable fallback strategies without browser cookies:
    # 1. Primary: Android & iOS Mobile Client + Player Skip + Android User-Agent
    opts_android_ios = dict(base_shared)
    opts_android_ios["extractor_args"] = {
        "youtube": {
            "player_client": ["android", "ios"],
            "player_skip": ["webpage", "configs"]
        }
    }
    opts_android_ios["http_headers"] = {
        "User-Agent": "com.google.android.youtube/19.05.36 (Linux; U; Android 14; US) gzip"
    }

    # 2. Secondary: Android & Web Client
    opts_android_web = dict(base_shared)
    opts_android_web["extractor_args"] = {
        "youtube": {
            "player_client": ["android", "web"]
        }
    }

    # 3. Tertiary: TV & Web Safari Client
    opts_tv_safari = dict(base_shared)
    opts_tv_safari["extractor_args"] = {
        "youtube": {
            "player_client": ["tv", "web_safari"]
        }
    }

    # 4. Quaternary: Standard default fallback
    opts_default = dict(base_shared)

    strategies: List[Tuple[str, Dict[str, Any]]] = [
        ("Android/iOS Mobile Client", opts_android_ios),
        ("Android/Web Client", opts_android_web),
        ("TV/Safari Client", opts_tv_safari),
        ("Default Extractor", opts_default)
    ]

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

    tips_msg = "Tips: Jika YouTube memblokir IP, letakkan file cookies.txt di folder proyek."
    if last_error:
        raise RuntimeError(f"Gagal mengunduh video: {str(last_error)}\n{tips_msg}") from last_error
    raise RuntimeError(f"Gagal mengunduh video setelah mencoba seluruh strategi yt-dlp.\n{tips_msg}")
