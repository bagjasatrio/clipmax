import os
import sys
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
                if res and len(res) > 0:
                    return res[0]
            except Exception as e:
                print(f"[Desktop Dialog Error]: {e}")
        return None

    def open_external_url(self, url: str):
        import webbrowser
        webbrowser.open(url)

    def save_clip_dialog(self, clip_id: int, default_filename: str) -> Optional[str]:
        w = self.window_holder.get("window")
        if w:
            try:
                res = w.create_file_dialog(
                    webview.FileDialog.SAVE,
                    save_filename=default_filename,
                    file_types=('MP4 Video (*.mp4)', 'All files (*.*)')
                )
                if res:
                    clip = next((c for c in state.clips if c.clip_id == clip_id), None)
                    if clip and os.path.exists(clip.staging_path):
                        import shutil
                        dest = Path(res)
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(clip.staging_path, str(dest))
                        return str(dest)
            except Exception as e:
                print(f"[Desktop Dialog Error]: {e}")
        return None

    def export_all_dialog(self) -> Optional[str]:
        w = self.window_holder.get("window")
        if w:
            try:
                res = w.create_file_dialog(webview.FileDialog.FOLDER)
                if res and len(res) > 0:
                    import shutil
                    dest_dir = Path(res[0])
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    for c in state.clips:
                        if os.path.exists(c.staging_path):
                            target = dest_dir / f"clipmax_{c.clip_id}_{int(c.start_time)}.mp4"
                            shutil.copy2(c.staging_path, str(target))
                    return str(dest_dir)
            except Exception as e:
                print(f"[Desktop Dialog Error]: {e}")
        return None

def start_server(port: int):
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

def main():
    port = find_free_port(20130)
    server_thread = threading.Thread(target=start_server, args=(port,), daemon=True)
    server_thread.start()

    # Wait for server readiness
    url = f"http://127.0.0.1:{port}"
    ready = False
    for _ in range(30):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    ready = True
                    break
        except Exception:
            pass
        time.sleep(0.1)

    if not ready:
        print("[ClipMax Error] Failed to start local web server.", file=sys.stderr)
        sys.exit(1)

    window_holder = state.window_holder
    api = DesktopJsApi(window_holder)

    window = webview.create_window(
        title="ClipMax Studio",
        url=url,
        width=1280,
        height=820,
        min_size=(1024, 680),
        resizable=True,
        js_api=api
    )
    window_holder["window"] = window

    webview.start(debug=False)
    clear_temp_cache()

if __name__ == "__main__":
    main()
