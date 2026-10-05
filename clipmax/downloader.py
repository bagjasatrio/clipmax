import os
import re
import subprocess
import threading
import requests
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List
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

def _download_file_stream(
    url: str,
    target_path: str,
    cancel_event: Optional[threading.Event] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None,
    label: str = "Invidious"
) -> bool:
    try:
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(target_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if cancel_event and cancel_event.is_set():
                        return False
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            pct = int((downloaded / total_size) * 100)
                            progress_callback(pct, f"Mengunduh {label}: {pct}%")
            return os.path.exists(target_path) and os.path.getsize(target_path) > 0
    except Exception as e:
        print(f"[Invidious Stream Error] {label}: {e}")
        return False

def download_via_invidious(
    youtube_url: str,
    output_path: str,
    cancel_event: Optional[threading.Event] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> bool:
    """
    Downloads YouTube video stream using public Invidious instances without requiring login or cookies.
    Strictly prioritizes Full HD 1080p streams before falling back to lower resolutions.
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
            adaptive_formats = data.get("adaptiveFormats", [])

            # 1. Prioritize formatStreams with >= 1080p
            high_muxed = [
                s for s in format_streams
                if int(re.sub(r'\D', '', str(s.get("qualityLabel", "0"))) or 0) >= 1080 and s.get("url")
            ]
            if high_muxed:
                best_stream = max(
                    high_muxed,
                    key=lambda s: int(re.sub(r'\D', '', str(s.get("qualityLabel", "0"))) or 0)
                )
                if _download_file_stream(best_stream.get("url"), output_path, cancel_event, progress_callback, "1080p Invidious"):
                    return True

            # 2. Check adaptiveFormats for 1080p video + audio
            v1080_candidates = [
                f for f in adaptive_formats
                if "video" in f.get("type", "") and (
                    int(re.sub(r'\D', '', str(f.get("qualityLabel", "0"))) or 0) >= 1080
                    or (f.get("height") and f.get("height") >= 1080)
                ) and f.get("url")
            ]
            audio_candidates = [
                f for f in adaptive_formats
                if "audio" in f.get("type", "") and f.get("url")
            ]

            if v1080_candidates and audio_candidates:
                best_video = max(
                    v1080_candidates,
                    key=lambda s: int(re.sub(r'\D', '', str(s.get("qualityLabel", "0"))) or 0)
                )
                best_audio = audio_candidates[0]
                temp_v = str(Path(output_path).with_suffix(".temp_v.mp4"))
                temp_a = str(Path(output_path).with_suffix(".temp_a.m4a"))
                try:
                    ok_v = _download_file_stream(best_video.get("url"), temp_v, cancel_event, progress_callback, "1080p Video")
                    ok_a = _download_file_stream(best_audio.get("url"), temp_a, cancel_event, None, "Audio")
                    if ok_v and ok_a:
                        ffmpeg_bin = get_ffmpeg_bin()
                        mux_cmd = [
                            ffmpeg_bin, "-y",
                            "-i", temp_v,
                            "-i", temp_a,
                            "-c", "copy",
                            str(Path(output_path).resolve())
                        ]
                        subprocess.run(mux_cmd, capture_output=True)
                        if os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
                            return True
                finally:
                    Path(temp_v).unlink(missing_ok=True)
                    Path(temp_a).unlink(missing_ok=True)

            # 3. If no 1080p found, only accept format_streams if >= 720p (otherwise prefer yt-dlp HD)
            if format_streams:
                best_stream = max(
                    format_streams,
                    key=lambda s: int(re.sub(r'\D', '', str(s.get("qualityLabel", "0"))) or 0)
                )
                q_num = int(re.sub(r'\D', '', str(best_stream.get("qualityLabel", "0"))) or 0)
                if q_num >= 720 and best_stream.get("url"):
                    if _download_file_stream(best_stream.get("url"), output_path, cancel_event, progress_callback, f"Invidious ({q_num}p)"):
                        return True
        except Exception as e:
            print(f"[Invidious] Error fetching from {base_url}: {e}")
            continue

    return False

def probe_youtube_audio_tracks(url: str) -> List[Dict[str, Any]]:
    """
    Probes YouTube video metadata for available multi-language audio tracks.
    Returns list of dicts: [{'code': 'en', 'label': 'English (Original)', 'is_original': True}, ...]
    """
    import yt_dlp

    if not is_valid_video_url(url):
        return []

    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "skip_download": True,
        "nocheckcertificate": True,
        "socket_timeout": 8
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url.strip(), download=False)
            if not info:
                return []
            formats = info.get("formats", [])
            tracks_map: Dict[str, Dict[str, Any]] = {}
            for f in formats:
                if f.get("vcodec") == "none" and f.get("acodec") != "none":
                    lang = (f.get("language") or "").strip().lower()
                    note = (f.get("format_note") or "").strip()
                    if not lang and not note:
                        continue

                    track_code = lang or "default"
                    if track_code not in tracks_map:
                        is_orig = "original" in note.lower() or "default" in note.lower()
                        is_dub = "dubbed" in note.lower() or "dub" in note.lower()

                        label = note if note else track_code.upper()
                        if " - " in label:
                            label = label.split(" - ")[0].strip()

                        if "indonesia" in label.lower() or track_code == "id":
                            label = "Bahasa Indonesia"
                        elif "english" in label.lower() or track_code.startswith("en"):
                            label = "English"

                        if is_orig:
                            label = f"{label} (Original)"
                        elif is_dub or (not track_code.startswith("en") and track_code != "default"):
                            label = f"{label} (Dubbed)"

                        tracks_map[track_code] = {
                            "code": track_code,
                            "label": label,
                            "is_original": is_orig
                        }

            track_list = list(tracks_map.values())
            def sort_key(t):
                c = t["code"].lower()
                if t["is_original"] or c.startswith("en"):
                    return 0
                if c.startswith("id"):
                    return 1
                return 2
            track_list.sort(key=sort_key)
            return track_list
    except Exception as e:
        print(f"[Audio Tracks Probe Warning] Failed to probe tracks: {e}")
        return []

def get_ydl_options(output_path: str, audio_lang: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Returns yt-dlp options configured for safe fallback without requiring login or cookies.
    Forces highest resolution (up to 4K 2160p / 1440p / 1080p).
    Supports selecting specific audio track language if multi-language audio is available.
    """
    opts: Dict[str, Any] = {
        "outtmpl": output_path,
        "nocheckcertificate": True,
        "no_warnings": True,
        "quiet": False
    }

    if audio_lang and audio_lang != "default":
        base_lang = audio_lang.split("-")[0].lower()
        opts["format"] = (
            f"bestvideo[height<=2160]+bestaudio[language={audio_lang}]/"
            f"bestvideo[height<=2160]+bestaudio[language*={base_lang}]/"
            f"bestvideo[height<=2160]+bestaudio[format_note*={base_lang}]/"
            f"bestvideo+bestaudio[language={audio_lang}]/"
            f"bestvideo+bestaudio[language*={base_lang}]/"
            f"bestvideo[height<=2160]+bestaudio/best"
        )
        # Multi-track audio: Do not restrict player_client to tv_embedded,
        # which omits dub tracks and forces fallback to format 18.
    else:
        opts["format"] = "bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=2160]+bestaudio/bestvideo+bestaudio/best[height>=1080]/best[ext=mp4]/best"
        opts["extractor_args"] = {
            "youtube": {
                "player_client": ["tv_embedded", "creator", "android", "ios"],
                "player_skip": ["webpage", "configs"]
            }
        }
        opts["http_headers"] = {
            "User-Agent": "Mozilla/5.0 (PlayStation 4 9.00) AppleWebKit/537.78 (KHTML, like Gecko)"
        }

    return opts

def download_video(
    url: str,
    output_dir: str,
    cancel_event: Optional[threading.Event] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None,
    audio_lang: Optional[str] = None,
    **kwargs
) -> str:
    """
    Downloads video using Invidious API instance as primary engine (for default tracks),
    or yt-dlp directly when specific multi-language audio track is selected.
    """
    import yt_dlp

    if not is_valid_video_url(url):
        raise ValueError(f"Invalid URL: '{url}'. Harap masukkan URL http:// atau https://")

    out_dir_path = Path(output_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)

    # 1. Primary Engine: Invidious API stream download (only if default audio track requested)
    vid_id = extract_video_id(url)
    if (not audio_lang or audio_lang == "default") and vid_id:
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

    # 2. yt-dlp engine
    auto_update_ytdlp()

    lang_suffix = f"_{audio_lang}" if (audio_lang and audio_lang != "default") else ""
    out_template = str(out_dir_path / f"yt_download_%(id)s{lang_suffix}.%(ext)s")

    def progress_hook(d: Dict[str, Any]):
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("Download cancelled by user")
        if d.get("status") == "downloading" and progress_callback:
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            pct = int((downloaded / total) * 100) if total > 0 else 0
            msg = f"Mengunduh audio track [{audio_lang}] ({pct}%)" if (audio_lang and audio_lang != "default") else f"Mengunduh (yt-dlp): {pct}%"
            progress_callback(pct, msg)

    ffmpeg_bin = get_ffmpeg_bin()

    opts = get_ydl_options(out_template, audio_lang=audio_lang)
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
