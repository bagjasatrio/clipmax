import os
import sys
import traceback

# Ensure stdout/stderr are valid under pythonw.exe (windowless python) and logged
log_dir = os.environ.get("LOCALAPPDATA", ".")
log_file = os.path.join(log_dir, "clipmax_desktop.log")
try:
    log_fp = open(log_file, "a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = log_fp
    if sys.stderr is None:
        sys.stderr = log_fp
except Exception:
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

def global_excepthook(exctype, value, tb):
    err = "".join(traceback.format_exception(exctype, value, tb))
    sys.stderr.write(f"\n[FATAL ERROR]:\n{err}\n")
    sys.stderr.flush()
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, f"ClipMax Fatal Error:\n{value}\n\nDetail: {log_file}", "ClipMax Error", 0x10)
        except Exception:
            pass

sys.excepthook = global_excepthook

# Workaround for Microsoft WebView2 DirectComposition / GPU compositing black screen bug on Windows
if "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS" not in os.environ:
    os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = "--disable-gpu-compositing --disable-direct-composition"

# Setup CUDA DLL paths before any AI / audio / video libraries are loaded
from clipmax.dll_setup import setup_cuda_dll_paths
setup_cuda_dll_paths()

def main():
    if "--pyside" in sys.argv:
        from PySide6.QtWidgets import QApplication
        from clipmax.ui.main_window import MainWindow
        from clipmax.ui.theme import DARK_THEME_QSS
        app = QApplication(sys.argv)
        app.setStyleSheet(DARK_THEME_QSS)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    else:
        from desktop_app import main as desktop_main
        desktop_main()

if __name__ == "__main__":
    main()
