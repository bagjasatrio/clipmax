import os
import sys
import shutil
from pathlib import Path
from typing import Optional, List
from PySide6.QtCore import Qt, QThread, Signal, QPoint, QUrl
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QProgressBar,
    QFileDialog, QMessageBox, QFrame, QStackedWidget, QTabWidget,
    QScrollArea, QSlider, QSizePolicy, QSplitter, QSpinBox,
    QPlainTextEdit
)
from clipmax.config import AppConfig
from clipmax.ai_gateway import discover_models
from clipmax.pipeline import PipelineOrchestrator, PipelineStatus, ClipResult
from clipmax.downloader import is_valid_video_url

class PipelineWorker(QThread):
    progress_changed = Signal(str, int, str)
    finished = Signal(list)
    failed = Signal(str)

    def __init__(
        self,
        orchestrator: PipelineOrchestrator,
        input_source: str,
        target_clip_count: int = 3,
        min_duration: float = 30.0,
        max_duration: float = 60.0,
        campaign_rules: str = ""
    ):
        super().__init__()
        self.orchestrator = orchestrator
        self.input_source = input_source
        self.target_clip_count = target_clip_count
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.campaign_rules = campaign_rules

    def run(self):
        try:
            def on_progress(status: PipelineStatus, pct: int, msg: str):
                self.progress_changed.emit(status.value, pct, msg)

            clips = self.orchestrator.run(
                self.input_source,
                on_progress,
                target_clip_count=self.target_clip_count,
                min_duration=self.min_duration,
                max_duration=self.max_duration,
                campaign_rules=self.campaign_rules
            )
            self.finished.emit(clips)
        except Exception as e:
            self.failed.emit(str(e))

class ClipCardWidget(QFrame):
    clicked = Signal(object)

    def __init__(self, clip: ClipResult):
        super().__init__()
        self.clip = clip
        self.setProperty("class", "ClipCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # Thumbnail
        self.thumb_lbl = QLabel()
        self.thumb_lbl.setFixedSize(68, 100)
        self.thumb_lbl.setStyleSheet("background-color: #000000; border-radius: 4px;")
        self.thumb_lbl.setAlignment(Qt.AlignCenter)
        if clip.thumbnail_path and os.path.exists(clip.thumbnail_path):
            pix = QPixmap(clip.thumbnail_path)
            self.thumb_lbl.setPixmap(pix.scaled(68, 100, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        else:
            self.thumb_lbl.setText("9:16")
            self.thumb_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(self.thumb_lbl)

        # Info container
        info_layout = QVBoxLayout()
        info_layout.setSpacing(3)

        # Top row: title + score badge
        top_row = QHBoxLayout()
        title_lbl = QLabel(clip.title)
        title_lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #f3f4f6;")
        title_lbl.setWordWrap(True)
        top_row.addWidget(title_lbl, 1)

        badge_class = "BadgeHigh" if clip.virality_score >= 80 else "BadgeMid"
        score_lbl = QLabel(f"{clip.virality_score} 🔥")
        score_lbl.setProperty("class", badge_class)
        score_lbl.setFixedHeight(20)
        top_row.addWidget(score_lbl)
        info_layout.addLayout(top_row)

        # Hook
        hook_lbl = QLabel(f'"{clip.hook}"')
        hook_lbl.setStyleSheet("color: #60a5fa; font-style: italic; font-size: 11px;")
        hook_lbl.setWordWrap(True)
        info_layout.addWidget(hook_lbl)

        # Time range
        dur = max(0.0, clip.end_time - clip.start_time)
        mode_val = getattr(clip, "reframe_mode", "DYNAMIC_SCENE")
        if mode_val == "DYNAMIC_SCENE":
            mode_tag = "🔄 Dynamic Split"
        elif mode_val == "CROP_TRACKING":
            mode_tag = "👤 Face Crop"
        else:
            mode_tag = "🖼 Blurred BG"
        time_lbl = QLabel(f"⏱ {int(clip.start_time)}s - {int(clip.end_time)}s ({dur:.1f}s) • {mode_tag}")
        time_lbl.setStyleSheet("color: #9ca3af; font-size: 11px;")
        info_layout.addWidget(time_lbl)

        layout.addLayout(info_layout, 1)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.clip)
            event.accept()

    def set_active(self, is_active: bool):
        self.setProperty("class", "ClipCardActive" if is_active else "ClipCard")
        self.style().unpolish(self)
        self.style().polish(self)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(1000, 720)

        self.config = AppConfig.load()
        self.orchestrator = PipelineOrchestrator(self.config)
        self.worker: Optional[PipelineWorker] = None
        self._drag_pos = QPoint()

        # Staging clips
        self.current_clips: List[ClipResult] = []
        self.selected_clip: Optional[ClipResult] = None
        self.card_widgets: List[ClipCardWidget] = []

        # Video Player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        self._build_ui()
        self._setup_player_events()

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(20, 16, 20, 20)
        root_layout.setSpacing(12)

        # Custom Frameless Titlebar
        title_bar = QHBoxLayout()
        title_lbl = QLabel("ClipMax ⚡ Autonomous Desktop Clipper")
        title_lbl.setProperty("class", "Title")

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(30, 30)
        btn_close.setProperty("class", "Secondary")
        btn_close.clicked.connect(self.close)

        title_bar.addWidget(title_lbl)
        title_bar.addStretch()
        title_bar.addWidget(btn_close)
        root_layout.addLayout(title_bar)

        # Stacked Widget (Page 0: Input/Queue, Page 1: Review Workspace)
        self.stack = QStackedWidget()
        root_layout.addWidget(self.stack, 1)

        # Build Pages
        self.page_input = self._build_input_page()
        self.page_review = self._build_review_page()
        self.stack.addWidget(self.page_input)
        self.stack.addWidget(self.page_review)
        self.stack.setCurrentIndex(0)

    def _build_input_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

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

        layout.addWidget(provider_card)

        # Card 2: Input Video Source (Tabs: File Lokal vs Link Video)
        video_card = QFrame()
        video_card.setProperty("class", "Card")
        v_layout = QVBoxLayout(video_card)

        v_lbl = QLabel("Input Video Ingestion (16:9 Long Form)")
        v_lbl.setStyleSheet("font-weight: bold; color: #93c5fd;")
        v_layout.addWidget(v_lbl)

        self.input_tabs = QTabWidget()

        # Tab 1: File Lokal
        tab_local = QWidget()
        tl_layout = QHBoxLayout(tab_local)
        self.txt_video = QLineEdit()
        self.txt_video.setPlaceholderText("Pilih file video MP4/MKV...")
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.setProperty("class", "Secondary")
        self.btn_browse.clicked.connect(self._on_browse_video)
        tl_layout.addWidget(self.txt_video, 4)
        tl_layout.addWidget(self.btn_browse, 1)

        # Tab 2: Link Video yt-dlp
        tab_url = QWidget()
        tu_layout = QHBoxLayout(tab_url)
        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText("Tempel URL video (YouTube, X, Instagram, TikTok)...")
        tu_layout.addWidget(self.txt_url, 1)

        self.input_tabs.addTab(tab_local, "📁 File Video Lokal")
        self.input_tabs.addTab(tab_url, "🌐 Video Link (yt-dlp)")
        v_layout.addWidget(self.input_tabs)

        layout.addWidget(video_card)

        # Card 3: Generation & Campaign Settings
        gen_card = QFrame()
        gen_card.setProperty("class", "Card")
        g_layout = QVBoxLayout(gen_card)
        g_layout.setSpacing(8)

        g_lbl = QLabel("Generation & Campaign Settings")
        g_lbl.setStyleSheet("font-weight: bold; color: #93c5fd;")
        g_layout.addWidget(g_lbl)

        row_params = QHBoxLayout()
        row_params.setSpacing(12)

        # Target clip count
        count_box = QVBoxLayout()
        count_lbl = QLabel("Target Clip Count:")
        count_lbl.setStyleSheet("color: #d1d5db; font-size: 12px;")
        self.spn_clip_count = QSpinBox()
        self.spn_clip_count.setRange(1, 10)
        self.spn_clip_count.setValue(self.config.target_clip_count or 3)
        count_box.addWidget(count_lbl)
        count_box.addWidget(self.spn_clip_count)
        row_params.addLayout(count_box, 1)

        # Clip Duration Range
        dur_box = QVBoxLayout()
        dur_lbl = QLabel("Clip Duration Range:")
        dur_lbl.setStyleSheet("color: #d1d5db; font-size: 12px;")
        self.cmb_duration = QComboBox()
        self.cmb_duration.addItems([
            "Auto / Optimal (30-60s)",
            "Short (15-30s)",
            "Medium (30-60s)",
            "Long (60-90s)",
            "Custom"
        ])
        preset_idx = self.cmb_duration.findText(self.config.duration_preset)
        if preset_idx >= 0:
            self.cmb_duration.setCurrentIndex(preset_idx)
        self.cmb_duration.currentIndexChanged.connect(self._on_duration_preset_changed)

        dur_box.addWidget(dur_lbl)
        dur_box.addWidget(self.cmb_duration)
        row_params.addLayout(dur_box, 2)

        # Custom duration container
        self.custom_dur_widget = QWidget()
        custom_layout = QHBoxLayout(self.custom_dur_widget)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.setSpacing(6)

        min_layout = QVBoxLayout()
        min_lbl = QLabel("Min (s):")
        min_lbl.setStyleSheet("color: #9ca3af; font-size: 11px;")
        self.spn_min_dur = QSpinBox()
        self.spn_min_dur.setRange(5, 300)
        self.spn_min_dur.setValue(int(self.config.min_duration or 30))
        min_layout.addWidget(min_lbl)
        min_layout.addWidget(self.spn_min_dur)
        custom_layout.addLayout(min_layout)

        max_layout = QVBoxLayout()
        max_lbl = QLabel("Max (s):")
        max_lbl.setStyleSheet("color: #9ca3af; font-size: 11px;")
        self.spn_max_dur = QSpinBox()
        self.spn_max_dur.setRange(10, 600)
        self.spn_max_dur.setValue(int(self.config.max_duration or 60))
        max_layout.addWidget(max_lbl)
        max_layout.addWidget(self.spn_max_dur)
        custom_layout.addLayout(max_layout)

        row_params.addWidget(self.custom_dur_widget, 2)
        self.custom_dur_widget.setVisible(self.cmb_duration.currentText() == "Custom")

        g_layout.addLayout(row_params)

        # Campaign Rules
        rules_lbl = QLabel("Campaign Rules / Custom Guidelines (Opsional):")
        rules_lbl.setStyleSheet("color: #d1d5db; font-size: 12px;")
        g_layout.addWidget(rules_lbl)

        self.txt_rules = QPlainTextEdit()
        self.txt_rules.setPlaceholderText(
            "Contoh: Fokus pada pembahasan produk X, pastikan klip memiliki call to action di akhir, hindari topik politik..."
        )
        self.txt_rules.setPlainText(self.config.campaign_rules or "")
        self.txt_rules.setFixedHeight(65)
        g_layout.addWidget(self.txt_rules)

        layout.addWidget(gen_card)

        # Card 4: Execution & Progress
        exec_card = QFrame()
        exec_card.setProperty("class", "Card")
        e_layout = QVBoxLayout(exec_card)

        self.lbl_status = QLabel("Status: Siap memproses video...")
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

        layout.addWidget(exec_card)
        layout.addStretch()
        return page

    def _build_review_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Workspace Header
        top_bar = QHBoxLayout()
        w_title = QLabel("Staging & Review Workspace")
        w_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #60a5fa;")
        
        self.btn_back = QPushButton("← Proses Video Baru")
        self.btn_back.setProperty("class", "Secondary")
        self.btn_back.clicked.connect(self._on_back_to_input)

        top_bar.addWidget(w_title)
        top_bar.addStretch()
        top_bar.addWidget(self.btn_back)
        layout.addLayout(top_bar)

        # Main Splitter: Left Gallery, Right Player & Export
        splitter = QSplitter(Qt.Horizontal)

        # Left: Scrollable Card Gallery
        left_panel = QFrame()
        left_panel.setProperty("class", "Card")
        lp_layout = QVBoxLayout(left_panel)
        lp_layout.setContentsMargins(8, 8, 8, 8)

        self.lbl_gallery_count = QLabel("Daftar Klip Terdeteksi (0 Klip)")
        self.lbl_gallery_count.setStyleSheet("font-weight: bold; color: #93c5fd; margin-bottom: 4px;")
        lp_layout.addWidget(self.lbl_gallery_count)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.gallery_container = QWidget()
        self.gallery_layout = QVBoxLayout(self.gallery_container)
        self.gallery_layout.setContentsMargins(4, 4, 4, 4)
        self.gallery_layout.setSpacing(8)
        self.gallery_layout.addStretch()
        self.scroll_area.setWidget(self.gallery_container)
        lp_layout.addWidget(self.scroll_area)

        splitter.addWidget(left_panel)

        # Right: Built-in Video Player & Action Controls
        right_panel = QFrame()
        right_panel.setProperty("class", "Card")
        rp_layout = QVBoxLayout(right_panel)
        rp_layout.setContentsMargins(12, 12, 12, 12)
        rp_layout.setSpacing(10)

        # Player Container
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #000000; border-radius: 8px;")
        self.video_widget.setMinimumSize(270, 480)
        self.player.setVideoOutput(self.video_widget)
        rp_layout.addWidget(self.video_widget, 1)

        # Playback Controls
        ctrl_layout = QHBoxLayout()
        self.btn_play_pause = QPushButton("▶")
        self.btn_play_pause.setFixedSize(36, 36)
        self.btn_play_pause.clicked.connect(self._toggle_playback)

        self.slider_progress = QSlider(Qt.Horizontal)
        self.slider_progress.setRange(0, 1000)
        self.slider_progress.sliderMoved.connect(self._on_seek)

        self.lbl_time = QLabel("00:00 / 00:00")
        self.lbl_time.setStyleSheet("font-size: 11px; color: #9ca3af;")

        ctrl_layout.addWidget(self.btn_play_pause)
        ctrl_layout.addWidget(self.slider_progress, 1)
        ctrl_layout.addWidget(self.lbl_time)
        rp_layout.addLayout(ctrl_layout)

        # Selected Clip Detail Label
        self.lbl_clip_info = QLabel("Pilih klip di sebelah kiri untuk memutar pratinjau.")
        self.lbl_clip_info.setStyleSheet("color: #e5e7eb; font-size: 12px;")
        self.lbl_clip_info.setWordWrap(True)
        rp_layout.addWidget(self.lbl_clip_info)

        # Export Action Buttons
        act_layout = QHBoxLayout()
        self.btn_save_one = QPushButton("💾 Simpan Klip Ini")
        self.btn_save_one.clicked.connect(self._on_save_selected_clip)
        self.btn_save_all = QPushButton("📦 Simpan Semua Klip")
        self.btn_save_all.setProperty("class", "Success")
        self.btn_save_all.clicked.connect(self._on_save_all_clips)

        act_layout.addWidget(self.btn_save_one, 1)
        act_layout.addWidget(self.btn_save_all, 1)
        rp_layout.addLayout(act_layout)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter, 1)
        return page

    def _setup_player_events(self):
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)

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

    def _on_duration_preset_changed(self):
        preset = self.cmb_duration.currentText()
        is_custom = (preset == "Custom")
        self.custom_dur_widget.setVisible(is_custom)
        if not is_custom:
            if "15-30" in preset:
                self.spn_min_dur.setValue(15)
                self.spn_max_dur.setValue(30)
            elif "30-60" in preset:
                self.spn_min_dur.setValue(30)
                self.spn_max_dur.setValue(60)
            elif "60-90" in preset:
                self.spn_min_dur.setValue(60)
                self.spn_max_dur.setValue(90)

    def _on_browse_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Pilih Video", "", "Video Files (*.mp4 *.mkv *.mov *.avi)"
        )
        if file_path:
            self.txt_video.setText(file_path)

    def _on_start(self):
        # Determine input source from active tab
        if self.input_tabs.currentIndex() == 0:
            source = self.txt_video.text().strip()
            if not source or not Path(source).exists():
                QMessageBox.warning(self, "Validasi", "Pilih file video valid terlebih dahulu.")
                return
        else:
            source = self.txt_url.text().strip()
            if not is_valid_video_url(source):
                QMessageBox.warning(self, "Validasi", "Masukkan tautan video valid (http:// atau https://).")
                return

        target_count = self.spn_clip_count.value()
        preset = self.cmb_duration.currentText()
        if preset == "Custom":
            min_dur = float(self.spn_min_dur.value())
            max_dur = float(self.spn_max_dur.value())
            if max_dur <= min_dur:
                QMessageBox.warning(self, "Validasi", "Durasi Max harus lebih besar daripada Min.")
                return
        elif "15-30" in preset:
            min_dur, max_dur = 15.0, 30.0
        elif "30-60" in preset:
            min_dur, max_dur = 30.0, 60.0
        elif "60-90" in preset:
            min_dur, max_dur = 60.0, 90.0
        else:
            min_dur, max_dur = 30.0, 60.0

        rules = self.txt_rules.toPlainText().strip()

        self.config.endpoint_url = self.txt_endpoint.text().strip()
        self.config.api_key = self.txt_key.text().strip()
        self.config.selected_model = self.cmb_models.currentText()
        self.config.target_clip_count = target_count
        self.config.duration_preset = preset
        self.config.min_duration = min_dur
        self.config.max_duration = max_dur
        self.config.campaign_rules = rules
        self.config.save()

        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)

        self.worker = PipelineWorker(
            self.orchestrator,
            source,
            target_clip_count=target_count,
            min_duration=min_dur,
            max_duration=max_dur,
            campaign_rules=rules
        )
        self.worker.progress_changed.connect(self._on_worker_progress)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.failed.connect(self._on_worker_failed)
        self.worker.start()

    def _on_cancel(self):
        if self.worker and self.worker.isRunning():
            self.lbl_status.setText("Membatalkan proses dan membersihkan alokasi...")
            self.orchestrator.cancel()
            self.worker.wait(3000)
            self.btn_start.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            self.progress_bar.setValue(0)
            self.lbl_status.setText("Status: Dibatalkan oleh pengguna.")

    def _on_worker_progress(self, status: str, pct: int, msg: str):
        self.progress_bar.setValue(pct)
        self.lbl_status.setText(f"[{status}] {msg}")

    def _on_worker_finished(self, clips: List[ClipResult]):
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setValue(100)
        self.lbl_status.setText(f"Selesai! {len(clips)} klip dibuat di staging.")

        self.current_clips = clips
        self._populate_review_workspace()
        self.stack.setCurrentIndex(1)

    def _on_worker_failed(self, error: str):
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.lbl_status.setText("Gagal!")
        QMessageBox.critical(self, "Error Pipeline", f"Pipeline terhenti: {error}")

    def _populate_review_workspace(self):
        # Clear existing card widgets
        for c in self.card_widgets:
            c.deleteLater()
        self.card_widgets.clear()

        self.lbl_gallery_count.setText(f"Daftar Klip Terdeteksi ({len(self.current_clips)} Klip)")

        for clip in self.current_clips:
            card = ClipCardWidget(clip)
            card.clicked.connect(self._select_clip)
            self.gallery_layout.insertWidget(len(self.card_widgets), card)
            self.card_widgets.append(card)

        if self.current_clips:
            self._select_clip(self.current_clips[0])

    def _select_clip(self, clip: ClipResult):
        self.selected_clip = clip
        for card in self.card_widgets:
            card.set_active(card.clip.clip_id == clip.clip_id)

        dur = max(0.0, clip.end_time - clip.start_time)
        mode_val = getattr(clip, "reframe_mode", "DYNAMIC_SCENE")
        if mode_val == "DYNAMIC_SCENE":
            mode_str = "🔄 Transisi Dinamis (Talking Head 9:16 + Screen Record Fit)"
        elif mode_val == "CROP_TRACKING":
            mode_str = "👤 Crop Wajah Penuh 9:16"
        else:
            mode_str = "🖼 Blurred Background (Screen / Slide Utuh)"

        self.lbl_clip_info.setText(
            f"<b>{clip.title}</b> <span style='color: #a78bfa;'>[{mode_str}]</span><br/>"
            f"<span style='color: #60a5fa;'>Hook: \"{clip.hook}\"</span> | Skor: <b>{clip.virality_score}</b> | Durasi: <b>{dur:.1f}s</b><br/>"
            f"<span style='color: #9ca3af;'>{clip.reasoning}</span>"
        )

        if os.path.exists(clip.staging_path):
            self.player.setSource(QUrl.fromLocalFile(clip.staging_path))
            self.player.play()

    def _toggle_playback(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlayingState:
            self.btn_play_pause.setText("⏸")
        else:
            self.btn_play_pause.setText("▶")

    def _on_position_changed(self, position: int):
        duration = self.player.duration()
        if duration > 0:
            self.slider_progress.setValue(int((position / duration) * 1000))
        self._update_time_label(position, duration)

    def _on_duration_changed(self, duration: int):
        self._update_time_label(self.player.position(), duration)

    def _on_seek(self, value: int):
        duration = self.player.duration()
        if duration > 0:
            new_pos = int((value / 1000) * duration)
            self.player.setPosition(new_pos)

    def _update_time_label(self, pos_ms: int, dur_ms: int):
        cur_sec = int(pos_ms / 1000)
        tot_sec = int(dur_ms / 1000)
        self.lbl_time.setText(f"{cur_sec//60:02d}:{cur_sec%60:02d} / {tot_sec//60:02d}:{tot_sec%60:02d}")

    def _on_save_selected_clip(self):
        if not self.selected_clip or not os.path.exists(self.selected_clip.staging_path):
            QMessageBox.warning(self, "Simpan", "Tidak ada klip aktif untuk disimpan.")
            return

        default_name = f"clip_{self.selected_clip.clip_id}_{int(self.selected_clip.start_time)}.mp4"
        dest_path, _ = QFileDialog.getSaveFileName(
            self, "Simpan Klip 9:16", default_name, "Video Files (*.mp4)"
        )
        if dest_path:
            try:
                shutil.copy2(self.selected_clip.staging_path, dest_path)
                QMessageBox.information(self, "Berhasil", f"Klip berhasil disimpan ke:\n{dest_path}")
            except Exception as e:
                QMessageBox.critical(self, "Gagal", f"Gagal menyimpan file: {str(e)}")

    def _on_save_all_clips(self):
        if not self.current_clips:
            QMessageBox.warning(self, "Simpan Semua", "Tidak ada klip untuk disimpan.")
            return

        dest_dir = QFileDialog.getExistingDirectory(self, "Pilih Folder Penyimpanan Semua Klip")
        if dest_dir:
            dest_dir_path = Path(dest_dir)
            copied_count = 0
            for clip in self.current_clips:
                if os.path.exists(clip.staging_path):
                    target = dest_dir_path / f"clipmax_{clip.clip_id}_{int(clip.start_time)}.mp4"
                    shutil.copy2(clip.staging_path, target)
                    copied_count += 1
            QMessageBox.information(
                self, "Selesai", f"Berhasil menyimpan {copied_count} klip ke:\n{dest_dir}"
            )

    def _on_back_to_input(self):
        self.player.stop()
        self.stack.setCurrentIndex(0)
