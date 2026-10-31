import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger("clipmax.uploader.tiktok")


def is_tiktok_authenticated(
    cookies_path: Optional[str] = "cookies.txt",
    session_id: Optional[str] = None,
) -> bool:
    """Memeriksa apakah kredensial TikTok (sessionid atau cookies.txt) tersedia."""
    if session_id and session_id.strip():
        return True
    if cookies_path:
        cp = Path(cookies_path).resolve()
        if cp.exists() and cp.is_file():
            try:
                content = cp.read_text(encoding="utf-8", errors="ignore")
                return "tiktok.com" in content and "sessionid" in content.lower()
            except Exception:
                return False
    return False


def upload_tiktok_video(
    video_path: str,
    description: str = "",
    cookies_path: Optional[str] = "cookies.txt",
    session_id: Optional[str] = None,
    visibility: str = "everyone",
    headless: bool = True,
) -> Dict[str, Any]:
    """
    Mengunggah video ke TikTok menggunakan session cookie atau sessionid melalui browser automation (Playwright).
    Visibility options: 'everyone', 'friends', 'only_you'.
    """
    vpath = Path(video_path).resolve()
    if not vpath.exists() or not vpath.is_file():
        return {
            "success": False,
            "platform": "tiktok",
            "error": f"File video tidak ditemukan: {vpath}",
        }

    # Resolve cookies / sessionid
    resolved_cookies_file = None
    if cookies_path:
        cp = Path(cookies_path).resolve()
        if cp.exists() and cp.is_file():
            # If cookies file contains non-tiktok domains, generate sanitized temporary file
            try:
                content = cp.read_text(encoding="utf-8", errors="ignore")
                lines = content.splitlines()
                tiktok_lines = [l for l in lines if "tiktok.com" in l.lower()]
                if len(tiktok_lines) < len(lines) - 5:
                    sanitized_p = cp.parent / "tiktok_cookies_sanitized.txt"
                    sanitized_p.write_text("# Netscape HTTP Cookie File\n" + "\n".join(tiktok_lines) + "\n", encoding="utf-8")
                    resolved_cookies_file = str(sanitized_p)
                else:
                    resolved_cookies_file = str(cp)
            except Exception:
                resolved_cookies_file = str(cp)

    clean_session_id = session_id.strip() if session_id and session_id.strip() else None

    if not resolved_cookies_file and not clean_session_id:
        return {
            "success": False,
            "platform": "tiktok",
            "error": (
                "Kredensial TikTok tidak ditemukan. "
                "Sediakan file cookies.txt (format Netscape) atau masukkan sessionid TikTok di pengaturan."
            ),
        }

    # Normalize visibility
    valid_vis = ("everyone", "friends", "only_you")
    vis = visibility.lower() if visibility.lower() in valid_vis else "everyone"

    try:
        from tiktok_uploader.upload import upload_video

        logger.info(f"Memulai upload TikTok untuk {vpath.name} (headless={headless}, visibility={vis})...")

        # Note: tiktok-uploader requires cookies string/path or sessionid
        failed_videos = upload_video(
            filename=str(vpath),
            description=description,
            cookies=resolved_cookies_file or "",
            sessionid=clean_session_id,
            visibility=vis,
            browser="chromium",
            headless=headless,
        )

        if failed_videos:
            err = f"TikTok uploader mengembalikan kegagalan untuk video: {failed_videos}"
            logger.warning(err)
            return {"success": False, "platform": "tiktok", "error": err}

        return {
            "success": True,
            "platform": "tiktok",
            "message": "Video berhasil diposting ke TikTok.",
            "visibility": vis,
        }

    except Exception as e:
        logger.error(f"Error saat mengunggah video ke TikTok: {e}")
        return {"success": False, "platform": "tiktok", "error": str(e)}
