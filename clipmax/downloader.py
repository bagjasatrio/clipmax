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

def download_video(
    url: str,
    output_dir: str,
    cancel_event: Optional[threading.Event] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> str:
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

    base_opts: Dict[str, Any] = {
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

    # Check for manual cookies.txt in project or home dir
    project_root = Path(__file__).resolve().parent.parent
    cookie_candidates = [
        project_root / "cookies.txt",
        project_root / "bin" / "cookies.txt",
        Path.home() / "cookies.txt"
    ]
    cookie_file = next((str(p) for p in cookie_candidates if p.exists()), None)
    if cookie_file:
        base_opts["cookiefile"] = cookie_file

    # Build fallback strategies in order:
    # 1. Browser cookies (Chrome, Edge, Firefox, Brave)
    # 2. Android + Web player client fallback (bypasses bot verification)
    # 3. TV + Web Safari player client fallback
    # 4. Standard extractor
    strategies: List[Tuple[str, Dict[str, Any]]] = []

    if not cookie_file:
        for browser in ["chrome", "edge", "firefox", "brave"]:
            b_opts = dict(base_opts)
            b_opts["cookiesfrombrowser"] = (browser, )
            b_opts["extractor_args"] = {
                "youtube": {
                    "player_client": ["android", "web"]
                }
            }
            strategies.append((f"Browser Cookie ({browser})", b_opts))

    # Android & Web player client fallback
    android_opts = dict(base_opts)
    android_opts["extractor_args"] = {
        "youtube": {
            "player_client": ["android", "web"]
        }
    }
    strategies.append(("Android/Web Client Fallback", android_opts))

    # TV & Web Safari client fallback
    tv_opts = dict(base_opts)
    tv_opts["extractor_args"] = {
        "youtube": {
            "player_client": ["tv", "web_safari"]
        }
    }
    strategies.append(("TV/Safari Client Fallback", tv_opts))

    # Default options fallback
    strategies.append(("Default Strategy", dict(base_opts)))

    last_error: Optional[Exception] = None

    for strategy_name, opts in strategies:
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("Download dibatalkan oleh pengguna.")

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
            # Continue to next strategy (e.g., if browser DB is locked or decryption fails)
            continue

    if last_error:
        raise last_error
    raise RuntimeError("Gagal mengunduh video setelah mencoba seluruh strategi yt-dlp.")
