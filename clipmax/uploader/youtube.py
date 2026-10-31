import os
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

logger = logging.getLogger("clipmax.uploader.youtube")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def get_youtube_service(
    client_secrets_path: str = "client_secrets.json",
    token_path: str = "youtube_token.json",
    interactive: bool = True,
):
    """
    Mengambil instance YouTube API Service v3 terotentikasi.
    Mendukung token cache dan refresh otomatis.
    """
    token_p = Path(token_path).resolve()
    secrets_p = Path(client_secrets_path).resolve()

    creds = None
    if token_p.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_p), SCOPES)
        except Exception as e:
            logger.warning(f"Gagal memuat token YouTube dari {token_p}: {e}")
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(token_p, "w", encoding="utf-8") as tf:
                    tf.write(creds.to_json())
            except Exception as e:
                logger.warning(f"Gagal me-refresh token YouTube: {e}")
                creds = None

        if not creds or not creds.valid:
            if not secrets_p.exists():
                raise FileNotFoundError(
                    f"File client secrets tidak ditemukan di: {secrets_p}. "
                    "Unduh client_secrets.json (OAuth 2.0 Desktop) dari Google Cloud Console."
                )

            if not interactive:
                raise PermissionError("YouTube belum terotentikasi dan mode interaktif dinonaktifkan.")

            flow = InstalledAppFlow.from_client_secrets_file(str(secrets_p), SCOPES)
            creds = flow.run_local_server(port=0)
            token_p.parent.mkdir(parents=True, exist_ok=True)
            with open(token_p, "w", encoding="utf-8") as tf:
                tf.write(creds.to_json())

    return build("youtube", "v3", credentials=creds)


def is_youtube_authenticated(token_path: str = "youtube_token.json") -> bool:
    """Memeriksa apakah token YouTube sudah ada dan valid atau dapat di-refresh."""
    token_p = Path(token_path).resolve()
    if not token_p.exists():
        return False
    try:
        creds = Credentials.from_authorized_user_file(str(token_p), SCOPES)
        return bool(creds and (creds.valid or creds.refresh_token))
    except Exception:
        return False


def authenticate_youtube(
    client_secrets_path: str = "client_secrets.json",
    token_path: str = "youtube_token.json",
) -> Dict[str, Any]:
    """Menjalankan OAuth interaktif sekali untuk membuat youtube_token.json."""
    try:
        get_youtube_service(
            client_secrets_path=client_secrets_path,
            token_path=token_path,
            interactive=True,
        )
        return {"success": True, "message": "Otentikasi YouTube berhasil. Token tersimpan."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def upload_youtube_short(
    video_path: str,
    title: str,
    description: str = "",
    tags: Optional[List[str]] = None,
    privacy_status: str = "private",
    client_secrets_path: str = "client_secrets.json",
    token_path: str = "youtube_token.json",
    interactive: bool = True,
) -> Dict[str, Any]:
    """
    Mengunggah video ke YouTube Shorts.
    Memastikan judul/deskripsi memiliki tag #Shorts agar dideteksi sebagai Shorts.
    """
    vpath = Path(video_path).resolve()
    if not vpath.exists() or not vpath.is_file():
        return {
            "success": False,
            "platform": "youtube",
            "error": f"File video tidak ditemukan: {vpath}",
        }

    # Format title & Shorts tag
    short_title = title.strip()
    if "#Shorts" not in short_title and "#shorts" not in short_title:
        if len(short_title) > 90:
            short_title = f"{short_title[:88]}... #Shorts"
        else:
            short_title = f"{short_title} #Shorts"

    final_tags = tags or ["Shorts", "ClipMax", "Viral"]
    if "Shorts" not in final_tags and "shorts" not in final_tags:
        final_tags.append("Shorts")

    try:
        youtube = get_youtube_service(
            client_secrets_path=client_secrets_path,
            token_path=token_path,
            interactive=interactive,
        )

        body = {
            "snippet": {
                "title": short_title[:100],
                "description": description or short_title,
                "tags": final_tags,
                "categoryId": "22",
            },
            "status": {
                "privacyStatus": privacy_status.lower() if privacy_status.lower() in ("public", "unlisted", "private") else "private",
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(str(vpath), chunksize=-1, resumable=True, mimetype="video/mp4")
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        while response is None:
            status, response = request.next_chunk()

        video_id = response.get("id")
        return {
            "success": True,
            "platform": "youtube",
            "video_id": video_id,
            "url": f"https://www.youtube.com/shorts/{video_id}",
            "privacy": privacy_status,
        }

    except HttpError as e:
        error_msg = f"YouTube API Error {e.resp.status}: {e.content.decode('utf-8') if hasattr(e, 'content') else str(e)}"
        logger.error(error_msg)
        return {"success": False, "platform": "youtube", "error": error_msg}
    except Exception as e:
        logger.error(f"Gagal mengunggah video ke YouTube: {e}")
        return {"success": False, "platform": "youtube", "error": str(e)}
