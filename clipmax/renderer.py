import os
import sys
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Optional, Callable, List, Any, Union
from clipmax.config import get_ffmpeg_bin, sanitize_ffmpeg_path, is_cuda_available

def is_nvenc_supported() -> bool:
    if not is_cuda_available():
        return False
    ffmpeg_bin = get_ffmpeg_bin()
    try:
        res = subprocess.run(
            [ffmpeg_bin, "-encoders"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return "h264_nvenc" in res.stdout
    except Exception:
        return False

def render_clip(
    input_video: str,
    output_clip: str,
    start_time: float,
    end_time: float,
    crop_x: Union[int, float, str] = 0,
    ass_path: Optional[str] = None,
    use_gpu: bool = True,
    video_bitrate: str = "6000k",
    audio_bitrate: str = "192k",
    cancel_event: Optional[threading.Event] = None,
    pid_callback: Optional[Callable[[int], None]] = None,
    reframe_mode: str = "CROP_TRACKING",
    scenes: Optional[List[Any]] = None
) -> str:
    in_p = Path(input_video)
    if not os.path.exists(str(in_p)):
        raise FileNotFoundError(f"Input video not found: {input_video}")

    out_p = Path(output_clip)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    # Force NVENC GPU encoder
    encoder = "h264_nvenc" if use_gpu else "libx264"
    preset = "p6" if encoder == "h264_nvenc" else "veryfast"
    clip_dur = max(0.1, end_time - start_time)
    print(f"[CUT] Memotong segmen dari detik {start_time:.2f} sampai {end_time:.2f} (durasi: {clip_dur:.2f}s)")
    print(f"[ClipMax Render] Rendering via FFmpeg using encoder={encoder}, preset={preset}, mode={reframe_mode}...")

    escaped_ass = sanitize_ffmpeg_path(ass_path) if (ass_path and os.path.exists(ass_path)) else None

    # Resolve active mode and crop_x
    active_mode = reframe_mode
    active_crop_x = crop_x
    if scenes and len(scenes) >= 1:
        active_mode = scenes[0].mode
        if scenes[0].mode in ("CROP_9_16", "CROP_TRACKING"):
            active_crop_x = scenes[0].crop_x

    # NVENC & audio encoder settings for highest Full HD 1080x1920 quality
    if encoder == "h264_nvenc":
        encoder_args = [
            "-c:v", "h264_nvenc",
            "-preset", "p6",
            "-tune", "hq",
            "-rc", "vbr",
            "-cq", "19",
            "-b:v", "6M",
            "-maxrate", "10M",
            "-bufsize", "12M",
            "-c:a", "aac",
            "-b:a", "192k",
        ]
    else:
        encoder_args = [
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "19",
            "-b:v", video_bitrate or "6M",
            "-c:a", "aac",
            "-b:a", audio_bitrate or "192k",
        ]

    # Multi-scene dynamic layout transition inside the same clip
    if scenes and len(scenes) > 1:
        v_chains = []
        for i, sc in enumerate(scenes):
            t_s = f"{sc.start_time:.3f}"
            t_e = f"{sc.end_time:.3f}"
            if sc.mode in ("BLURRED_BACKGROUND", "BLURRED_BG"):
                chain = (
                    f"[0:v]trim=start={t_s}:end={t_e},setpts=PTS-STARTPTS,split[bg_in{i}][fg_in{i}];"
                    f"[bg_in{i}]scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,boxblur=20:20[bg{i}];"
                    f"[fg_in{i}]scale=1080:-1:flags=lanczos[fg{i}];"
                    f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2,setsar=1[v{i}]"
                )
            else:
                crop_x_val = f"'{sc.crop_x}'" if (isinstance(sc.crop_x, str) and not str(sc.crop_x).isdigit()) else str(sc.crop_x)
                chain = (
                    f"[0:v]trim=start={t_s}:end={t_e},setpts=PTS-STARTPTS,"
                    f"crop=ih*(9/16):ih:{crop_x_val}:0,scale=1080:1920:flags=lanczos,setsar=1[v{i}]"
                )
            v_chains.append(chain)

        concat_inputs = "".join([f"[v{i}]" for i in range(len(scenes))])
        sub_filter = f",subtitles='{escaped_ass}'" if escaped_ass else ""
        concat_line = f"{concat_inputs}concat=n={len(scenes)}:v=1:a=0{sub_filter}[outv]"
        audio_line = f"[0:a]atrim=start=0.0:end={clip_dur:.3f},asetpts=PTS-STARTPTS[outa]"

        full_filter = ";".join(v_chains) + ";" + concat_line + ";" + audio_line

        cmd = [
            get_ffmpeg_bin(),
            "-y",
            "-ss", f"{start_time:.2f}",
            "-i", str(in_p.resolve()),
            "-to", f"{clip_dur:.2f}",
            "-filter_complex", full_filter,
            "-map", "[outv]",
            "-map", "[outa]",
            *encoder_args,
            str(out_p.resolve())
        ]

    elif active_mode in ("BLURRED_BACKGROUND", "BLURRED_BG"):
        # Mode BLURRED_BACKGROUND: Canvas 1080x1920 with blurred background and centered 16:9 foreground
        sub_filter = f",subtitles='{escaped_ass}'" if escaped_ass else ""
        filter_str = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,boxblur=20:20[bg];"
            f"[0:v]scale=1080:-1:flags=lanczos[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1{sub_filter}[outv]"
        )
        cmd = [
            get_ffmpeg_bin(),
            "-y",
            "-ss", f"{start_time:.2f}",
            "-i", str(in_p.resolve()),
            "-to", f"{clip_dur:.2f}",
            "-filter_complex", filter_str,
            "-map", "[outv]",
            "-map", "0:a?",
            *encoder_args,
            str(out_p.resolve())
        ]
    else:
        # Mode CROP_9_16 / CROP_TRACKING: 9:16 crop centered on tracked face with subtle edge sharpening
        crop_x_val = f"'{active_crop_x}'" if (isinstance(active_crop_x, str) and not str(active_crop_x).isdigit()) else str(active_crop_x)
        filter_parts = [
            f"crop=ih*(9/16):ih:{crop_x_val}:0",
            "scale=1080:1920:flags=lanczos",
            "unsharp=5:5:0.6:3:3:0.3",
            "setsar=1"
        ]
        if escaped_ass:
            filter_parts.append(f"subtitles='{escaped_ass}'")
        vf_chain = ",".join(filter_parts)

        cmd = [
            get_ffmpeg_bin(),
            "-y",
            "-ss", f"{start_time:.2f}",
            "-i", str(in_p.resolve()),
            "-to", f"{clip_dur:.2f}",
            "-vf", vf_chain,
            *encoder_args,
            str(out_p.resolve())
        ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    if pid_callback:
        pid_callback(proc.pid)

    stdout, stderr = proc.communicate()

    if cancel_event and cancel_event.is_set():
        if out_p.exists():
            out_p.unlink(missing_ok=True)
        raise RuntimeError("Video rendering cancelled by user")

    if proc.returncode != 0:
        err_msg = stderr.decode('utf-8', errors='ignore')
        print(f"\n[ClipMax Render ERROR] FFmpeg render failed:\n{err_msg}", file=sys.stderr)
        raise RuntimeError(f"FFmpeg render failed: {err_msg}")

    return str(out_p.resolve())

def apply_clip_overlays(
    input_video: str,
    output_video: str,
    ass_path: Optional[str] = None,
    image_path: Optional[str] = None,
    image_x_pct: float = 85.0,
    image_y_pct: float = 8.0,
    image_scale_pct: float = 16.0,
    image_opacity: float = 1.0,
    use_gpu: bool = True
) -> str:
    """Burns an ASS subtitle/text overlay and/or an image watermark overlay onto an existing 9:16 video."""
    in_p = Path(input_video)
    if not in_p.exists():
        raise FileNotFoundError(f"Input video not found: {input_video}")
    out_p = Path(output_video)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    encoder = "h264_nvenc" if (use_gpu and is_nvenc_supported()) else "libx264"
    preset = "p6" if encoder == "h264_nvenc" else "veryfast"

    if encoder == "h264_nvenc":
        encoder_args = [
            "-c:v", "h264_nvenc",
            "-preset", "p6",
            "-tune", "hq",
            "-rc", "vbr",
            "-cq", "19",
            "-b:v", "6M",
            "-maxrate", "10M",
            "-bufsize", "12M",
            "-c:a", "copy"
        ]
    else:
        encoder_args = [
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "18",
            "-c:a", "copy"
        ]

    has_ass = bool(ass_path and os.path.exists(ass_path))
    has_img = bool(image_path and os.path.exists(image_path))

    if not has_ass and not has_img:
        shutil.copy2(str(in_p), str(out_p))
        return str(out_p.resolve())

    cmd = [get_ffmpeg_bin(), "-y", "-i", str(in_p.resolve())]

    if has_ass and has_img:
        cmd.extend(["-i", str(Path(image_path).resolve())])
        escaped_ass = sanitize_ffmpeg_path(ass_path)
        img_w = max(32, int(round((image_scale_pct / 100.0) * 1080)))
        alpha_filter = f",colorchannelmixer=aa={image_opacity:.2f}" if image_opacity < 0.99 else ""
        filter_complex = (
            f"[1:v]scale={img_w}:-1,format=rgba{alpha_filter}[logo];"
            f"[0:v]subtitles='{escaped_ass}'[v_sub];"
            f"[v_sub][logo]overlay="
            f"x='min(max(0,(main_w*{image_x_pct}/100)-(overlay_w/2)),main_w-overlay_w)':"
            f"y='min(max(0,(main_h*{image_y_pct}/100)-(overlay_h/2)),main_h-overlay_h)'"
        )
        cmd.extend(["-filter_complex", filter_complex])
    elif has_img:
        cmd.extend(["-i", str(Path(image_path).resolve())])
        img_w = max(32, int(round((image_scale_pct / 100.0) * 1080)))
        alpha_filter = f",colorchannelmixer=aa={image_opacity:.2f}" if image_opacity < 0.99 else ""
        filter_complex = (
            f"[1:v]scale={img_w}:-1,format=rgba{alpha_filter}[logo];"
            f"[0:v][logo]overlay="
            f"x='min(max(0,(main_w*{image_x_pct}/100)-(overlay_w/2)),main_w-overlay_w)':"
            f"y='min(max(0,(main_h*{image_y_pct}/100)-(overlay_h/2)),main_h-overlay_h)'"
        )
        cmd.extend(["-filter_complex", filter_complex])
    else:
        escaped_ass = sanitize_ffmpeg_path(ass_path)
        cmd.extend(["-vf", f"subtitles='{escaped_ass}'"])

    cmd.extend([*encoder_args, str(out_p.resolve())])

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"[Overlay Render ERROR] FFmpeg failed: {proc.stderr}", file=sys.stderr)
        raise RuntimeError(f"FFmpeg overlay rendering failed: {proc.stderr}")

    return str(out_p.resolve())

def apply_ass_overlay(
    input_video: str,
    output_video: str,
    ass_path: str,
    use_gpu: bool = True
) -> str:
    """Burns an ASS subtitle or text overlay onto an existing 9:16 video."""
    return apply_clip_overlays(
        input_video=input_video,
        output_video=output_video,
        ass_path=ass_path,
        use_gpu=use_gpu
    )
