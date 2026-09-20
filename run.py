import sys

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
