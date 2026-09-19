DARK_THEME_QSS = """
QMainWindow {
    background-color: #0b0f19;
    border: 1px solid #1e293b;
    border-radius: 12px;
}

QWidget#CentralWidget {
    background-color: #0b0f19;
    border-radius: 12px;
}

/* Floating Cards with subtle ambient glow */
QFrame.Card {
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 10px;
    padding: 14px;
}

/* Clip Gallery Card */
QFrame.ClipCard {
    background-color: #131d31;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 10px;
}

QFrame.ClipCard:hover {
    border: 1px solid #3b82f6;
    background-color: #1a2744;
}

QFrame.ClipCardActive {
    background-color: #1e2d4d;
    border: 1px solid #60a5fa;
    border-radius: 8px;
    padding: 10px;
}

QLabel {
    color: #f3f4f6;
    font-family: 'Segoe UI', -apple-system, sans-serif;
    font-size: 13px;
}

QLabel.Title {
    font-size: 18px;
    font-weight: 700;
    color: #60a5fa;
    letter-spacing: 0.5px;
}

QLabel.Sub {
    font-size: 12px;
    color: #9ca3af;
}

QLabel.BadgeHigh {
    background-color: #064e3b;
    color: #34d399;
    font-size: 11px;
    font-weight: bold;
    border-radius: 4px;
    padding: 2px 6px;
    border: 1px solid #059669;
}

QLabel.BadgeMid {
    background-color: #78350f;
    color: #fbbf24;
    font-size: 11px;
    font-weight: bold;
    border-radius: 4px;
    padding: 2px 6px;
    border: 1px solid #d97706;
}

QLineEdit, QComboBox {
    background-color: #1a2234;
    border: 1px solid #2d3748;
    border-radius: 7px;
    color: #f9fafb;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: #3b82f6;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #3b82f6;
    background-color: #1e293b;
}

QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #4f46e5);
    color: #ffffff;
    font-weight: 600;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 7px;
    padding: 9px 18px;
    font-size: 13px;
}

QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1d4ed8, stop:1 #4338ca);
}

QPushButton:pressed {
    background: #1e40af;
}

QPushButton.Secondary {
    background: #1f2937;
    color: #e5e7eb;
    border: 1px solid #374151;
}

QPushButton.Secondary:hover {
    background: #374151;
    border: 1px solid #4b5563;
}

QPushButton.Success {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
    color: #ffffff;
}

QPushButton.Success:hover {
    background: #047857;
}

QPushButton.Danger {
    background: #dc2626;
    border: 1px solid rgba(255, 255, 255, 0.1);
}

QPushButton.Danger:hover {
    background: #b91c1c;
}

QPushButton:disabled {
    background: #1f2937;
    color: #6b7280;
    border: 1px solid #2d3748;
}

QProgressBar {
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 7px;
    text-align: center;
    color: #f9fafb;
    font-weight: 600;
    font-size: 11px;
    height: 18px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #8b5cf6);
    border-radius: 6px;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #1f2937;
    background: #111827;
    border-radius: 8px;
    padding: 8px;
}

QTabBar::tab {
    background: #1a2234;
    color: #9ca3af;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 4px;
    font-size: 12px;
    font-weight: 600;
}

QTabBar::tab:selected {
    background: #2563eb;
    color: #ffffff;
}

/* Sliders */
QSlider::groove:horizontal {
    border: 1px solid #2d3748;
    height: 6px;
    background: #1f2937;
    margin: 2px 0;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #3b82f6;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #ffffff;
    border: 1px solid #3b82f6;
    width: 14px;
    margin-top: -4px;
    margin-bottom: -4px;
    border-radius: 7px;
}

/* ScrollBars */
QScrollArea {
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    background: #0b0f19;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #2d3748;
    min-height: 24px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #4b5563;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""
