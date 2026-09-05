from __future__ import annotations

import math
from PySide6.QtCore import QElapsedTimer, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


class ScanVisual(QWidget):
    """Small vector-based scan animation with a distinct visual per phase."""

    MODES = {"system", "cpu", "gpu", "memory", "storage", "battery", "network", "windows", "completed", "idle"}

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.mode = "idle"
        self.running = False
        self.frame = 0
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self._tick)
        self.elapsed = QElapsedTimer()
        self.setMinimumHeight(150)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().verticalPolicy())

    def set_mode(self, mode: str, running: bool = True) -> None:
        mode = mode if mode in self.MODES else "system"
        changed = mode != self.mode or running != self.running
        self.mode = mode
        self.running = running and mode != "completed"
        if self.running and not self.timer.isActive():
            self.elapsed.restart()
            self.timer.start()
        elif not self.running:
            self.timer.stop()
        if changed:
            self.frame = 0
            self.update()

    def _tick(self) -> None:
        self.frame += 1
        self.update()

    def _palette(self):
        return QColor("#24a9ff"), QColor("#77d7ff"), QColor("#0b2036")

    def paintEvent(self, event) -> None:
        del event
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = QRectF(self.rect()).adjusted(4, 4, -4, -4)
            cx, cy = rect.center().x(), rect.center().y()
            pulse = 0.5 + 0.5 * math.sin(self.frame * 0.12)
            a, b, bg = self._palette()

            # Ambient rings
            for i in range(3):
                r = 30 + i * 20 + pulse * 3
                alpha = 85 - i * 20
                pen = QPen(QColor(a.red(), a.green(), a.blue(), alpha), 1.3)
                p.setPen(pen)
                p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))

            if self.mode == "completed":
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor("#2ac769"))
                p.drawEllipse(QRectF(cx - 34, cy - 34, 68, 68))
                p.setPen(QPen(QColor("white"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                p.drawLine(cx - 16, cy + 1, cx - 4, cy + 14)
                p.drawLine(cx - 4, cy + 14, cx + 20, cy - 14)
                self._draw_label(p, "Completed", cx, cy + 76, QColor("#2ac769"))
            elif self.mode == "storage":
                self._draw_storage(p, cx, cy, a, b)
            elif self.mode == "network":
                self._draw_network(p, cx, cy, a, b)
            elif self.mode == "cpu":
                self._draw_cpu(p, cx, cy, a, b)
            elif self.mode == "gpu":
                self._draw_gpu(p, cx, cy, a, b)
            elif self.mode == "memory":
                self._draw_memory(p, cx, cy, a, b)
            elif self.mode == "battery":
                self._draw_battery(p, cx, cy, a, b)
            elif self.mode == "windows":
                self._draw_windows(p, cx, cy, a, b)
            else:
                self._draw_system(p, cx, cy, a, b)
        finally:
            p.end()

    def _draw_core(self, p: QPainter, cx: float, cy: float, a: QColor, label: str) -> None:
        p.setPen(QPen(a, 2))
        p.setBrush(QColor(8, 22, 38, 210))
        p.drawRoundedRect(QRectF(cx - 34, cy - 34, 68, 68), 12, 12)
        f = QFont("Segoe UI", 15, QFont.Weight.Bold)
        p.setFont(f)
        p.setPen(QColor("#e6f4ff"))
        p.drawText(QRectF(cx - 32, cy - 12, 64, 28), Qt.AlignmentFlag.AlignCenter, label)

    def _draw_cpu(self, p, cx, cy, a, b):
        self._draw_core(p, cx, cy, a, "CPU")
        for i in range(8):
            ang = i * math.pi / 4
            x = cx + math.cos(ang) * 48
            y = cy + math.sin(ang) * 48
            p.setPen(QPen(b, 2))
            p.drawLine(cx + math.cos(ang) * 37, cy + math.sin(ang) * 37, x, y)

    def _draw_gpu(self, p, cx, cy, a, b):
        p.setPen(QPen(a, 2))
        p.setBrush(QColor(8, 22, 38, 210))
        p.drawRoundedRect(QRectF(cx - 46, cy - 28, 92, 56), 10, 10)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(cx - 30, cy - 18, 36, 36))
        p.drawEllipse(QRectF(cx + 2, cy - 18, 36, 36))
        p.setPen(QPen(b, 2))
        p.drawLine(cx - 46, cy, cx - 54, cy)

    def _draw_memory(self, p, cx, cy, a, b):
        p.setPen(QPen(a, 2))
        p.setBrush(QColor(8, 22, 38, 210))
        p.drawRoundedRect(QRectF(cx - 48, cy - 24, 96, 48), 8, 8)
        for i in range(6):
            x = cx - 35 + i * 14
            p.drawRect(QRectF(x, cy - 14, 9, 28))
        sweep = (self.frame % 80) / 80 * 70 - 35
        p.setPen(QPen(b, 3))
        p.drawLine(cx + sweep - 12, cy - 31, cx + sweep + 12, cy - 31)

    def _draw_storage(self, p, cx, cy, a, b):
        p.setPen(QPen(a, 2))
        p.setBrush(QColor(8, 22, 38, 210))
        p.drawRoundedRect(QRectF(cx - 42, cy - 42, 84, 84), 12, 12)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(cx - 25, cy - 25, 50, 50))
        ang = (self.frame * 7) % 360
        p.save()
        p.translate(cx, cy)
        p.rotate(ang)
        p.setPen(QPen(b, 3))
        p.drawLine(0, 0, 0, -22)
        p.drawLine(0, -22, 7, -14)
        p.restore()

    def _draw_network(self, p, cx, cy, a, b):
        nodes = [(cx, cy - 34), (cx - 40, cy + 18), (cx + 40, cy + 18), (cx, cy + 44)]
        p.setPen(QPen(QColor(a.red(), a.green(), a.blue(), 150), 2))
        for x, y in nodes[1:]:
            p.drawLine(cx, cy - 34, x, y)
        p.drawLine(nodes[1][0], nodes[1][1], nodes[3][0], nodes[3][1])
        p.drawLine(nodes[2][0], nodes[2][1], nodes[3][0], nodes[3][1])
        for idx, (x, y) in enumerate(nodes):
            pulse = 6 + ((self.frame + idx * 12) % 20) / 5
            p.setPen(QPen(b, 2))
            p.setBrush(QColor(8, 22, 38, 235))
            p.drawEllipse(QRectF(x - pulse, y - pulse, pulse * 2, pulse * 2))

    def _draw_windows(self, p, cx, cy, a, b):
        p.setPen(QPen(a, 2))
        tilt = math.sin(self.frame * 0.07) * 4
        p.save(); p.translate(cx, cy); p.rotate(tilt)
        p.drawRect(QRectF(-42, -42, 38, 38))
        p.drawRect(QRectF(4, -42, 38, 38))
        p.drawRect(QRectF(-42, 4, 38, 38))
        p.drawRect(QRectF(4, 4, 38, 38))
        p.restore()
        p.setPen(QPen(b, 2))
        p.drawArc(QRectF(cx - 55, cy - 55, 110, 110), self.frame * 80, 120 * 16)

    def _draw_battery(self, p, cx, cy, a, b):
        p.setPen(QPen(a, 2)); p.setBrush(QColor(8, 22, 38, 210))
        p.drawRoundedRect(QRectF(cx - 48, cy - 26, 88, 52), 8, 8)
        p.drawRect(QRectF(cx + 40, cy - 11, 9, 22))
        level = 0.35 + 0.5 * (0.5 + 0.5 * math.sin(self.frame * 0.06))
        p.setBrush(b)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(cx - 42, cy - 20, 76 * level, 40), 6, 6)
        p.setPen(QPen(QColor("#dff7ff"), 2))
        p.drawLine(cx - 6, cy - 13, cx + 2, cy - 2)
        p.drawLine(cx + 2, cy - 2, cx - 4, cy - 2)
        p.drawLine(cx - 4, cy - 2, cx + 6, cy + 13)

    def _draw_system(self, p, cx, cy, a, b):
        p.setPen(QPen(a, 2)); p.setBrush(QColor(8, 22, 38, 210))
        p.drawEllipse(QRectF(cx - 34, cy - 34, 68, 68))
        angle = (self.frame * 6) % 360
        p.save(); p.translate(cx, cy); p.rotate(angle)
        p.setPen(QPen(b, 3)); p.drawLine(0, -25, 0, -13); p.drawLine(0, 13, 0, 25)
        p.restore()
        p.setPen(QPen(a, 2)); p.drawEllipse(QRectF(cx - 10, cy - 10, 20, 20))

    def _draw_label(self, p, text, x, y, color):
        p.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        p.setPen(color)
        p.drawText(QRectF(x - 80, y - 12, 160, 24), Qt.AlignmentFlag.AlignCenter, text)
