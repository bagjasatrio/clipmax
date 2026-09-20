import os
import re
import json
import time
import datetime
import subprocess
import threading
import requests
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List, Tuple
from clipmax.config import get_ffmpeg_bin

_OAUTH_CLIENT_ID = "861556708454-d6dlm3lh05idd8npek18k6be8ba3oc68.apps.googleusercontent.com"
_OAUTH_CLIENT_SECRET = "SboVhoG9s0rNafixCSGGKXAT"
_OAUTH_SCOPES = "https://gdata.youtube.com https://www.googleapis.com/auth/youtube"

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
    """Updates yt-dlp to the latest version to maintain extraction compatibility against YouTube changes."""
    try:
        res = subprocess.run(
            ["uv", "pip", "install", "-U", "yt-dlp", "yt-dlp-youtube-oauth2"],
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

def is_youtube_oauth_authenticated() -> bool:
    """Checks whether valid YouTube OAuth2 credentials are saved in yt-dlp cache."""
    try:
        import yt_dlp
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            token = ydl.cache.load("youtube-oauth2", "token_data")
            return bool(token and isinstance(token, dict) and "access_token" in token)
    except Exception:
        return False

def initiate_youtube_oauth() -> Dict[str, Any]:
    """
    Initiates YouTube OAuth2 Device Flow.
    Returns verification_url and user_code for display in UI.
    """
    res = requests.post(
        "https://www.youtube.com/o/oauth2/device/code",
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        json={
            "client_id": _OAUTH_CLIENT_ID,
            "scope": _OAUTH_SCOPES,
            "device_id": "clipmax-desktop-client",
            "device_model": "ytlr::"
        },
        timeout=10
    )
    if res.status_code != 200:
        raise RuntimeError(f"Gagal menginisialisasi OAuth2: HTTP {res.status_code} - {res.text}")
    return res.json()

def poll_youtube_oauth_token(device_code: str) -> Dict[str, Any]:
    """
    Polls YouTube OAuth2 token endpoint with device_code.
    Stores token to yt-dlp cache once authorized.
    """
    import yt_dlp
    res = requests.post(
        "https://www.youtube.com/o/oauth2/token",
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        json={
            "client_id": _OAUTH_CLIENT_ID,
            "client_secret": _OAUTH_CLIENT_SECRET,
            "device_code": device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
        },
        timeout=10
    )
    data = res.json()
    if "access_token" in data:
        token_data = {
            "access_token": data["access_token"],
            "expires": datetime.datetime.now(datetime.timezone.utc).timestamp() + data.get("expires_in", 3600),
            "token_type": data.get("token_type", "Bearer"),
            "refresh_token": data.get("refresh_token", "")
        }
        with yt_dlp.YoutubeDL({"username": "oauth2", "password": "", "quiet": True}) as ydl:
            ydl.cache.store("youtube-oauth2", "token_data", token_data)
        return {"status": "success", "message": "Akun YouTube berhasil terhubung!"}
    elif data.get("error") == "authorization_pending":
        return {"status": "pending", "message": "Menunggu konfirmasi perangkat..."}
    else:
        err_msg = data.get("error_description") or data.get("error") or "Unknown error"
        return {"status": "error", "message": str(err_msg)}

def get_ydl_options(output_path: str, **kwargs) -> Dict[str, Any]:
    """
    Returns yt-dlp options configured for official YouTube OAuth2 permanently.
    """
    return {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": output_path,
        "username": "oauth2",
        "password": "",
        "nocheckcertificate": True,
        "no_warnings": False,
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
    Downloads video using official YouTube OAuth2 extraction.
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

    opts = get_ydl_options(out_template)
    opts.update({
        "merge_output_format": "mp4",
        "ffmpeg_location": ffmpeg_bin,
        "progress_hooks": [progress_hook],
        "ignoreerrors": False,
        "extract_flat": False,
    })

    if progress_callback:
        progress_callback(0, "Menghubungkan ke YouTube (OAuth2)...")

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

            vid_id = info.get("id", "")
            matches = list(out_dir_path.glob(f"yt_download_{vid_id}.*"))
            if matches:
                return str(matches[0].resolve())
            raise FileNotFoundError(f"File video unduhan tidak ditemukan di {output_dir}")
    except Exception as e:
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("Download dibatalkan oleh pengguna.") from e
        cleaned_err = clean_error_message(str(e))
        raise RuntimeError(f"Gagal mengunduh video: {cleaned_err}") from e
