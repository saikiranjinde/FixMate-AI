"""Small reusable UI animations for FixMate-AI."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QWidget


def fade_in(widget: QWidget, duration: int = 260) -> QPropertyAnimation:
    animation = QPropertyAnimation(widget, b"windowOpacity", widget)
    animation.setDuration(duration)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    widget._fixmate_fade_animation = animation
    return animation
