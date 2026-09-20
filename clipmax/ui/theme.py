DARK_THEME_QSS = """
QMainWindow {
    background-color: #1E2024;
    border: 1px solid #3B3F47;
    border-radius: 10px;
}

QWidget#CentralWidget {
    background-color: #1E2024;
    border-radius: 10px;
}

/* Base Typography */
QWidget {
    font-family: 'Segoe UI', -apple-system, sans-serif;
    color: #E4E7EB;
    font-size: 13px;
}

QLabel {
    color: #E4E7EB;
    font-size: 13px;
}

QLabel.Title {
    font-size: 15px;
    font-weight: 600;
    color: #E4E7EB;
    letter-spacing: 0.2px;
}

QLabel.SectionHeader {
    font-size: 13px;
    font-weight: 600;
    color: #E4E7EB;
}

QLabel.Sub {
    font-size: 12px;
    color: #9CA3AF;
}

/* Cards & Containers (Soft Muted Slate Surface) */
QFrame.Card {
    background-color: #272A30;
    border: 1px solid #3B3F47;
    border-radius: 8px;
    padding: 12px;
}

/* Clip Gallery Card */
QFrame.ClipCard {
    background-color: #272A30;
    border: 1px solid #3B3F47;
    border-radius: 8px;
    padding: 12px;
}

QFrame.ClipCard:hover {
    background-color: #32363E;
    border: 1px solid #4A6FA5;
}

QFrame.ClipCardActive {
    background-color: #32363E;
    border: 1px solid #4A6FA5;
    border-radius: 8px;
    padding: 12px;
}

/* Minimalist Pill Badges (Utilitarian) */
QLabel.BadgePill {
    background-color: #1E2024;
    color: #E4E7EB;
    font-size: 11px;
    font-weight: 600;
    border-radius: 9px;
    padding: 2px 8px;
    border: 1px solid #3B3F47;
}

QLabel.BadgeAccent {
    background-color: #1E2024;
    color: #4A6FA5;
    font-size: 11px;
    font-weight: 600;
    border-radius: 9px;
    padding: 2px 8px;
    border: 1px solid #4A6FA5;
}

/* Inputs & Form Controls */
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {
    background-color: #181A1D;
    border: 1px solid #363A42;
    border-radius: 6px;
    color: #E4E7EB;
    padding: 8px 10px;
    font-size: 13px;
    selection-background-color: #386FA4;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {
    border: 1px solid #4A6FA5;
    background-color: #181A1D;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid #363A42;
}

QComboBox QAbstractItemView {
    background-color: #181A1D;
    border: 1px solid #3B3F47;
    color: #E4E7EB;
    selection-background-color: #272A30;
}

QSpinBox::up-button, QSpinBox::down-button {
    background-color: #272A30;
    border: 1px solid #363A42;
    border-radius: 3px;
    width: 18px;
    margin: 1px;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #32363E;
    border-color: #4A6FA5;
}

/* Flat Slate Buttons */
QPushButton {
    background-color: #386FA4;
    color: #E4E7EB;
    font-weight: 600;
    border: 1px solid #437EB7;
    border-radius: 6px;
    padding: 9px 18px;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #437EB7;
    border-color: #4A6FA5;
}

QPushButton:pressed {
    background-color: #2E5B88;
}

QPushButton.Secondary {
    background-color: #272A30;
    color: #E4E7EB;
    border: 1px solid #3B3F47;
}

QPushButton.Secondary:hover {
    background-color: #32363E;
    border-color: #4A6FA5;
}

QPushButton.Secondary:pressed {
    background-color: #1E2024;
}

QPushButton.Success {
    background-color: #2B7A58;
    color: #E4E7EB;
    border: 1px solid #348F67;
}

QPushButton.Success:hover {
    background-color: #348F67;
    border-color: #3DA879;
}

QPushButton.Success:pressed {
    background-color: #226146;
}

QPushButton.Danger {
    background-color: #8B4444;
    color: #E4E7EB;
    border: 1px solid #A35050;
}

QPushButton.Danger:hover {
    background-color: #A35050;
    border-color: #B55A5A;
}

QPushButton.Danger:pressed {
    background-color: #733737;
}

QPushButton:disabled {
    background-color: #272A30;
    color: #6B7280;
    border: 1px solid #363A42;
}

/* Progress Bar */
QProgressBar {
    background-color: #181A1D;
    border: 1px solid #363A42;
    border-radius: 6px;
    text-align: center;
    color: #E4E7EB;
    font-weight: 600;
    font-size: 11px;
    height: 16px;
}

QProgressBar::chunk {
    background-color: #386FA4;
    border-radius: 5px;
}

/* Segmented Control / Flat Tabs */
QTabWidget::pane {
    border: 1px solid #3B3F47;
    background: #272A30;
    border-radius: 6px;
    padding: 10px;
    top: -1px;
}

QTabBar::tab {
    background: transparent;
    color: #9CA3AF;
    padding: 8px 18px;
    border: 1px solid transparent;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 4px;
    font-size: 12px;
    font-weight: 600;
}

QTabBar::tab:selected {
    background: #272A30;
    color: #E4E7EB;
    border: 1px solid #3B3F47;
    border-bottom: 1px solid #272A30;
}

QTabBar::tab:hover:!selected {
    color: #E4E7EB;
    background: #1E2024;
}

/* Minimalist Flat Video Slider */
QSlider::groove:horizontal {
    border: none;
    height: 4px;
    background: #3B3F47;
    border-radius: 2px;
}

QSlider::sub-page:horizontal {
    background: #4A6FA5;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #E4E7EB;
    border: none;
    width: 12px;
    margin-top: -4px;
    margin-bottom: -4px;
    border-radius: 6px;
}

QSlider::handle:horizontal:hover {
    background: #FFFFFF;
}

/* ScrollBars */
QScrollArea {
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    background: #1E2024;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #363A42;
    min-height: 24px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #4A6FA5;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""
