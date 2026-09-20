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
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Thumbnail
        self.thumb_lbl = QLabel()
        self.thumb_lbl.setFixedSize(68, 100)
        self.thumb_lbl.setStyleSheet("background-color: #181A1D; border: 1px solid #3B3F47; border-radius: 4px;")
        self.thumb_lbl.setAlignment(Qt.AlignCenter)
        if clip.thumbnail_path and os.path.exists(clip.thumbnail_path):
            pix = QPixmap(clip.thumbnail_path)
            self.thumb_lbl.setPixmap(pix.scaled(68, 100, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        else:
            self.thumb_lbl.setText("9:16")
            self.thumb_lbl.setStyleSheet("color: #9CA3AF; font-size: 11px;")
        layout.addWidget(self.thumb_lbl)

        # Info container
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        # Top row: title + score badge
        top_row = QHBoxLayout()
        title_lbl = QLabel(clip.title)
        title_lbl.setStyleSheet("font-weight: 600; font-size: 13px; color: #E4E7EB;")
        title_lbl.setWordWrap(True)
        top_row.addWidget(title_lbl, 1)

        score_lbl = QLabel(f"{clip.virality_score} pts")
        score_lbl.setProperty("class", "BadgePill")
        score_lbl.setFixedHeight(20)
        top_row.addWidget(score_lbl)
        info_layout.addLayout(top_row)

        # Hook
        hook_lbl = QLabel(f'"{clip.hook}"')
        hook_lbl.setStyleSheet("color: #9CA3AF; font-style: italic; font-size: 11px;")
        hook_lbl.setWordWrap(True)
        info_layout.addWidget(hook_lbl)

        # Time range & Mode tag
        dur = max(0.0, clip.end_time - clip.start_time)
        mode_val = getattr(clip, "reframe_mode", "DYNAMIC_SCENE")
        if mode_val == "DYNAMIC_SCENE":
            mode_tag = "🔄 Dynamic Split"
        elif mode_val == "CROP_TRACKING":
            mode_tag = "👤 Face Crop"
        else:
            mode_tag = "🖼 Blurred BG"

        time_row = QHBoxLayout()
        time_row.setSpacing(6)
        time_lbl = QLabel(f"⏱ {int(clip.start_time)}s - {int(clip.end_time)}s ({dur:.1f}s)")
        time_lbl.setStyleSheet("color: #9CA3AF; font-size: 11px;")
        time_row.addWidget(time_lbl)

        mode_lbl = QLabel(mode_tag)
        mode_lbl.setProperty("class", "BadgePill")
        mode_lbl.setStyleSheet("font-size: 10px; padding: 1px 6px;")
        time_row.addWidget(mode_lbl)
        time_row.addStretch()

        info_layout.addLayout(time_row)
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
        self.resize(1080, 780)

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
        root_layout.setSpacing(14)

        # Baris 1: Header Minimalis (Title + Subtitle + Hardware Badge + Close)
        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(0, 0, 0, 2)
        title_bar.setSpacing(12)

        header_info = QVBoxLayout()
        header_info.setSpacing(2)
        title_lbl = QLabel("ClipMax")
        title_lbl.setProperty("class", "Title")
        sub_lbl = QLabel("Autonomous Desktop Clipper")
        sub_lbl.setProperty("class", "Sub")
        header_info.addWidget(title_lbl)
        header_info.addWidget(sub_lbl)
        title_bar.addLayout(header_info)

        title_bar.addStretch()

        # Hardware Badge
        self.lbl_hw_badge = QLabel("RTX 3050 • CUDA")
        self.lbl_hw_badge.setProperty("class", "BadgeHardware")
        title_bar.addWidget(self.lbl_hw_badge)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(32, 32)
        btn_close.setProperty("class", "Secondary")
        btn_close.clicked.connect(self.close)
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

        # Baris 2: Split 2 Kolom (Kiri: AI Gateway, Kanan: Campaign & Target)
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(14)

        # Kolom Kiri: AI Provider & Model Discovery
        card_provider = QFrame()
        card_provider.setProperty("class", "Card")
        cp_layout = QVBoxLayout(card_provider)
        cp_layout.setContentsMargins(16, 14, 16, 14)
        cp_layout.setSpacing(8)

        lbl_p_title = QLabel("AI PROVIDER & GATEWAY")
        lbl_p_title.setProperty("class", "SectionHeader")
        cp_layout.addWidget(lbl_p_title)

        lbl_ep = QLabel("Endpoint URL:")
        lbl_ep.setProperty("class", "FormLabel")
        self.txt_endpoint = QLineEdit(self.config.endpoint_url)
        self.txt_endpoint.setPlaceholderText("http://localhost:20128/v1")
        cp_layout.addWidget(lbl_ep)
        cp_layout.addWidget(self.txt_endpoint)

        lbl_key = QLabel("API Key (Opsional):")
        lbl_key.setProperty("class", "FormLabel")
        self.txt_key = QLineEdit(self.config.api_key)
        self.txt_key.setPlaceholderText("Bearer token / sk-...")
        self.txt_key.setEchoMode(QLineEdit.Password)
        cp_layout.addWidget(lbl_key)
        cp_layout.addWidget(self.txt_key)

        lbl_model = QLabel("Model:")
        lbl_model.setProperty("class", "FormLabel")
        cp_layout.addWidget(lbl_model)

        model_row = QHBoxLayout()
        model_row.setSpacing(8)
        self.cmb_models = QComboBox()
        self.cmb_models.addItem(self.config.selected_model)
        self.btn_discover = QPushButton("Discover")
        self.btn_discover.setProperty("class", "Secondary")
        self.btn_discover.clicked.connect(self._on_discover_models)
        model_row.addWidget(self.cmb_models, 1)
        model_row.addWidget(self.btn_discover)
        cp_layout.addLayout(model_row)

        cp_layout.addStretch()
        row2_layout.addWidget(card_provider, 1)

        # Kolom Kanan: Generation & Campaign Settings
        card_campaign = QFrame()
        card_campaign.setProperty("class", "Card")
        cc_layout = QVBoxLayout(card_campaign)
        cc_layout.setContentsMargins(16, 14, 16, 14)
        cc_layout.setSpacing(8)

        lbl_c_title = QLabel("CAMPAIGN & TARGET RULES")
        lbl_c_title.setProperty("class", "SectionHeader")
        cc_layout.addWidget(lbl_c_title)

        param_row = QHBoxLayout()
        param_row.setSpacing(10)

        count_box = QVBoxLayout()
        count_box.setSpacing(4)
        lbl_count = QLabel("Target Klip:")
        lbl_count.setProperty("class", "FormLabel")
        self.spn_clip_count = QSpinBox()
        self.spn_clip_count.setRange(1, 10)
        self.spn_clip_count.setValue(self.config.target_clip_count or 3)
        count_box.addWidget(lbl_count)
        count_box.addWidget(self.spn_clip_count)
        param_row.addLayout(count_box, 1)

        dur_box = QVBoxLayout()
        dur_box.setSpacing(4)
        lbl_dur = QLabel("Rentang Durasi:")
        lbl_dur.setProperty("class", "FormLabel")
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
        dur_box.addWidget(lbl_dur)
        dur_box.addWidget(self.cmb_duration)
        param_row.addLayout(dur_box, 2)

        cc_layout.addLayout(param_row)

        # Custom duration container
        self.custom_dur_widget = QWidget()
        custom_layout = QHBoxLayout(self.custom_dur_widget)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.setSpacing(8)

        min_box = QVBoxLayout()
        min_box.setSpacing(2)
        lbl_min = QLabel("Min (s):")
        lbl_min.setProperty("class", "FormLabel")
        self.spn_min_dur = QSpinBox()
        self.spn_min_dur.setRange(5, 300)
        self.spn_min_dur.setValue(int(self.config.min_duration or 30))
        min_box.addWidget(lbl_min)
        min_box.addWidget(self.spn_min_dur)
        custom_layout.addLayout(min_box)

        max_box = QVBoxLayout()
        max_box.setSpacing(2)
        lbl_max = QLabel("Max (s):")
        lbl_max.setProperty("class", "FormLabel")
        self.spn_max_dur = QSpinBox()
        self.spn_max_dur.setRange(10, 600)
        self.spn_max_dur.setValue(int(self.config.max_duration or 60))
        max_box.addWidget(lbl_max)
        max_box.addWidget(self.spn_max_dur)
        custom_layout.addLayout(max_box)

        cc_layout.addWidget(self.custom_dur_widget)
        self.custom_dur_widget.setVisible(self.cmb_duration.currentText() == "Custom")

        lbl_rules = QLabel("Brief / Aturan Kampanye (Opsional):")
        lbl_rules.setProperty("class", "FormLabel")
        cc_layout.addWidget(lbl_rules)

        self.txt_rules = QPlainTextEdit()
        self.txt_rules.setPlaceholderText(
            "Contoh: Fokus pada hook solusi, sertakan call-to-action di akhir, hindari topik sensitif..."
        )
        self.txt_rules.setPlainText(self.config.campaign_rules or "")
        self.txt_rules.setFixedHeight(75)
        cc_layout.addWidget(self.txt_rules)

        row2_layout.addWidget(card_campaign, 1)
        layout.addLayout(row2_layout)

        # Baris 3 (Full Width): Input Video Ingestion
        card_video = QFrame()
        card_video.setProperty("class", "Card")
        cv_layout = QVBoxLayout(card_video)
        cv_layout.setContentsMargins(16, 14, 16, 14)
        cv_layout.setSpacing(10)

        lbl_v_title = QLabel("INPUT VIDEO INGESTION (16:9)")
        lbl_v_title.setProperty("class", "SectionHeader")
        cv_layout.addWidget(lbl_v_title)

        self.input_tabs = QTabWidget()

        # Tab 1: File Lokal
        tab_local = QWidget()
        tl_layout = QHBoxLayout(tab_local)
        tl_layout.setContentsMargins(8, 8, 8, 8)
        tl_layout.setSpacing(10)
        self.txt_video = QLineEdit()
        self.txt_video.setPlaceholderText("Pilih file video MP4, MKV, MOV...")
        self.btn_browse = QPushButton("Browse File...")
        self.btn_browse.setProperty("class", "Secondary")
        self.btn_browse.clicked.connect(self._on_browse_video)
        tl_layout.addWidget(self.txt_video, 1)
        tl_layout.addWidget(self.btn_browse)

        # Tab 2: Link Video yt-dlp
        tab_url = QWidget()
        tu_layout = QHBoxLayout(tab_url)
        tu_layout.setContentsMargins(8, 8, 8, 8)
        tu_layout.setSpacing(10)
        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText("Tempel tautan video YouTube, X, Instagram, TikTok...")
        tu_layout.addWidget(self.txt_url, 1)

        self.input_tabs.addTab(tab_local, "📁 File Video Lokal")
        self.input_tabs.addTab(tab_url, "🌐 Video Link (yt-dlp)")
        cv_layout.addWidget(self.input_tabs)

        layout.addWidget(card_video)

        # Baris 4 (Full Width): Progress Section & Tombol Aksi Utama
        card_exec = QFrame()
        card_exec.setProperty("class", "Card")
        ce_layout = QVBoxLayout(card_exec)
        ce_layout.setContentsMargins(16, 14, 16, 14)
        ce_layout.setSpacing(12)

        self.lbl_status = QLabel("Status: Siap memproses video...")
        self.lbl_status.setProperty("class", "Sub")
        ce_layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        ce_layout.addWidget(self.progress_bar)

        btn_action_row = QHBoxLayout()
        btn_action_row.setSpacing(12)

        self.btn_start = QPushButton("Mulai Generate Klip 9:16")
        self.btn_start.setProperty("class", "PrimaryAction")
        self.btn_start.clicked.connect(self._on_start)

        self.btn_cancel = QPushButton("Batal / Stop")
        self.btn_cancel.setProperty("class", "Danger")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._on_cancel)

        btn_action_row.addWidget(self.btn_start, 4)
        btn_action_row.addWidget(self.btn_cancel, 1)
        ce_layout.addLayout(btn_action_row)

        layout.addWidget(card_exec)
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
        w_title.setProperty("class", "Title")
        
        self.btn_back = QPushButton("← Proses Video Baru")
        self.btn_back.setProperty("class", "Secondary")
        self.btn_back.clicked.connect(self._on_back_to_input)

        top_bar.addWidget(w_title)
        top_bar.addStretch()
        top_bar.addWidget(self.btn_back)
        layout.addLayout(top_bar)

        # Main Splitter: Left Gallery, Right Player & Export
        splitter = QSplitter(Qt.Horizontal)

        # Left: Scrollable Card Gallery (Minimum 360px)
        left_panel = QFrame()
        left_panel.setProperty("class", "Card")
        left_panel.setMinimumWidth(360)
        lp_layout = QVBoxLayout(left_panel)
        lp_layout.setContentsMargins(12, 12, 12, 12)
        lp_layout.setSpacing(10)

        self.lbl_gallery_count = QLabel("Daftar Klip Terdeteksi (0 Klip)")
        self.lbl_gallery_count.setProperty("class", "SectionHeader")
        lp_layout.addWidget(self.lbl_gallery_count)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.gallery_container = QWidget()
        self.gallery_layout = QVBoxLayout(self.gallery_container)
        self.gallery_layout.setContentsMargins(2, 2, 2, 2)
        self.gallery_layout.setSpacing(8)
        self.gallery_layout.addStretch()
        self.scroll_area.setWidget(self.gallery_container)
        lp_layout.addWidget(self.scroll_area)

        splitter.addWidget(left_panel)

        # Right: Built-in Video Player & Action Controls
        right_panel = QFrame()
        right_panel.setProperty("class", "Card")
        rp_layout = QVBoxLayout(right_panel)
        rp_layout.setContentsMargins(16, 16, 16, 16)
        rp_layout.setSpacing(12)

        # Player Container
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #181A1D; border: 1px solid #3B3F47; border-radius: 6px;")
        self.video_widget.setMinimumSize(280, 480)
        self.player.setVideoOutput(self.video_widget)
        rp_layout.addWidget(self.video_widget, 1)

        # Playback Controls
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(8)
        self.btn_play_pause = QPushButton("▶")
        self.btn_play_pause.setFixedSize(36, 36)
        self.btn_play_pause.setProperty("class", "Secondary")
        self.btn_play_pause.clicked.connect(self._toggle_playback)

        self.slider_progress = QSlider(Qt.Horizontal)
        self.slider_progress.setRange(0, 1000)
        self.slider_progress.sliderMoved.connect(self._on_seek)

        self.lbl_time = QLabel("00:00 / 00:00")
        self.lbl_time.setStyleSheet("font-size: 11px; color: #9CA3AF;")

        ctrl_layout.addWidget(self.btn_play_pause)
        ctrl_layout.addWidget(self.slider_progress, 1)
        ctrl_layout.addWidget(self.lbl_time)
        rp_layout.addLayout(ctrl_layout)

        # Selected Clip Detail Frame
        info_frame = QFrame()
        info_frame.setStyleSheet("background-color: #1E2024; border: 1px solid #363A42; border-radius: 6px; padding: 10px;")
        info_frame_layout = QVBoxLayout(info_frame)
        info_frame_layout.setContentsMargins(8, 8, 8, 8)
        self.lbl_clip_info = QLabel("Pilih klip di sebelah kiri untuk memutar pratinjau.")
        self.lbl_clip_info.setStyleSheet("color: #E4E7EB; font-size: 12px; line-height: 1.4;")
        self.lbl_clip_info.setWordWrap(True)
        info_frame_layout.addWidget(self.lbl_clip_info)
        rp_layout.addWidget(info_frame)

        # Export Action Buttons
        act_layout = QHBoxLayout()
        act_layout.setSpacing(10)
        self.btn_save_one = QPushButton("💾 Simpan Klip Ini")
        self.btn_save_one.setFixedHeight(38)
        self.btn_save_one.clicked.connect(self._on_save_selected_clip)

        self.btn_save_all = QPushButton("📦 Simpan Semua Klip")
        self.btn_save_all.setFixedHeight(38)
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
            f"<b>{clip.title}</b> &nbsp; <span style='color: #4A6FA5; font-size: 11px; font-weight: 600;'>[{mode_str}]</span><br/>"
            f"<span style='color: #E4E7EB;'>Hook: \"{clip.hook}\"</span> &nbsp;•&nbsp; <span style='color: #9CA3AF;'>Skor: <b>{clip.virality_score}</b> &nbsp;•&nbsp; Durasi: <b>{dur:.1f}s</b></span><br/>"
            f"<span style='color: #9CA3AF;'>{clip.reasoning}</span>"
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
