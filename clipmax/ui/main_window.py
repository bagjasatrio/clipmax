import os
import sys
import shutil
from pathlib import Path
from typing import Optional, List, Dict
from PySide6.QtCore import Qt, QThread, Signal, QPoint, QUrl, QSettings
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QProgressBar,
    QFileDialog, QMessageBox, QFrame, QStackedWidget, QTabWidget,
    QScrollArea, QSlider, QSizePolicy, QSplitter, QSpinBox,
    QPlainTextEdit
)
from clipmax.config import AppConfig, clear_temp_cache
from clipmax.ai_gateway import discover_models
from clipmax.pipeline import PipelineOrchestrator, PipelineStatus, ClipResult
from clipmax.downloader import is_valid_video_url, clean_error_message

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
        campaign_rules: str = "",
        clip_mode: str = "single",
        subtitle_base_color: str = "#FFFFFF",
        subtitle_highlight_color: str = "#FF2A2A"
    ):
        super().__init__()
        self.orchestrator = orchestrator
        self.input_source = input_source
        self.target_clip_count = target_clip_count
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.campaign_rules = campaign_rules
        self.clip_mode = clip_mode
        self.subtitle_base_color = subtitle_base_color
        self.subtitle_highlight_color = subtitle_highlight_color

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
                campaign_rules=self.campaign_rules,
                clip_mode=self.clip_mode,
                subtitle_base_color=self.subtitle_base_color,
                subtitle_highlight_color=self.subtitle_highlight_color
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
        self.setFixedHeight(94)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Thumbnail
        self.thumb_lbl = QLabel()
        self.thumb_lbl.setFixedSize(48, 76)
        self.thumb_lbl.setStyleSheet("background-color: #121417; border: 1px solid #282C35; border-radius: 4px;")
        self.thumb_lbl.setAlignment(Qt.AlignCenter)
        if clip.thumbnail_path and os.path.exists(clip.thumbnail_path):
            pix = QPixmap(clip.thumbnail_path)
            self.thumb_lbl.setPixmap(pix.scaled(48, 76, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        else:
            self.thumb_lbl.setText("9:16")
            self.thumb_lbl.setStyleSheet("color: #8B949E; font-size: 10px;")
        layout.addWidget(self.thumb_lbl)

        # Info container
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setAlignment(Qt.AlignVCenter)

        # Top row: title + score badge
        top_row = QHBoxLayout()
        title_lbl = QLabel(clip.title)
        title_lbl.setStyleSheet("font-weight: 600; font-size: 12px; color: #E6E9EE;")
        title_lbl.setWordWrap(True)
        top_row.addWidget(title_lbl, 1)

        score_lbl = QLabel(f"{clip.virality_score} pts")
        score_lbl.setProperty("class", "BadgePill")
        top_row.addWidget(score_lbl)
        info_layout.addLayout(top_row)

        # Hook
        hook_lbl = QLabel(f'"{clip.hook}"')
        hook_lbl.setStyleSheet("color: #8B949E; font-style: italic; font-size: 11px;")
        hook_lbl.setWordWrap(True)
        info_layout.addWidget(hook_lbl)

        # Time range & Mode tag
        dur = max(0.0, clip.end_time - clip.start_time)
        mode_val = getattr(clip, "reframe_mode", "DYNAMIC_SCENE")
        if mode_val == "MONTAGE":
            mode_tag = "✂ Montage"
        elif mode_val == "DYNAMIC_SCENE":
            mode_tag = "Dynamic Split"
        elif mode_val == "CROP_TRACKING":
            mode_tag = "Face Crop 9:16"
        else:
            mode_tag = "Blurred BG"

        time_row = QHBoxLayout()
        time_row.setSpacing(6)
        time_lbl = QLabel(f"{int(clip.start_time)}s - {int(clip.end_time)}s ({dur:.1f}s)")
        time_lbl.setStyleSheet("color: #8B949E; font-size: 11px;")
        time_row.addWidget(time_lbl)

        mode_lbl = QLabel(mode_tag)
        mode_lbl.setProperty("class", "BadgePill")
        mode_lbl.setStyleSheet("font-size: 10px; color: #8B949E;")
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

class ResponsivePlayerArea(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.video_widget: Optional[QVideoWidget] = None
        self.setStyleSheet("background-color: #121417; border: 1px solid #282C35; border-radius: 8px;")

    def set_video_widget(self, widget: QVideoWidget):
        self.video_widget = widget

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.video_widget:
            avail_w = max(100, self.width() - 36)
            avail_h = max(100, self.height() - 180)
            target_w = int(avail_h * (9.0 / 16.0))
            if target_w <= avail_w:
                target_h = avail_h
            else:
                target_w = avail_w
                target_h = int(avail_w * (16.0 / 9.0))
            self.video_widget.setFixedSize(max(180, target_w), max(320, target_h))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(1024, 680)
        self.resize(1180, 780)

        self.config = AppConfig.load()
        self.orchestrator = PipelineOrchestrator(self.config)
        self.worker: Optional[PipelineWorker] = None
        self._drag_pos = QPoint()

        # Staging clips
        self.current_clips: List[ClipResult] = []
        self.selected_clip: Optional[ClipResult] = None
        self.card_widgets: List[ClipCardWidget] = []
        self.active_cookie_path: Optional[str] = None

        # Video Player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        # Settings & Default Volume (40% / 0.4f)
        self.settings = QSettings("ClipMax", "ClipMaxStudio")
        try:
            self.current_volume = int(self.settings.value("player_volume", 40))
            if not (0 <= self.current_volume <= 100):
                self.current_volume = 40
        except (ValueError, TypeError):
            self.current_volume = 40
        self.audio_output.setVolume(self.current_volume / 100.0)

        self._build_ui()
        self._setup_player_events()

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(1, 1, 1, 1)
        root_layout.setSpacing(0)

        # 1. Top App Header (42px)
        header_frame = QFrame()
        header_frame.setObjectName("AppHeader")
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(16, 0, 16, 0)
        h_layout.setSpacing(8)

        # Left: App Brand
        brand_lbl = QLabel("ClipMax Studio")
        brand_lbl.setProperty("class", "AppBrand")
        h_layout.addWidget(brand_lbl)

        h_layout.addStretch()

        # Right: Monochrome System Pill (Hardware status)
        self.lbl_hw_pill = QLabel("<span style='color: #10B981;'>●</span> &nbsp;NVIDIA RTX 3050 | CUDA Active")
        self.lbl_hw_pill.setObjectName("HardwarePill")
        h_layout.addWidget(self.lbl_hw_pill)

        # Reset Form & Clear Cache
        btn_reset_cache = QPushButton("Reset & Clear Cache")
        btn_reset_cache.setFixedHeight(28)
        btn_reset_cache.setProperty("class", "Secondary")
        btn_reset_cache.setToolTip("Reset input URL & Campaign Brief, serta bersihkan cache sementara")
        btn_reset_cache.clicked.connect(self._on_reset_and_clear_cache)
        h_layout.addWidget(btn_reset_cache)

        # Window Controls: Minimize, Maximize/Restore, Close
        btn_min = QPushButton("—")
        btn_min.setFixedSize(28, 28)
        btn_min.setProperty("class", "Secondary")
        btn_min.clicked.connect(self.showMinimized)
        h_layout.addWidget(btn_min)

        self.btn_max = QPushButton("□")
        self.btn_max.setFixedSize(28, 28)
        self.btn_max.setProperty("class", "Secondary")
        self.btn_max.clicked.connect(self._toggle_maximize)
        h_layout.addWidget(self.btn_max)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(28, 28)
        btn_close.setProperty("class", "Secondary")
        btn_close.clicked.connect(self.close)
        h_layout.addWidget(btn_close)

        root_layout.addWidget(header_frame)

        # 2. Main Studio Body (Responsive Splitter View)
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setHandleWidth(1)
        self.main_splitter.setStyleSheet("QSplitter::handle { background-color: #282C35; }")

        # Panel Kiri (Sidebar Controls - 360px to 450px)
        sidebar = self._build_sidebar()
        self.main_splitter.addWidget(sidebar)

        # Panel Kanan (Studio Stage / Canvas Area - Expanding)
        self.stage_stack = QStackedWidget()
        self.stage_stack.setObjectName("StageCanvas")
        self.stage_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.view_standby = self._build_standby_stage()
        self.view_processing = self._build_processing_stage()
        self.view_review = self._build_review_stage()

        self.stage_stack.addWidget(self.view_standby)      # Index 0
        self.stage_stack.addWidget(self.view_processing)   # Index 1
        self.stage_stack.addWidget(self.view_review)       # Index 2
        self.stage_stack.setCurrentIndex(0)

        self.main_splitter.addWidget(self.stage_stack)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setCollapsible(0, False)
        self.main_splitter.setCollapsible(1, False)

        root_layout.addWidget(self.main_splitter, 1)

    def _build_divider(self) -> QFrame:
        div = QFrame()
        div.setProperty("class", "Divider")
        return div

    def _build_sidebar(self) -> QWidget:
        sidebar_frame = QFrame()
        sidebar_frame.setObjectName("Sidebar")
        sidebar_frame.setMinimumWidth(360)
        sidebar_frame.setMaximumWidth(450)
        sidebar_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        outer_layout = QVBoxLayout(sidebar_frame)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("background: transparent; border: none;")

        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(12)

        # Section 1: Ingestion Source
        lbl_s1 = QLabel("SOURCE INGESTION")
        lbl_s1.setProperty("class", "SectionHeader")
        layout.addWidget(lbl_s1)

        self.input_tabs = QTabWidget()

        # Tab YouTube URL
        tab_url = QWidget()
        tu_layout = QVBoxLayout(tab_url)
        tu_layout.setContentsMargins(6, 6, 6, 6)
        tu_layout.setSpacing(6)
        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText("Paste YouTube / X / web video URL...")
        tu_layout.addWidget(self.txt_url)

        # Tab Local File
        tab_local = QWidget()
        tl_layout = QHBoxLayout(tab_local)
        tl_layout.setContentsMargins(6, 6, 6, 6)
        tl_layout.setSpacing(6)
        self.txt_video = QLineEdit()
        self.txt_video.setPlaceholderText("Select video (MP4, MKV)...")
        self.btn_browse = QPushButton("Browse")
        self.btn_browse.setProperty("class", "Secondary")
        self.btn_browse.clicked.connect(self._on_browse_video)
        tl_layout.addWidget(self.txt_video, 1)
        tl_layout.addWidget(self.btn_browse)

        self.input_tabs.addTab(tab_url, "🌐 YouTube URL")
        self.input_tabs.addTab(tab_local, "📁 Local File")
        layout.addWidget(self.input_tabs)

        layout.addWidget(self._build_divider())

        # Section 2: AI & Model Engine
        lbl_s2 = QLabel("AI INFERENCE ENGINE")
        lbl_s2.setProperty("class", "SectionHeader")
        layout.addWidget(lbl_s2)

        model_row = QHBoxLayout()
        model_row.setSpacing(8)
        self.cmb_models = QComboBox()
        self.cmb_models.addItem(self.config.selected_model)
        self.btn_discover = QPushButton("Discover")
        self.btn_discover.setProperty("class", "Secondary")
        self.btn_discover.clicked.connect(self._on_discover_models)
        model_row.addWidget(self.cmb_models, 1)
        model_row.addWidget(self.btn_discover)
        layout.addLayout(model_row)

        # Optional Endpoint & Key container (compact)
        ep_row = QHBoxLayout()
        ep_row.setSpacing(6)
        self.txt_endpoint = QLineEdit(self.config.endpoint_url)
        self.txt_endpoint.setPlaceholderText("Gateway endpoint...")
        self.txt_key = QLineEdit(self.config.api_key)
        self.txt_key.setPlaceholderText("API Key (optional)...")
        self.txt_key.setEchoMode(QLineEdit.Password)
        ep_row.addWidget(self.txt_endpoint, 1)
        ep_row.addWidget(self.txt_key, 1)
        layout.addLayout(ep_row)

        layout.addWidget(self._build_divider())

        # Section 3: Campaign & Rules
        lbl_s3 = QLabel("CURATION & RULES")
        lbl_s3.setProperty("class", "SectionHeader")
        layout.addWidget(lbl_s3)

        # Clip Type / Mode
        mode_box = QVBoxLayout()
        mode_box.setSpacing(3)
        lbl_mode = QLabel("Clip Type (Mode):")
        lbl_mode.setProperty("class", "FormLabel")
        self.cmb_clip_mode = QComboBox()
        self.cmb_clip_mode.addItem("Single Clip (Default)", "single")
        self.cmb_clip_mode.addItem("Multi-Cut Montage", "montage")
        if getattr(self.config, "clip_mode", "single") == "montage":
            self.cmb_clip_mode.setCurrentIndex(1)
        mode_box.addWidget(lbl_mode)
        mode_box.addWidget(self.cmb_clip_mode)
        layout.addLayout(mode_box)

        row_params = QHBoxLayout()
        row_params.setSpacing(8)

        # Target clip count
        count_box = QVBoxLayout()
        count_box.setSpacing(3)
        lbl_cnt = QLabel("Target Clips:")
        lbl_cnt.setProperty("class", "FormLabel")
        self.spn_clip_count = QSpinBox()
        self.spn_clip_count.setRange(1, 10)
        self.spn_clip_count.setValue(self.config.target_clip_count or 3)
        count_box.addWidget(lbl_cnt)
        count_box.addWidget(self.spn_clip_count)
        row_params.addLayout(count_box, 1)

        # Duration range
        dur_box = QVBoxLayout()
        dur_box.setSpacing(3)
        lbl_dr = QLabel("Clip Duration:")
        lbl_dr.setProperty("class", "FormLabel")
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
        dur_box.addWidget(lbl_dr)
        dur_box.addWidget(self.cmb_duration)
        row_params.addLayout(dur_box, 2)
        layout.addLayout(row_params)

        # Custom duration container
        self.custom_dur_widget = QWidget()
        custom_layout = QHBoxLayout(self.custom_dur_widget)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.setSpacing(6)

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

        layout.addWidget(self.custom_dur_widget)
        self.custom_dur_widget.setVisible(self.cmb_duration.currentText() == "Custom")

        # Campaign brief
        lbl_brief = QLabel("Campaign Brief & Directives:")
        lbl_brief.setProperty("class", "FormLabel")
        layout.addWidget(lbl_brief)

        self.txt_rules = QPlainTextEdit()
        self.txt_rules.setPlaceholderText("Optional: focus on key solutions, exclude intros, highlight call-to-actions...")
        self.txt_rules.setPlainText(self.config.campaign_rules or "")
        self.txt_rules.setFixedHeight(75)
        layout.addWidget(self.txt_rules)

        # Section 4: Subtitle Style & Colors
        lbl_s4 = QLabel("SUBTITLE STYLE (KARAOKE)")
        lbl_s4.setProperty("class", "SectionHeader")
        layout.addWidget(lbl_s4)

        # Preset selector
        sub_box = QVBoxLayout()
        sub_box.setSpacing(3)
        lbl_preset = QLabel("Color Preset:")
        lbl_preset.setProperty("class", "FormLabel")
        self.cmb_sub_preset = QComboBox()
        self.cmb_sub_preset.addItem("Merah - Putih (Default)", "red_white")
        self.cmb_sub_preset.addItem("Kuning TikTok (#FFE81F)", "tiktok_yellow")
        self.cmb_sub_preset.addItem("Hijau Neon (#39FF14)", "neon_green")
        self.cmb_sub_preset.addItem("Cyan Gamer (#00F0FF)", "cyan_gamer")
        self.cmb_sub_preset.addItem("Custom", "custom")
        self.cmb_sub_preset.currentIndexChanged.connect(self._on_sub_preset_changed)
        sub_box.addWidget(lbl_preset)
        sub_box.addWidget(self.cmb_sub_preset)
        layout.addLayout(sub_box)

        # Color inputs row
        row_colors = QHBoxLayout()
        row_colors.setSpacing(8)

        base_box = QVBoxLayout()
        base_box.setSpacing(2)
        lbl_b_col = QLabel("Base Color:")
        lbl_b_col.setProperty("class", "FormLabel")
        self.txt_base_color = QLineEdit(getattr(self.config, "subtitle_base_color", "#FFFFFF"))
        base_box.addWidget(lbl_b_col)
        base_box.addWidget(self.txt_base_color)
        row_colors.addLayout(base_box)

        hl_box = QVBoxLayout()
        hl_box.setSpacing(2)
        lbl_h_col = QLabel("Active Highlight:")
        lbl_h_col.setProperty("class", "FormLabel")
        self.txt_hl_color = QLineEdit(getattr(self.config, "subtitle_highlight_color", "#FF2A2A"))
        hl_box.addWidget(lbl_h_col)
        hl_box.addWidget(self.txt_hl_color)
        row_colors.addLayout(hl_box)

        layout.addLayout(row_colors)

        layout.addStretch()
        layout.addWidget(self._build_divider())

        # Bottom Action: Generate Clips
        self.btn_start = QPushButton("Generate Clips")
        self.btn_start.setObjectName("BtnGenerate")
        self.btn_start.clicked.connect(self._on_start)
        layout.addWidget(self.btn_start)

        self.btn_cancel = QPushButton("Stop Process")
        self.btn_cancel.setProperty("class", "Danger")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self._on_cancel)
        layout.addWidget(self.btn_cancel)

        scroll_area.setWidget(content_widget)
        outer_layout.addWidget(scroll_area)
        return sidebar_frame

    def _build_standby_stage(self) -> QWidget:
        stage = QWidget()
        layout = QVBoxLayout(stage)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(14)

        # Minimalist 9:16 aspect ratio placeholder frame
        frame_box = QFrame()
        frame_box.setFixedSize(160, 260)
        frame_box.setStyleSheet(
            "background-color: #121417; border: 2px dashed #282C35; border-radius: 8px;"
        )
        fb_layout = QVBoxLayout(frame_box)
        fb_layout.setAlignment(Qt.AlignCenter)

        icon_lbl = QLabel("🎬")
        icon_lbl.setStyleSheet("font-size: 36px; color: #8B949E; background: transparent; border: none;")
        icon_lbl.setAlignment(Qt.AlignCenter)
        fb_layout.addWidget(icon_lbl)

        sub_916 = QLabel("9:16 Canvas")
        sub_916.setStyleSheet("color: #8B949E; font-size: 11px; font-weight: 600; background: transparent; border: none;")
        sub_916.setAlignment(Qt.AlignCenter)
        fb_layout.addWidget(sub_916)

        layout.addWidget(frame_box, 0, Qt.AlignCenter)

        main_prompt = QLabel("Masukkan video untuk memulai kurasi klip")
        main_prompt.setStyleSheet("font-size: 15px; font-weight: 600; color: #E6E9EE;")
        main_prompt.setAlignment(Qt.AlignCenter)
        layout.addWidget(main_prompt)

        sub_prompt = QLabel(
            "ClipMax Studio mentranskrip ucapan (CUDA), mengevaluasi viralitas via AI Gateway,\n"
            "dan mereframe ke vertikal 9:16 dengan pelacakan wajah aktif."
        )
        sub_prompt.setStyleSheet("font-size: 12px; color: #8B949E; line-height: 1.4;")
        sub_prompt.setAlignment(Qt.AlignCenter)
        layout.addWidget(sub_prompt)

        return stage

    def _build_processing_stage(self) -> QWidget:
        stage = QWidget()
        layout = QVBoxLayout(stage)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)

        tracker_frame = QFrame()
        tracker_frame.setFixedWidth(520)
        tracker_frame.setStyleSheet(
            "background-color: #1B1E24; border: 1px solid #282C35; border-radius: 8px; padding: 20px;"
        )
        t_layout = QVBoxLayout(tracker_frame)
        t_layout.setSpacing(14)

        top_header = QHBoxLayout()
        title_proc = QLabel("PROCESSING PIPELINE")
        title_proc.setProperty("class", "SectionHeader")
        self.lbl_proc_pct = QLabel("0%")
        self.lbl_proc_pct.setStyleSheet("font-size: 13px; font-weight: 700; color: #386FA4;")
        top_header.addWidget(title_proc)
        top_header.addStretch()
        top_header.addWidget(self.lbl_proc_pct)
        t_layout.addLayout(top_header)

        # Visual Step Tracker Bertingkat
        self.step_widgets: Dict[str, QLabel] = {}
        steps = [
            ("STEP_AUDIO", "1. Ingestion & Audio Extraction"),
            ("STEP_WHISPER", "2. Transcribing Speech (Faster-Whisper CUDA)"),
            ("STEP_LLM", "3. Curating Viral Hooks (AI Gateway)"),
            ("STEP_REFRAME", "4. Visual Reframing & Face Tracking (9:16)"),
            ("STEP_RENDER", "5. Burning Subtitles & Hardware NVENC Export"),
        ]

        for key, name in steps:
            row = QHBoxLayout()
            row.setSpacing(10)
            dot = QLabel("○")
            dot.setStyleSheet("color: #8B949E; font-size: 14px; font-weight: bold;")
            text = QLabel(name)
            text.setStyleSheet("color: #8B949E; font-size: 12px;")
            row.addWidget(dot)
            row.addWidget(text, 1)
            t_layout.addLayout(row)
            self.step_widgets[key] = dot

        t_layout.addWidget(self._build_divider())

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        t_layout.addWidget(self.progress_bar)

        self.lbl_stage_log = QLabel("Inisialisasi pipeline...")
        self.lbl_stage_log.setStyleSheet("color: #8B949E; font-size: 11px;")
        t_layout.addWidget(self.lbl_stage_log)

        layout.addWidget(tracker_frame, 0, Qt.AlignCenter)
        return stage

    def _build_review_stage(self) -> QWidget:
        stage = QWidget()
        layout = QVBoxLayout(stage)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Top Bar of Review Stage
        top_bar = QHBoxLayout()
        w_title = QLabel("STUDIO REVIEW WORKSPACE")
        w_title.setProperty("class", "SectionHeader")
        
        self.btn_new_task = QPushButton("← New Project")
        self.btn_new_task.setProperty("class", "Secondary")
        self.btn_new_task.clicked.connect(self._on_back_to_standby)

        top_bar.addWidget(w_title)
        top_bar.addStretch()
        top_bar.addWidget(self.btn_new_task)
        layout.addLayout(top_bar)

        # Review Body (Left: 9:16 Center Player, Right: Clip Strip Gallery)
        splitter = QSplitter(Qt.Horizontal)

        # Center Studio Player Area (Responsive 9:16 Aspect Ratio)
        player_area = ResponsivePlayerArea()
        p_layout = QVBoxLayout(player_area)
        p_layout.setContentsMargins(16, 16, 16, 16)
        p_layout.setSpacing(10)

        # Video Widget (Centered 9:16 aspect)
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #0B0D0F; border-radius: 6px;")
        self.video_widget.setFixedSize(270, 480)
        player_area.set_video_widget(self.video_widget)
        self.player.setVideoOutput(self.video_widget)
        p_layout.addWidget(self.video_widget, 0, Qt.AlignCenter)

        # Player Controls
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
        self.lbl_time.setStyleSheet("font-size: 11px; color: #8B949E;")

        # Volume Controls
        self.btn_mute = QPushButton("🔊" if self.current_volume > 0 else "🔇")
        self.btn_mute.setObjectName("BtnMute")
        self.btn_mute.setFixedSize(28, 28)
        self.btn_mute.setToolTip("Mute / Unmute")
        self.btn_mute.clicked.connect(self._toggle_mute)

        self.slider_volume = QSlider(Qt.Horizontal)
        self.slider_volume.setObjectName("VolumeSlider")
        self.slider_volume.setRange(0, 100)
        self.slider_volume.setValue(self.current_volume)
        self.slider_volume.setFixedWidth(80)
        self.slider_volume.setToolTip(f"Volume: {self.current_volume}%")
        self.slider_volume.valueChanged.connect(self._on_volume_changed)

        ctrl_layout.addWidget(self.btn_play_pause)
        ctrl_layout.addWidget(self.slider_progress, 1)
        ctrl_layout.addWidget(self.lbl_time)
        ctrl_layout.addSpacing(6)
        ctrl_layout.addWidget(self.btn_mute)
        ctrl_layout.addWidget(self.slider_volume)
        p_layout.addLayout(ctrl_layout)

        # Selected Clip Info Frame
        info_frame = QFrame()
        info_frame.setStyleSheet("background-color: #1B1E24; border: 1px solid #282C35; border-radius: 6px; padding: 10px;")
        info_l = QVBoxLayout(info_frame)
        info_l.setContentsMargins(8, 8, 8, 8)
        self.lbl_clip_info = QLabel("Select a clip to preview.")
        self.lbl_clip_info.setStyleSheet("color: #E6E9EE; font-size: 12px; line-height: 1.4;")
        self.lbl_clip_info.setWordWrap(True)
        info_l.addWidget(self.lbl_clip_info)
        p_layout.addWidget(info_frame)

        splitter.addWidget(player_area)

        # Right / Side Clip Strip
        gallery_panel = QFrame()
        gallery_panel.setStyleSheet("background-color: #1B1E24; border: 1px solid #282C35; border-radius: 8px;")
        gp_layout = QVBoxLayout(gallery_panel)
        gp_layout.setContentsMargins(12, 12, 12, 12)
        gp_layout.setSpacing(10)

        self.lbl_gallery_count = QLabel("CURATED CLIPS (0)")
        self.lbl_gallery_count.setProperty("class", "SectionHeader")
        gp_layout.addWidget(self.lbl_gallery_count)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.gallery_container = QWidget()
        self.gallery_layout = QVBoxLayout(self.gallery_container)
        self.gallery_layout.setContentsMargins(2, 2, 2, 2)
        self.gallery_layout.setSpacing(8)
        self.gallery_layout.addStretch()
        self.scroll_area.setWidget(self.gallery_container)
        gp_layout.addWidget(self.scroll_area, 1)

        # Export Actions at Bottom of Gallery
        gp_layout.addWidget(self._build_divider())
        act_layout = QVBoxLayout()
        act_layout.setSpacing(8)
        self.btn_save_one = QPushButton("💾 Export Selected Clip")
        self.btn_save_one.setFixedHeight(38)
        self.btn_save_one.clicked.connect(self._on_save_selected_clip)

        self.btn_save_all = QPushButton("📦 Export All Clips")
        self.btn_save_all.setFixedHeight(38)
        self.btn_save_all.setProperty("class", "Success")
        self.btn_save_all.clicked.connect(self._on_save_all_clips)

        act_layout.addWidget(self.btn_save_one)
        act_layout.addWidget(self.btn_save_all)
        gp_layout.addLayout(act_layout)

        splitter.addWidget(gallery_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter, 1)
        return stage

    def _setup_player_events(self):
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            self.btn_max.setText("□")
        else:
            self.showMaximized()
            self.btn_max.setText("❐")

    def mouseDoubleClickEvent(self, event):
        if event.position().y() < 42:
            self._toggle_maximize()
            event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.position().y() < 42:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = QPoint()
        event.accept()

    def _on_discover_models(self):
        url = self.txt_endpoint.text().strip()
        key = self.txt_key.text().strip()
        try:
            models = discover_models(url, key)
            self.cmb_models.clear()
            self.cmb_models.addItems(models)
            QMessageBox.information(self, "Models Discovered", f"Successfully loaded {len(models)} model(s).")
        except Exception as e:
            QMessageBox.warning(self, "Discovery Error", f"Failed to retrieve models: {str(e)}")

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

    def _on_sub_preset_changed(self):
        code = self.cmb_sub_preset.currentData()
        presets = {
            "red_white": ("#FFFFFF", "#FF2A2A"),
            "tiktok_yellow": ("#FFFFFF", "#FFE81F"),
            "neon_green": ("#FFFFFF", "#39FF14"),
            "cyan_gamer": ("#FFFFFF", "#00F0FF"),
        }
        if code in presets:
            base, hl = presets[code]
            self.txt_base_color.setText(base)
            self.txt_hl_color.setText(hl)

    def _on_reset_and_clear_cache(self):
        self.txt_url.clear()
        self.txt_video.clear()
        self.txt_rules.clear()
        count = clear_temp_cache()
        QMessageBox.information(self, "Cache Cleared", f"Form telah di-reset dan {count} file cache sementara berhasil dibersihkan.")

    def closeEvent(self, event):
        clear_temp_cache()
        super().closeEvent(event)

    def _on_browse_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Source Video", "", "Video Files (*.mp4 *.mkv *.mov *.avi)"
        )
        if file_path:
            self.txt_video.setText(file_path)

    def _on_start(self):
        if self.input_tabs.currentIndex() == 0:
            source = self.txt_url.text().strip()
            if not is_valid_video_url(source):
                QMessageBox.warning(self, "Invalid Source", "Enter a valid video URL (http:// or https://).")
                return
        else:
            source = self.txt_video.text().strip()
            if not source or not Path(source).exists():
                QMessageBox.warning(self, "Invalid Source", "Select a valid local video file first.")
                return

        target_count = self.spn_clip_count.value()
        preset = self.cmb_duration.currentText()
        if preset == "Custom":
            min_dur = float(self.spn_min_dur.value())
            max_dur = float(self.spn_max_dur.value())
            if max_dur <= min_dur:
                QMessageBox.warning(self, "Validation", "Max duration must be strictly greater than Min duration.")
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
        clip_mode = self.cmb_clip_mode.currentData() or "single"
        sub_base = self.txt_base_color.text().strip() or "#FFFFFF"
        sub_hl = self.txt_hl_color.text().strip() or "#FF2A2A"
        sub_preset = self.cmb_sub_preset.currentData() or "red_white"

        self.config.endpoint_url = endpoint
        self.config.api_key = key
        self.config.selected_model = model
        self.config.target_clip_count = target_count
        self.config.duration_preset = preset
        self.config.min_duration = min_dur
        self.config.max_duration = max_dur
        self.config.campaign_rules = rules
        self.config.clip_mode = clip_mode
        self.config.subtitle_base_color = sub_base
        self.config.subtitle_highlight_color = sub_hl
        self.config.subtitle_color_preset = sub_preset
        self.config.save()

        # Switch to Stage 1: Processing
        self.btn_start.setEnabled(False)
        self.btn_cancel.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_proc_pct.setText("0%")
        self.stage_stack.setCurrentIndex(1)
        self._reset_step_indicators()

        self.worker = PipelineWorker(
            self.orchestrator,
            source,
            target_clip_count=target_count,
            min_duration=min_dur,
            max_duration=max_dur,
            campaign_rules=rules,
            clip_mode=clip_mode,
            subtitle_base_color=sub_base,
            subtitle_highlight_color=sub_hl
        )
        self.worker.progress_changed.connect(self._on_worker_progress)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.failed.connect(self._on_worker_failed)
        self.worker.start()

    def _reset_step_indicators(self):
        for dot in self.step_widgets.values():
            dot.setText("○")
            dot.setStyleSheet("color: #8B949E; font-size: 14px; font-weight: bold;")

    def _on_cancel(self):
        if self.worker and self.worker.isRunning():
            self.lbl_stage_log.setText("Cancelling pipeline execution...")
            self.orchestrator.cancel()
            self.worker.wait(3000)
            self.btn_start.setEnabled(True)
            self.btn_cancel.setVisible(False)
            self.stage_stack.setCurrentIndex(0)

    def _on_worker_progress(self, status: str, pct: int, msg: str):
        self.progress_bar.setValue(pct)
        self.lbl_proc_pct.setText(f"{pct}%")
        self.lbl_stage_log.setText(f"[{status}] {msg}")

        # Update visual step tracker
        if pct < 20:
            self._set_active_step("STEP_AUDIO")
        elif pct < 50:
            self._set_done_step("STEP_AUDIO")
            self._set_active_step("STEP_WHISPER")
        elif pct < 65:
            self._set_done_step("STEP_WHISPER")
            self._set_active_step("STEP_LLM")
        elif pct < 80:
            self._set_done_step("STEP_LLM")
            self._set_active_step("STEP_REFRAME")
        else:
            self._set_done_step("STEP_REFRAME")
            self._set_active_step("STEP_RENDER")

    def _set_active_step(self, key: str):
        if key in self.step_widgets:
            self.step_widgets[key].setText("●")
            self.step_widgets[key].setStyleSheet("color: #386FA4; font-size: 14px; font-weight: bold;")

    def _set_done_step(self, key: str):
        if key in self.step_widgets:
            self.step_widgets[key].setText("✓")
            self.step_widgets[key].setStyleSheet("color: #10B981; font-size: 14px; font-weight: bold;")

    def _on_worker_finished(self, clips: List[ClipResult]):
        self.btn_start.setEnabled(True)
        self.btn_cancel.setVisible(False)
        self.progress_bar.setValue(100)
        self.lbl_proc_pct.setText("100%")

        for key in self.step_widgets:
            self._set_done_step(key)

        self.current_clips = clips
        self._populate_review_workspace()
        self.stage_stack.setCurrentIndex(2)

    def _on_worker_failed(self, error: str):
        self.btn_start.setEnabled(True)
        self.btn_cancel.setVisible(False)
        self.stage_stack.setCurrentIndex(0)

        cleaned_err = clean_error_message(error)
        QMessageBox.critical(self, "Pipeline Error", f"Pipeline execution failed:\n{cleaned_err}")

    def _populate_review_workspace(self):
        for c in self.card_widgets:
            c.deleteLater()
        self.card_widgets.clear()

        self.lbl_gallery_count.setText(f"CURATED CLIPS ({len(self.current_clips)})")

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
            mode_str = "Dynamic Split (Talking Head 9:16 + Screen Fit)"
        elif mode_val == "CROP_TRACKING":
            mode_str = "Full Face Crop 9:16"
        else:
            mode_str = "Blurred Background (Original Fit 16:9)"

        self.lbl_clip_info.setText(
            f"<b>{clip.title}</b> &nbsp; <span style='color: #386FA4; font-size: 11px; font-weight: 600;'>[{mode_str}]</span><br/>"
            f"<span style='color: #E6E9EE;'>Hook: \"{clip.hook}\"</span> &nbsp;•&nbsp; <span style='color: #8B949E;'>Score: <b>{clip.virality_score}</b> &nbsp;•&nbsp; Duration: <b>{dur:.1f}s</b></span><br/>"
            f"<span style='color: #8B949E;'>{clip.reasoning}</span>"
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

    def _toggle_mute(self):
        is_muted = self.audio_output.isMuted()
        if is_muted:
            self.audio_output.setMuted(False)
            val = self.slider_volume.value()
            if val == 0:
                self.slider_volume.setValue(40)
            self.btn_mute.setText("🔊")
        else:
            self.audio_output.setMuted(True)
            self.btn_mute.setText("🔇")

    def _on_volume_changed(self, val: int):
        vol_float = max(0.0, min(1.0, val / 100.0))
        self.audio_output.setVolume(vol_float)
        if val > 0 and self.audio_output.isMuted():
            self.audio_output.setMuted(False)

        if val == 0 or self.audio_output.isMuted():
            self.btn_mute.setText("🔇")
        else:
            self.btn_mute.setText("🔊")

        self.slider_volume.setToolTip(f"Volume: {val}%")
        self.settings.setValue("player_volume", val)

    def _on_save_selected_clip(self):
        if not self.selected_clip or not os.path.exists(self.selected_clip.staging_path):
            QMessageBox.warning(self, "Export", "No clip selected to export.")
            return

        default_name = f"clipmax_{self.selected_clip.clip_id}_{int(self.selected_clip.start_time)}.mp4"
        result = QFileDialog.getSaveFileName(
            self, "Export 9:16 Clip", default_name, "Video Files (*.mp4)"
        )
        if isinstance(result, (tuple, list)):
            dest_path = result[0]
        else:
            dest_path = result

        if dest_path and isinstance(dest_path, str) and dest_path.strip():
            try:
                shutil.copy2(self.selected_clip.staging_path, dest_path.strip())
                QMessageBox.information(self, "Export Successful", f"Clip saved to:\n{dest_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Failed to save file: {str(e)}")

    def _on_save_all_clips(self):
        if not self.current_clips:
            QMessageBox.warning(self, "Export All", "No clips available to export.")
            return

        result = QFileDialog.getExistingDirectory(self, "Select Destination Folder for All Clips")
        if isinstance(result, (tuple, list)):
            dest_dir = result[0]
        else:
            dest_dir = result

        if dest_dir and isinstance(dest_dir, str) and dest_dir.strip():
            dest_dir_path = Path(dest_dir.strip())
            copied_count = 0
            for clip in self.current_clips:
                if os.path.exists(clip.staging_path):
                    target = dest_dir_path / f"clipmax_{clip.clip_id}_{int(clip.start_time)}.mp4"
                    shutil.copy2(clip.staging_path, target)
                    copied_count += 1
            QMessageBox.information(
                self, "Export Complete", f"Successfully exported {copied_count} clip(s) to:\n{dest_dir}"
            )

    def _on_back_to_standby(self):
        self.player.stop()
        self.stage_stack.setCurrentIndex(0)
