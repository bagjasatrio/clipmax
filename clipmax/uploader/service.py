import time
import uuid
import logging
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from clipmax.config import AppConfig
from clipmax.uploader.youtube import upload_youtube_short
from clipmax.uploader.tiktok import upload_tiktok_video

logger = logging.getLogger("clipmax.uploader.service")


class SocialUploadJob(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    clip_id: int
    video_path: str
    title: str
    caption: str
    platforms: List[str]
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED
    results: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    completed_at: Optional[float] = None


class SocialUploaderManager:
    def __init__(self):
        self._jobs: Dict[str, SocialUploadJob] = {}
        self._lock = threading.Lock()

    def get_job(self, job_id: str) -> Optional[SocialUploadJob]:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> List[SocialUploadJob]:
        with self._lock:
            return sorted(list(self._jobs.values()), key=lambda j: j.created_at, reverse=True)

    def submit_upload_job(
        self,
        clip_id: int,
        video_path: str,
        title: str,
        caption: str,
        platforms: List[str],
        config: AppConfig,
    ) -> str:
        job = SocialUploadJob(
            clip_id=clip_id,
            video_path=video_path,
            title=title,
            caption=caption,
            platforms=platforms,
        )

        with self._lock:
            self._jobs[job.job_id] = job

        # Jalankan di background thread agar tidak memblokir server
        t = threading.Thread(
            target=self._run_upload_worker,
            args=(job.job_id, config),
            daemon=True,
            name=f"SocialUpload-{job.job_id}",
        )
        t.start()
        return job.job_id

    def _run_upload_worker(self, job_id: str, config: AppConfig):
        job = self.get_job(job_id)
        if not job:
            return

        job.status = "RUNNING"
        logger.info(f"Memulai pekerjaan posting sosial {job_id} untuk klip {job.clip_id} ke {job.platforms}...")

        all_success = True

        for platform in job.platforms:
            plat = platform.lower().strip()
            if plat == "youtube":
                res = upload_youtube_short(
                    video_path=job.video_path,
                    title=job.title,
                    description=job.caption,
                    privacy_status=getattr(config, "youtube_privacy", "private"),
                    client_secrets_path=getattr(config, "youtube_client_secrets", "client_secrets.json"),
                    token_path=getattr(config, "youtube_token_file", "youtube_token.json"),
                    interactive=False,  # Non-interactive in background worker
                )
                job.results["youtube"] = res
                if not res.get("success"):
                    all_success = False
                    job.errors.append(f"YouTube: {res.get('error')}")

            elif plat == "tiktok":
                tiktok_cookie = getattr(config, "tiktok_cookie_file", None) or getattr(config, "cookie_file", None)
                tiktok_session = getattr(config, "tiktok_session_id", None)
                res = upload_tiktok_video(
                    video_path=job.video_path,
                    description=job.caption,
                    cookies_path=tiktok_cookie,
                    session_id=tiktok_session,
                    visibility=getattr(config, "tiktok_privacy", "everyone"),
                    headless=True,
                )
                job.results["tiktok"] = res
                if not res.get("success"):
                    all_success = False
                    job.errors.append(f"TikTok: {res.get('error')}")

            else:
                job.errors.append(f"Platform '{platform}' tidak didukung.")
                all_success = False

        job.completed_at = time.time()
        job.status = "COMPLETED" if all_success else ("PARTIAL" if any(r.get("success") for r in job.results.values()) else "FAILED")
        logger.info(f"Pekerjaan posting sosial {job_id} selesai dengan status: {job.status}")


upload_manager = SocialUploaderManager()
