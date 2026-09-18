import sys
from pathlib import Path
from typing import Optional, List
from PySide6.QtCore import Qt, QThread, Signal, QPoint
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QProgressBar,
    QFileDialog, QMessageBox, QFrame
)
from clipmax.config import AppConfig
from clipmax.ai_gateway import discover_models
from clipmax.pipeline import PipelineOrchestrator, PipelineStatus

class PipelineWorker(QThread):
    progress_changed = Signal(str, int, str)
    finished = Signal(list)
    failed = Signal(str)

    def __init__(self, orchestrator: PipelineOrchestrator, video_path: str):
        super().__init__()
        self.orchestrator = orchestrator
        self.video_path = video_path

    def run(self):
        try:
            def on_progress(status: PipelineStatus, pct: int, msg: str):
                self.progress_changed.emit(status.value, pct, msg)

            clips = self.orchestrator.run(self.video_path, on_progress)
            self.finished.emit(clips)
        except Exception as e:
            self.failed.emit(str(e))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(880, 680)

        self.config = AppConfig.load()
        self.orchestrator = PipelineOrchestrator(self.config)
        self.worker: Optional[PipelineWorker] = None
        self._drag_pos = QPoint()

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(24, 20, 24, 24)
        main_layout.setSpacing(16)

        # Titlebar
        title_bar = QHBoxLayout()
        title_lbl = QLabel("ClipMax ⚡ Autonomous Desktop Clipper")
        title_lbl.setProperty("class", "Title")
        
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(32, 32)
        btn_close.setProperty("class", "Secondary")
        btn_close.clicked.connect(self.close)

        title_bar.addWidget(title_lbl)
        title_bar.addStretch()
        title_bar.addWidget(btn_close)
        main_layout.addLayout(title_bar)

        # Card 1: AI Provider Gateway
        provider_card = QFrame()
        provider_card.setProperty("class", "Card")
        p_layout = QVBoxLayout(provider_card)

        p_lbl = QLabel("AI Provider & Dynamic Model Discovery")
        p_lbl.setStyleSheet("font-weight: bold; color: #93c5fd;")
        p_layout.addWidget(p_lbl)

        row1 = QHBoxLayout()
        self.txt_endpoint = QLineEdit(self.config.endpoint_url)
        self.txt_endpoint.setPlaceholderText("Endpoint URL (e.g. http://localhost:20128/v1)")
        self.txt_key = QLineEdit(self.config.api_key)
        self.txt_key.setPlaceholderText("API Key (opsional)")
        self.txt_key.setEchoMode(QLineEdit.Password)
        self.btn_discover = QPushButton("Discover Models")
        self.btn_discover.setProperty("class", "Secondary")
        self.btn_discover.clicked.connect(self._on_discover_models)

        row1.addWidget(self.txt_endpoint, 3)
        row1.addWidget(self.txt_key, 2)
        row1.addWidget(self.btn_discover, 1)
        p_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.cmb_models = QComboBox()
        self.cmb_models.addItem(self.config.selected_model)
        self.lbl_device = QLabel(f"Hardware: {self.config.device.upper()} ({self.config.compute_type})")
        self.lbl_device.setStyleSheet("color: #10b981; font-weight: bold;")
        row2.addWidget(QLabel("Model:"))
        row2.addWidget(self.cmb_models, 3)
        row2.addWidget(self.lbl_device, 1)
        p_layout.addLayout(row2)

        main_layout.addWidget(provider_card)

        # Card 2: Video Selection
        video_card = QFrame()
        video_card.setProperty("class", "Card")
        v_layout = QVBoxLayout(video_card)

        v_lbl = QLabel("Input Video (16:9 Long Form)")
        v_lbl.setStyleSheet("font-weight: bold; color: #93c5fd;")
        v_layout.addWidget(v_lbl)

        v_row = QHBoxLayout()
        self.txt_video = QLineEdit()
        self.txt_video.setPlaceholderText("Pilih file video MP4/MKV...")
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.setProperty("class", "Secondary")
        self.btn_browse.clicked.connect(self._on_browse_video)

        v_row.addWidget(self.txt_video, 4)
        v_row.addWidget(self.btn_browse, 1)
        v_layout.addLayout(v_row)
        main_layout.addWidget(video_card)

        # Card 3: Execution & Progress
        exec_card = QFrame()
        exec_card.setProperty("class", "Card")
        e_layout = QVBoxLayout(exec_card)

        self.lbl_status = QLabel("Status: Menunggu instruksi...")
        self.lbl_status.setProperty("class", "Sub")
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)

        e_layout.addWidget(self.lbl_status)
        e_layout.addWidget(self.progress_bar)

        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("Mulai Generate Klip 9:16")
        self.btn_start.clicked.connect(self._on_start)
        self.btn_cancel = QPushButton("Batal / Stop")
        self.btn_cancel.setProperty("class", "Danger")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._on_cancel)

        btn_row.addWidget(self.btn_start, 3)
        btn_row.addWidget(self.btn_cancel, 1)
        e_layout.addLayout(btn_row)

        main_layout.addWidget(exec_card)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _on_discover_models(self):
        url = self.txt_endpoint.text().strip()
        key = self.txt_key.text().strip()
        try:
            models = discover_models(url, key)
            self.cmb_models.clear()
            self.cmb_models.addItems(models)
            QMessageBox.information(self, "Sukses", f"Ditemukan {len(models)} model.")
        except Exception as e:
            QMessageBox.warning(self, "Error Discovery", f"Gagal mengambil model: {str(e)}")

    def _on_browse_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Pilih Video", "", "Video Files (*.mp4 *.mkv *.mov *.avi)"
        )
        if file_path:
            self.txt_video.setText(file_path)

    def _on_start(self):
        video = self.txt_video.text().strip()
        if not video or not Path(video).exists():
            QMessageBox.warning(self, "Validasi", "Pilih file video valid terlebih dahulu.")
            return

        self.config.endpoint_url = self.txt_endpoint.text().strip()
        self.config.api_key = self.txt_key.text().strip()
        self.config.selected_model = self.cmb_models.currentText()
        self.config.save()

        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)

        self.worker = PipelineWorker(self.orchestrator, video)
        self.worker.progress_changed.connect(self._on_worker_progress)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.failed.connect(self._on_worker_failed)
        self.worker.start()

    def _on_cancel(self):
        if self.worker and self.worker.isRunning():
            self.lbl_status.setText("Membatalkan dan membersihkan VRAM/temp...")
            self.orchestrator.cancel()
            self.worker.wait(3000)
            self.btn_start.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            self.progress_bar.setValue(0)
            self.lbl_status.setText("Status: Dibatalkan oleh pengguna.")

    def _on_worker_progress(self, status: str, pct: int, msg: str):
        self.progress_bar.setValue(pct)
        self.lbl_status.setText(f"[{status}] {msg}")

    def _on_worker_finished(self, clips: List[str]):
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setValue(100)
        self.lbl_status.setText(f"Selesai! {len(clips)} klip dibuat di folder output.")
        QMessageBox.information(self, "Selesai", f"Berhasil membuat {len(clips)} video klip 9:16!")

    def _on_worker_failed(self, error: str):
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.lbl_status.setText("Gagal!")
        QMessageBox.critical(self, "Error Pipeline", f"Pipeline terhenti: {error}")
