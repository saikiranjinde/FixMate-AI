"""FixMate-AI light/dark theme definitions."""

from __future__ import annotations

from storage.database import get_setting, set_setting

LIGHT_QSS = r"""
QWidget {
    background: #f4f6fa;
    color: #182235;
    font-family: "Segoe UI";
    font-size: 14px;
}
QFrame#sidebar {
    background: #111827;
    border: none;
}
QLabel#brand {
    color: #ffffff;
    font-size: 20px;
    font-weight: 700;
}
QLabel#pageTitle {
    font-size: 30px;
    font-weight: 700;
}
QLabel#subtitle, QLabel#muted {
    color: #60708a;
}
QFrame#card {
    background: #ffffff;
    border: 1px solid #dbe2ec;
    border-radius: 16px;
}
QPushButton {
    border: 1px solid #d5deea;
    border-radius: 10px;
    padding: 9px 14px;
    background: #ffffff;
}
QPushButton:hover {
    background: #edf3ff;
}
QPushButton#primaryButton {
    background: #2f6df6;
    color: white;
    border: none;
    font-weight: 600;
}
QProgressBar {
    background: #e8edf4;
    border: none;
    border-radius: 6px;
    min-height: 12px;
    max-height: 12px;
}
QProgressBar::chunk {
    background: #2f6df6;
    border-radius: 6px;
}
QListWidget {
    background: transparent;
    border: none;
}
QListWidget::item {
    padding: 10px;
    border-radius: 8px;
}
QListWidget::item:selected {
    background: #263348;
    color: white;
}
"""

DARK_QSS = r"""
QWidget {
    background: #0b1220;
    color: #edf2fa;
    font-family: "Segoe UI";
    font-size: 14px;
}
QFrame#sidebar {
    background: #070d18;
    border: none;
}
QLabel#brand {
    color: #ffffff;
    font-size: 20px;
    font-weight: 700;
}
QLabel#pageTitle {
    font-size: 30px;
    font-weight: 700;
}
QLabel#subtitle, QLabel#muted {
    color: #94a5bf;
}
QFrame#card {
    background: #121b2a;
    border: 1px solid #243246;
    border-radius: 16px;
}
QPushButton {
    border: 1px solid #2a3950;
    border-radius: 10px;
    padding: 9px 14px;
    background: #121b2a;
    color: #edf2fa;
}
QPushButton:hover {
    background: #1b2940;
}
QPushButton#primaryButton {
    background: #3b78ff;
    color: white;
    border: none;
    font-weight: 600;
}
QProgressBar {
    background: #1e2a3c;
    border: none;
    border-radius: 6px;
    min-height: 12px;
    max-height: 12px;
}
QProgressBar::chunk {
    background: #4f86ff;
    border-radius: 6px;
}
QListWidget {
    background: transparent;
    border: none;
}
QListWidget::item {
    padding: 10px;
    border-radius: 8px;
}
QListWidget::item:selected {
    background: #263652;
    color: white;
}
"""


def load_theme(default: str = "dark") -> str:
    return get_setting("theme", default) or default


def save_theme(theme: str) -> None:
    set_setting("theme", theme)
