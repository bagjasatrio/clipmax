import os
import subprocess
import threading
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, List
from clipmax.config import AppConfig
from clipmax.audio import extract_audio
from clipmax.transcriber import transcribe_audio, cleanup_vram
from clipmax.ai_gateway import evaluate_viral_clips, ViralClipCandidate
from clipmax.reframe import detect_face_centers, calculate_crop_box, smooth_ema_series
from clipmax.subtitle import generate_kinetic_ass
from clipmax.renderer import render_clip

class PipelineStatus(str, Enum):
    IDLE = "IDLE"
    EXTRACTING_AUDIO = "EXTRACTING_AUDIO"
    TRANSCRIBING = "TRANSCRIBING"
    AI_EVALUATING = "AI_EVALUATING"
    TRACKING_FACES = "TRACKING_FACES"
    RENDERING = "RENDERING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

def kill_process_tree(pid: int) -> None:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        else:
            os.kill(pid, 9)
    except Exception:
        pass

class PipelineOrchestrator:
    def __init__(self, config: AppConfig):
        self.config = config
        self.cancel_requested = threading.Event()
        self.active_pid: Optional[int] = None
        self.status = PipelineStatus.IDLE
        self.temp_files: List[str] = []

    def set_pid(self, pid: int) -> None:
        self.active_pid = pid

    def cancel(self) -> None:
        self.cancel_requested.set()
        if self.active_pid:
            kill_process_tree(self.active_pid)
            self.active_pid = None
        self.cleanup()
        self.status = PipelineStatus.CANCELLED

    def cleanup(self) -> None:
        for f in self.temp_files:
            try:
                p = Path(f)
                if p.exists():
                    p.unlink(missing_ok=True)
            except Exception:
                pass
        self.temp_files.clear()
        cleanup_vram()

    def run(
        self,
        video_path: str,
        progress_callback: Optional[Callable[[PipelineStatus, int, str], None]] = None
    ) -> List[str]:
        self.cancel_requested.clear()
        self.temp_files.clear()
        generated_clips: List[str] = []

        temp_dir = Path(self.config.temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        temp_wav = str((temp_dir / "temp_audio.wav").resolve())
        self.temp_files.append(temp_wav)

        try:
            # Stage 1: Audio Extraction (10%)
            self.status = PipelineStatus.EXTRACTING_AUDIO
            if progress_callback:
                progress_callback(self.status, 10, "Mengestrak audio WAV 16kHz mono...")
            extract_audio(video_path, temp_wav, self.cancel_requested, self.set_pid)
            self.active_pid = None

            if self.cancel_requested.is_set():
                self.status = PipelineStatus.CANCELLED
                return []

            # Stage 2: Transcription (30%)
            self.status = PipelineStatus.TRANSCRIBING
            if progress_callback:
                progress_callback(self.status, 30, "Transkripsi kata via Faster-Whisper...")
            words, full_text = transcribe_audio(
                temp_wav,
                model_size=self.config.whisper_model,
                device=self.config.device,
                compute_type=self.config.compute_type
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
                model=self.config.selected_model
            )

            if not candidates:
                raise RuntimeError("Tidak ada klip viral yang ditemukan dari transkrip")

            if self.cancel_requested.is_set():
                self.status = PipelineStatus.CANCELLED
                return []

            # Process Each Clip (Stages 4, 5, 6)
            total_clips = len(candidates)
            for idx, clip in enumerate(candidates):
                clip_num = idx + 1
                base_pct = 50 + int((idx / total_clips) * 45)

                # Stage 4: Tracking Faces (70%)
                self.status = PipelineStatus.TRACKING_FACES
                if progress_callback:
                    progress_callback(self.status, base_pct, f"Auto-reframe wajah klip {clip_num}/{total_clips}...")

                centers, strategy = detect_face_centers(video_path, clip.start_time, clip.end_time)
                if centers:
                    smoothed = smooth_ema_series(centers, alpha=0.15)
                    avg_center = sum(smoothed) / len(smoothed)
                else:
                    avg_center = 960.0

                crop_x, crop_w, crop_h = calculate_crop_box(1920, 1080, avg_center)

                if self.cancel_requested.is_set():
                    self.status = PipelineStatus.CANCELLED
                    return []

                # Stage 5: Subtitle Generation
                temp_ass = str((temp_dir / f"clip_{clip_num}.ass").resolve())
                self.temp_files.append(temp_ass)
                generate_kinetic_ass(words, clip.start_time, clip.end_time, temp_ass)

                # Stage 6: Video Rendering (90%)
                self.status = PipelineStatus.RENDERING
                if progress_callback:
                    progress_callback(self.status, min(95, base_pct + 10), f"Rendering NVENC klip {clip_num}/{total_clips}...")

                out_clip_path = str((output_dir / f"clipmax_{clip_num}_{int(clip.start_time)}.mp4").resolve())
                render_clip(
                    input_video=video_path,
                    output_clip=out_clip_path,
                    start_time=clip.start_time,
                    end_time=clip.end_time,
                    crop_x=crop_x,
                    ass_path=temp_ass,
                    use_gpu=(self.config.device == "cuda"),
                    video_bitrate=self.config.video_bitrate,
                    audio_bitrate=self.config.audio_bitrate,
                    cancel_event=self.cancel_requested,
                    pid_callback=self.set_pid
                )
                self.active_pid = None
                generated_clips.append(out_clip_path)

            self.status = PipelineStatus.COMPLETED
            if progress_callback:
                progress_callback(self.status, 100, "Semua klip berhasil diproses!")
            return generated_clips

        except Exception as e:
            self.cleanup()
            if self.cancel_requested.is_set():
                self.status = PipelineStatus.CANCELLED
                return []
            self.status = PipelineStatus.FAILED
            raise e
        finally:
            self.cleanup()
