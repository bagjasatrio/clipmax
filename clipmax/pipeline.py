import os
import subprocess
import threading
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, List
from pydantic import BaseModel
from clipmax.config import AppConfig, get_ffmpeg_bin
from clipmax.audio import extract_audio
from clipmax.transcriber import transcribe_audio, cleanup_vram
from clipmax.ai_gateway import evaluate_viral_clips, ViralClipCandidate
from clipmax.reframe import detect_face_centers, calculate_crop_box, smooth_ema_series, ReframeStrategy
from clipmax.subtitle import generate_kinetic_ass
from clipmax.renderer import render_clip
from clipmax.downloader import download_video, is_valid_video_url

class PipelineStatus(str, Enum):
    IDLE = "IDLE"
    DOWNLOADING = "DOWNLOADING"
    EXTRACTING_AUDIO = "EXTRACTING_AUDIO"
    TRANSCRIBING = "TRANSCRIBING"
    AI_EVALUATING = "AI_EVALUATING"
    TRACKING_FACES = "TRACKING_FACES"
    RENDERING = "RENDERING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

class ClipResult(BaseModel):
    clip_id: int
    title: str
    hook: str
    virality_score: int
    reasoning: str
    start_time: float
    end_time: float
    staging_path: str
    thumbnail_path: str
    reframe_mode: str = "CROP_TRACKING"

def kill_process_tree(pid: int) -> None:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        else:
            os.kill(pid, 9)
    except Exception:
        pass

def generate_thumbnail(video_path: str, output_thumb_path: str, time_offset: float = 1.0) -> str:
    out_p = Path(output_thumb_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = get_ffmpeg_bin()
    cmd = [
        ffmpeg_bin,
        "-y",
        "-ss", str(time_offset),
        "-i", str(Path(video_path).resolve()),
        "-vframes", "1",
        "-vf", "scale=360:640:force_original_aspect_ratio=decrease",
        "-q:v", "2",
        str(out_p.resolve())
    ]
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode != 0 and not out_p.exists():
        # Fallback without time offset if video shorter than time_offset
        cmd[2] = "0.0"
        subprocess.run(cmd, capture_output=True)
    return str(out_p.resolve())

class PipelineOrchestrator:
    def __init__(self, config: AppConfig):
        self.config = config
        self.cancel_requested = threading.Event()
        self.active_pid: Optional[int] = None
        self.status = PipelineStatus.IDLE
        self.temp_files: List[str] = []
        self.staging_files: List[str] = []

    def set_pid(self, pid: int) -> None:
        self.active_pid = pid

    def cancel(self) -> None:
        self.cancel_requested.set()
        if self.active_pid:
            kill_process_tree(self.active_pid)
            self.active_pid = None
        self.cleanup(clean_staging=True)
        self.status = PipelineStatus.CANCELLED

    def cleanup(self, clean_staging: bool = False) -> None:
        for f in self.temp_files:
            try:
                p = Path(f)
                if p.exists():
                    p.unlink(missing_ok=True)
            except Exception:
                pass
        self.temp_files.clear()

        if clean_staging:
            for f in self.staging_files:
                try:
                    p = Path(f)
                    if p.exists():
                        p.unlink(missing_ok=True)
                except Exception:
                    pass
            self.staging_files.clear()

        cleanup_vram()

    def run(
        self,
        input_source: str,
        progress_callback: Optional[Callable[[PipelineStatus, int, str], None]] = None,
        target_clip_count: Optional[int] = None,
        min_duration: Optional[float] = None,
        max_duration: Optional[float] = None,
        campaign_rules: Optional[str] = None
    ) -> List[ClipResult]:
        self.cancel_requested.clear()
        self.temp_files.clear()
        self.staging_files.clear()
        results: List[ClipResult] = []

        target_count = target_clip_count if target_clip_count is not None else self.config.target_clip_count
        min_dur = min_duration if min_duration is not None else self.config.min_duration
        max_dur = max_duration if max_duration is not None else self.config.max_duration
        rules = campaign_rules if campaign_rules is not None else self.config.campaign_rules

        temp_dir = Path(self.config.temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        staging_dir = temp_dir / "staging"
        staging_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Step 0: Check if URL or local file
            if is_valid_video_url(input_source):
                self.status = PipelineStatus.DOWNLOADING
                if progress_callback:
                    progress_callback(self.status, 5, "Mengunduh video dari tautan via yt-dlp...")
                
                download_folder = str((temp_dir / "downloads").resolve())
                def on_dl_progress(pct, msg):
                    if progress_callback:
                        progress_callback(PipelineStatus.DOWNLOADING, min(10, int(pct * 0.1)), msg)

                video_path = download_video(
                    input_source,
                    download_folder,
                    cancel_event=self.cancel_requested,
                    progress_callback=on_dl_progress
                )
                self.temp_files.append(video_path)
            else:
                video_path = input_source
                if not Path(video_path).exists():
                    raise FileNotFoundError(f"Video file not found: {video_path}")

            if self.cancel_requested.is_set():
                self.status = PipelineStatus.CANCELLED
                return []

            # Stage 1: Audio Extraction (10%)
            self.status = PipelineStatus.EXTRACTING_AUDIO
            temp_wav = str((temp_dir / "temp_audio.wav").resolve())
            self.temp_files.append(temp_wav)

            if progress_callback:
                progress_callback(self.status, 15, "Mengekstrak audio WAV 16kHz mono...")
            extract_audio(video_path, temp_wav, self.cancel_requested, self.set_pid)
            self.active_pid = None

            if self.cancel_requested.is_set():
                self.status = PipelineStatus.CANCELLED
                return []

            # Stage 2: Transcription (30%)
            self.status = PipelineStatus.TRANSCRIBING
            if progress_callback:
                progress_callback(self.status, 35, "Transkripsi kata via Faster-Whisper (CUDA float16)...")
            words, full_text = transcribe_audio(
                temp_wav,
                model_size=self.config.whisper_model,
                device="cuda",
                compute_type="float16"
            )

            if self.cancel_requested.is_set():
                self.status = PipelineStatus.CANCELLED
                return []

            # Stage 3: LLM Virality Evaluation (50%)
            self.status = PipelineStatus.AI_EVALUATING
            if progress_callback:
                progress_callback(self.status, 50, "Mengevaluasi hook & klip viral via LLM...")
            candidates = evaluate_viral_clips(
                transcript=full_text,
                endpoint_url=self.config.endpoint_url,
                api_key=self.config.api_key,
                model=self.config.selected_model,
                target_clip_count=target_count,
                min_duration=min_dur,
                max_duration=max_dur,
                campaign_rules=rules
            )

            if not candidates:
                raise RuntimeError("Tidak ada klip viral yang ditemukan dari transkrip")

            if self.cancel_requested.is_set():
                self.status = PipelineStatus.CANCELLED
                return []

            # Process Each Clip in Staging Directory (Stages 4, 5, 6)
            total_clips = len(candidates)
            for idx, clip in enumerate(candidates):
                clip_num = idx + 1
                base_pct = 50 + int((idx / total_clips) * 45)

                # Stage 4: Scene & Content-Aware Tracking (70%)
                self.status = PipelineStatus.TRACKING_FACES
                if progress_callback:
                    progress_callback(self.status, base_pct, f"Analisis konten visual klip {clip_num}/{total_clips}...")

                centers, strategy = detect_face_centers(video_path, clip.start_time, clip.end_time)
                if strategy in (ReframeStrategy.CROP_TRACKING, "CROP_TRACKING", "single_speaker") and centers:
                    smoothed = smooth_ema_series(centers, alpha=0.15)
                    avg_center = sum(smoothed) / len(smoothed)
                    crop_x, crop_w, crop_h = calculate_crop_box(1920, 1080, avg_center)
                    mode = "CROP_TRACKING"
                else:
                    crop_x = 0
                    mode = "BLURRED_BACKGROUND"

                if self.cancel_requested.is_set():
                    self.status = PipelineStatus.CANCELLED
                    return []

                # Stage 5: Subtitle Generation
                temp_ass = str((temp_dir / f"clip_{clip_num}.ass").resolve())
                self.temp_files.append(temp_ass)
                generate_kinetic_ass(words, clip.start_time, clip.end_time, temp_ass)

                # Stage 6: Video Rendering into Staging Cache (NVENC Forced)
                self.status = PipelineStatus.RENDERING
                if progress_callback:
                    mode_label = "Crop Wajah 9:16" if mode == "CROP_TRACKING" else "Blurred BG (Utuh)"
                    progress_callback(self.status, min(95, base_pct + 10), f"Rendering NVENC ({mode_label}) klip {clip_num}/{total_clips}...")

                staging_clip_path = str((staging_dir / f"clipmax_{clip_num}_{int(clip.start_time)}.mp4").resolve())
                self.staging_files.append(staging_clip_path)

                render_clip(
                    input_video=video_path,
                    output_clip=staging_clip_path,
                    start_time=clip.start_time,
                    end_time=clip.end_time,
                    crop_x=crop_x,
                    ass_path=temp_ass,
                    use_gpu=True,
                    video_bitrate=self.config.video_bitrate,
                    audio_bitrate=self.config.audio_bitrate,
                    cancel_event=self.cancel_requested,
                    pid_callback=self.set_pid,
                    reframe_mode=mode
                )
                self.active_pid = None

                # Generate thumbnail for preview gallery
                staging_thumb_path = str((staging_dir / f"thumb_{clip_num}_{int(clip.start_time)}.jpg").resolve())
                self.staging_files.append(staging_thumb_path)
                generate_thumbnail(staging_clip_path, staging_thumb_path)

                results.append(
                    ClipResult(
                        clip_id=clip_num,
                        title=clip.title,
                        hook=clip.hook,
                        virality_score=clip.virality_score,
                        reasoning=clip.reasoning,
                        start_time=clip.start_time,
                        end_time=clip.end_time,
                        staging_path=staging_clip_path,
                        thumbnail_path=staging_thumb_path,
                        reframe_mode=mode
                    )
                )

            self.status = PipelineStatus.COMPLETED
            if progress_callback:
                progress_callback(self.status, 100, f"Selesai! {len(results)} klip siap di Review Workspace.")
            return results

        except Exception as e:
            self.cleanup(clean_staging=True)
            if self.cancel_requested.is_set():
                self.status = PipelineStatus.CANCELLED
                return []
            self.status = PipelineStatus.FAILED
            raise e
        finally:
            # Clean intermediate temp files (.wav, .ass) but preserve staging clips on normal run
            self.cleanup(clean_staging=False)
