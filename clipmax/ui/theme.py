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

/* Floating Card with subtle glow */
QFrame.Card {
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 10px;
    padding: 14px;
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
"""
