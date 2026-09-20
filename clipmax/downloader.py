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

def get_ydl_options(output_path: str) -> Dict[str, Any]:
    """
    Returns yt-dlp options prioritizing local browser cookies (chrome -> edge -> firefox -> brave)
    with seamless fallback to Android client extractor.
    """
    browsers = ["chrome", "edge", "firefox", "brave"]
    for b in browsers:
        try:
            return {
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "outtmpl": output_path,
                "cookiesfrombrowser": (b, ),
                "quiet": True,
                "no_warnings": True,
                "nocheckcertificate": True
            }
        except Exception:
            continue

    return {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": output_path,
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True
    }

def download_video(
    url: str,
    output_dir: str,
    cancel_event: Optional[threading.Event] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> str:
    """
    Downloads video using a safe download wrapper loop:
    1. Check for manual cookies.txt.
    2. Sequentially attempt browser cookie extraction (Chrome -> Edge -> Firefox -> Brave).
    3. Fallback to Android client extractor args.
    4. Fallback to TV / Safari client extractor args.
    5. Fallback to default extractor.
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

    # Check for manual cookies.txt in project or home dir
    project_root = Path(__file__).resolve().parent.parent
    cookie_candidates = [
        project_root / "cookies.txt",
        project_root / "bin" / "cookies.txt",
        Path.home() / "cookies.txt"
    ]
    cookie_file = next((str(p) for p in cookie_candidates if p.exists()), None)

    strategies: List[Tuple[str, Dict[str, Any]]] = []

    if cookie_file:
        c_opts = dict(base_shared)
        c_opts["cookiefile"] = cookie_file
        strategies.append(("Manual Cookies File", c_opts))
    else:
        # Browser cookies loop (Chrome -> Edge -> Firefox -> Brave)
        for b in ["chrome", "edge", "firefox", "brave"]:
            b_opts = dict(base_shared)
            b_opts["cookiesfrombrowser"] = (b, )
            strategies.append((f"Browser Cookies ({b})", b_opts))

    # Android & Web player client fallback (no cookies to avoid mismatch)
    android_opts = dict(base_shared)
    android_opts["extractor_args"] = {
        "youtube": {
            "player_client": ["android", "web"]
        }
    }
    strategies.append(("Android/Web Client Fallback", android_opts))

    # TV & Web Safari client fallback
    tv_opts = dict(base_shared)
    tv_opts["extractor_args"] = {
        "youtube": {
            "player_client": ["tv", "web_safari"]
        }
    }
    strategies.append(("TV/Safari Client Fallback", tv_opts))

    # Generic default fallback
    strategies.append(("Default Strategy", dict(base_shared)))

    last_error: Optional[Exception] = None

    # Safe Download Wrapper Loop:
    # If a browser DB is locked or challenged, immediately catch and advance to the next strategy
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
            # Continue to next strategy in wrapper loop
            continue

    if last_error:
        raise last_error
    raise RuntimeError("Gagal mengunduh video setelah mencoba seluruh strategi yt-dlp.")
