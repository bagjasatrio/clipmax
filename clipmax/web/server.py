import os
import time
import shutil
import asyncio
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from clipmax.config import AppConfig, is_cuda_available, clear_temp_cache
from clipmax.pipeline import PipelineOrchestrator, PipelineStatus, ClipResult
from clipmax.ai_gateway import discover_models
from clipmax.downloader import is_valid_video_url, clean_error_message, extract_video_id, download_via_invidious
from clipmax.subtitle import generate_overlay_ass
from clipmax.renderer import apply_ass_overlay, apply_clip_overlays

class PipelineStartRequest(BaseModel):
    input_source: str
    target_clip_count: int = 3
    min_duration: float = 30.0
    max_duration: float = 60.0
    campaign_rules: str = ""
    clip_mode: str = "single"
    subtitle_base_color: str = "#FFFFFF"
    subtitle_highlight_color: str = "#FF2A2A"
    audio_language: Optional[str] = None
    cookie_file: Optional[str] = None

class AudioTracksProbeRequest(BaseModel):
    url: str

class ConfigUpdateRequest(BaseModel):
    endpoint_url: Optional[str] = None
    api_key: Optional[str] = None
    selected_model: Optional[str] = None
    target_clip_count: Optional[int] = None
    duration_preset: Optional[str] = None
    min_duration: Optional[float] = None
    max_duration: Optional[float] = None
    campaign_rules: Optional[str] = None
    clip_mode: Optional[str] = None
    subtitle_base_color: Optional[str] = None
    subtitle_highlight_color: Optional[str] = None
    subtitle_color_preset: Optional[str] = None
    cookie_file: Optional[str] = None

class ExportSingleRequest(BaseModel):
    clip_id: int
    dest_path: str

class ExportAllRequest(BaseModel):
    dest_dir: str

class ClipOverlayRequest(BaseModel):
    clip_id: int
    text: str
    font_name: str = "Impact"
    font_size: int = 56
    text_color: str = "#FFFFFF"
    bg_color: str = "#000000"
    has_bg: bool = True
    position: str = "top"
    x_pct: Optional[float] = None
    y_pct: Optional[float] = None

class ClipImageOverlayRequest(BaseModel):
    clip_id: int
    image_path: str
    x_pct: float = 85.0
    y_pct: float = 8.0
    scale_pct: float = 16.0
    opacity: float = 1.0

class RemoveOverlayRequest(BaseModel):
    clip_id: int

class AppState:
    def __init__(self):
        self.config = AppConfig.load()
        self.orchestrator = PipelineOrchestrator(self.config)
        self.worker_thread: Optional[threading.Thread] = None
        self.status: str = "IDLE"
        self.progress: int = 0
        self.message: str = "Masukkan video untuk memulai kurasi klip 9:16."
        self.clips: List[ClipResult] = []
        self.clip_overlays: Dict[int, Dict[str, Any]] = {}
        self.window_holder: Dict[str, Any] = {"window": None}
        self.active_websockets: List[WebSocket] = []
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def broadcast_sync(self, payload: Dict[str, Any]):
        if self.loop and self.active_websockets:
            asyncio.run_coroutine_threadsafe(self.broadcast(payload), self.loop)

    async def broadcast(self, payload: Dict[str, Any]):
        disconnected = []
        for ws in self.active_websockets:
            try:
                await ws.send_json(payload)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            if ws in self.active_websockets:
                self.active_websockets.remove(ws)

state = AppState()

@asynccontextmanager
async def lifespan(app: FastAPI):
    state.loop = asyncio.get_running_loop()
    # Auto-clean cache on startup (intermediate temp files only, keep staging videos safe)
    clear_temp_cache(state.config.temp_dir, purge_staging=False)
    yield
    # Auto-clean cache on shutdown (intermediate temp files only, keep staging videos safe)
    clear_temp_cache(state.config.temp_dir, purge_staging=False)

app = FastAPI(title="ClipMax Studio Backend", version="2.4.0", lifespan=lifespan)

@app.on_event("startup")
def on_startup():
    clear_temp_cache(state.config.temp_dir, purge_staging=False)

@app.on_event("shutdown")
def on_shutdown():
    clear_temp_cache(state.config.temp_dir, purge_staging=False)

@app.post("/api/cache/clear")
def api_clear_cache():
    count = clear_temp_cache(state.config.temp_dir, purge_staging=True)
    state.clips = []
    return {"status": "ok", "message": f"Cache cleared ({count} items removed)"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/system")
def get_system_status():
    cuda = is_cuda_available()
    device_label = "NVIDIA RTX 3050 | CUDA Active" if cuda else "CPU Only (CUDA Unavailable)"
    return {
        "cuda_available": cuda,
        "device_name": device_label,
        "whisper_model": state.config.whisper_model,
        "nvenc_preset": state.config.nvenc_preset,
    }

@app.get("/api/config")
def get_config():
    return {
        "endpoint_url": state.config.endpoint_url,
        "api_key": state.config.api_key,
        "selected_model": state.config.selected_model,
        "target_clip_count": state.config.target_clip_count,
        "duration_preset": state.config.duration_preset,
        "min_duration": state.config.min_duration,
        "max_duration": state.config.max_duration,
        "campaign_rules": state.config.campaign_rules,
        "clip_mode": getattr(state.config, "clip_mode", "single"),
        "subtitle_base_color": getattr(state.config, "subtitle_base_color", "#FFFFFF"),
        "subtitle_highlight_color": getattr(state.config, "subtitle_highlight_color", "#FF2A2A"),
        "subtitle_color_preset": getattr(state.config, "subtitle_color_preset", "red_white"),
        "engine": "invidious_api"
    }

@app.post("/api/config")
def update_config(req: ConfigUpdateRequest):
    if req.endpoint_url is not None:
        state.config.endpoint_url = req.endpoint_url
    if req.api_key is not None:
        state.config.api_key = req.api_key
    if req.selected_model is not None:
        state.config.selected_model = req.selected_model
    if req.target_clip_count is not None:
        state.config.target_clip_count = req.target_clip_count
    if req.duration_preset is not None:
        state.config.duration_preset = req.duration_preset
    if req.min_duration is not None:
        state.config.min_duration = req.min_duration
    if req.max_duration is not None:
        state.config.max_duration = req.max_duration
    if req.campaign_rules is not None:
        state.config.campaign_rules = req.campaign_rules
    if req.clip_mode is not None:
        state.config.clip_mode = req.clip_mode
    if req.subtitle_base_color is not None:
        state.config.subtitle_base_color = req.subtitle_base_color
    if req.subtitle_highlight_color is not None:
        state.config.subtitle_highlight_color = req.subtitle_highlight_color
    if req.subtitle_color_preset is not None:
        state.config.subtitle_color_preset = req.subtitle_color_preset

    state.config.save()
    state.orchestrator = PipelineOrchestrator(state.config)
    return {"status": "ok", "message": "Config updated"}

@app.get("/api/models")
def get_models():
    models = discover_models(state.config.endpoint_url, state.config.api_key)
    return {"models": models}

@app.post("/api/youtube/audio-tracks")
def probe_youtube_audio_tracks_api(req: AudioTracksProbeRequest):
    from clipmax.downloader import probe_youtube_audio_tracks
    tracks = probe_youtube_audio_tracks(req.url)
    return {"tracks": tracks}

@app.post("/api/pipeline/start")
def start_pipeline(req: PipelineStartRequest):
    if state.worker_thread and state.worker_thread.is_alive():
        raise HTTPException(status_code=400, detail="Pipeline is already running")

    state.status = "STARTING"
    state.progress = 0
    state.message = "Mempersiapkan pipeline..."
    state.clips = []

    def run_worker():
        try:
            def on_progress(p_status: PipelineStatus, pct: int, msg: str):
                state.status = p_status.value
                state.progress = pct
                state.message = msg
                state.broadcast_sync({
                    "type": "progress",
                    "status": p_status.value,
                    "progress": pct,
                    "message": msg
                })

            results = state.orchestrator.run(
                input_source=req.input_source,
                progress_callback=on_progress,
                target_clip_count=req.target_clip_count,
                min_duration=req.min_duration,
                max_duration=req.max_duration,
                campaign_rules=req.campaign_rules,
                clip_mode=req.clip_mode,
                subtitle_base_color=req.subtitle_base_color,
                subtitle_highlight_color=req.subtitle_highlight_color,
                audio_language=req.audio_language
            )

            if state.orchestrator.cancel_requested.is_set():
                state.status = "CANCELLED"
                state.progress = 0
                state.message = "Proses dibatalkan oleh pengguna."
                state.broadcast_sync({
                    "type": "cancelled",
                    "status": "CANCELLED",
                    "progress": 0,
                    "message": state.message
                })
            else:
                state.status = "COMPLETED"
                state.progress = 100
                state.message = f"Selesai! {len(results)} klip siap di Review Workspace."
                state.clips = results
                try:
                    import clipmax.project_manager as pm
                    pm.save_project(
                        clips=results,
                        input_source=req.input_source,
                        clip_mode=req.clip_mode
                    )
                except Exception as ex:
                    print(f"[ProjectManager Error] Gagal simpan project otomatis: {ex}")

                state.broadcast_sync({
                    "type": "complete",
                    "status": "COMPLETED",
                    "progress": 100,
                    "message": state.message,
                    "clips": [c.model_dump() for c in results]
                })

        except Exception as e:
            cleaned_msg = clean_error_message(str(e))
            state.status = "FAILED"
            state.message = cleaned_msg
            state.broadcast_sync({
                "type": "error",
                "status": "FAILED",
                "progress": 0,
                "message": cleaned_msg
            })

    state.worker_thread = threading.Thread(target=run_worker, daemon=True)
    state.worker_thread.start()

    return {"status": "ok", "message": "Pipeline started"}

@app.post("/api/pipeline/cancel")
def cancel_pipeline():
    state.orchestrator.cancel()
    state.status = "CANCELLED"
    state.message = "Proses dibatalkan oleh pengguna."
    state.broadcast_sync({
        "type": "cancelled",
        "status": "CANCELLED",
        "progress": 0,
        "message": state.message
    })
    return {"status": "ok", "message": "Pipeline cancelled"}

@app.get("/api/pipeline/status")
def get_pipeline_status():
    return {
        "status": state.status,
        "progress": state.progress,
        "message": state.message,
        "clips": [c.model_dump() for c in state.clips]
    }

@app.get("/api/clips/{clip_id}/stream")
def stream_clip_video(clip_id: str):
    target_clip = None
    try:
        cid_int = int(clip_id)
        target_clip = next((c for c in state.clips if c.clip_id == cid_int), None)
    except ValueError:
        target_clip = next((c for c in state.clips if str(c.clip_id) == clip_id or c.title == clip_id), None)

    # 1. Try clip.staging_path directly
    if target_clip and target_clip.staging_path and os.path.isfile(target_clip.staging_path):
        return FileResponse(target_clip.staging_path, media_type="video/mp4")

    # 2. Try looking in staging directory
    staging_dir = Path(state.config.temp_dir) / "staging"
    possible_files = list(staging_dir.glob(f"*{clip_id}*.mp4"))
    possible_files = [p for p in possible_files if not p.stem.endswith("_base")]
    if possible_files:
        if target_clip:
            target_clip.staging_path = str(possible_files[0].resolve())
        return FileResponse(str(possible_files[0]), media_type="video/mp4")

    # 3. Try looking in projects directory
    projects_dir = Path("./projects").resolve()
    if projects_dir.exists():
        proj_matches = list(projects_dir.glob(f"**/*{clip_id}*.mp4"))
        proj_matches = [p for p in proj_matches if not p.stem.endswith("_base")]
        if proj_matches:
            dest = staging_dir / proj_matches[0].name
            staging_dir.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                try:
                    shutil.copy2(str(proj_matches[0]), str(dest))
                except Exception:
                    dest = proj_matches[0]
            if target_clip:
                target_clip.staging_path = str(dest.resolve())
            return FileResponse(str(dest), media_type="video/mp4")

    raise HTTPException(status_code=404, detail="Clip video not found on disk")

@app.get("/api/clips/{clip_id}/thumbnail")
def get_clip_thumbnail(clip_id: str):
    target_clip = None
    try:
        cid_int = int(clip_id)
        target_clip = next((c for c in state.clips if c.clip_id == cid_int), None)
    except ValueError:
        target_clip = next((c for c in state.clips if str(c.clip_id) == clip_id or c.title == clip_id), None)

    if target_clip and target_clip.thumbnail_path and os.path.isfile(target_clip.thumbnail_path):
        return FileResponse(target_clip.thumbnail_path, media_type="image/jpeg")

    staging_dir = Path(state.config.temp_dir) / "staging"
    thumb_files = list(staging_dir.glob(f"thumb_{clip_id}*.jpg"))
    if thumb_files:
        return FileResponse(str(thumb_files[0]), media_type="image/jpeg")

    projects_dir = Path("./projects").resolve()
    if projects_dir.exists():
        proj_thumbs = list(projects_dir.glob(f"**/thumb_{clip_id}*.jpg"))
        if proj_thumbs:
            return FileResponse(str(proj_thumbs[0]), media_type="image/jpeg")

    raise HTTPException(status_code=404, detail="Thumbnail not found")

@app.get("/api/export/{clip_id}")
def download_clip_direct(clip_id: str):
    """Direct file download response for browser export fallback."""
    target_clip = None
    try:
        cid_int = int(clip_id)
        target_clip = next((c for c in state.clips if c.clip_id == cid_int), None)
    except ValueError:
        target_clip = next((c for c in state.clips if str(c.clip_id) == clip_id or c.title == clip_id), None)

    if not target_clip or not os.path.exists(target_clip.staging_path):
        staging_dir = Path(state.config.temp_dir) / "staging"
        possible_files = list(staging_dir.glob(f"*{clip_id}*.mp4"))
        if possible_files:
            return FileResponse(
                path=str(possible_files[0]),
                filename=possible_files[0].name,
                media_type="video/mp4"
            )
        raise HTTPException(status_code=404, detail="Clip not found in staging")

    clean_filename = f"clipmax_{target_clip.clip_id}_{int(target_clip.start_time)}.mp4"
    return FileResponse(
        path=target_clip.staging_path,
        filename=clean_filename,
        media_type="video/mp4"
    )

@app.post("/api/clips/export-single")
def export_single_clip(req: ExportSingleRequest):
    clip = next((c for c in state.clips if c.clip_id == req.clip_id), None)
    if not clip or not os.path.exists(clip.staging_path):
        raise HTTPException(status_code=404, detail="Clip not found in staging")

    dest_str = req.dest_path[0] if isinstance(req.dest_path, (tuple, list)) else req.dest_path
    if not dest_str or not isinstance(dest_str, str) or not dest_str.strip():
        return {"status": "cancelled"}

    dest = Path(dest_str)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(clip.staging_path, str(dest))
    return {"status": "ok", "path": str(dest)}

@app.post("/api/clips/export-all")
def export_all_clips(req: ExportAllRequest):
    if not state.clips:
        raise HTTPException(status_code=400, detail="No clips to export")

    dest_dir_str = req.dest_dir[0] if isinstance(req.dest_dir, (tuple, list)) else req.dest_dir
    if not dest_dir_str or not isinstance(dest_dir_str, str) or not dest_dir_str.strip():
        return {"status": "cancelled"}

    dest_dir = Path(dest_dir_str)
    dest_dir.mkdir(parents=True, exist_ok=True)
    exported = []
    for c in state.clips:
        if os.path.exists(c.staging_path):
            target = dest_dir / f"clipmax_{c.clip_id}_{int(c.start_time)}.mp4"
            shutil.copy2(c.staging_path, str(target))
            exported.append(str(target))

    return {"status": "ok", "exported_count": len(exported), "directory": str(dest_dir)}

def rebuild_clip_overlays(clip_id: int) -> Path:
    clip = next((c for c in state.clips if c.clip_id == clip_id), None)
    if not clip or not os.path.exists(clip.staging_path):
        raise HTTPException(status_code=404, detail="Clip not found in staging")

    staging_path = Path(clip.staging_path)
    base_backup_path = staging_path.parent / f"{staging_path.stem}_base{staging_path.suffix}"

    if not base_backup_path.exists():
        shutil.copy2(str(staging_path), str(base_backup_path))

    cfg = state.clip_overlays.get(clip_id, {})
    text_cfg = cfg.get("text_config")
    img_cfg = cfg.get("image_config")

    ass_path = None
    if text_cfg and text_cfg.get("text", "").strip():
        temp_dir = Path(state.config.temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        ass_path = str((temp_dir / f"overlay_clip_{clip_id}.ass").resolve())
        duration = max(0.1, clip.end_time - clip.start_time)
        generate_overlay_ass(
            text=text_cfg["text"],
            duration=duration,
            output_ass_path=ass_path,
            font_name=text_cfg.get("font_name", "Impact"),
            font_size=text_cfg.get("font_size", 56),
            text_color=text_cfg.get("text_color", "#FFFFFF"),
            bg_color=text_cfg.get("bg_color", "#000000"),
            has_bg=text_cfg.get("has_bg", True),
            position=text_cfg.get("position", "top"),
            x_pct=text_cfg.get("x_pct"),
            y_pct=text_cfg.get("y_pct")
        )

    img_path = None
    img_x = 85.0
    img_y = 8.0
    img_scale = 16.0
    img_opacity = 1.0
    if img_cfg and img_cfg.get("image_path") and os.path.exists(img_cfg["image_path"]):
        img_path = img_cfg["image_path"]
        img_x = float(img_cfg.get("x_pct", 85.0))
        img_y = float(img_cfg.get("y_pct", 8.0))
        img_scale = float(img_cfg.get("scale_pct", 16.0))
        img_opacity = float(img_cfg.get("opacity", 1.0))

    if not ass_path and not img_path:
        shutil.copy2(str(base_backup_path), str(staging_path))
        return staging_path

    temp_render_path = staging_path.parent / f"temp_{staging_path.name}"
    try:
        apply_clip_overlays(
            input_video=str(base_backup_path),
            output_video=str(temp_render_path),
            ass_path=ass_path,
            image_path=img_path,
            image_x_pct=img_x,
            image_y_pct=img_y,
            image_scale_pct=img_scale,
            image_opacity=img_opacity,
            use_gpu=is_cuda_available()
        )
        if temp_render_path.exists():
            shutil.move(str(temp_render_path), str(staging_path))
    finally:
        if temp_render_path.exists():
            temp_render_path.unlink(missing_ok=True)

    return staging_path

@app.post("/api/clips/overlay")
def add_clip_overlay(req: ClipOverlayRequest):
    clip = next((c for c in state.clips if c.clip_id == req.clip_id), None)
    if not clip or not os.path.exists(clip.staging_path):
        raise HTTPException(status_code=404, detail="Clip not found in staging")

    state.clip_overlays.setdefault(req.clip_id, {})["text_config"] = req.model_dump()
    staging_path = rebuild_clip_overlays(req.clip_id)

    return {
        "status": "ok",
        "clip_id": req.clip_id,
        "staging_path": str(staging_path),
        "timestamp": time.time()
    }

@app.post("/api/clips/remove-overlay")
def remove_clip_overlay(req: RemoveOverlayRequest):
    clip = next((c for c in state.clips if c.clip_id == req.clip_id), None)
    if not clip or not os.path.exists(clip.staging_path):
        raise HTTPException(status_code=404, detail="Clip not found in staging")

    state.clip_overlays.setdefault(req.clip_id, {})["text_config"] = None
    rebuild_clip_overlays(req.clip_id)
    return {"status": "ok", "message": "Overlay removed, reverted to base clip"}

@app.post("/api/clips/image-overlay")
def add_clip_image_overlay(req: ClipImageOverlayRequest):
    clip = next((c for c in state.clips if c.clip_id == req.clip_id), None)
    if not clip or not os.path.exists(clip.staging_path):
        raise HTTPException(status_code=404, detail="Clip not found in staging")

    if not os.path.exists(req.image_path):
        raise HTTPException(status_code=400, detail="Image file not found on server")

    state.clip_overlays.setdefault(req.clip_id, {})["image_config"] = req.model_dump()
    staging_path = rebuild_clip_overlays(req.clip_id)

    return {
        "status": "ok",
        "clip_id": req.clip_id,
        "staging_path": str(staging_path),
        "timestamp": time.time()
    }

@app.post("/api/clips/remove-image-overlay")
def remove_clip_image_overlay(req: RemoveOverlayRequest):
    clip = next((c for c in state.clips if c.clip_id == req.clip_id), None)
    if not clip or not os.path.exists(clip.staging_path):
        raise HTTPException(status_code=404, detail="Clip not found in staging")

    state.clip_overlays.setdefault(req.clip_id, {})["image_config"] = None
    rebuild_clip_overlays(req.clip_id)
    return {"status": "ok", "message": "Image overlay removed"}

@app.post("/api/clips/upload-overlay-image")
async def upload_overlay_image(file: UploadFile = File(...)):
    temp_dir = Path(state.config.temp_dir) / "overlays"
    temp_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename).suffix or ".png"
    target_path = temp_dir / f"overlay_{int(time.time() * 1000)}{suffix}"
    with open(target_path, "wb") as f:
        content = await file.read()
        f.write(content)
    return {
        "status": "ok",
        "image_path": str(target_path.resolve()),
        "filename": target_path.name
    }

@app.get("/api/media/image-preview")
def preview_image(path: str):
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    suffix = p.suffix.lower()
    media_type = "image/png"
    if suffix in [".jpg", ".jpeg"]:
        media_type = "image/jpeg"
    elif suffix == ".webp":
        media_type = "image/webp"
    return FileResponse(path=str(p), media_type=media_type)

@app.post("/api/dialog/image")
def dialog_choose_image():
    window = state.window_holder.get("window")
    if window:
        try:
            import webview
            res = window.create_file_dialog(
                webview.FileDialog.OPEN,
                allow_multiple=False,
                file_types=('Image Files (*.png;*.jpg;*.jpeg;*.webp)', 'All files (*.*)')
            )
            if res:
                path_str = res[0] if isinstance(res, (tuple, list)) else res
                if isinstance(path_str, str) and path_str.strip():
                    return {"status": "ok", "path": path_str.strip()}
        except Exception as e:
            print(f"[Desktop Dialog Image Error]: {e}")
    return {"status": "cancelled"}

# Native Desktop Dialog Bridge via pywebview (if running in desktop window)
@app.post("/api/dialog/video")
def dialog_choose_video():
    window = state.window_holder.get("window")
    if window:
        try:
            import webview
            res = window.create_file_dialog(
                webview.FileDialog.OPEN,
                allow_multiple=False,
                file_types=('Video Files (*.mp4;*.mkv;*.mov;*.avi;*.webm)', 'All files (*.*)')
            )
            if res:
                path_str = res[0] if isinstance(res, (tuple, list)) else res
                if path_str and isinstance(path_str, str) and path_str.strip():
                    return {"path": path_str}
        except Exception:
            pass
    return {"path": None}

@app.post("/api/dialog/save-clip")
def dialog_save_clip(clip_id: int, default_name: str):
    window = state.window_holder.get("window")
    if window:
        try:
            import webview
            res = window.create_file_dialog(
                webview.FileDialog.SAVE,
                save_filename=default_name,
                file_types=('MP4 Video (*.mp4)', 'All files (*.*)')
            )
            if res:
                save_path = res[0] if isinstance(res, (tuple, list)) else res
                if not save_path or not isinstance(save_path, str) or not save_path.strip():
                    return {"path": None, "success": False, "status": "cancelled"}
                # Copy file
                clip = next((c for c in state.clips if c.clip_id == clip_id), None)
                if clip and os.path.exists(clip.staging_path):
                    dest = Path(save_path)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(clip.staging_path, str(dest))
                    return {"path": str(dest), "success": True}
        except Exception as e:
            return {"error": str(e), "success": False}
    return {"path": None, "success": False}

@app.post("/api/dialog/folder")
def dialog_choose_folder():
    window = state.window_holder.get("window")
    if window:
        try:
            import webview
            res = window.create_file_dialog(webview.FileDialog.FOLDER)
            if res:
                folder_str = res[0] if isinstance(res, (tuple, list)) else res
                if folder_str and isinstance(folder_str, str) and folder_str.strip():
                    return {"path": folder_str}
        except Exception:
            pass
    return {"path": None}

@app.websocket("/ws/progress")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    state.active_websockets.append(websocket)
    # Send current state immediately upon connection
    await websocket.send_json({
        "type": "state",
        "status": state.status,
        "progress": state.progress,
        "message": state.message,
        "clips": [c.model_dump() for c in state.clips]
    })
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in state.active_websockets:
            state.active_websockets.remove(websocket)
    except Exception:
        if websocket in state.active_websockets:
            state.active_websockets.remove(websocket)

# Fallback Staging File Resolver (Checks temp/staging and projects/)
project_root = Path(__file__).resolve().parent.parent.parent
staging_path = project_root / "temp" / "staging"
staging_path.mkdir(parents=True, exist_ok=True)

@app.get("/staging/{filename:path}")
def get_staging_file_fallback(filename: str):
    staging_dir = Path(state.config.temp_dir) / "staging"
    target = staging_dir / filename
    if target.exists() and target.is_file():
        media_type = "video/mp4" if target.suffix == ".mp4" else ("image/jpeg" if target.suffix in [".jpg", ".jpeg"] else None)
        return FileResponse(str(target), media_type=media_type)

    # Search in projects/
    projects_dir = Path("./projects").resolve()
    if projects_dir.exists():
        found = list(projects_dir.glob(f"**/{filename}"))
        if found and found[0].is_file():
            staging_dir.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(str(found[0]), str(target))
                return FileResponse(str(target), media_type="video/mp4" if target.suffix == ".mp4" else None)
            except Exception:
                return FileResponse(str(found[0]), media_type="video/mp4" if found[0].suffix == ".mp4" else None)

    raise HTTPException(status_code=404, detail="File not found in staging or projects")

app.mount("/staging", StaticFiles(directory=str(staging_path)), name="staging")

# Mount Projects Directory for Saved Project Media
projects_path = project_root / "projects"
projects_path.mkdir(parents=True, exist_ok=True)
app.mount("/projects_media", StaticFiles(directory=str(projects_path)), name="projects_media")

# --- Project Management Endpoints ---
@app.get("/api/projects")
def get_projects_list():
    import clipmax.project_manager as pm
    return {"projects": pm.list_projects()}

@app.get("/api/projects/last")
def get_last_project_api():
    import clipmax.project_manager as pm
    last = pm.get_last_project()
    return {"project": last}

@app.post("/api/projects/{project_id}/load")
def load_project_api(project_id: str):
    import clipmax.project_manager as pm
    staging_dir = Path(state.config.temp_dir) / "staging"
    restored = pm.restore_project_to_staging(project_id, staging_dir)
    if restored is None:
        raise HTTPException(status_code=404, detail="Project not found")

    state.clips = restored
    state.status = "COMPLETED"
    state.progress = 100
    state.message = f"Proyek berhasil dimuat ulang ({len(restored)} klip)."

    state.broadcast_sync({
        "type": "complete",
        "status": "COMPLETED",
        "progress": 100,
        "message": state.message,
        "clips": [c.model_dump() for c in restored]
    })

    record = pm.get_project_by_id(project_id)
    return {
        "status": "ok",
        "project": record,
        "clips": [c.model_dump() for c in restored]
    }

@app.delete("/api/projects/{project_id}")
def delete_project_api(project_id: str):
    import clipmax.project_manager as pm
    pm.delete_project(project_id)
    return {"status": "ok"}

# Mount Static UI Files
static_dir = Path(__file__).resolve().parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
