"""FixMate-AI desktop dashboard.

Features:
- Real background diagnostic scan through ScanManager
- Live phase-based progress updates
- Dynamic ETA based on actual scan progress
- Click-to-expand System/CPU/Memory/Storage cards
- Smooth expand/collapse animation
- Drop shadows on dashboard cards
- Light/Dark theme support
"""

from __future__ import annotations

import json
import platform
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QParallelAnimationGroup,
    QPropertyAnimation,
    Qt,
    QTimer,
    QUrl,
    Signal,
    QThread,
)
from PySide6.QtGui import QColor, QFont, QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QLineEdit,
    QDialog,
    QFormLayout,
    QDialogButtonBox,
    QComboBox,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QScrollArea,
    QTextBrowser,
    QPushButton,
    QToolButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.scan_manager import ScanManager
from system_info import get_system_info
from storage.history import save_diagnosis, update_ai_analysis, APP_DATA_DIR, REPORTS_DIR
from ui.history_dialog import HistoryDialog
from ai.diagnostic_analyzer import DiagnosticAnalyzer
from ai.openrouter_client import (
    OpenRouterClient,
    OpenRouterConfig,
    OpenRouterConfigError,
    OpenRouterCancelled,
    DEFAULT_MODEL,
    get_saved_api_key,
    get_saved_model,
    save_api_key,
    save_model,
    delete_saved_api_key,
)
from ui.animations import fade_in
from ui.theme import DARK_QSS, LIGHT_QSS, load_theme, save_theme


class AIWorker(QThread):
    finished = Signal(str)
    chunk = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, mode: str, result: dict, conversation=None, message: str = "", parent=None):
        super().__init__(parent)
        from threading import Event
        self.mode = mode
        self.result = result
        self.conversation = conversation or []
        self.message = message
        self.cancel_event = Event()
        self._response = None

    def cancel(self) -> None:
        self.cancel_event.set()
        response = self._response
        if response is not None:
            try:
                response.close()
            except Exception:
                pass

    def _set_response(self, response) -> None:
        self._response = response

    def run(self):
        try:
            analyzer = DiagnosticAnalyzer()
            common = {
                "cancel_event": self.cancel_event,
                "on_response": self._set_response,
                "on_chunk": self.chunk.emit,
            }
            if self.mode == "analysis":
                answer = analyzer.analyze_stream(self.result, **common)
            else:
                answer = analyzer.chat_stream(
                    self.result, self.conversation, self.message, **common
                )
            if self.cancel_event.is_set():
                self.cancelled.emit()
                return
            self.finished.emit(answer)
        except OpenRouterCancelled:
            self.cancelled.emit()
        except OpenRouterConfigError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            if self.cancel_event.is_set():
                self.cancelled.emit()
            else:
                self.failed.emit(str(exc))


class AITestWorker(QThread):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, api_key: str, model: str, parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.model = model

    def run(self):
        try:
            client = OpenRouterClient(
                OpenRouterConfig(api_key=self.api_key, model=self.model or DEFAULT_MODEL)
            )
            self.finished.emit(client.test_connection())
        except Exception as exc:
            self.failed.emit(str(exc))


class SystemInfoWorker(QThread):
    """Fetch startup dashboard information without blocking the UI."""

    finished = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            self.finished.emit(get_system_info())
        except Exception as exc:
            self.failed.emit(str(exc))


class CollapsiblePanel(QFrame):
    """Expandable panel with independent open/close and user-resizable height."""

    toggled = Signal(bool)
    BASE_HEIGHT = 58
    MIN_EXPANDED_HEIGHT = 150
    ANIMATION_MS = 220

    def __init__(self, title: str, object_name: str = "card", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setMinimumHeight(self.BASE_HEIGHT)
        self.setMaximumHeight(self.BASE_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._expanded = False
        self._user_height = None

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 6, 0, 0)
        self._content_layout.setSpacing(12)
        self._content.setVisible(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 10, 18, 8)
        root.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        self.header_button = QToolButton()
        self.header_button.setObjectName("collapseHeader")
        self.header_button.setText(title)
        self.header_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.header_button.setArrowType(Qt.ArrowType.RightArrow)
        self.header_button.setAutoRaise(True)
        self.header_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_button.clicked.connect(self.toggle)
        header.addWidget(self.header_button)
        header.addStretch()
        self.loader_label = QLabel("")
        self.loader_label.setObjectName("panelLoader")
        self.loader_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.loader_label)
        self.status_label = QLabel("")
        self.status_label.setObjectName("muted")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self.status_label)
        root.addLayout(header)
        root.addWidget(self._content)

        self.resize_handle = QLabel("⋮  ⋮")
        self.resize_handle.setObjectName("panelResizeHandle")
        self.resize_handle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.resize_handle.setCursor(Qt.CursorShape.SizeVerCursor)
        self.resize_handle.setVisible(False)
        self.resize_handle.setFixedHeight(14)
        root.addWidget(self.resize_handle)

        self._animation = QPropertyAnimation(self, b"maximumHeight", self)
        self._animation.setDuration(self.ANIMATION_MS)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.finished.connect(self._finish_animation)

        self._loader_timer = QTimer(self)
        self._loader_timer.setInterval(130)
        self._loader_timer.timeout.connect(self._advance_loader)
        self._loader_frames = ("◐", "◓", "◑", "◒")
        self._loader_index = 0
        self.set_loading(False)

        self.resize_handle.installEventFilter(self)

    @property
    def content_layout(self):
        return self._content_layout

    @property
    def expanded(self) -> bool:
        return self._expanded

    def set_status(self, text: str) -> None:
        self.status_label.setText(str(text))

    def set_loading(self, active: bool) -> None:
        if active:
            self.loader_label.setText(self._loader_frames[self._loader_index])
            self._loader_timer.start()
        else:
            self._loader_timer.stop()
            self.loader_label.setText("")

    def _advance_loader(self) -> None:
        self._loader_index = (self._loader_index + 1) % len(self._loader_frames)
        self.loader_label.setText(self._loader_frames[self._loader_index])

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    def _natural_content_height(self) -> int:
        self._content.setVisible(True)
        self._content.setMaximumHeight(16777215)
        self._content.adjustSize()
        return max(90, self._content.sizeHint().height())

    def _available_max_height(self) -> int:
        parent = self.parentWidget()
        if parent is None:
            return 620
        # Keep room for the sibling panel and the page margins. The user can
        # resize freely within the useful visible area, without swallowing the
        # complete diagnosis workspace.
        room = max(260, parent.height() - 170)
        return min(760, room)

    def set_expanded(self, expanded: bool) -> None:
        expanded = bool(expanded)
        if expanded == self._expanded and not self._animation.state():
            return

        self._animation.stop()
        self._expanded = expanded
        self.header_button.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)

        if expanded:
            self._content.setVisible(True)
            self.resize_handle.setVisible(True)
            natural = self._natural_content_height() + 54
            target = int(self._user_height or natural)
            target = max(self.MIN_EXPANDED_HEIGHT, min(target, self._available_max_height()))
            start = max(self.BASE_HEIGHT, self.height())
            self._animation.setStartValue(start)
            self._animation.setEndValue(target)
        else:
            start = max(self.BASE_HEIGHT, self.height())
            self._animation.setStartValue(start)
            self._animation.setEndValue(self.BASE_HEIGHT)
        self._animation.start()
        self.toggled.emit(expanded)

    def _finish_animation(self) -> None:
        if self._expanded:
            self._content.setVisible(True)
            self.setMaximumHeight(self.height())
        else:
            self._content.setVisible(False)
            self.resize_handle.setVisible(False)
            self.setMaximumHeight(self.BASE_HEIGHT)

    def set_user_height(self, height: int) -> None:
        if not self._expanded:
            return
        clamped = max(self.MIN_EXPANDED_HEIGHT, min(int(height), self._available_max_height()))
        self._user_height = clamped
        self._animation.stop()
        self.setMaximumHeight(clamped)

    def mousePressEvent(self, event) -> None:
        # Header is the explicit click target. This prevents child widgets from
        # accidentally toggling the panel.
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        super().mouseMoveEvent(event)

    def eventFilter(self, obj, event):
        if obj is self.resize_handle and event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._resize_drag_start = event.globalPosition().toPoint().y()
            self._resize_drag_height = self.height()
            self._resize_dragging = True
            return True
        if obj is self.resize_handle and event.type() == QEvent.Type.MouseMove and getattr(self, "_resize_dragging", False):
            delta = event.globalPosition().toPoint().y() - self._resize_drag_start
            self.set_user_height(self._resize_drag_height + delta)
            return True
        if obj is self.resize_handle and event.type() == QEvent.Type.MouseButtonRelease:
            self._resize_dragging = False
            return True
        return super().eventFilter(obj, event)



class ExpandableCard(QFrame):
    """Dashboard card with smooth expand/collapse and a soft shadow."""

    toggled = Signal(bool)

    BASE_HEIGHT = 110
    ANIMATION_MS = 300

    def __init__(self, title: str, value: str, parent=None) -> None:
        super().__init__(parent)

        self.setObjectName("card")
        self.setMinimumHeight(self.BASE_HEIGHT)
        self.setMaximumHeight(self.BASE_HEIGHT)
        self.setMinimumWidth(0)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._expanded = False
        self._details_ready = False

        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(22)
        self._shadow.setOffset(0, 4)
        self._shadow.setColor(QColor(0, 0, 0, 75))
        self.setGraphicsEffect(self._shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(7)

        header = QHBoxLayout()
        header.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("muted")
        header.addWidget(title_label)
        header.addStretch()

        self.arrow_label = QLabel("⌄")
        self.arrow_label.setObjectName("cardArrow")
        self.arrow_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        header.addWidget(self.arrow_label)

        layout.addLayout(header)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("cardValue")
        self.value_label.setWordWrap(True)
        self.value_label.setFont(
            QFont("Segoe UI", 19, QFont.Weight.DemiBold)
        )
        layout.addWidget(self.value_label)

        self.details = QFrame()
        self.details.setObjectName("cardDetails")
        self.details.setMinimumHeight(0)
        self.details.setMaximumHeight(0)
        self.details.setVisible(False)

        self.details_layout = QVBoxLayout(self.details)
        self.details_layout.setContentsMargins(0, 7, 0, 0)
        self.details_layout.setSpacing(5)

        layout.addWidget(self.details)
        self._install_click_filters()

        # Permanent animations. We never disconnect signals dynamically,
        # so PySide6 cannot produce the "Failed to disconnect" warning.
        self._card_animation = QPropertyAnimation(
            self,
            b"maximumHeight",
            self,
        )
        self._card_animation.setDuration(self.ANIMATION_MS)
        self._card_animation.setEasingCurve(
            QEasingCurve.Type.OutCubic
        )

        self._details_animation = QPropertyAnimation(
            self.details,
            b"maximumHeight",
            self.details,
        )
        self._details_animation.setDuration(self.ANIMATION_MS)
        self._details_animation.setEasingCurve(
            QEasingCurve.Type.OutCubic
        )

        self._animation_group = QParallelAnimationGroup(self)
        self._animation_group.addAnimation(
            self._card_animation
        )
        self._animation_group.addAnimation(
            self._details_animation
        )
        self._animation_group.finished.connect(
            self._animation_finished
        )

    def set_value(self, value: str) -> None:
        self.value_label.setText(str(value))

    def set_details(self, details: list[tuple[str, str]]) -> None:
        while self.details_layout.count():
            item = self.details_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not details:
            details = [("Status", "No additional information available.")]

        for name, value in details:
            row = QHBoxLayout()
            row.setSpacing(10)

            key_label = QLabel(str(name))
            key_label.setObjectName("cardDetailKey")
            key_label.setMinimumWidth(0)
            key_label.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred,
            )

            value_label = QLabel(str(value))
            value_label.setObjectName("cardDetailValue")
            value_label.setWordWrap(True)
            value_label.setAlignment(
                Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignVCenter
            )
            value_label.setMinimumWidth(0)
            value_label.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred,
            )

            row.addWidget(key_label, 42)
            row.addWidget(value_label, 58)
            self.details_layout.addLayout(row)

        self._install_click_filters()
        self._details_ready = True

        # Refresh the open card's target height when data changes.
        if self._expanded and not self._animation_group.state():
            self._apply_expanded_geometry()

    def _install_click_filters(self) -> None:
        for child in self.findChildren(QWidget):
            if child is not self:
                child.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            if self._expanded and isinstance(obj, QWidget):
                # Detail fields are informational only; clicking anywhere on the card
                # consistently toggles it, including text/blank areas.
                self.toggle()
                return True
            if isinstance(obj, QWidget):
                self.toggle()
                return True
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle()
        super().mousePressEvent(event)

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded: bool) -> None:
        expanded = bool(expanded)
        if expanded == self._expanded and not self._animation_group.state():
            return

        self._expanded = expanded
        self._animation_group.stop()

        if self._expanded:
            self._open()
        else:
            self._close()

        self.toggled.emit(expanded)

    def _calculate_details_height(self) -> int:
        self.details.setVisible(True)

        # Temporarily remove the height restriction so Qt can calculate
        # the real content height.
        self.details.setMaximumHeight(16777215)
        self.details.adjustSize()
        height = max(1, self.details.sizeHint().height())
        self.details.setMaximumHeight(0)

        return height

    def _open(self) -> None:
        detail_height = self._calculate_details_height()

        start_card = max(
            self.BASE_HEIGHT,
            self.height(),
        )
        target_card = min(self.BASE_HEIGHT + detail_height + 14, 390)

        self.arrow_label.setText("⌃")

        self._details_animation.setStartValue(0)
        self._details_animation.setEndValue(detail_height)

        self._card_animation.setStartValue(start_card)
        self._card_animation.setEndValue(target_card)

        self._animation_group.start()

    def _close(self) -> None:
        start_card = max(
            self.BASE_HEIGHT,
            self.height(),
        )
        start_details = max(
            0,
            self.details.maximumHeight(),
        )

        self.arrow_label.setText("⌄")

        self._details_animation.setStartValue(start_details)
        self._details_animation.setEndValue(0)

        self._card_animation.setStartValue(start_card)
        self._card_animation.setEndValue(self.BASE_HEIGHT)

        self._animation_group.start()

    def _animation_finished(self) -> None:
        if self._expanded:
            self.details.setVisible(True)
        else:
            self.details.setVisible(False)
            self.details.setMaximumHeight(0)
            self.setMaximumHeight(self.BASE_HEIGHT)

    def _apply_expanded_geometry(self) -> None:
        if not self._details_ready:
            return

        detail_height = self._calculate_details_height()
        self.details.setMaximumHeight(detail_height)
        self.setMaximumHeight(
            min(self.BASE_HEIGHT + detail_height + 14, 390)
        )

    def set_shadow_color(self, color: QColor) -> None:
        self._shadow.setColor(color)



class DiagnosticFindingPanel(CollapsiblePanel):
    """Expandable per-diagnostic result bar with evidence, causes and cure."""

    def __init__(self, title: str, parent=None):
        super().__init__(title, "diagnosticFinding", parent)
        self.title = title
        self.summary_label = QLabel("Waiting for diagnosis…")
        self.summary_label.setObjectName("sectionTitle")
        self.summary_label.setWordWrap(True)
        self.content_layout.addWidget(self.summary_label)
        self._labels = {}
        for key, caption in (
            ("severity", "Severity"),
            ("cause", "Cause"),
            ("evidence", "Evidence"),
            ("cure", "Cure / Process"),
        ):
            row = QHBoxLayout()
            key_label = QLabel(caption)
            key_label.setObjectName("cardDetailKey")
            value_label = QLabel("—")
            value_label.setObjectName("cardDetailValue")
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row.addWidget(key_label, 28)
            row.addWidget(value_label, 72)
            self.content_layout.addLayout(row)
            self._labels[key] = value_label
        self.content_layout.addStretch()

    def set_result(self, summary: str, severity: str, cause: str, evidence: str, cure: str, status: str = "Checked") -> None:
        self.summary_label.setText(summary)
        self._labels["severity"].setText(str(severity))
        self._labels["cause"].setText(str(cause))
        self._labels["evidence"].setText(str(evidence))
        self._labels["cure"].setText(str(cure))
        self.set_status(status)


class OpenRouterHelpDialog(QDialog):
    """Visual step-by-step guide for creating an OpenRouter API key."""

    STEPS = (
        (
            "1. Open OpenRouter",
            "Visit openrouter.ai and sign in, or create an account if you do not have one yet.",
            "openrouter_step_1.png",
        ),
        (
            "2. Open the API Keys page",
            "Go to the API Keys page. The current OpenRouter dashboard exposes it at /settings/keys.",
            "openrouter_step_2.png",
        ),
        (
            "3. Create the API key",
            "Choose Create API Key, give it a name such as FixMate-AI, and create the key.",
            "openrouter_step_3.png",
        ),
        (
            "4. Copy the key into FixMate-AI",
            "Copy the generated key (normally beginning with sk-or-) immediately, then paste it into FixMate-AI → AI Settings.",
            "openrouter_step_4.png",
        ),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FixMate-AI — OpenRouter API Key Help")
        self.setModal(True)
        self.resize(960, 780)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        title = QLabel("How to get an OpenRouter API key")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        subtitle = QLabel(
            "Follow the steps below. The dashboard layout can change over time, so use the current OpenRouter site if a label looks different."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("muted")
        root.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(4, 4, 8, 8)
        body_layout.setSpacing(16)

        assets_dir = Path(__file__).resolve().parent / "help_assets"
        for heading, description, filename in self.STEPS:
            card = QFrame()
            card.setObjectName("helpStepCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 14, 14, 14)
            card_layout.setSpacing(9)

            step_title = QLabel(heading)
            step_title.setObjectName("helpStepTitle")
            card_layout.addWidget(step_title)

            step_desc = QLabel(description)
            step_desc.setWordWrap(True)
            step_desc.setObjectName("muted")
            card_layout.addWidget(step_desc)

            image_label = QLabel()
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            image_label.setMinimumHeight(250)
            image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            image_label.setProperty("helpImage", True)

            image_path = assets_dir / filename
            if image_path.exists():
                pixmap = QPixmap(str(image_path))
                if not pixmap.isNull():
                    image_label.setPixmap(
                        pixmap.scaled(
                            820,
                            470,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
            else:
                image_label.setText("Guide image unavailable")
                image_label.setObjectName("muted")
            card_layout.addWidget(image_label)
            body_layout.addWidget(card)

        note = QLabel(
            "Security note: never paste your API key into chat messages or screenshots you share publicly. FixMate-AI stores the key in the operating system credential store when keyring is installed."
        )
        note.setWordWrap(True)
        note.setObjectName("muted")
        body_layout.addWidget(note)
        body_layout.addStretch()

        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        open_keys = QPushButton("Open OpenRouter API Keys")
        open_keys.setObjectName("primaryButton")
        open_keys.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://openrouter.ai/settings/keys"))
        )
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(open_keys)
        buttons.addStretch()
        buttons.addWidget(close_btn)
        root.addLayout(buttons)



class SystemInformationPanel(QFrame):
    """Single expandable landscape frame containing all startup information.

    The four informational groups stay in separate horizontal columns while
    sharing one expandable container. No diagnostic severity/fault data is
    shown here; this panel is information-only.
    """

    BASE_HEIGHT = 92
    ANIMATION_MS = 260

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setMinimumHeight(self.BASE_HEIGHT)
        self.setMaximumHeight(self.BASE_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._expanded = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 12, 18, 12)
        outer.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(10)
        self.header_button = QToolButton()
        self.header_button.setObjectName("collapseHeader")
        self.header_button.setText("System Information")
        self.header_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.header_button.setArrowType(Qt.ArrowType.RightArrow)
        self.header_button.setAutoRaise(True)
        self.header_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_button.clicked.connect(self.toggle)
        header.addWidget(self.header_button)
        header.addStretch()
        self.status_label = QLabel("Fetching...")
        self.status_label.setObjectName("muted")
        header.addWidget(self.status_label)
        outer.addLayout(header)

        self.content = QWidget()
        self.content.setVisible(False)
        self.content_layout = QHBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 8, 0, 0)
        self.content_layout.setSpacing(0)
        outer.addWidget(self.content)

        self.columns = {}
        self._build_column("System", "system")
        self._build_column("CPU", "cpu")
        self._build_column("Memory", "memory")
        self._build_column("Storage", "storage")

        self._animation = QPropertyAnimation(self, b"maximumHeight", self)
        self._animation.setDuration(self.ANIMATION_MS)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.finished.connect(self._animation_finished)

    def _build_column(self, title: str, key: str) -> None:
        if self.columns:
            separator = QFrame()
            separator.setFrameShape(QFrame.Shape.VLine)
            separator.setFrameShadow(QFrame.Shadow.Plain)
            separator.setObjectName("infoColumnSeparator")
            self.content_layout.addWidget(separator)

        column = QFrame()
        column.setObjectName("infoColumn")
        layout = QVBoxLayout(column)
        layout.setContentsMargins(14, 4, 14, 6)
        layout.setSpacing(7)

        heading = QLabel(title)
        heading.setObjectName("infoColumnTitle")
        layout.addWidget(heading)

        value = QLabel("Fetching...")
        value.setObjectName("infoColumnValue")
        value.setWordWrap(True)
        layout.addWidget(value)

        details = QFrame()
        details.setObjectName("infoColumnDetails")
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(0, 2, 0, 0)
        details_layout.setSpacing(4)
        layout.addWidget(details)
        layout.addStretch()

        self.content_layout.addWidget(column, 1)
        self.columns[key] = {
            "frame": column,
            "value": value,
            "details": details_layout,
        }

    @property
    def expanded(self) -> bool:
        return self._expanded

    def set_status(self, text: str) -> None:
        self.status_label.setText(str(text))

    def _set_column(self, key: str, value: str, details: list[tuple[str, str]]) -> None:
        column = self.columns[key]
        column["value"].setText(str(value))
        layout = column["details"]
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not details:
            details = [("Status", "No data available")]
        for label, data in details:
            row = QHBoxLayout()
            row.setSpacing(8)
            k = QLabel(str(label))
            k.setObjectName("infoDetailKey")
            v = QLabel(str(data))
            v.setObjectName("infoDetailValue")
            v.setWordWrap(True)
            v.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(k, 1)
            row.addWidget(v, 1)
            layout.addLayout(row)

    def set_state(self, state: str, error: str = "") -> None:
        self.set_status(state)
        detail = [("Status", state)]
        if error:
            detail.append(("Error", error))
        for key in self.columns:
            self._set_column(key, state, detail)

    def set_snapshot(self, info: dict) -> None:
        if not isinstance(info, dict) or info.get("error"):
            self.set_state("Error", str(info.get("error") or "No system information was returned."))
            return

        required = ("windows_display_name", "cpu_name", "ram_total_gb", "storage_total_gb")
        missing = [key for key in required if info.get(key) in (None, "", "Unknown")]
        self.set_status("Ready" if not missing else "Ready • Partial")

        os_name = str(info.get("windows_display_name") or info.get("os") or "Windows")
        os_version = str(info.get("windows_version") or info.get("version") or "Unknown")
        build = str(info.get("windows_build") or "Unknown")
        arch = str(info.get("architecture") or "Unknown")
        computer = str(info.get("computer_name") or "Unknown")
        system_value = str(info.get("windows_summary") or f"{os_name} {os_version}").strip()
        self._set_column("system", system_value, [
            ("Operating System", os_name),
            ("Version", os_version),
            ("Build", build),
            ("Architecture", arch),
            ("Computer Name", computer),
        ])

        cpu_name = str(info.get("cpu_name") or "Unknown processor")
        vendor = str(info.get("cpu_vendor") or "Unknown")
        generation = str(info.get("cpu_generation") or "Not detected")
        series = str(info.get("cpu_series") or "Not detected")
        base_clock = str(info.get("cpu_current_clock") or info.get("cpu_base_clock") or "Unknown")
        max_clock = str(info.get("cpu_max_clock") or "Unknown")
        summary = str(info.get("cpu_summary") or f"{series} • {generation} • {max_clock}")
        self._set_column("cpu", summary, [
            ("Processor", cpu_name),
            ("Vendor", vendor),
            ("Generation", generation),
            ("Series", series),
            ("Current Clock", base_clock),
            ("Max Clock", max_clock),
            ("Cores / Threads", f"{info.get('physical_cores', 'Unknown')} / {info.get('logical_cores', 'Unknown')}"),
        ])

        total = info.get("ram_total_gb")
        used = info.get("ram_used_gb")
        available = info.get("ram_available_gb")
        usage = info.get("ram_usage_percent")
        free_mem = info.get("ram_free_gb")
        memory_value = (
            f"{free_mem:.2f} GB free" if isinstance(free_mem, (int, float))
            else (f"{usage:.1f}% used" if isinstance(usage, (int, float)) else "Ready")
        )
        memory_details = [
            ("Total RAM", f"{total:.2f} GB" if isinstance(total, (int, float)) else "Unknown"),
            ("Used RAM", f"{used:.2f} GB" if isinstance(used, (int, float)) else "Unknown"),
            ("Free Memory", f"{free_mem:.2f} GB" if isinstance(free_mem, (int, float)) else "Unknown"),
            ("Available RAM", f"{available:.2f} GB" if isinstance(available, (int, float)) else "Unknown"),
            ("Usage", f"{usage:.1f}%" if isinstance(usage, (int, float)) else "Unknown"),
        ]
        if info.get("ram_speed_mhz"):
            memory_details.append(("Memory Speed", f"{info['ram_speed_mhz']} MHz"))
        self._set_column("memory", memory_value, memory_details)

        free_storage = info.get("storage_free_gb")
        storage_summary = (
            f"{float(free_storage):.1f} GB free" if isinstance(free_storage, (int, float))
            else str(info.get("storage_summary") or "Ready")
        )
        storage_details = [("System Drive", str(info.get("system_drive") or "C:"))]
        for label, key, unit in (
            ("Capacity", "storage_total_gb", " GB"),
            ("Used", "storage_used_gb", " GB"),
            ("Free Storage", "storage_free_gb", " GB"),
            ("Free Space", "storage_free_percent", "%"),
        ):
            value = info.get(key)
            if value is not None:
                try:
                    precision = 1
                    storage_details.append((label, f"{float(value):.{precision}f}{unit}"))
                except (TypeError, ValueError):
                    storage_details.append((label, str(value)))
        if info.get("storage_device"):
            storage_details.append(("Device", str(info["storage_device"])))
        self._set_column("storage", storage_summary, storage_details)

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded: bool) -> None:
        expanded = bool(expanded)
        if expanded == self._expanded:
            return
        self._expanded = expanded
        self._animation.stop()
        if expanded:
            self.content.setVisible(True)
            self.content.adjustSize()
            self.content.updateGeometry()
            target = max(self.BASE_HEIGHT, self.sizeHint().height())
            target = min(target, 430)
            self.header_button.setArrowType(Qt.ArrowType.DownArrow)
            self._animation.setStartValue(max(self.BASE_HEIGHT, self.height()))
            self._animation.setEndValue(target)
        else:
            self.header_button.setArrowType(Qt.ArrowType.RightArrow)
            self._animation.setStartValue(max(self.BASE_HEIGHT, self.height()))
            self._animation.setEndValue(self.BASE_HEIGHT)
        self._animation.start()

    def _animation_finished(self) -> None:
        if self._expanded:
            self.content.setVisible(True)
            self.setMaximumHeight(min(max(self.BASE_HEIGHT, self.sizeHint().height()), 430))
        else:
            self.content.setVisible(False)
            self.setMaximumHeight(self.BASE_HEIGHT)

    def set_shadow_color(self, color: QColor) -> None:
        shadow = self.graphicsEffect()
        if isinstance(shadow, QGraphicsDropShadowEffect):
            shadow.setColor(color)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.current_theme = load_theme("dark")
        self.scan_manager = ScanManager()
        self.system_snapshot: dict = {}
        self._last_primary_row = 0

        self.scan_start_time: float | None = None
        self.scan_started_iso: str | None = None
        self.last_progress = 0
        self.progress_history: list[tuple[float, int]] = []
        self.last_scan_result: dict | None = None
        self.current_history_id: int | None = None
        self.ai_worker: AIWorker | None = None
        self.ai_conversation: list[dict[str, str]] = []
        self._accordion_items: list[object] = []
        self.ai_test_worker: AITestWorker | None = None
        self.system_info_worker: SystemInfoWorker | None = None
        self.ai_typing_timer = QTimer(self)
        self.ai_typing_timer.setInterval(16)
        self.ai_typing_timer.timeout.connect(self._type_next_ai_character)
        self._ai_typing_text = ""
        self._ai_typing_index = 0
        self._ai_typing_prefix = ""
        self._ai_typing_mode = "analysis"
        self._ai_partial_stream = ""
        self._scan_visual_mode = "idle"
        self._scan_visual_index = 0
        self.scan_visual_timer = QTimer(self)
        self.scan_visual_timer.setInterval(120)
        self.scan_visual_timer.timeout.connect(self._advance_scan_visual)

        self.setWindowTitle("FixMate-AI")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)

        self._build_ui()
        self.apply_theme(self.current_theme)

        # Fetch a lightweight system snapshot as soon as the application opens.
        # This is informational only; it does not start the diagnostic engine.
        self._load_initial_system_information()
        self._refresh_dashboard_history()
        self._set_primary_view(0)

        self.eta_timer = QTimer(self)
        self.eta_timer.setInterval(1000)
        self.eta_timer.timeout.connect(self._update_eta)

        fade_in(self)

    # ============================================================
    # UI
    # ============================================================

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)

        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 22, 18, 18)
        side.setSpacing(10)

        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(0, 0, 0, 0)
        brand_row.setSpacing(10)
        logo = QLabel()
        logo.setObjectName("brandLogo")
        logo_path = Path(__file__).resolve().parent.parent / "assets" / "fixmate_logo.svg"
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            if not pixmap.isNull():
                logo.setPixmap(pixmap.scaled(36, 36, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        brand_row.addWidget(logo)
        brand_text = QVBoxLayout()
        brand_text.setContentsMargins(0, 0, 0, 0)
        brand_text.setSpacing(0)
        brand = QLabel("FixMate-AI")
        brand.setObjectName("brand")
        brand_text.addWidget(brand)
        tagline = QLabel("DIAGNOSE • ANALYZE • FIX")
        tagline.setObjectName("brandTagline")
        brand_text.addWidget(tagline)
        brand_row.addLayout(brand_text, 1)
        side.addLayout(brand_row)
        side.addSpacing(20)

        self.nav = QListWidget()

        for label in (
            "Dashboard",
            "Run Diagnosis",
            "History",
            "Reports",
            "Settings",
            "Help",
        ):
            self.nav.addItem(QListWidgetItem(label))

        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self._navigation_changed)
        side.addWidget(self.nav)
        side.addStretch()

        self.ai_settings_button = QPushButton("⚙  AI Settings")
        self.ai_settings_button.clicked.connect(self._show_ai_settings)
        side.addWidget(self.ai_settings_button)

        self.theme_button = QPushButton("☾  Dark")
        self.theme_button.clicked.connect(self.toggle_theme)
        side.addWidget(self.theme_button)

        content = QFrame()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(34, 28, 34, 30)
        content_layout.setSpacing(18)

        header = QHBoxLayout()

        self.page_title = QLabel("Dashboard")
        self.page_title.setObjectName("pageTitle")
        header.addWidget(self.page_title)
        header.addStretch()

        content_layout.addLayout(header)

        self.page_subtitle = QLabel(
            "System information, live hardware details and recent diagnosis history."
        )
        self.page_subtitle.setObjectName("subtitle")
        content_layout.addWidget(self.page_subtitle)

        # --------------------------------------------------------
        # MERGED SYSTEM INFORMATION FRAME
        # --------------------------------------------------------
        self.system_information_panel = SystemInformationPanel()
        self._system_info_shadow = QGraphicsDropShadowEffect(self.system_information_panel)
        self._system_info_shadow.setBlurRadius(22)
        self._system_info_shadow.setOffset(0, 4)
        self._system_info_shadow.setColor(QColor(0, 0, 0, 75))
        self.system_information_panel.setGraphicsEffect(self._system_info_shadow)
        content_layout.addWidget(self.system_information_panel)

        # --------------------------------------------------------
        # RECENT HISTORY (Dashboard)
        # --------------------------------------------------------
        self.recent_history_panel = QFrame()
        self.recent_history_panel.setObjectName("card")
        history_layout = QVBoxLayout(self.recent_history_panel)
        history_layout.setContentsMargins(18, 14, 18, 14)
        history_layout.setSpacing(8)

        history_header = QHBoxLayout()
        history_title = QLabel("Recent Diagnosis History")
        history_title.setObjectName("sectionTitle")
        history_header.addWidget(history_title)
        history_header.addStretch()
        history_hint = QLabel("Latest 5 scans")
        history_hint.setObjectName("muted")
        history_header.addWidget(history_hint)
        history_layout.addLayout(history_header)

        self.recent_history_browser = QTextBrowser()
        self.recent_history_browser.setObjectName("recentHistory")
        self.recent_history_browser.setOpenExternalLinks(False)
        self.recent_history_browser.setOpenLinks(False)
        self.recent_history_browser.anchorClicked.connect(self._open_history_from_dashboard)
        self.recent_history_browser.setMaximumHeight(190)
        self.recent_history_browser.setText(
            "<span style=\"color:#8ea0b7\">No diagnosis history yet. Run your first diagnosis to see it here.</span>"
        )
        history_layout.addWidget(self.recent_history_browser)
        content_layout.addWidget(self.recent_history_panel)

        # --------------------------------------------------------
        # QUICK ACTIONS (Dashboard)
        # --------------------------------------------------------
        quick_actions = QFrame()
        quick_actions.setObjectName("card")
        quick_layout = QHBoxLayout(quick_actions)
        quick_layout.setContentsMargins(18, 12, 18, 12)
        quick_layout.setSpacing(10)

        quick_title = QLabel("Quick Actions")
        quick_title.setObjectName("sectionTitle")
        quick_layout.addWidget(quick_title)
        quick_layout.addStretch()

        run_diag_btn = QPushButton("Run Diagnosis")
        run_diag_btn.setObjectName("primaryButton")
        run_diag_btn.clicked.connect(lambda: self.nav.setCurrentRow(1))
        quick_layout.addWidget(run_diag_btn)

        history_btn = QPushButton("History")
        history_btn.clicked.connect(lambda: self.nav.setCurrentRow(2))
        quick_layout.addWidget(history_btn)

        reports_btn = QPushButton("Reports")
        reports_btn.clicked.connect(lambda: self.nav.setCurrentRow(3))
        quick_layout.addWidget(reports_btn)

        ai_btn = QPushButton("AI Settings")
        ai_btn.clicked.connect(self._show_ai_settings)
        quick_layout.addWidget(ai_btn)

        content_layout.addWidget(quick_actions)

        # --------------------------------------------------------
        # DIAGNOSIS WORKSPACE (scrollable)
        # --------------------------------------------------------
        self.diagnosis_scroll = QScrollArea()
        self.diagnosis_scroll.setObjectName("diagnosisScroll")
        self.diagnosis_scroll.setWidgetResizable(True)
        self.diagnosis_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.diagnosis_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        diagnosis_body = QWidget()
        self.diagnosis_body_layout = QVBoxLayout(diagnosis_body)
        self.diagnosis_body_layout.setContentsMargins(2, 4, 12, 8)
        self.diagnosis_body_layout.setSpacing(12)

        self.scan_panel = CollapsiblePanel("Diagnosis", "card")
        self.scan_panel.set_status("Ready")
        self.scan_panel.set_loading(False)
        scan_layout = self.scan_panel.content_layout

        self.scan_status = QLabel("Ready to analyze this PC")
        self.scan_status.setObjectName("muted")
        self.scan_status.setWordWrap(True)
        scan_layout.addWidget(self.scan_status)

        self.scan_visual = QLabel("◌")
        self.scan_visual.setObjectName("scanVisual")
        self.scan_visual.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scan_visual.setMinimumHeight(42)
        scan_layout.addWidget(self.scan_visual)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        scan_layout.addWidget(self.progress)

        progress_row = QHBoxLayout()
        self.stage_label = QLabel("Current analysis: Not running")
        self.stage_label.setObjectName("muted")
        self.stage_label.setWordWrap(True)
        progress_row.addWidget(self.stage_label)
        progress_row.addStretch()
        self.percent_label = QLabel("0%")
        self.percent_label.setObjectName("muted")
        progress_row.addWidget(self.percent_label)
        scan_layout.addLayout(progress_row)

        eta_row = QHBoxLayout()
        self.eta_label = QLabel("Estimated time: —")
        self.eta_label.setObjectName("muted")
        eta_row.addStretch()
        eta_row.addWidget(self.eta_label)
        scan_layout.addLayout(eta_row)

        self.start_button = QPushButton("Run Full Diagnosis")
        self.start_button.setObjectName("primaryButton")
        self.start_button.clicked.connect(self.start_scan)
        scan_layout.addWidget(self.start_button, alignment=Qt.AlignmentFlag.AlignLeft)

        self.diagnosis_body_layout.addWidget(self.scan_panel)
        self._register_accordion_item(self.scan_panel)

        self.result_label = QLabel("")
        self.result_label.setObjectName("muted")
        self.result_label.setWordWrap(True)

        summary_frame = QFrame()
        summary_frame.setObjectName("diagnosisSummaryFrame")
        summary_layout = QHBoxLayout(summary_frame)
        summary_layout.setContentsMargins(14, 10, 14, 10)
        summary_layout.setSpacing(24)
        self.overall_health_value = QLabel("Waiting")
        self.overall_health_value.setObjectName("sectionTitle")
        self.problem_count_value = QLabel("0")
        self.problem_count_value.setObjectName("sectionTitle")
        self.warning_count_value = QLabel("0")
        self.warning_count_value.setObjectName("sectionTitle")
        self.hardware_fault_value = QLabel("0")
        self.hardware_fault_value.setObjectName("sectionTitle")
        for caption, value in (("Overall Health", self.overall_health_value), ("Problems", self.problem_count_value), ("Warnings", self.warning_count_value), ("Hardware Faults", self.hardware_fault_value)):
            block = QVBoxLayout()
            label = QLabel(caption)
            label.setObjectName("muted")
            block.addWidget(label)
            block.addWidget(value)
            summary_layout.addLayout(block, 1)
        self.diagnosis_body_layout.addWidget(summary_frame)
        self.diagnosis_body_layout.addWidget(self.result_label)

        findings_title = QLabel("Diagnostic Checks & Findings")
        findings_title.setObjectName("sectionTitle")
        self.diagnosis_body_layout.addWidget(findings_title)

        self.diagnosis_findings_layout = QVBoxLayout()
        self.diagnosis_findings_layout.setSpacing(10)
        self.diagnosis_body_layout.addLayout(self.diagnosis_findings_layout)
        self.diagnosis_finding_panels = {}

        # --------------------------------------------------------
        # AI DIAGNOSIS — ALWAYS LAST IN THE DIAGNOSIS SCROLLER
        # --------------------------------------------------------
        self.ai_panel = CollapsiblePanel("✦  FixMate AI Diagnosis", "aiCard")
        self.ai_panel.set_status(self._ai_ready_status())
        ai_layout = self.ai_panel.content_layout

        self.ai_analyze_button = QPushButton("Analyze with FixMate AI")
        self.ai_analyze_button.setObjectName("primaryButton")
        self.ai_analyze_button.setEnabled(False)
        self.ai_analyze_button.clicked.connect(self._start_ai_analysis_from_button)
        ai_layout.addWidget(self.ai_analyze_button, alignment=Qt.AlignmentFlag.AlignLeft)

        self.ai_output = QTextBrowser()
        self.ai_output.setObjectName("aiOutput")
        self.ai_output.setOpenExternalLinks(True)
        self.ai_output.setMinimumHeight(190)
        self.ai_output.setMaximumHeight(16777215)
        self.ai_output.setPlainText(
            "Run a full diagnosis to let FixMate AI analyze the scan and explain any problems step by step."
        )
        ai_layout.addWidget(self.ai_output)

        chat_row = QHBoxLayout()
        self.ai_input = QLineEdit()
        self.ai_input.setPlaceholderText(
            "Still confused? Ask FixMate AI about this diagnosis..."
        )
        self.ai_input.returnPressed.connect(self._send_ai_message)
        chat_row.addWidget(self.ai_input, 1)

        self.ai_send_button = QPushButton("Ask AI")
        self.ai_send_button.setObjectName("primaryButton")
        self.ai_send_button.setEnabled(False)
        self.ai_send_button.clicked.connect(self._ai_action_button_clicked)
        chat_row.addWidget(self.ai_send_button)
        ai_layout.addLayout(chat_row)

        self.diagnosis_body_layout.addWidget(self.ai_panel)
        self._register_accordion_item(self.ai_panel)
        self.diagnosis_body_layout.addStretch()
        self.diagnosis_scroll.setWidget(diagnosis_body)
        content_layout.addWidget(self.diagnosis_scroll, 1)

        root_layout.addWidget(sidebar)
        root_layout.addWidget(content, 1)

        self.setCentralWidget(root)

    def _ai_ready_status(self) -> str:
        return "AI configured" if get_saved_api_key() else "AI not configured"

    def _navigation_changed(self, row: int) -> None:
        if row in (0, 1):
            self._last_primary_row = row
            self._set_primary_view(row)
            return

        restore_row = self._last_primary_row
        if row == 2:
            HistoryDialog(self, mode="history").exec()
        elif row == 3:
            HistoryDialog(self, mode="reports").exec()
        elif row == 4:
            self._show_settings()
        elif row == 5:
            OpenRouterHelpDialog(self).exec()

        self._refresh_dashboard_history()
        self.nav.blockSignals(True)
        self.nav.setCurrentRow(restore_row)
        self.nav.blockSignals(False)
        self._set_primary_view(restore_row)

    def _set_primary_view(self, row: int) -> None:
        """Switch between the information dashboard and the diagnosis workspace."""
        diagnosis = row == 1

        self.system_information_panel.setVisible(not diagnosis)
        self.recent_history_panel.setVisible(not diagnosis)
        self.diagnosis_scroll.setVisible(diagnosis)

        if diagnosis:
            self.page_title.setText("Run Diagnosis")
            self.page_subtitle.setText(
                "Run a full PC diagnosis, review findings and optionally analyze them with FixMate AI."
            )
        else:
            self.page_title.setText("Dashboard")
            self.page_subtitle.setText(
                "System information, live hardware details and recent diagnosis history."
            )
            self._refresh_dashboard_history()

    def _load_initial_system_information(self) -> None:
        """Start a non-diagnostic startup information fetch."""
        self.system_snapshot = {"loading": True}
        self._set_information_cards_state("Fetching...")
        self.system_info_worker = SystemInfoWorker(self)
        self.system_info_worker.finished.connect(self._initial_system_info_ready)
        self.system_info_worker.failed.connect(self._initial_system_info_failed)
        self.system_info_worker.finished.connect(self.system_info_worker.deleteLater)
        self.system_info_worker.failed.connect(self.system_info_worker.deleteLater)
        self.system_info_worker.start()

    def _initial_system_info_ready(self, info: object) -> None:
        self.system_info_worker = None
        snapshot = info if isinstance(info, dict) else {}
        self.system_snapshot = snapshot
        self._apply_system_snapshot_to_cards()

    def _initial_system_info_failed(self, error: str) -> None:
        self.system_info_worker = None
        self.system_snapshot = {"error": str(error)}
        self._set_information_cards_state("Error", str(error))

    def _set_information_cards_state(self, state: str, error: str = "") -> None:
        """Keep the merged information panel honest about loading vs errors."""
        self.system_information_panel.set_state(state, error)

    def _apply_system_snapshot_to_cards(self) -> None:
        info = self.system_snapshot if isinstance(self.system_snapshot, dict) else {}
        self.system_information_panel.set_snapshot(info)

    def _refresh_dashboard_history(self) -> None:
        try:
            rows = __import__("storage.history", fromlist=["list_diagnoses"]).list_diagnoses(limit=5)
        except Exception as exc:
            self.recent_history_browser.setText(
                f'<span style="color:#ef8888">History error: {exc}</span>'
            )
            return
        if not rows:
            self.recent_history_browser.setText(
                '<span style="color:#8ea0b7">No diagnosis history yet. Run your first diagnosis to see it here.</span>'
            )
            return
        chunks = []
        for row in rows:
            completed = str(row.get("completed_at") or row.get("started_at") or "Unknown")
            severity = str(row.get("overall_severity") or "UNKNOWN").upper()
            issues = row.get("issue_count", 0)
            row_id = row.get("id", "")
            label = f"{completed}  •  {severity}  •  {issues} issue(s)"
            chunks.append(
                f'<a href="history:{row_id}" style="text-decoration:none;color:#79b8ff">{label}</a>'
            )
        self.recent_history_browser.setHtml("<br>".join(chunks))

    def _open_history_from_dashboard(self, url: QUrl) -> None:
        """Opening any recent-history row takes the user to the full History view."""
        HistoryDialog(self, mode="history").exec()
        self._refresh_dashboard_history()

    def _show_settings(self) -> None:
        """Open the main FixMate-AI settings hub."""
        dialog = QDialog(self)
        dialog.setWindowTitle("FixMate-AI — Settings")
        dialog.setModal(True)
        dialog.setMinimumSize(650, 520)

        layout = QVBoxLayout(dialog)
        title = QLabel("Settings")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        subtitle = QLabel("Customize FixMate-AI, configure AI, manage reports and view application information.")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        appearance = QFrame()
        appearance.setObjectName("card")
        ap = QVBoxLayout(appearance)
        ap_title = QLabel("Appearance")
        ap_title.setObjectName("sectionTitle")
        ap.addWidget(ap_title)
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Theme"))
        theme_combo = QComboBox()
        theme_combo.addItems(["Dark", "Light"])
        theme_combo.setCurrentText("Dark" if self.current_theme == "dark" else "Light")
        theme_row.addWidget(theme_combo, 1)
        apply_theme_btn = QPushButton("Apply")
        apply_theme_btn.clicked.connect(lambda: self.apply_theme(theme_combo.currentText().lower()))
        theme_row.addWidget(apply_theme_btn)
        ap.addLayout(theme_row)
        layout.addWidget(appearance)

        ai = QFrame()
        ai.setObjectName("card")
        aip = QVBoxLayout(ai)
        ai_title = QLabel("FixMate AI")
        ai_title.setObjectName("sectionTitle")
        aip.addWidget(ai_title)
        ai_status = QLabel(self._ai_ready_status())
        ai_status.setObjectName("muted")
        aip.addWidget(ai_status)
        ai_row = QHBoxLayout()
        configure_ai = QPushButton("Open AI Settings")
        configure_ai.clicked.connect(lambda: self._show_ai_settings())
        ai_row.addWidget(configure_ai)
        help_ai = QPushButton("API Key Help")
        help_ai.clicked.connect(lambda: OpenRouterHelpDialog(dialog).exec())
        ai_row.addWidget(help_ai)
        ai_row.addStretch()
        aip.addLayout(ai_row)
        layout.addWidget(ai)

        storage = QFrame()
        storage.setObjectName("card")
        sp = QVBoxLayout(storage)
        st = QLabel("Storage")
        st.setObjectName("sectionTitle")
        sp.addWidget(st)
        reports_dir = Path(REPORTS_DIR)
        local_data = Path(APP_DATA_DIR)
        sp.addWidget(QLabel(f"Application data: {local_data}"))
        sp.addWidget(QLabel(f"Reports: {reports_dir}"))
        storage_row = QHBoxLayout()
        open_reports = QPushButton("Open Reports Folder")
        open_reports.clicked.connect(lambda: self._open_folder(reports_dir))
        storage_row.addWidget(open_reports)
        open_data = QPushButton("Open App Data")
        open_data.clicked.connect(lambda: self._open_folder(local_data))
        storage_row.addWidget(open_data)
        storage_row.addStretch()
        sp.addLayout(storage_row)
        layout.addWidget(storage)

        about = QFrame()
        about.setObjectName("card")
        bp = QVBoxLayout(about)
        bt = QLabel("About FixMate-AI")
        bt.setObjectName("sectionTitle")
        bp.addWidget(bt)
        bp.addWidget(QLabel("FixMate-AI — Windows PC diagnostics and AI-assisted troubleshooting."))
        bp.addWidget(QLabel("Version 0.6 • Secure • Stable • Optimized"))
        about_row = QHBoxLayout()
        about_btn = QPushButton("About")
        about_btn.clicked.connect(lambda: self._show_about())
        about_row.addWidget(about_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        about_row.addStretch()
        about_row.addWidget(close_btn)
        bp.addLayout(about_row)
        layout.addWidget(about)
        dialog.exec()

    def _open_folder(self, path: Path) -> None:
        try:
            path.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))
        except Exception as exc:
            QMessageBox.warning(self, "Could Not Open Folder", str(exc))

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About FixMate-AI",
            "<h2>FixMate-AI</h2>"
            "<p>Windows PC diagnostics with optional OpenRouter-powered FixMate AI.</p>"
            "<p><b>Version:</b> 0.6</p>"
            "<p>Diagnose Today. A Better Tomorrow.</p>",
        )

    def _show_ai_settings(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("FixMate-AI — AI Settings")
        dialog.setModal(True)
        dialog.setMinimumWidth(560)

        layout = QVBoxLayout(dialog)
        intro = QLabel(
            "Configure OpenRouter for FixMate AI. The API key is stored in the operating system credential store."
        )
        intro.setWordWrap(True)
        intro.setObjectName("muted")
        layout.addWidget(intro)

        form = QFormLayout()
        key_edit = QLineEdit()
        key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        key_edit.setPlaceholderText("sk-or-v1-…")
        existing_key = get_saved_api_key()
        if existing_key:
            key_edit.setText(existing_key)

        key_row = QHBoxLayout()
        key_row.setContentsMargins(0, 0, 0, 0)
        key_row.setSpacing(8)
        key_row.addWidget(key_edit, 1)
        help_btn = QPushButton("?  Help")
        help_btn.setToolTip("See a visual step-by-step guide for getting an OpenRouter API key")
        help_btn.clicked.connect(lambda: OpenRouterHelpDialog(dialog).exec())
        key_row.addWidget(help_btn)
        key_row_widget = QWidget()
        key_row_widget.setLayout(key_row)
        form.addRow("OpenRouter API key", key_row_widget)

        model_edit = QLineEdit(get_saved_model() or DEFAULT_MODEL)
        model_edit.setPlaceholderText(DEFAULT_MODEL)
        form.addRow("Model", model_edit)
        layout.addLayout(form)

        hint = QLabel(
            "Recommended for testing: openrouter/free. Free-model availability and limits can change on OpenRouter."
        )
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        layout.addWidget(hint)

        status = QLabel(
            "Saved key: Yes" if existing_key else "Saved key: No"
        )
        status.setObjectName("muted")
        layout.addWidget(status)

        buttons = QDialogButtonBox()
        save_btn = buttons.addButton("Save", QDialogButtonBox.ButtonRole.AcceptRole)
        test_btn = buttons.addButton("Test Connection", QDialogButtonBox.ButtonRole.ActionRole)
        clear_btn = buttons.addButton("Clear Key", QDialogButtonBox.ButtonRole.DestructiveRole)
        cancel_btn = buttons.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(buttons)

        def do_save(close_after: bool = False) -> bool:
            key = key_edit.text().strip()
            model = model_edit.text().strip() or DEFAULT_MODEL
            try:
                # An empty key is allowed: AI is optional and the local
                # diagnostic application continues to work without it.
                save_api_key(key)
                if key:
                    save_model(model)
            except Exception as exc:
                QMessageBox.critical(dialog, "Could Not Save", str(exc))
                return False
            status.setText("Saved key: Yes" if key else "Saved key: No — AI disabled")
            self.ai_panel.set_status("AI configured" if key else "AI not configured")
            if self.last_scan_result is not None:
                # The button remains clickable so a user without a key gets
                # a clear explanation instead of a disabled/hidden action.
                self.ai_analyze_button.setEnabled(True)
            if close_after:
                dialog.accept()
            return True

        def do_test() -> None:
            key = key_edit.text().strip()
            model = model_edit.text().strip() or DEFAULT_MODEL
            if not key:
                QMessageBox.warning(dialog, "API Key Required", "Enter an OpenRouter API key first.")
                return
            test_btn.setEnabled(False)
            save_btn.setEnabled(False)
            status.setText("Testing OpenRouter connection…")
            worker = AITestWorker(key, model, dialog)
            self.ai_test_worker = worker
            worker.finished.connect(lambda text: finish_test(True, text))
            worker.failed.connect(lambda text: finish_test(False, text))
            worker.finished.connect(worker.deleteLater)
            worker.failed.connect(worker.deleteLater)
            worker.start()

        def finish_test(ok: bool, text: str) -> None:
            test_btn.setEnabled(True)
            save_btn.setEnabled(True)
            status.setText("Connection test passed" if ok else "Connection test failed")
            if ok:
                QMessageBox.information(dialog, "OpenRouter", "Connection successful.\n\n" + text)
            else:
                QMessageBox.critical(dialog, "OpenRouter", text)
            self.ai_test_worker = None

        def do_clear() -> None:
            try:
                delete_saved_api_key()
                key_edit.clear()
                status.setText("Saved key: No — AI disabled")
                self.ai_panel.set_status("AI not configured")
                if self.last_scan_result is not None:
                    self.ai_analyze_button.setEnabled(True)
                self.ai_input.setEnabled(False)
                self.ai_send_button.setEnabled(False)
            except Exception as exc:
                QMessageBox.critical(dialog, "Could Not Clear", str(exc))

        save_btn.clicked.connect(lambda: do_save(False))
        test_btn.clicked.connect(do_test)
        clear_btn.clicked.connect(do_clear)
        cancel_btn.clicked.connect(dialog.reject)

        dialog.exec()

    # ============================================================
    # ACCORDION BEHAVIOR
    # ============================================================

    def _register_accordion_item(self, item) -> None:
        self._accordion_items.append(item)
        item.toggled.connect(
            lambda expanded, source=item: self._accordion_changed(source, expanded)
        )

    def _accordion_changed(self, source, expanded: bool) -> None:
        # Panels are intentionally independent. The user decides which
        # cards/panels stay expanded or collapsed; expanding one never
        # forces another panel to close.
        return

    # ============================================================
    # THEME
    # ============================================================

    def apply_theme(self, theme: str) -> None:
        if theme not in ("dark", "light"):
            theme = "dark"

        self.current_theme = theme

        base_qss = DARK_QSS if theme == "dark" else LIGHT_QSS
        accent_qss = """
        QFrame#aiCard {
            border: 1px solid #1f6feb;
            border-radius: 14px;
        }
        QLabel#brandLogo {
            min-width: 36px;
            max-width: 36px;
            min-height: 36px;
            max-height: 36px;
        }
        QLabel#brandTagline {
            color: #6fa8dc;
            font-size: 8px;
            font-weight: 700;
            letter-spacing: 1px;
        }
        QLabel#scanVisual {
            color: #58a6ff;
            font-size: 30px;
            font-weight: 700;
            min-height: 42px;
        }
        QLabel#panelResizeHandle {
            color: #4c86b8;
            font-size: 9px;
            padding: 0;
            background: transparent;
        }
        QToolButton#collapseHeader {
            font-size: 16px;
            font-weight: 650;
            padding: 2px 0;
        }
        QLabel#sectionTitle {
            font-size: 15px;
            font-weight: 700;
        }
        QTextBrowser#recentHistory {
            border: none;
            background: transparent;
            padding: 0;
        }
        QProgressBar {
            min-height: 10px;
            max-height: 10px;
            border-radius: 5px;
            background: #0b2036;
        }
        QPushButton#primaryButton {
            border: 1px solid #248eff;
            border-radius: 10px;
            padding: 9px 16px;
            font-weight: 650;
        }
        QFrame#infoColumn {
            background: transparent;
        }
        QFrame#infoColumnSeparator {
            color: #263a55;
            background: #263a55;
            max-width: 1px;
        }
        QLabel#infoColumnTitle {
            color: #79b8ff;
            font-size: 13px;
            font-weight: 650;
        }
        QLabel#infoColumnValue {
            color: #edf2fa;
            font-size: 20px;
            font-weight: 700;
        }
        QLabel#infoDetailKey {
            color: #8ea0b7;
        }
        QLabel#infoDetailValue {
            color: #d7e2f2;
        }
        QPushButton#primaryButton:hover {
            border-color: #58a6ff;
            padding-left: 18px;
            padding-right: 18px;
        }
        QListWidget::item:hover {
            background: rgba(31, 111, 235, 0.15);
        }

        QToolButton#collapseHeader {
            border: none;
            background: transparent;
            color: #58a6ff;
            font-size: 17px;
            font-weight: 600;
            padding: 4px 0;
        }
        QToolButton#collapseHeader:hover {
            color: #79c0ff;
        }
        QLabel#panelLoader {
            color: #58a6ff;
            font-size: 18px;
            font-weight: 700;
            min-width: 20px;
        }
        QLabel#aiTitle {
            color: #58a6ff;
            font-size: 18px;
            font-weight: 600;
        }
        QTextBrowser#aiOutput {
            border: 1px solid #30363d;
            border-radius: 10px;
            padding: 10px;
        }
        QFrame#helpStepCard {
            border: 1px solid #30363d;
            border-radius: 12px;
            background: rgba(8, 18, 32, 0.72);
        }
        QLabel#helpStepTitle {
            color: #58a6ff;
            font-size: 17px;
            font-weight: 650;
        }
        QLineEdit {
            border: 1px solid #30363d;
            border-radius: 9px;
            padding: 9px 12px;
        }
        QProgressBar::chunk {
            background: #1f6feb;
            border-radius: 6px;
        }
        """
        if theme == "light":
            accent_qss += """
            QFrame#aiCard { border-color: #0969da; }
            QToolButton#collapseHeader { color: #0969da; }
            QFrame#infoColumnSeparator { color: #d0d7de; background: #d0d7de; }
            QLabel#infoColumnTitle { color: #0969da; }
            QLabel#infoColumnValue { color: #182235; }
            QLabel#infoDetailKey { color: #60708a; }
            QLabel#infoDetailValue { color: #25344a; }
            QLabel#panelLoader { color: #0969da; }
            QTextBrowser#aiOutput, QLineEdit { border-color: #c7d0d9; }
            QProgressBar::chunk { background: #0969da; }
            QFrame#helpStepCard { border-color: #c7d0d9; background: #f6f8fa; }
            QLabel#helpStepTitle { color: #0969da; }
            QLabel#scanVisual { color: #0969da; }
            QLabel#brandTagline { color: #477ea8; }
            QProgressBar { background: #e6eef6; }
            """
        self.setStyleSheet(base_qss + accent_qss)

        self.theme_button.setText(
            "☀  Light"
            if theme == "dark"
            else "☾  Dark"
        )

        shadow_color = (
            QColor(0, 0, 0, 105)
            if theme == "dark"
            else QColor(0, 0, 0, 55)
        )

        self.system_information_panel.set_shadow_color(shadow_color)

        save_theme(theme)

    def toggle_theme(self) -> None:
        self.apply_theme(
            "light"
            if self.current_theme == "dark"
            else "dark"
        )

    # ============================================================
    # START SCAN
    # ============================================================

    def start_scan(self) -> None:
        # While a diagnosis is running, the same button acts as Cancel.
        if (
            self.scan_manager.worker is not None
            and self.scan_manager.worker.isRunning()
        ):
            self._cancel_diagnosis()
            return

        # Explain the expected Command Prompt / PowerShell windows before
        # starting any diagnostic commands.
        note = QMessageBox(self)
        note.setIcon(QMessageBox.Icon.Information)
        note.setWindowTitle("Before Diagnosis Starts")
        note.setText(
            "Command Prompt or PowerShell windows may briefly open and close "
            "during diagnosis."
        )
        note.setInformativeText(
            "This is normal. Some Windows diagnostic checks run through command-line "
            "tools. Please ignore those brief windows and do not close them manually. "
            "FixMate-AI will continue the diagnosis automatically."
        )
        start_btn = note.addButton(
            "Start Diagnosis",
            QMessageBox.ButtonRole.AcceptRole,
        )
        note.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        note.exec()

        if note.clickedButton() is not start_btn:
            return

        # A new scan supersedes any previous result/AI context.
        self.last_scan_result = None
        self.completed_scan_stages = []
        self.cancelled_scan = False
        self.current_scan_stage = None
        self._prepare_diagnostic_finding_placeholders()
        if not self.scan_manager.start():
            return

        self.scan_started_iso = datetime.now().astimezone().isoformat(timespec="seconds")

        worker = self.scan_manager.worker
        if worker is None:
            return

        worker.progress.connect(self._scan_progress)
        worker.output.connect(self._scan_output)
        worker.finished.connect(self._scan_finished)
        worker.failed.connect(self._scan_failed)

        self.progress.setValue(0)
        self.percent_label.setText("0%")
        self.scan_status.setText("Diagnosis in progress — 0%")
        self.start_button.setText("Cancel Diagnosis")
        self.start_button.setEnabled(True)
        self.scan_panel.set_status("Running")
        self.scan_panel.set_loading(True)
        self._set_scan_visual_mode("system")
        self.stage_label.setText(
            "Current analysis: Starting full system diagnosis..."
        )
        self.eta_label.setText("Estimated time: Calculating...")
        self.result_label.clear()

        # Keep the main action available as a Cancel control while the
        # diagnosis worker is running.
        self.start_button.setText("Cancel Diagnosis")
        self.start_button.setEnabled(True)

        # A new scan invalidates the previous AI analysis. AI must be
        # started explicitly by the user after this scan finishes.
        # AI is optional, but the Analyze button stays available so the user
        # gets an explicit "AI not configured" message when no key exists.
        self.ai_analyze_button.setEnabled(False)
        self.ai_panel.set_status(self._ai_ready_status())
        self.ai_output.setPlainText("AI analysis has not been started. Run the scan first, then click 'Analyze with FixMate AI'.")
        self.ai_input.setEnabled(False)
        self.ai_send_button.setEnabled(False)

        self.scan_start_time = time.monotonic()
        self.last_progress = 0
        self.progress_history = [
            (self.scan_start_time, 0)
        ]

        self.eta_timer.start()

        worker.start()


    def _prepare_diagnostic_finding_placeholders(self) -> None:
        if self.diagnosis_finding_panels:
            for panel in self.diagnosis_finding_panels.values():
                panel.set_status("Waiting")
                panel.set_result("Waiting for this diagnostic check…", "PENDING", "Not checked yet.", "This check will be evaluated during the running diagnosis.", "No action until the check completes.")
            return
        # Build lightweight bars before the first scan result exists.
        titles = (
            "System Information", "Hardware", "System Resources", "Process Analysis",
            "GPU Diagnostics", "Thermal Diagnostics", "Storage Diagnostics", "Battery Diagnosis",
            "Driver Diagnostics", "Network Diagnostics", "Windows Health", "Startup Diagnostics",
        )
        for title in titles:
            panel = DiagnosticFindingPanel(title, self)
            panel.set_status("Waiting")
            panel.set_result("Waiting for this diagnostic check…", "PENDING", "Not checked yet.", "This check will be evaluated during the running diagnosis.", "No action until the check completes.", "Waiting")
            self.diagnosis_findings_layout.addWidget(panel)
            self.diagnosis_finding_panels[title] = panel
    # ============================================================
    # PROGRESS
    # ============================================================

    def _scan_progress(
        self,
        value: int,
        message: str,
    ) -> None:
        value = max(0, min(100, int(value)))

        # Never allow progress to move backwards.
        value = max(value, self.last_progress)
        self.last_progress = value

        now = time.monotonic()

        if not self.progress_history or value != self.progress_history[-1][1]:
            self.progress_history.append((now, value))

        self.progress.setValue(value)
        self.percent_label.setText(f"{value}%")
        self.stage_label.setText(
            f"Current analysis: {message}"
        )
        self._set_scan_visual_mode(message)

        if value < 100:
            self.scan_status.setText(
                f"Diagnosis in progress — {value}%"
            )
            self.scan_panel.set_status(f"{value}%")
            self._mark_diagnostic_stage_progress(message)

            # Safety net: if the worker advances directly over a milestone,
            # mark every earlier diagnostic phase as completed rather than
            # incorrectly showing it as cancelled later.
            milestones = (
                (8, "System Information"),
                (16, "Hardware"),
                (24, "System Resources"),
                (32, "Process Analysis"),
                (42, "GPU Diagnostics"),
                (50, "Thermal Diagnostics"),
                (60, "Storage Diagnostics"),
                (70, "Battery Diagnosis"),
                (78, "Driver Diagnostics"),
                (84, "Network Diagnostics"),
                (90, "Windows Health"),
                (94, "Startup Diagnostics"),
            )
            for milestone, title in milestones:
                if value >= milestone and title not in self.completed_scan_stages:
                    panel = self.diagnosis_finding_panels.get(title)
                    if panel is not None:
                        # Do not overwrite an actively checking stage.
                        current = self.current_scan_stage
                        if current != title:
                            panel.set_status("Completed")
                            panel.set_result(
                                f"{title} completed before cancellation/checkpoint.",
                                "COMPLETED",
                                "This diagnostic stage completed before a later progress milestone.",
                                "Detailed evidence is finalized and displayed when the full scan completes.",
                                "Run the full diagnosis to generate the final detailed evidence summary.",
                                "Completed",
                            )
                    if current != title:
                        self.completed_scan_stages.append(title)

        self._update_eta()


    def _mark_diagnostic_stage_progress(self, message: str) -> None:
        text = str(message).lower()
        mapping = (
            ("system information", "System Information"),
            ("hardware", "Hardware Diagnostics"),
            ("resource", "System Resources"),
            ("process", "Process Analysis"),
            ("gpu", "GPU Diagnostics"),
            ("thermal", "Thermal Diagnostics"),
            ("storage", "Storage Diagnostics"),
            ("battery", "Battery Diagnosis"),
            ("driver", "Driver Diagnostics"),
            ("network", "Network Diagnostics"),
            ("windows", "Windows Health"),
            ("startup", "Startup Diagnostics"),
        )
        current_title = next((title for keyword, title in mapping if keyword in text), None)
        if not current_title:
            return

        # When a progress message jumps over one or more phases, treat the
        # skipped earlier phases as completed. This is important because some
        # hardware/system checks can finish too quickly to produce a separate
        # GUI progress signal even though the diagnostic function actually ran.
        order = [title for _, title in mapping]
        current_index = order.index(current_title)
        previous_index = order.index(self.current_scan_stage) if self.current_scan_stage in order else -1

        for idx in range(previous_index + 1, current_index):
            skipped_title = order[idx]
            skipped_panel = self.diagnosis_finding_panels.get(skipped_title)
            if skipped_panel is not None:
                skipped_panel.set_status("Completed")
                skipped_panel.set_result(
                    f"{skipped_title} completed before the next diagnostic stage.",
                    "COMPLETED",
                    "The diagnostic stage finished before the next progress milestone was emitted.",
                    "Final evidence is available after a complete scan; this stage did execute before the scan moved forward.",
                    "Complete the diagnosis to view the full evidence summary.",
                    "Completed",
                )
            if skipped_title not in self.completed_scan_stages:
                self.completed_scan_stages.append(skipped_title)

        # The previously active phase is complete when the scan advances.
        if self.current_scan_stage and self.current_scan_stage != current_title:
            previous = self.diagnosis_finding_panels.get(self.current_scan_stage)
            if previous is not None:
                previous.set_status("Completed")
            if self.current_scan_stage not in self.completed_scan_stages:
                self.completed_scan_stages.append(self.current_scan_stage)

        self.current_scan_stage = current_title
        panel = self.diagnosis_finding_panels.get(current_title)
        if panel is not None:
            panel.set_status("Checking")
            panel.summary_label.setText(
                f"{current_title} is currently being checked."
            )
            panel.set_result(
                f"Checking {current_title.lower()}…",
                "PENDING",
                "The diagnostic engine is currently collecting evidence.",
                f"Current scan stage: {message}",
                "No corrective action until this check completes.",
                "Checking",
            )

    # ============================================================
    # SCAN VISUALS
    # ============================================================

    def _set_scan_visual_mode(self, message: str) -> None:
        text = str(message).lower()
        if "storage" in text:
            mode = "storage"
        elif "gpu" in text:
            mode = "gpu"
        elif "cpu" in text or "process" in text:
            mode = "cpu"
        elif "memory" in text or "resource" in text:
            mode = "memory"
        elif "battery" in text:
            mode = "battery"
        elif "network" in text:
            mode = "network"
        elif "windows" in text or "startup" in text:
            mode = "windows"
        elif "completed" in text:
            mode = "completed"
        else:
            mode = "system"

        if mode == self._scan_visual_mode and self.scan_visual_timer.isActive():
            return

        self._scan_visual_mode = mode
        self._scan_visual_index = 0

        if mode == "completed":
            self.scan_visual_timer.stop()
            self.scan_visual.setText("✓")
            return

        frames = {
            "system": ("◌", "◍", "◎", "◍"),
            "cpu": ("◈", "◇", "◆", "◇"),
            "gpu": ("◉", "◍", "●", "◍"),
            "memory": ("▱", "▰", "▱", "▰"),
            "storage": ("◒", "◐", "◓", "◑"),
            "battery": ("▱", "▰", "▰", "▱"),
            "network": ("◌", "↗", "◌", "↙"),
            "windows": ("⊞", "⊡", "⊞", "⊡"),
        }
        self._scan_visual_frames = frames.get(mode, frames["system"])
        self.scan_visual_timer.start()
        self._advance_scan_visual()

    def _advance_scan_visual(self) -> None:
        frames = getattr(self, "_scan_visual_frames", ("◌", "◍", "◎", "◍"))
        self.scan_visual.setText(frames[self._scan_visual_index % len(frames)])
        self._scan_visual_index += 1

    # ============================================================
    # LIVE OUTPUT
    # ============================================================

    def _scan_output(self, text: str) -> None:
        # ScanManager already converts actual full_scan output into
        # phase progress. This signal is intentionally lightweight.
        lower = text.lower()

        stages = (
            ("system information", "Checking System Information"),
            ("hardware information", "Checking Hardware"),
            ("system diagnostics", "Analyzing System Resources"),
            ("process analysis", "Analyzing Running Processes"),
            ("gpu diagnostics", "Diagnosing GPU"),
            ("thermal diagnostics", "Checking Thermal Sensors"),
            ("storage diagnostics", "Scanning Storage"),
            ("battery diagnosis", "Checking Battery"),
            ("driver", "Checking Drivers"),
            ("network", "Testing Network"),
            ("windows health", "Checking Windows Health"),
            ("startup", "Checking Startup"),
            ("report", "Generating Diagnosis Report"),
        )

        for keyword, stage in stages:
            if keyword in lower:
                self.stage_label.setText(
                    f"Current analysis: {stage}"
                )
                break

    # ============================================================
    # ETA
    # ============================================================

    def _update_eta(self) -> None:
        if self.scan_start_time is None:
            return

        progress = self.progress.value()

        if progress >= 100:
            return

        elapsed = time.monotonic() - self.scan_start_time

        # Before meaningful progress exists, there is not enough data
        # for a reliable ETA.
        if progress < 5 or elapsed < 2:
            self.eta_label.setText(
                "Estimated time: Calculating..."
            )
            return

        # Use the latest progress samples rather than the very first
        # sample. This prevents a slow first phase from making the ETA
        # wildly inaccurate.
        samples = self.progress_history[-8:]

        if len(samples) >= 2:
            first_time, first_progress = samples[0]
            last_time, last_progress = samples[-1]

            delta_progress = last_progress - first_progress
            delta_time = last_time - first_time

            if delta_progress > 0 and delta_time > 0:
                rate = delta_progress / delta_time
            else:
                rate = 0.0
        else:
            rate = 0.0

        # Fallback to overall observed rate.
        if rate <= 0:
            rate = progress / elapsed

        if rate <= 0:
            self.eta_label.setText(
                "Estimated time: Calculating..."
            )
            return

        remaining = (100 - progress) / rate

        # Prevent an obviously noisy ETA from jumping to hours.
        remaining = max(1, min(remaining, 15 * 60))

        minutes = int(remaining // 60)
        seconds = int(remaining % 60)

        if minutes:
            text = f"~{minutes}m {seconds:02d}s remaining"
        else:
            text = f"~{seconds}s remaining"

        self.eta_label.setText(
            f"Estimated time: {text}"
        )

    def _cancel_diagnosis(self) -> None:
        """Safely request cancellation without terminating the GUI/thread forcibly."""
        worker = self.scan_manager.worker
        if worker is None or not worker.isRunning():
            self.start_button.setText("Run Full Diagnosis")
            self.start_button.setEnabled(True)
            return

        reply = QMessageBox.question(
            self,
            "Cancel Diagnosis",
            "Are you sure you want to cancel the current diagnosis?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.cancelled_scan = True
        self.start_button.setText("Cancelling...")
        self.start_button.setEnabled(False)
        self.scan_status.setText("Stopping diagnosis safely...")
        self.stage_label.setText("Current analysis: Cancelling diagnosis")

        # Mark the currently active stage as canceled; anything before it has
        # already been completed when the scan advanced to the current stage.
        current = self.current_scan_stage
        for title, panel in self.diagnosis_finding_panels.items():
            if title in self.completed_scan_stages:
                panel.set_status("Completed")
                # Keep the information already gathered for this stage visible.
                # If no final result was available, provide a truthful interim
                # explanation instead of leaving a confusing PENDING state.
                if panel._labels.get("severity") and panel._labels["severity"].text() in {"PENDING", "—"}:
                    panel.set_result(
                        f"{title} completed before the scan was cancelled.",
                        "COMPLETED",
                        "The stage executed before cancellation; the final aggregate evidence is only produced at the end of a complete scan.",
                        "Partial diagnostic execution completed. No final fault summary was created because the overall scan was cancelled.",
                        "Run the diagnosis again to generate the complete evidence and recommendation summary.",
                        "Completed",
                    )
                continue
            if title == current:
                panel.set_status("Cancelled")
                panel.summary_label.setText(f"{title} was cancelled before completion.")
            else:
                panel.set_status("Cancelled")
                panel.summary_label.setText(f"{title} was not run because the diagnosis was cancelled.")

        try:
            worker.requestInterruption()
        except Exception:
            pass
        try:
            worker.quit()
        except Exception:
            pass

        # Do not call wait() or terminate() here. The worker owns the scan and
        # will finish/stop on its own; the GUI stays alive and responsive.
        QTimer.singleShot(100, self._finish_cancel_ui)

    def _finish_cancel_ui(self) -> None:
        """Reset UI after a cancellation request without killing the app."""
        try:
            self.eta_timer.stop()
        except Exception:
            pass
        self.scan_start_time = None
        self.scan_status.setText("Diagnosis cancelled")
        self.stage_label.setText("Current analysis: Diagnosis cancelled")
        self.eta_label.setText("Estimated time: —")
        self.start_button.setText("Run Full Diagnosis")
        self.start_button.setEnabled(True)
        try:
            self.scan_panel.set_status("Cancelled")
            self.scan_panel.set_loading(False)
        except Exception:
            pass
        try:
            self._set_scan_visual_mode("idle")
        except Exception:
            pass

    # ============================================================
    # FINISHED
    # ============================================================

    def _scan_finished(self, result) -> None:
        if self.cancelled_scan:
            self._finish_cancel_ui()
            return
        self.eta_timer.stop()

        self.progress.setValue(100)
        self.percent_label.setText("100%")
        self.scan_status.setText(
            "Diagnosis completed successfully"
        )
        self.scan_panel.set_status("Completed")
        self.scan_panel.set_loading(False)
        self._set_scan_visual_mode("completed")
        self.stage_label.setText(
            "Current analysis: Diagnosis completed"
        )
        self.eta_label.setText(
            "Estimated time: Completed"
        )

        self.start_button.setText("Run Full Diagnosis")
        self.start_button.setEnabled(True)
        self.scan_start_time = None

        if not isinstance(result, dict):
            self.result_label.setText(
                "Diagnosis completed, but no structured "
                "diagnostic result was returned."
            )
            return

        if self.current_scan_stage and self.current_scan_stage not in self.completed_scan_stages:
            panel = self.diagnosis_finding_panels.get(self.current_scan_stage)
            if panel is not None:
                panel.set_status("Completed")
            self.completed_scan_stages.append(self.current_scan_stage)
        self._update_dashboard(result)
        self.last_scan_result = result
        self._populate_diagnostic_findings(result)

        # Persist every completed scan locally. Saving history never blocks
        # or invalidates the live diagnosis/AI workflow.
        try:
            history_record = save_diagnosis(result, self.scan_started_iso)
            self.current_history_id = history_record.get("id")
            self.result_label.setText(
                self.result_label.text() +
                f"    |    Saved to History: {history_record.get('report_name', 'Yes')}"
            )
        except Exception as exc:
            # The diagnosis remains valid even if persistence fails.
            self.result_label.setText(
                self.result_label.text() +
                f"    |    History save failed: {exc}"
            )
        self.scan_started_iso = None
        self.completed_scan_stages = []
        self.cancelled_scan = False
        self.current_scan_stage = None
        self.ai_conversation = []
        has_key = bool(get_saved_api_key())
        self.ai_panel.set_status("Ready to analyze" if has_key else "AI not configured")
        self.ai_output.setPlainText(
            "The diagnosis is complete. Click 'Analyze with FixMate AI' to verify the OpenRouter key and then start AI analysis."
            if has_key
            else
            "The diagnosis is complete. FixMate AI is optional. Add an OpenRouter API key in AI Settings to enable AI analysis; the local diagnosis works without one."
        )
        # Keep the Analyze button clickable even when AI is not configured.
        # Clicking it explains the setup state instead of silently doing nothing.
        self.ai_analyze_button.setEnabled(True)
        self.ai_input.setEnabled(False)
        self.ai_send_button.setText("Ask AI")
        self.ai_send_button.setEnabled(False)


    # ============================================================
    # DIAGNOSTIC FINDINGS
    # ============================================================

    def _clear_diagnostic_findings(self) -> None:
        self.diagnosis_finding_panels.clear()
        while self.diagnosis_findings_layout.count():
            item = self.diagnosis_findings_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    @staticmethod
    def _flatten_fault_text(fault: dict) -> str:
        parts = []
        for key in ("component", "problem", "fault_type", "assessment"):
            value = fault.get(key)
            if value:
                parts.append(str(value))
        return " ".join(parts).lower()

    @staticmethod
    def _format_list(value, fallback="Not provided") -> str:
        if isinstance(value, (list, tuple)):
            vals = [str(v) for v in value if str(v).strip()]
            return "; ".join(vals) if vals else fallback
        if value is None:
            return fallback
        return str(value)

    def _populate_diagnostic_findings(self, result: dict) -> None:
        self._clear_diagnostic_findings()
        faults = result.get("faults", []) if isinstance(result, dict) else []
        faults = faults if isinstance(faults, list) else []

        stage_defs = (
            ("System Information", ("system",), "startup information, Windows version, CPU identity, memory and storage snapshot"),
            ("Hardware", ("hardware", "gpu"), "hardware inventory and device health"),
            ("System Resources", ("diagnostics",), "CPU and memory resource pressure"),
            ("Process Analysis", ("top_cpu", "top_memory"), "running-process CPU and memory consumption"),
            ("GPU Diagnostics", ("gpu",), "GPU telemetry, driver and device state"),
            ("Thermal Diagnostics", ("thermal",), "available thermal sensors and temperature observations"),
            ("Storage Diagnostics", ("storage",), "physical disk and volume health/free-space checks"),
            ("Battery Diagnosis", ("battery",), "battery health, charge, wear and runtime indicators"),
            ("Driver Diagnostics", ("drivers",), "Windows device/driver status and problem codes"),
            ("Network Diagnostics", ("network",), "connectivity, latency and packet-loss checks"),
            ("Windows Health", ("windows_health",), "DISM/SFC, update service and pending-reboot checks"),
            ("Startup Diagnostics", ("startup",), "startup entries, targets, publishers and signatures"),
        )

        self._diagnostic_stage_key_by_name = {}
        for title, keys, scope in stage_defs:
            panel = DiagnosticFindingPanel(title, self)
            panel.set_status("Checked")
            self.diagnosis_findings_layout.addWidget(panel)
            self.diagnosis_finding_panels[title] = panel
            self._diagnostic_stage_key_by_name[title] = keys

            relevant = []
            for fault in faults:
                text = self._flatten_fault_text(fault)
                title_words = set(title.lower().replace("diagnostics", "").replace("diagnosis", "").split())
                if any(word in text for word in title_words if len(word) > 3):
                    relevant.append(fault)

            component_data = {k: result.get(k) for k in keys}
            stage_status = self._stage_status_from_data(component_data, relevant)
            summary, severity, cause, evidence, cure = self._stage_details(title, component_data, relevant, scope)
            panel.set_result(summary, severity, cause, evidence, cure, stage_status)

    def _stage_status_from_data(self, data: dict, faults: list) -> str:
        if faults:
            severities = {str(f.get("severity", "")).upper() for f in faults}
            if "CRITICAL" in severities:
                return "Critical issue"
            if "HIGH" in severities:
                return "Issue found"
            if "MODERATE" in severities:
                return "Attention"
            return "Warning / Advisory"
        if any(v not in (None, {}, [], "") for v in data.values()):
            return "Checked"
        return "No data"

    @staticmethod
    def _pretty_value(value, unit: str = "") -> str:
        if value is None or value == "":
            return "Not available"
        if isinstance(value, bool):
            text = "Yes" if value else "No"
        elif isinstance(value, float):
            text = f"{value:.2f}".rstrip("0").rstrip(".")
        else:
            text = str(value)
        return f"{text}{unit}"

    @staticmethod
    def _format_info_lines(items: list[tuple[str, object]]) -> str:
        lines = []
        for label, value in items:
            if value is None or value == "":
                continue
            if isinstance(value, (dict, list, tuple)):
                if isinstance(value, dict):
                    value = "; ".join(f"{k}: {v}" for k, v in value.items())
                else:
                    value = "; ".join(str(v) for v in value)
            lines.append(f"{label}: {value}")
        return "\n".join(lines) if lines else "No detailed evidence was returned by this diagnostic check."

    def _stage_details(self, title: str, data: dict, faults: list, scope: str):
        """Create user-facing, evidence-based details without changing the diagnostic engine."""
        if faults:
            primary = max(
                faults,
                key=lambda f: {
                    "CRITICAL": 4,
                    "HIGH": 3,
                    "MODERATE": 2,
                    "LOW": 1,
                }.get(str(f.get("severity", "LOW")).upper(), 0),
            )
            severity = str(primary.get("severity") or "LOW").upper()
            summary = str(primary.get("problem") or primary.get("assessment") or f"{title} issue detected")
            cause = self._format_list(primary.get("causes"), "Review the evidence below; the diagnostic engine did not provide a separate cause.")
            evidence = str(primary.get("evidence") or "Deterministic FixMate diagnostic signal.")
            cure = self._format_list(
                primary.get("recommendations"),
                "Review the evidence, apply the relevant corrective action, then run the diagnosis again.",
            )
            return summary, severity, cause, evidence, cure

        severity = "NORMAL"
        summary = f"{title} completed"
        cause = "No deterministic fault was reported for this check."
        evidence = scope
        cure = "No corrective action required. Re-run the diagnosis if a related symptom returns."

        if title == "System Information":
            info = data.get("system") or {}
            if isinstance(info, dict):
                cpu = info.get("cpu_name") or info.get("processor_name") or info.get("cpu")
                windows = info.get("windows_display_name") or info.get("windows_name") or info.get("os")
                summary = f"System snapshot ready — {cpu or windows or 'Windows PC'}"
                evidence = self._format_info_lines([
                    ("Windows", windows),
                    ("Version", info.get("windows_version") or info.get("version")),
                    ("Build", info.get("windows_build") or info.get("build")),
                    ("Architecture", info.get("architecture") or info.get("system_architecture")),
                    ("Computer", info.get("computer_name") or info.get("hostname")),
                    ("CPU", cpu),
                    ("CPU cores", info.get("cpu_physical_cores") or info.get("physical_cores")),
                    ("CPU threads", info.get("cpu_logical_cores") or info.get("logical_cores")),
                    ("CPU frequency", self._pretty_value(info.get("cpu_frequency_mhz"), " MHz") if info.get("cpu_frequency_mhz") else info.get("cpu_frequency")),
                    ("RAM", self._pretty_value(info.get("ram_gb"), " GB") if info.get("ram_gb") else info.get("memory")),
                ])
                cure = "Informational snapshot only; no corrective action is required."

        elif title == "Hardware":
            hw = data.get("hardware") or {}
            gpu = data.get("gpu") or {}
            if isinstance(hw, dict):
                evidence = self._format_info_lines([
                    ("Processor", hw.get("cpu_name") or hw.get("processor")),
                    ("CPU", hw.get("cpu") if isinstance(hw.get("cpu"), str) else None),
                    ("Physical cores", hw.get("physical_cores") or hw.get("cpu_physical_cores")),
                    ("Logical cores", hw.get("logical_cores") or hw.get("cpu_logical_cores")),
                    ("RAM", hw.get("ram") or hw.get("memory")),
                    ("GPU", hw.get("gpu_name") or (gpu.get("name") if isinstance(gpu, dict) else None)),
                    ("Storage", hw.get("storage")),
                ])

        elif title == "System Resources":
            diag = data.get("diagnostics") or {}
            if isinstance(diag, dict):
                cpu = diag.get("cpu") or diag.get("cpu_usage")
                memory = diag.get("memory") or diag.get("memory_usage")
                cpu_usage = cpu.get("usage_percent") if isinstance(cpu, dict) else None
                mem_usage = memory.get("usage_percent") if isinstance(memory, dict) else None
                summary = "CPU and memory resources checked"
                evidence = self._format_info_lines([
                    ("CPU usage", self._pretty_value(cpu_usage, "%") if cpu_usage is not None else cpu),
                    ("Memory usage", self._pretty_value(mem_usage, "%") if mem_usage is not None else memory),
                    ("CPU status", cpu.get("status") if isinstance(cpu, dict) else None),
                    ("Memory status", memory.get("status") if isinstance(memory, dict) else None),
                ])

        elif title == "Process Analysis":
            top_cpu = data.get("top_cpu")
            top_mem = data.get("top_memory")
            evidence = self._format_info_lines([
                ("Top CPU consumer", top_cpu.get("process_name") if isinstance(top_cpu, dict) else top_cpu),
                ("Top CPU usage", self._pretty_value(top_cpu.get("cpu_percent"), "%") if isinstance(top_cpu, dict) and top_cpu.get("cpu_percent") is not None else None),
                ("Top memory consumer", top_mem.get("process_name") if isinstance(top_mem, dict) else top_mem),
                ("Top memory usage", self._pretty_value(top_mem.get("memory_percent"), "%") if isinstance(top_mem, dict) and top_mem.get("memory_percent") is not None else None),
            ])
            summary = "Running-process resource usage checked"

        elif title == "GPU Diagnostics":
            gpu = data.get("gpu") or {}
            if isinstance(gpu, dict):
                temp = gpu.get("temperature_c") or gpu.get("temperature")
                usage = gpu.get("gpu_usage_percent") or gpu.get("usage_percent")
                summary = f"GPU diagnostics completed — {gpu.get('name') or gpu.get('gpu_name') or 'GPU'}"
                evidence = self._format_info_lines([
                    ("GPU", gpu.get("name") or gpu.get("gpu_name")),
                    ("Vendor", gpu.get("vendor") or gpu.get("manufacturer")),
                    ("Driver", gpu.get("driver_version") or gpu.get("driver")),
                    ("Temperature", self._pretty_value(temp, " °C") if temp is not None else None),
                    ("Usage", self._pretty_value(usage, "%") if usage is not None else None),
                    ("VRAM", gpu.get("vram_gb") or gpu.get("memory")),
                    ("Status", gpu.get("status") or gpu.get("health")),
                ])

        elif title == "Thermal Diagnostics":
            thermal = data.get("thermal") or {}
            summary = "Thermal sensors checked"
            if isinstance(thermal, dict):
                evidence = self._format_info_lines([
                    ("Overall status", thermal.get("overall_status") or thermal.get("status")),
                    ("CPU temperature", thermal.get("cpu_temperature") or thermal.get("cpu_temp_c")),
                    ("GPU temperature", thermal.get("gpu_temperature") or thermal.get("gpu_temp_c")),
                    ("Available sensors", thermal.get("available_sensors") or thermal.get("sensor_count")),
                    ("Note", thermal.get("note") or thermal.get("message")),
                ])
                if not evidence or evidence.startswith("Overall status: Not available"):
                    evidence = "Thermal telemetry was checked using the sensors available to Windows on this PC."

        elif title == "Storage Diagnostics":
            storage = data.get("storage") or {}
            if isinstance(storage, dict):
                vol = storage.get("system_volume") or {}
                device = (storage.get("devices") or [{}])[0]
                if isinstance(vol, dict):
                    free_pct = vol.get("free_percent")
                    summary = f"Storage check complete — {self._pretty_value(free_pct, '%')} free on {vol.get('drive', 'system drive')}"
                evidence = self._format_info_lines([
                    ("System drive", vol.get("drive")),
                    ("Capacity", f"{vol.get('size_gb')} GB" if vol.get("size_gb") is not None else None),
                    ("Used", f"{vol.get('used_gb')} GB" if vol.get("used_gb") is not None else None),
                    ("Free", f"{vol.get('free_gb')} GB" if vol.get("free_gb") is not None else None),
                    ("Free space", self._pretty_value(vol.get("free_percent"), "%") if vol.get("free_percent") is not None else None),
                    ("Physical disk", device.get("name") if isinstance(device, dict) else None),
                    ("Media", device.get("media_type") if isinstance(device, dict) else None),
                    ("Bus", device.get("bus_type") if isinstance(device, dict) else None),
                    ("Health", device.get("health") if isinstance(device, dict) else None),
                ])

        elif title == "Battery Diagnosis":
            battery = data.get("battery") or {}
            if isinstance(battery, dict):
                health = battery.get("health_percent") or battery.get("health")
                summary = f"Battery diagnostics completed — health {health}%" if health is not None else "Battery diagnostics completed"
                evidence = self._format_info_lines([
                    ("Health", self._pretty_value(health, "%") if health is not None else None),
                    ("Charge", battery.get("charge_percent") or battery.get("charge")),
                    ("Design capacity", battery.get("design_capacity_mwh")),
                    ("Full charge capacity", battery.get("full_charge_capacity_mwh")),
                    ("Wear", battery.get("wear_percent") or battery.get("wear")),
                    ("Cycles", battery.get("cycle_count") or battery.get("cycles")),
                    ("Status", battery.get("status") or battery.get("battery_status")),
                ])

        elif title == "Driver Diagnostics":
            drivers = data.get("drivers") or {}
            if isinstance(drivers, dict):
                findings = drivers.get("findings") or drivers.get("devices") or drivers.get("issues") or []
                count = len(findings) if isinstance(findings, list) else 0
                summary = f"Driver check completed — {count} reported item(s)" if count else "Driver check completed — no reported driver items"
                if isinstance(findings, list) and findings:
                    items = []
                    for item in findings[:8]:
                        if isinstance(item, dict):
                            name = item.get("device_name") or item.get("name") or item.get("device") or "Driver item"
                            code = item.get("problem_code") or item.get("code")
                            sev = item.get("severity") or item.get("status")
                            extra = f" — Code {code}" if code is not None else ""
                            extra += f" — {sev}" if sev else ""
                            items.append(f"{name}{extra}")
                        else:
                            items.append(str(item))
                    evidence = "Reported driver/device items:\n" + "\n".join(f"• {x}" for x in items)
                else:
                    evidence = "No driver/device problem items were returned by the driver diagnostic module."

        elif title == "Network Diagnostics":
            network = data.get("network") or {}
            if isinstance(network, dict):
                latency = network.get("latency_ms") or network.get("ping_ms")
                loss = network.get("packet_loss_percent") or network.get("packet_loss")
                summary = "Network connectivity check completed"
                evidence = self._format_info_lines([
                    ("Interface", network.get("interface") or network.get("adapter") or network.get("active_adapter")),
                    ("Connection", network.get("connection_type") or network.get("type")),
                    ("Latency", self._pretty_value(latency, " ms") if latency is not None else None),
                    ("Packet loss", self._pretty_value(loss, "%") if loss is not None else None),
                    ("Gateway", network.get("gateway")),
                    ("DNS", network.get("dns")),
                    ("Status", network.get("status") or network.get("overall_status")),
                ])

        elif title == "Windows Health":
            health = data.get("windows_health") or {}
            if isinstance(health, dict):
                summary = "Windows health checks completed"
                evidence = self._format_info_lines([
                    ("DISM", health.get("dism") or health.get("dism_status")),
                    ("SFC", health.get("sfc") or health.get("sfc_status")),
                    ("Pending reboot", health.get("pending_reboot")),
                    ("Windows Update", health.get("windows_update") or health.get("update_service")),
                    ("Overall", health.get("overall_status") or health.get("status")),
                ])

        elif title == "Startup Diagnostics":
            startup = data.get("startup") or {}
            if isinstance(startup, dict):
                entries = startup.get("entries") or []
                task_count = len(startup.get("scheduled_tasks") or []) if isinstance(startup.get("scheduled_tasks"), list) else startup.get("scheduled_tasks_count", 0)
                summary = f"Startup check completed — {len(entries) if isinstance(entries, list) else 0} startup item(s)"
                evidence = self._format_info_lines([
                    ("Startup entries", len(entries) if isinstance(entries, list) else None),
                    ("Scheduled tasks", task_count),
                    ("Overall status", startup.get("overall_status") or startup.get("status")),
                ])

        return summary, severity, cause, evidence, cure

    # ============================================================
    # AI DIAGNOSIS
    # ============================================================

    def _ai_action_button_clicked(self) -> None:
        if self.ai_worker is not None and self.ai_worker.isRunning():
            self._cancel_ai_request()
            return
        self._send_ai_message()

    def _start_ai_analysis_from_button(self) -> None:
        # This button intentionally remains clickable even when no API key is
        # configured. The handler will show "AI not configured" instead of
        # silently disabling the feature.
        if not self.last_scan_result:
            self.ai_panel.set_status("Run diagnosis first")
            self.ai_output.setPlainText(
                "Run a full diagnosis first. AI analysis uses the completed diagnostic result."
            )
            return
        self._start_ai_analysis(self.last_scan_result)

    def _start_ai_analysis(self, result: dict) -> None:
        if self.ai_worker is not None and self.ai_worker.isRunning():
            return

        api_key = get_saved_api_key()
        if not api_key:
            self.ai_panel.set_status("AI not configured")
            self.ai_output.setPlainText(
                "AI not configured. No OpenRouter API key is available.\n\n"
                "Open AI Settings → add an OpenRouter API key, then click "
                "Analyze with FixMate AI again.\n\n"
                "Your local FixMate-AI diagnosis continues to work without AI."
            )
            # Keep this button enabled. AI is optional, and the user can retry
            # immediately after configuring a key.
            self.ai_analyze_button.setEnabled(True)
            return

        # First verify the key/model. Only after a successful test do we
        # start the actual analysis request.
        self.ai_panel.set_status("Verifying API key")
        self.ai_analyze_button.setEnabled(False)
        self.ai_input.setEnabled(False)
        self.ai_send_button.setEnabled(False)
        self.ai_output.setPlainText(
            "Checking the OpenRouter API key and selected model…\n\n"
            "AI analysis will start only after the connection test passes."
        )
        worker = AITestWorker(api_key, get_saved_model(), self)
        self.ai_test_worker = worker
        worker.finished.connect(lambda text: self._ai_key_test_finished(True, text, result))
        worker.failed.connect(lambda text: self._ai_key_test_finished(False, text, result))
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.start()

    def _ai_key_test_finished(self, ok: bool, text: str, result: dict) -> None:
        self.ai_test_worker = None
        # Settings may have been changed while the test was running. Re-check
        # configuration before starting the real analysis request.
        if not get_saved_api_key():
            self.ai_panel.set_status("AI not configured")
            self.ai_output.setPlainText(
                "AI not configured. The API key is no longer available, so AI analysis was not started."
            )
            self.ai_analyze_button.setEnabled(True)
            self.ai_send_button.setText("Ask AI")
            self.ai_send_button.setEnabled(False)
            return
        if not ok:
            self.ai_panel.set_status("Connection failed")
            self.ai_output.setPlainText(
                "OpenRouter connection test failed, so AI analysis was not started.\n\n"
                + text
                + "\n\nYou can fix the API key/model in AI Settings. The local diagnosis is still available."
            )
            self.ai_analyze_button.setEnabled(True)
            self.ai_input.setEnabled(False)
            self.ai_send_button.setText("Ask AI")
            self.ai_send_button.setEnabled(False)
            return
        self._start_ai_analysis_after_key_test(result)

    def _start_ai_analysis_after_key_test(self, result: dict) -> None:
        self.ai_panel.set_status("Analyzing")
        self.ai_analyze_button.setEnabled(False)
        self.ai_input.setEnabled(False)
        self.ai_send_button.setText("Cancel")
        self.ai_send_button.setEnabled(True)
        self.ai_output.setPlainText(
            "OpenRouter connection verified ✓\n\n"
            "FixMate AI is analyzing the complete diagnostic evidence…\n\n"
            "You can cancel this request at any time."
        )
        self._ai_partial_stream = ""

        self.ai_worker = AIWorker("analysis", result, parent=self)
        self.ai_worker.chunk.connect(self._ai_stream_chunk)
        self.ai_worker.finished.connect(self._ai_analysis_finished)
        self.ai_worker.failed.connect(self._ai_analysis_failed)
        self.ai_worker.cancelled.connect(self._ai_analysis_cancelled)
        self.ai_worker.start()

    def _ai_stream_chunk(self, text: str) -> None:
        # The streamed tokens naturally create a typewriter effect. Keep a
        # plain-text buffer during generation so the UI remains responsive.
        self._ai_partial_stream += text
        self.ai_output.setPlainText(
            "FixMate AI is typing…\n\n" + self._ai_partial_stream
        )
        bar = self.ai_output.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _start_ai_typing(self, text: str, *, prefix: str = "", mode: str = "analysis") -> None:
        self.ai_typing_timer.stop()
        self._ai_typing_text = text
        self._ai_typing_index = 0
        self._ai_typing_prefix = prefix
        self._ai_typing_mode = mode
        self.ai_output.setPlainText(prefix)
        self.ai_typing_timer.start()

    def _type_next_ai_character(self) -> None:
        if self._ai_typing_index >= len(self._ai_typing_text):
            self.ai_typing_timer.stop()
            if self._ai_typing_mode == "analysis":
                self.ai_output.setMarkdown(self._ai_typing_text)
            self._finish_ai_ui_state()
            return
        step = 2 if len(self._ai_typing_text) > 1200 else 1
        self._ai_typing_index = min(
            len(self._ai_typing_text), self._ai_typing_index + step
        )
        self.ai_output.setPlainText(
            self._ai_typing_prefix + self._ai_typing_text[: self._ai_typing_index]
        )
        bar = self.ai_output.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _finish_ai_ui_state(self) -> None:
        self.ai_panel.set_status("Ready" if get_saved_api_key() else "AI not configured")
        self.ai_analyze_button.setEnabled(self.last_scan_result is not None)
        self.ai_input.setEnabled(self.last_scan_result is not None)
        self.ai_send_button.setText("Ask AI")
        self.ai_send_button.setEnabled(self.last_scan_result is not None)

    def _ai_analysis_finished(self, answer: str) -> None:
        self.ai_conversation.append({"role": "assistant", "content": answer})
        self._persist_ai_analysis(answer)
        self._ai_typing_mode = "analysis"
        self._start_ai_typing(answer, mode="analysis")
        self._cleanup_ai_worker()

    def _persist_ai_analysis(self, answer: str) -> None:
        if not self.current_history_id:
            return
        try:
            update_ai_analysis(
                int(self.current_history_id),
                answer,
                list(self.ai_conversation),
            )
            self.result_label.setText(
                self.result_label.text() + "    |    AI analysis saved to report/history"
            )
        except Exception as exc:
            self.result_label.setText(
                self.result_label.text() + f"    |    AI save failed: {exc}"
            )

    def _ai_analysis_failed(self, error: str) -> None:
        self.ai_typing_timer.stop()
        self.ai_panel.set_status("Needs setup" if "API key" in error or "key" in error.lower() else "Unavailable")
        self.ai_output.setPlainText(
            "FixMate scan is complete, but AI analysis could not be started.\n\n"
            + error
            + "\n\nThe local diagnostic result is still available and the scan/report are not affected."
        )
        self.ai_analyze_button.setEnabled(self.last_scan_result is not None)
        self.ai_input.setEnabled(False)
        self.ai_send_button.setText("Ask AI")
        self.ai_send_button.setEnabled(False)
        self._cleanup_ai_worker()

    def _ai_analysis_cancelled(self) -> None:
        self.ai_typing_timer.stop()
        self.ai_panel.set_status("Cancelled")
        self.ai_output.setPlainText(
            "AI analysis was cancelled by you.\n\n"
            "The local diagnosis is still complete and available."
        )
        self.ai_analyze_button.setEnabled(self.last_scan_result is not None)
        self.ai_input.setEnabled(False)
        self.ai_send_button.setText("Ask AI")
        self.ai_send_button.setEnabled(False)
        self._cleanup_ai_worker()

    def _cleanup_ai_worker(self, *_args) -> None:
        worker = self.ai_worker
        if worker is not None:
            worker.deleteLater()
            self.ai_worker = None

    def _cancel_ai_request(self) -> None:
        worker = self.ai_worker
        if worker is None or not worker.isRunning():
            return
        self.ai_send_button.setEnabled(False)
        self.ai_panel.set_status("Cancelling…")
        worker.cancel()

    def _send_ai_message(self) -> None:
        message = self.ai_input.text().strip()
        if not message or not self.last_scan_result:
            return
        if self.ai_worker is not None and self.ai_worker.isRunning():
            return
        if not get_saved_api_key():
            self.ai_panel.set_status("AI not configured")
            self.ai_output.append(
                "\n\nAI is not configured. Open AI Settings and add an OpenRouter API key, then run Analyze with FixMate AI."
            )
            self.ai_send_button.setText("Ask AI")
            self.ai_send_button.setEnabled(False)
            self.ai_analyze_button.setEnabled(self.last_scan_result is not None)
            return

        self.ai_conversation.append({"role": "user", "content": message})
        self.ai_input.clear()
        self.ai_panel.set_status("Thinking")
        self.ai_send_button.setText("Cancel")
        self.ai_send_button.setEnabled(True)
        self.ai_analyze_button.setEnabled(False)
        self._ai_partial_stream = ""
        existing = self.ai_output.toPlainText()
        self.ai_output.setPlainText(existing + f"\n\nYou: {message}\n\nFixMate AI: ")

        self.ai_worker = AIWorker(
            "chat",
            self.last_scan_result,
            conversation=self.ai_conversation[:-1],
            message=message,
            parent=self,
        )
        self.ai_worker.chunk.connect(self._ai_chat_chunk)
        self.ai_worker.finished.connect(self._ai_chat_finished)
        self.ai_worker.failed.connect(self._ai_chat_failed)
        self.ai_worker.cancelled.connect(self._ai_chat_cancelled)
        self.ai_worker.start()

    def _ai_chat_chunk(self, text: str) -> None:
        self._ai_partial_stream += text
        cursor = self.ai_output.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self.ai_output.setTextCursor(cursor)
        bar = self.ai_output.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _ai_chat_finished(self, answer: str) -> None:
        self.ai_conversation.append({"role": "assistant", "content": answer})
        self._finish_ai_ui_state()
        self._cleanup_ai_worker()

    def _ai_chat_failed(self, error: str) -> None:
        self.ai_panel.set_status("Unavailable")
        self.ai_output.append("\n\n<b>AI error:</b> " + error)
        if self.ai_conversation and self.ai_conversation[-1].get("role") == "user":
            self.ai_conversation.pop()
        self.ai_send_button.setText("Ask AI")
        self.ai_send_button.setEnabled(self.last_scan_result is not None)
        self.ai_input.setEnabled(self.last_scan_result is not None)
        self.ai_analyze_button.setEnabled(self.last_scan_result is not None)
        self._cleanup_ai_worker()

    def _ai_chat_cancelled(self) -> None:
        self.ai_panel.set_status("Cancelled")
        self.ai_output.append("\n\nAI response cancelled by you.")
        if self.ai_conversation and self.ai_conversation[-1].get("role") == "user":
            self.ai_conversation.pop()
        self.ai_send_button.setText("Ask AI")
        self.ai_send_button.setEnabled(self.last_scan_result is not None)
        self.ai_input.setEnabled(self.last_scan_result is not None)
        self.ai_analyze_button.setEnabled(self.last_scan_result is not None)
        self._cleanup_ai_worker()

    # DASHBOARD RESULT
    # ============================================================

    def _update_dashboard(self, result: dict) -> None:
        # The dashboard information panel is intentionally information-only.
        # Refresh it from the latest structured scan snapshot when available.
        if isinstance(result, dict):
            scan_system = result.get("system")
            if isinstance(scan_system, dict) and scan_system:
                merged = dict(self.system_snapshot) if isinstance(self.system_snapshot, dict) else {}
                merged.update(scan_system)
                self.system_snapshot = merged
                self.system_information_panel.set_snapshot(merged)

        severity = result.get("severity", {}) if isinstance(result, dict) else {}
        overall = self._extract_overall_severity(severity)
        faults = result.get("faults", []) if isinstance(result, dict) else []
        faults = faults if isinstance(faults, list) else []
        issue_count = len(faults)
        critical_high = sum(1 for f in faults if str(f.get("severity", "")).upper() in {"CRITICAL", "HIGH", "MODERATE"})
        warnings = sum(1 for f in faults if str(f.get("severity", "")).upper() in {"LOW", "WARNING"})
        hardware_faults = sum(1 for f in faults if bool(f.get("hardware", False)))
        self.overall_health_value.setText(str(overall))
        self.problem_count_value.setText(str(critical_high))
        self.warning_count_value.setText(str(warnings))
        self.hardware_fault_value.setText(str(hardware_faults))
        self.result_label.setText(
            f"Overall diagnostic status: {overall}    |    Issues detected: {issue_count}"
        )

    # ============================================================
    # CARD DETAILS
    # ============================================================

    @staticmethod
    def _system_details(system) -> list[tuple[str, str]]:
        details = []

        if isinstance(system, dict):
            mapping = (
                ("Operating System", "os"),
                ("Release", "release"),
                ("Version", "version"),
                ("Architecture", "architecture"),
                ("Computer Name", "computer_name"),
                ("CPU", "cpu"),
                ("RAM", "ram"),
            )

            aliases = {
                "os": ("os", "system", "platform"),
                "architecture": ("architecture", "machine"),
                "computer_name": (
                    "computer_name",
                    "hostname",
                    "node",
                ),
            }

            for label, key in mapping:
                keys = aliases.get(key, (key,))
                value = MainWindow._first_value(
                    system,
                    *keys,
                )

                if value is not None:
                    details.append(
                        (label, str(value))
                    )

        if not details:
            details = [
                ("Operating System", platform.system()),
                ("Release", platform.release()),
                ("Architecture", platform.machine()),
                ("Computer Name", platform.node()),
            ]

        return details

    @staticmethod
    def _cpu_details(
        diagnostics,
        result,
        usage,
    ) -> list[tuple[str, str]]:
        details = [
            (
                "Current Usage",
                MainWindow._format_percent(
                    usage,
                    "Checked",
                ),
            ),
        ]

        data = {}

        if isinstance(diagnostics, dict):
            candidate = diagnostics.get(
                "cpu",
                {},
            )
            if isinstance(candidate, dict):
                data = candidate

        for label, keys in (
            # Keep the upper card informational only. Diagnostic
            # problems/warnings belong in the Diagnosis section below.
            ("Physical Cores", ("physical_cores", "cores")),
            ("Logical Cores", ("logical_cores", "threads")),
            ("Frequency", ("frequency", "freq_mhz")),
        ):
            value = MainWindow._first_value(
                data,
                *keys,
            )

            if value is not None:
                details.append(
                    (label, str(value))
                )

        if not any(
            label == "Physical Cores"
            for label, _ in details
        ):
            details.append(
                (
                    "Physical Cores",
                    str(
                        __import__("psutil").cpu_count(
                            logical=False
                        )
                    ),
                )
            )

        if not any(
            label == "Logical Cores"
            for label, _ in details
        ):
            details.append(
                (
                    "Logical Cores",
                    str(
                        __import__("psutil").cpu_count(
                            logical=True
                        )
                    ),
                )
            )

        return details

    @staticmethod
    def _memory_details(
        diagnostics,
        usage,
    ) -> list[tuple[str, str]]:
        details = [
            (
                "Current Usage",
                MainWindow._format_percent(
                    usage,
                    "Checked",
                ),
            ),
        ]

        data = {}

        if isinstance(diagnostics, dict):
            candidate = diagnostics.get(
                "memory",
                {},
            )
            if isinstance(candidate, dict):
                data = candidate

        for label, keys in (
            # Keep the upper card informational only. Diagnostic
            # problems/warnings belong in the Diagnosis section below.
            ("Total RAM", ("total_gb", "total")),
            ("Used RAM", ("used_gb", "used")),
            ("Free Memory", ("available_gb", "available", "free_gb")),
        ):
            value = MainWindow._first_value(
                data,
                *keys,
            )

            if value is not None:
                details.append(
                    (label, str(value))
                )

        return details

    @staticmethod
    def _storage_details(storage) -> list[tuple[str, str]]:
        if not isinstance(storage, dict):
            return [("Status", "Unavailable")]

        details = []

        devices = storage.get("devices", [])

        if isinstance(devices, list):
            for device in devices[:2]:
                if not isinstance(device, dict):
                    continue

                for label, key in (
                    ("Device", "name"),
                    ("Media", "media_type"),
                    ("Capacity", "size_gb"),
                    ("Bus", "bus_type"),
                    ("Firmware", "firmware"),
                ):
                    value = device.get(key)

                    if value is None:
                        continue

                    if key == "size_gb":
                        try:
                            value = f"{float(value):.2f} GB"
                        except (TypeError, ValueError):
                            pass

                    details.append(
                        (label, str(value))
                    )

                break

        volumes = storage.get("volumes", [])

        if isinstance(volumes, list):
            for volume in volumes:
                if not isinstance(volume, dict):
                    continue

                drive = str(
                    volume.get("drive", "")
                ).rstrip(":").upper()

                if not drive:
                    continue

                free = volume.get("free_percent")
                size = volume.get("size_gb")
                try:
                    free_text = f"{float(free):.1f}% free"
                except (TypeError, ValueError):
                    free_text = "Unknown"

                try:
                    size_text = f"{float(size):.1f} GB"
                except (TypeError, ValueError):
                    size_text = "Unknown size"

                details.append(
                    (
                        f"{drive}: Volume",
                        f"{free_text} • {size_text}",
                    )
                )

        return details

    @staticmethod
    def _first_value(data, *keys):
        if not isinstance(data, dict):
            return None

        for key in keys:
            value = data.get(key)

            if value is not None and str(value).strip():
                return value

        return None

    @staticmethod
    def _format_percent(value, fallback):
        if value is None:
            return fallback

        try:
            return f"{float(value):.1f}%"
        except (TypeError, ValueError):
            return str(value)

    # ============================================================
    # SEVERITY
    # ============================================================

    @staticmethod
    def _extract_overall_severity(severity) -> str:
        if isinstance(severity, str):
            return severity.upper()

        if isinstance(severity, dict):
            value = (
                severity.get("overall_severity")
                or severity.get("overall")
                or severity.get("severity")
                or severity.get("status")
            )

            if value:
                return str(value).upper()

        return "CHECKED"

    # ============================================================
    # FAILURE
    # ============================================================

    def _scan_failed(self, error_text: str) -> None:
        if self.cancelled_scan:
            self._finish_cancel_ui()
            return
        self.eta_timer.stop()
        self.scan_start_time = None

        self.start_button.setEnabled(True)
        self.start_button.setText("Run Full Diagnosis")

        self.scan_status.setText("Diagnosis failed")
        self.scan_panel.set_status("Failed")
        self.scan_panel.set_loading(False)
        self.stage_label.setText(
            "Current analysis: Scan failed"
        )
        self.eta_label.setText(
            "Estimated time: Failed"
        )

        QMessageBox.critical(
            self,
            "FixMate-AI — Diagnosis Failed",
            (
                "The diagnostic scan could not be completed.\n\n"
                f"{error_text}"
            ),
        )


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    window = MainWindow()
    window.show()

    raise SystemExit(app.exec())
