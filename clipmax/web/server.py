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
from clipmax.renderer import apply_ass_overlay

class PipelineStartRequest(BaseModel):
    input_source: str
    target_clip_count: int = 3
    min_duration: float = 30.0
    max_duration: float = 60.0
    campaign_rules: str = ""
    clip_mode: str = "single"
    subtitle_base_color: str = "#FFFFFF"
    subtitle_highlight_color: str = "#FF2A2A"
    cookie_file: Optional[str] = None

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
    # Auto-clean cache on startup
    clear_temp_cache(state.config.temp_dir)
    yield
    # Auto-clean cache on shutdown
    clear_temp_cache(state.config.temp_dir)

app = FastAPI(title="ClipMax Studio Backend", version="2.4.0", lifespan=lifespan)

@app.on_event("startup")
def on_startup():
    clear_temp_cache(state.config.temp_dir)

@app.on_event("shutdown")
def on_shutdown():
    clear_temp_cache(state.config.temp_dir)

@app.post("/api/cache/clear")
def api_clear_cache():
    count = clear_temp_cache(state.config.temp_dir)
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
                subtitle_highlight_color=req.subtitle_highlight_color
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

@app.post("/api/clips/overlay")
def add_clip_overlay(req: ClipOverlayRequest):
    clip = next((c for c in state.clips if c.clip_id == req.clip_id), None)
    if not clip or not os.path.exists(clip.staging_path):
        raise HTTPException(status_code=404, detail="Clip not found in staging")

    staging_path = Path(clip.staging_path)
    base_backup_path = staging_path.parent / f"{staging_path.stem}_base{staging_path.suffix}"

    # Backup the original clip if not already backed up
    if not base_backup_path.exists():
        shutil.copy2(str(staging_path), str(base_backup_path))

    temp_dir = Path(state.config.temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    ass_path = temp_dir / f"overlay_clip_{req.clip_id}.ass"

    duration = max(0.1, clip.end_time - clip.start_time)
    generate_overlay_ass(
        text=req.text,
        duration=duration,
        output_ass_path=str(ass_path),
        font_name=req.font_name,
        font_size=req.font_size,
        text_color=req.text_color,
        bg_color=req.bg_color,
        has_bg=req.has_bg,
        position=req.position
    )

    temp_render_path = staging_path.parent / f"temp_{staging_path.name}"
    try:
        apply_ass_overlay(
            input_video=str(base_backup_path),
            output_video=str(temp_render_path),
            ass_path=str(ass_path),
            use_gpu=is_cuda_available()
        )
        if temp_render_path.exists():
            shutil.move(str(temp_render_path), str(staging_path))
    finally:
        if temp_render_path.exists():
            temp_render_path.unlink(missing_ok=True)

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

    staging_path = Path(clip.staging_path)
    base_backup_path = staging_path.parent / f"{staging_path.stem}_base{staging_path.suffix}"

    if base_backup_path.exists():
        shutil.copy2(str(base_backup_path), str(staging_path))
        return {"status": "ok", "message": "Overlay removed, reverted to base clip"}
    return {"status": "ok", "message": "No base backup found"}

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

# Mount Staging Directory for Video & Thumbnail Streaming
project_root = Path(__file__).resolve().parent.parent.parent
staging_path = project_root / "temp" / "staging"
staging_path.mkdir(parents=True, exist_ok=True)
app.mount("/staging", StaticFiles(directory=str(staging_path)), name="staging")

# Mount Static UI Files
static_dir = Path(__file__).resolve().parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
