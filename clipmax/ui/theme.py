DARK_THEME_QSS = """
/* ClipMax Studio - Professional Desktop Multimedia Theme */

QMainWindow {
    background-color: #14161A;
    border: 1px solid #23272F;
    border-radius: 8px;
}

QWidget#CentralWidget {
    background-color: #14161A;
    border-radius: 8px;
}

/* Base Typography */
QWidget {
    font-family: 'Segoe UI', -apple-system, sans-serif;
    color: #E6E9EE;
    font-size: 13px;
}

QLabel {
    color: #E6E9EE;
    font-size: 13px;
}

QLabel.AppBrand {
    font-size: 14px;
    font-weight: 700;
    color: #E6E9EE;
    letter-spacing: 0.3px;
}

QLabel.SectionHeader {
    font-size: 11px;
    font-weight: 700;
    color: #8B949E;
    letter-spacing: 0.8px;
}

QLabel.FormLabel {
    font-size: 12px;
    font-weight: 600;
    color: #8B949E;
}

QLabel.Muted {
    font-size: 12px;
    color: #8B949E;
}

/* Top App Header (42px) */
QFrame#AppHeader {
    background-color: #14161A;
    border-bottom: 1px solid #23272F;
    min-height: 42px;
    max-height: 42px;
}

/* Sidebar Container (380px fixed) */
QFrame#Sidebar {
    background-color: #1B1E24;
    border-right: 1px solid #282C35;
}

/* Stage / Canvas Container */
QFrame#StageCanvas {
    background-color: #14161A;
}

/* Hairline Dividers */
QFrame.Divider {
    background-color: #282C35;
    max-height: 1px;
    min-height: 1px;
    border: none;
}

/* Monochrome Hardware Status Pill */
QLabel#HardwarePill {
    background-color: #1B1E24;
    border: 1px solid #282C35;
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
    color: #E6E9EE;
}

/* Inputs & Form Controls (#121417 surface) */
QLineEdit, QComboBox, QSpinBox {
    background-color: #121417;
    border: 1px solid #282C35;
    border-radius: 6px;
    color: #E6E9EE;
    padding: 8px 10px;
    min-height: 38px;
    font-size: 13px;
    selection-background-color: #386FA4;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {
    border: 1px solid #386FA4;
    background-color: #121417;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid #282C35;
}

QComboBox QAbstractItemView {
    background-color: #121417;
    border: 1px solid #282C35;
    color: #E6E9EE;
    selection-background-color: #1B1E24;
    padding: 4px;
}

QSpinBox::up-button, QSpinBox::down-button {
    background-color: #1B1E24;
    border: 1px solid #282C35;
    border-radius: 3px;
    width: 20px;
    margin: 1px;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #282C35;
    border-color: #386FA4;
}

QPlainTextEdit {
    background-color: #121417;
    border: 1px solid #282C35;
    border-radius: 6px;
    color: #E6E9EE;
    padding: 8px 10px;
    font-size: 12px;
    selection-background-color: #386FA4;
}

/* PushButtons */
QPushButton {
    background-color: #21242A;
    color: #E6E9EE;
    font-weight: 600;
    border: 1px solid #282C35;
    border-radius: 6px;
    padding: 8px 14px;
    min-height: 36px;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #282C35;
    border-color: #386FA4;
}

QPushButton:pressed {
    background-color: #121417;
}

/* Primary Action Button (Generate Clips) */
QPushButton#BtnGenerate {
    background-color: #386FA4;
    color: #FFFFFF;
    font-size: 13px;
    font-weight: 700;
    border: 1px solid #437EB7;
    border-radius: 6px;
    min-height: 44px;
    letter-spacing: 0.3px;
}

QPushButton#BtnGenerate:hover {
    background-color: #437EB7;
    border-color: #4F8DC8;
}

QPushButton#BtnGenerate:pressed {
    background-color: #2A547D;
}

QPushButton.Secondary {
    background-color: #121417;
    color: #E6E9EE;
    border: 1px solid #282C35;
}

QPushButton.Secondary:hover {
    background-color: #1B1E24;
    border-color: #386FA4;
}

QPushButton.Success {
    background-color: #2B7A58;
    color: #FFFFFF;
    border: 1px solid #348F67;
}

QPushButton.Success:hover {
    background-color: #348F67;
}

QPushButton.Danger {
    background-color: #8B4444;
    color: #FFFFFF;
    border: 1px solid #A35050;
    min-height: 44px;
    border-radius: 6px;
}

QPushButton.Danger:hover {
    background-color: #A35050;
}

QPushButton:disabled {
    background-color: #1B1E24;
    color: #555D68;
    border: 1px solid #23272F;
}

/* Progress Bar */
QProgressBar {
    background-color: #121417;
    border: 1px solid #282C35;
    border-radius: 4px;
    text-align: center;
    color: #E6E9EE;
    font-weight: 600;
    font-size: 11px;
    min-height: 12px;
    max-height: 12px;
}

QProgressBar::chunk {
    background-color: #386FA4;
    border-radius: 3px;
}

/* Segmented Control / Flat Tabs */
QTabWidget::pane {
    border: 1px solid #282C35;
    background: #1B1E24;
    border-radius: 6px;
    padding: 8px;
    top: -1px;
}

QTabBar::tab {
    background: transparent;
    color: #8B949E;
    padding: 6px 14px;
    border: 1px solid transparent;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    font-size: 12px;
    font-weight: 600;
}

QTabBar::tab:selected {
    background: #1B1E24;
    color: #E6E9EE;
    border: 1px solid #282C35;
    border-bottom: 1px solid #1B1E24;
}

QTabBar::tab:hover:!selected {
    color: #E6E9EE;
    background: #14161A;
}

/* Flat Studio Slider */
QSlider::groove:horizontal {
    border: none;
    height: 4px;
    background: #282C35;
    border-radius: 2px;
}

QSlider::sub-page:horizontal {
    background: #386FA4;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #E6E9EE;
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
    background: #14161A;
    width: 6px;
    margin: 0px;
    border-radius: 3px;
}

QScrollBar::handle:vertical {
    background: #282C35;
    min-height: 20px;
    border-radius: 3px;
}

QScrollBar::handle:vertical:hover {
    background: #386FA4;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Strip Card for Clips */
QFrame.ClipCard {
    background-color: #1B1E24;
    border: 1px solid #282C35;
    border-radius: 6px;
    padding: 8px;
}

QFrame.ClipCard:hover {
    background-color: #21242A;
    border: 1px solid #386FA4;
}

QFrame.ClipCardActive {
    background-color: #21242A;
    border: 1px solid #386FA4;
    border-radius: 6px;
    padding: 8px;
}

/* Badge Pills */
QLabel.BadgePill {
    background-color: #121417;
    color: #E6E9EE;
    font-size: 11px;
    font-weight: 600;
    border-radius: 4px;
    padding: 2px 6px;
    border: 1px solid #282C35;
}
"""
