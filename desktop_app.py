import os
import sys

# Workaround for Microsoft WebView2 DirectComposition / GPU compositing black screen bug on Windows
if "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS" not in os.environ:
    os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = "--disable-gpu-compositing --disable-direct-composition"

import socket
import time
import threading
from pathlib import Path
from typing import Optional

# Setup CUDA DLL paths before any AI / audio / video libraries are loaded
from clipmax.dll_setup import setup_cuda_dll_paths
setup_cuda_dll_paths()

import uvicorn
import webview
from clipmax.config import clear_temp_cache
from clipmax.web.server import app, state

def find_free_port(start_port: int = 20130) -> int:
    port = start_port
    while port < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
        port += 1
    return start_port

class DesktopJsApi:
    def __init__(self, window_holder):
        self.window_holder = window_holder

    def is_desktop(self) -> bool:
        return True

    def minimize_window(self):
        w = self.window_holder.get("window")
        if w:
            w.minimize()

    def close_window(self):
        clear_temp_cache()
        w = self.window_holder.get("window")
        if w:
            w.destroy()

    def choose_video_file(self) -> Optional[str]:
        w = self.window_holder.get("window")
        if w:
            try:
                res = w.create_file_dialog(
                    webview.FileDialog.OPEN,
                    allow_multiple=False,
                    file_types=('Video Files (*.mp4;*.mkv;*.mov;*.avi;*.webm)', 'All files (*.*)')
                )
                if res:
                    save_path = res[0] if isinstance(res, (tuple, list)) else res
                    if save_path and isinstance(save_path, str) and save_path.strip():
                        return save_path
            except Exception as e:
                print(f"[Desktop Dialog Error]: {e}")
        return None

    def choose_image_file(self) -> Optional[str]:
        w = self.window_holder.get("window")
        if w:
            try:
                res = w.create_file_dialog(
                    webview.FileDialog.OPEN,
                    allow_multiple=False,
                    file_types=('Image Files (*.png;*.jpg;*.jpeg;*.webp)', 'All files (*.*)')
                )
                if res:
                    save_path = res[0] if isinstance(res, (tuple, list)) else res
                    if save_path and isinstance(save_path, str) and save_path.strip():
                        return save_path
            except Exception as e:
                print(f"[Desktop Dialog Image Error]: {e}")
        return None

    def open_external_url(self, url: str):
        import webbrowser
        webbrowser.open(url)

    def save_clip_dialog(self, clip_id: int, default_filename: str, trim_start: Optional[float] = None, trim_end: Optional[float] = None) -> Optional[str]:
        w = self.window_holder.get("window")
        if w:
            try:
                res = w.create_file_dialog(
                    webview.FileDialog.SAVE,
                    save_filename=default_filename,
                    file_types=('MP4 Video (*.mp4)', 'All files (*.*)')
                )
                if res:
                    save_path = res[0] if isinstance(res, (tuple, list)) else res
                    if not save_path or not isinstance(save_path, str) or not save_path.strip():
                        return None
                    clip = next((c for c in state.clips if c.clip_id == clip_id), None)
                    if clip and os.path.exists(clip.staging_path):
                        from clipmax.web.server import execute_video_export
                        dest = Path(save_path)
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        execute_video_export(clip.staging_path, str(dest), trim_start, trim_end)
                        return str(dest)
            except Exception as e:
                print(f"[Desktop Dialog Error]: {e}")
        return None

    def export_all_dialog(self, clip_trims: Optional[dict] = None) -> Optional[str]:
        w = self.window_holder.get("window")
        if w:
            try:
                res = w.create_file_dialog(webview.FileDialog.FOLDER)
                if res:
                    dest_dir_str = res[0] if isinstance(res, (tuple, list)) else res
                    if not dest_dir_str or not isinstance(dest_dir_str, str) or not dest_dir_str.strip():
                        return None
                    from clipmax.web.server import execute_video_export, build_clip_export_filename
                    dest_dir = Path(dest_dir_str)
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    trims = clip_trims or {}
                    for c in state.clips:
                        if os.path.exists(c.staging_path):
                            fname = build_clip_export_filename(c)
                            t_info = trims.get(str(c.clip_id), {})
                            t_start = t_info.get("trim_start")
                            t_end = t_info.get("trim_end")
                            execute_video_export(c.staging_path, str(dest_dir / fname), t_start, t_end)
                    return str(dest_dir)
            except Exception as e:
                print(f"[Desktop Export All Dialog Error]: {e}")
        return None

def start_server(port: int):
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

def main():
    port = find_free_port(20130)
    server_thread = threading.Thread(target=start_server, args=(port,), daemon=True)
    server_thread.start()

    # Wait for server readiness (max 15 seconds)
    url = f"http://127.0.0.1:{port}"
    ready = False
    for _ in range(150):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.2)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    ready = True
                    break
        except Exception:
            pass
        time.sleep(0.1)

    if not ready:
        err_msg = f"Gagal memulai server lokal ClipMax di port {port} setelah 15 detik.\nSilakan periksa log di: %LOCALAPPDATA%\\clipmax_desktop.log"
        print(f"[ClipMax Error] {err_msg}", file=sys.stderr)
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, err_msg, "ClipMax Launch Error", 0x10)
            except Exception:
                pass
        sys.exit(1)

    window_holder = state.window_holder
    api = DesktopJsApi(window_holder)

    window = webview.create_window(
        title="ClipMax Studio Pro",
        url=url,
        width=1280,
        height=820,
        min_size=(1024, 680),
        resizable=True,
        background_color="#0C120E",
        js_api=api
    )
    window_holder["window"] = window

    webview.start(debug=False)
    clear_temp_cache()

if __name__ == "__main__":
    main()
