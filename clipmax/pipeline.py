import os
import shutil
import subprocess
import threading
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, List
from pydantic import BaseModel
from clipmax.config import AppConfig, get_ffmpeg_bin, sanitize_ffmpeg_path
from clipmax.audio import extract_audio
from clipmax.transcriber import transcribe_audio, cleanup_vram, WordSegment
from clipmax.ai_gateway import evaluate_viral_clips, ViralClipCandidate
from clipmax.reframe import (
    detect_face_centers,
    calculate_crop_box,
    smooth_ema_series,
    ReframeStrategy,
    build_dynamic_crop_expression,
    segment_clip_scenes,
    SceneSegment
)
from clipmax.subtitle import generate_kinetic_ass
from clipmax.subtitle_cleaner import polish_subtitles_with_llm
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
        campaign_rules: Optional[str] = None,
        clip_mode: Optional[str] = None,
        **kwargs
    ) -> List[ClipResult]:
        self.cancel_requested.clear()
        self.temp_files.clear()
        self.staging_files.clear()
        results: List[ClipResult] = []

        target_count = target_clip_count if target_clip_count is not None else self.config.target_clip_count
        min_dur = min_duration if min_duration is not None else self.config.min_duration
        max_dur = max_duration if max_duration is not None else self.config.max_duration
        rules = campaign_rules if campaign_rules is not None else self.config.campaign_rules
        mode_type = clip_mode or getattr(self.config, "clip_mode", "single")

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
                campaign_rules=rules,
                clip_mode=mode_type
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

                is_montage = (clip.mode == "montage" and clip.cuts and len(clip.cuts) >= 2)

                if is_montage:
                    mode_label = f"Montage ({len(clip.cuts)} cuts)"
                    self.status = PipelineStatus.TRACKING_FACES
                    if progress_callback:
                        progress_callback(self.status, base_pct, f"Memproses multi-cut montage klip {clip_num}/{total_clips}...")

                    part_files: List[str] = []
                    shifted_words: List[WordSegment] = []
                    accumulated_dur = 0.0

                    for k, cut in enumerate(clip.cuts):
                        if self.cancel_requested.is_set():
                            self.status = PipelineStatus.CANCELLED
                            return []

                        part_file = str((temp_dir / f"temp_part_{clip_num}_{k}.mp4").resolve())
                        part_files.append(part_file)
                        self.temp_files.append(part_file)

                        cut_scenes = segment_clip_scenes(video_path, cut.start, cut.end)
                        default_cx = cut_scenes[0].crop_x if cut_scenes else "0"
                        cut_mode = cut_scenes[0].mode if cut_scenes else "CROP_TRACKING"

                        render_clip(
                            input_video=video_path,
                            output_clip=part_file,
                            start_time=cut.start,
                            end_time=cut.end,
                            crop_x=default_cx,
                            ass_path=None,
                            use_gpu=True,
                            video_bitrate=self.config.video_bitrate,
                            audio_bitrate=self.config.audio_bitrate,
                            cancel_event=self.cancel_requested,
                            pid_callback=self.set_pid,
                            reframe_mode=cut_mode,
                            scenes=cut_scenes
                        )

                        cut_dur = cut.end - cut.start
                        for w in words:
                            if w.start >= (cut.start - 0.1) and w.end <= (cut.end + 0.1):
                                w_s = accumulated_dur + max(0.0, w.start - cut.start)
                                w_e = accumulated_dur + min(cut_dur, w.end - cut.start)
                                if w_e > w_s:
                                    shifted_words.append(WordSegment(word=w.word, start=w_s, end=w_e, probability=w.probability))
                        accumulated_dur += cut_dur

                    # Merge via concat demuxer
                    concat_list_path = str((temp_dir / f"concat_list_{clip_num}.txt").resolve())
                    self.temp_files.append(concat_list_path)
                    with open(concat_list_path, "w", encoding="utf-8") as cf:
                        for pf in part_files:
                            clean_pf = str(Path(pf).resolve()).replace("\\", "/")
                            cf.write(f"file '{clean_pf}'\n")

                    uncaptioned_montage = str((temp_dir / f"montage_raw_{clip_num}.mp4").resolve())
                    self.temp_files.append(uncaptioned_montage)

                    concat_cmd = [
                        get_ffmpeg_bin(),
                        "-y",
                        "-f", "concat",
                        "-safe", "0",
                        "-i", concat_list_path,
                        "-c", "copy",
                        uncaptioned_montage
                    ]
                    c_res = subprocess.run(concat_cmd, capture_output=True)
                    if c_res.returncode != 0:
                        concat_cmd_fb = [
                            get_ffmpeg_bin(),
                            "-y",
                            "-f", "concat",
                            "-safe", "0",
                            "-i", concat_list_path,
                            "-c:v", "h264_nvenc",
                            "-preset", "p4",
                            "-c:a", "aac",
                            uncaptioned_montage
                        ]
                        subprocess.run(concat_cmd_fb, capture_output=True)

                    # Subtitle generation for montage with auto-polisher
                    temp_ass = str((temp_dir / f"clip_{clip_num}.ass").resolve())
                    self.temp_files.append(temp_ass)
                    polished_shifted_words = polish_subtitles_with_llm(
                        words=shifted_words,
                        clip_start=0.0,
                        clip_end=accumulated_dur,
                        endpoint_url=self.config.endpoint_url,
                        api_key=self.config.api_key,
                        model=self.config.selected_model
                    )
                    generate_kinetic_ass(polished_shifted_words, 0.0, accumulated_dur, temp_ass)

                    self.status = PipelineStatus.RENDERING
                    if progress_callback:
                        progress_callback(self.status, min(95, base_pct + 10), f"Rendering NVENC ({mode_label}) klip {clip_num}/{total_clips}...")

                    staging_clip_path = str((staging_dir / f"clipmax_{clip_num}_{int(clip.start_time)}.mp4").resolve())
                    self.staging_files.append(staging_clip_path)

                    if os.path.exists(temp_ass) and os.path.getsize(temp_ass) > 300:
                        escaped_ass = sanitize_ffmpeg_path(temp_ass)
                        burn_cmd = [
                            get_ffmpeg_bin(),
                            "-y",
                            "-i", uncaptioned_montage,
                            "-vf", f"subtitles='{escaped_ass}'",
                            "-c:v", "h264_nvenc",
                            "-preset", "p4",
                            "-c:a", "copy",
                            staging_clip_path
                        ]
                        b_proc = subprocess.run(burn_cmd, capture_output=True)
                        if b_proc.returncode != 0:
                            burn_cmd[burn_cmd.index("h264_nvenc")] = "libx264"
                            subprocess.run(burn_cmd, capture_output=True)
                    else:
                        shutil.copy2(uncaptioned_montage, staging_clip_path)

                    # Clean up temporary part files after final render
                    for pf in part_files:
                        try:
                            Path(pf).unlink(missing_ok=True)
                        except Exception:
                            pass
                    try:
                        Path(concat_list_path).unlink(missing_ok=True)
                        Path(uncaptioned_montage).unlink(missing_ok=True)
                    except Exception:
                        pass

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
                            reframe_mode="MONTAGE"
                        )
                    )

                else:
                    # Single Clip Mode - existing flow completely untouched!
                    # Stage 4: Scene & Content-Aware Dynamic Split (70%)
                    self.status = PipelineStatus.TRACKING_FACES
                    if progress_callback:
                        progress_callback(self.status, base_pct, f"Segmentasi visual scene dinamis klip {clip_num}/{total_clips}...")

                    scenes = segment_clip_scenes(video_path, clip.start_time, clip.end_time)

                    has_crop = any(sc.mode == "CROP_TRACKING" for sc in scenes)
                    has_blur = any(sc.mode == "BLURRED_BACKGROUND" for sc in scenes)
                    if has_crop and has_blur:
                        mode = "DYNAMIC_SCENE"
                        mode_label = f"Dynamic ({len(scenes)} scenes)"
                    elif has_crop:
                        mode = "CROP_TRACKING"
                        mode_label = "Crop Wajah 9:16"
                    else:
                        mode = "BLURRED_BACKGROUND"
                        mode_label = "Blurred BG (Utuh)"

                    default_crop_x = scenes[0].crop_x if scenes else "0"

                    if self.cancel_requested.is_set():
                        self.status = PipelineStatus.CANCELLED
                        return []

                    # Stage 5: Subtitle Generation with auto-polisher
                    temp_ass = str((temp_dir / f"clip_{clip_num}.ass").resolve())
                    self.temp_files.append(temp_ass)
                    polished_words = polish_subtitles_with_llm(
                        words=words,
                        clip_start=clip.start_time,
                        clip_end=clip.end_time,
                        endpoint_url=self.config.endpoint_url,
                        api_key=self.config.api_key,
                        model=self.config.selected_model
                    )
                    generate_kinetic_ass(polished_words, clip.start_time, clip.end_time, temp_ass)

                    # Stage 6: Video Rendering into Staging Cache (NVENC Forced)
                    self.status = PipelineStatus.RENDERING
                    if progress_callback:
                        progress_callback(self.status, min(95, base_pct + 10), f"Rendering NVENC ({mode_label}) klip {clip_num}/{total_clips}...")

                    staging_clip_path = str((staging_dir / f"clipmax_{clip_num}_{int(clip.start_time)}.mp4").resolve())
                    self.staging_files.append(staging_clip_path)

                    render_clip(
                        input_video=video_path,
                        output_clip=staging_clip_path,
                        start_time=clip.start_time,
                        end_time=clip.end_time,
                        crop_x=default_crop_x,
                        ass_path=temp_ass,
                        use_gpu=True,
                        video_bitrate=self.config.video_bitrate,
                        audio_bitrate=self.config.audio_bitrate,
                        cancel_event=self.cancel_requested,
                        pid_callback=self.set_pid,
                        reframe_mode=scenes[0].mode if scenes else mode,
                        scenes=scenes
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
