DARK_THEME_QSS = """
QMainWindow {
    background-color: #181A1E;
    border: 1px solid #2F333B;
    border-radius: 10px;
}

QWidget#CentralWidget {
    background-color: #181A1E;
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
    font-size: 16px;
    font-weight: 700;
    color: #E4E7EB;
    letter-spacing: 0.2px;
}

QLabel.SectionHeader {
    font-size: 12px;
    font-weight: 700;
    color: #9CA3AF;
    letter-spacing: 0.4px;
}

QLabel.FormLabel {
    font-size: 12px;
    font-weight: 600;
    color: #9CA3AF;
}

QLabel.Sub {
    font-size: 12px;
    color: #9CA3AF;
}

/* Card Containers */
QFrame.Card {
    background-color: #21242A;
    border: 1px solid #2F333B;
    border-radius: 10px;
    padding: 14px;
}

/* Clip Gallery Card */
QFrame.ClipCard {
    background-color: #21242A;
    border: 1px solid #2F333B;
    border-radius: 8px;
    padding: 12px;
}

QFrame.ClipCard:hover {
    background-color: #2A2E36;
    border: 1px solid #3563A9;
}

QFrame.ClipCardActive {
    background-color: #2A2E36;
    border: 1px solid #3563A9;
    border-radius: 8px;
    padding: 12px;
}

/* Minimalist Pill Badges */
QLabel.BadgePill {
    background-color: #181A1E;
    color: #E4E7EB;
    font-size: 11px;
    font-weight: 600;
    border-radius: 10px;
    padding: 3px 8px;
    border: 1px solid #2F333B;
}

QLabel.BadgeHardware {
    background-color: #181A1E;
    color: #9CA3AF;
    font-size: 11px;
    font-weight: 600;
    border-radius: 12px;
    padding: 4px 12px;
    border: 1px solid #2F333B;
}

/* Inputs & Form Controls (Fixed Truncation, 40px min-height, centered) */
QLineEdit, QComboBox, QSpinBox {
    background-color: #141619;
    border: 1px solid #2F333B;
    border-radius: 6px;
    color: #E4E7EB;
    padding: 8px 12px;
    min-height: 40px;
    font-size: 13px;
    selection-background-color: #3563A9;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {
    border: 1px solid #3563A9;
    background-color: #141619;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border-left: 1px solid #2F333B;
}

QComboBox QAbstractItemView {
    background-color: #141619;
    border: 1px solid #2F333B;
    color: #E4E7EB;
    selection-background-color: #21242A;
    padding: 4px;
}

QSpinBox::up-button, QSpinBox::down-button {
    background-color: #21242A;
    border: 1px solid #2F333B;
    border-radius: 3px;
    width: 22px;
    margin: 1px;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #2A2E36;
    border-color: #3563A9;
}

QPlainTextEdit {
    background-color: #141619;
    border: 1px solid #2F333B;
    border-radius: 6px;
    color: #E4E7EB;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: #3563A9;
}

/* Buttons */
QPushButton {
    background-color: #21242A;
    color: #E4E7EB;
    font-weight: 600;
    border: 1px solid #2F333B;
    border-radius: 6px;
    padding: 8px 16px;
    min-height: 40px;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #2A2E36;
    border-color: #3563A9;
}

QPushButton:pressed {
    background-color: #181A1E;
}

QPushButton.PrimaryAction {
    background-color: #3563A9;
    color: #FFFFFF;
    font-size: 14px;
    font-weight: bold;
    border: 1px solid #4175C7;
    border-radius: 8px;
    min-height: 44px;
    padding: 10px 24px;
}

QPushButton.PrimaryAction:hover {
    background-color: #4175C7;
    border-color: #5289DE;
}

QPushButton.PrimaryAction:pressed {
    background-color: #2A4F87;
}

QPushButton.Secondary {
    background-color: #21242A;
    color: #E4E7EB;
    border: 1px solid #2F333B;
}

QPushButton.Secondary:hover {
    background-color: #2A2E36;
    border-color: #3563A9;
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
    border-radius: 8px;
}

QPushButton.Danger:hover {
    background-color: #A35050;
}

QPushButton:disabled {
    background-color: #1E2024;
    color: #6B7280;
    border: 1px solid #2F333B;
}

/* Progress Bar */
QProgressBar {
    background-color: #141619;
    border: 1px solid #2F333B;
    border-radius: 6px;
    text-align: center;
    color: #E4E7EB;
    font-weight: 600;
    font-size: 11px;
    min-height: 18px;
}

QProgressBar::chunk {
    background-color: #3563A9;
    border-radius: 5px;
}

/* Segmented Control / Flat Tabs */
QTabWidget::pane {
    border: 1px solid #2F333B;
    background: #21242A;
    border-radius: 8px;
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
    background: #21242A;
    color: #E4E7EB;
    border: 1px solid #2F333B;
    border-bottom: 1px solid #21242A;
}

QTabBar::tab:hover:!selected {
    color: #E4E7EB;
    background: #181A1E;
}

/* Minimalist Flat Video Slider */
QSlider::groove:horizontal {
    border: none;
    height: 4px;
    background: #2F333B;
    border-radius: 2px;
}

QSlider::sub-page:horizontal {
    background: #3563A9;
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
    background: #181A1E;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #2F333B;
    min-height: 24px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #3563A9;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""
