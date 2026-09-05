"""History and Reports views for FixMate-AI.

Provides a searchable/filterable local diagnosis history and a more polished
Reports view with report preview, AI status, open, data, and delete actions.
"""
from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
)

from storage.history import delete_diagnosis, list_diagnoses, load_result


class HistoryDialog(QDialog):
    def __init__(self, parent=None, mode: str = "history"):
        super().__init__(parent)
        self.mode = mode
        is_reports = mode == "reports"
        self.setWindowTitle("FixMate-AI — Reports" if is_reports else "FixMate-AI — History")
        self.setMinimumSize(1050, 650)
        self.resize(1180, 720)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)

        heading = QLabel("Reports" if is_reports else "Diagnosis History")
        heading.setObjectName("pageTitle")
        root.addWidget(heading)
        subtitle = QLabel(
            "Search, filter and inspect saved diagnosis reports."
            if is_reports
            else "Every completed scan is stored locally with its date, severity, issue count and report."
        )
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        # Search/filter toolbar.
        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by date, severity, report name…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filters)
        toolbar.addWidget(self.search, 1)

        self.severity_filter = QComboBox()
        self.severity_filter.addItems(["All severities", "CRITICAL", "HIGH", "MODERATE", "LOW", "NORMAL", "UNKNOWN"])
        self.severity_filter.currentTextChanged.connect(self._apply_filters)
        toolbar.addWidget(self.severity_filter)

        clear_btn = QPushButton("Clear filters")
        clear_btn.clicked.connect(self._clear_filters)
        toolbar.addWidget(clear_btn)
        root.addLayout(toolbar)

        # Main split view.
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)

        left = QFrame()
        left.setObjectName("card")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(8)

        self.summary = QLabel("0 reports")
        self.summary.setObjectName("muted")
        left_layout.addWidget(self.summary)

        self.list = QListWidget()
        self.list.setMinimumWidth(410)
        self.list.currentItemChanged.connect(self._selected)
        left_layout.addWidget(self.list, 1)
        splitter.addWidget(left)

        right = QFrame()
        right.setObjectName("card")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(10)

        self.detail_title = QLabel("Select a saved report")
        self.detail_title.setObjectName("sectionTitle")
        right_layout.addWidget(self.detail_title)

        self.details = QTextBrowser()
        self.details.setOpenExternalLinks(False)
        self.details.setOpenLinks(False)
        right_layout.addWidget(self.details, 1)

        actions = QHBoxLayout()
        self.open_btn = QPushButton("Open Report")
        self.open_btn.clicked.connect(self._open_report)
        actions.addWidget(self.open_btn)

        self.open_data_btn = QPushButton("Open Diagnosis Data")
        self.open_data_btn.clicked.connect(self._open_data)
        actions.addWidget(self.open_data_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete_current)
        actions.addWidget(self.delete_btn)
        actions.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        actions.addWidget(close_btn)
        right_layout.addLayout(actions)

        splitter.addWidget(right)
        splitter.setSizes([430, 700])

        self.rows: list[dict] = []
        self.filtered_rows: list[dict] = []
        self.refresh()

    def refresh(self):
        self.rows = list_diagnoses(500)
        self._apply_filters()

    def _clear_filters(self):
        self.search.clear()
        self.severity_filter.setCurrentIndex(0)

    def _apply_filters(self):
        query = self.search.text().strip().lower() if hasattr(self, "search") else ""
        severity = self.severity_filter.currentText() if hasattr(self, "severity_filter") else "All severities"

        self.filtered_rows = []
        for row in self.rows:
            row_severity = str(row.get("overall_severity") or "UNKNOWN").upper()
            searchable = " ".join(
                str(row.get(key) or "")
                for key in ("completed_at", "started_at", "overall_severity", "report_name", "report_path", "status")
            ).lower()
            if query and query not in searchable:
                continue
            if severity != "All severities" and row_severity != severity:
                continue
            self.filtered_rows.append(row)

        self.list.clear()
        self.details.clear()
        self._set_action_state(False)
        self.summary.setText(f"{len(self.filtered_rows)} report" + ("" if len(self.filtered_rows) == 1 else "s"))

        for row in self.filtered_rows:
            item = QListWidgetItem(self._row_label(row))
            item.setData(Qt.ItemDataRole.UserRole, row)
            self.list.addItem(item)

        if self.filtered_rows:
            self.list.setCurrentRow(0)
        else:
            self.detail_title.setText("No matching reports")
            self.details.setHtml(
                '<div style="padding:18px;color:#94a5bf">No reports match the current search/filter.</div>'
            )

    @staticmethod
    def _row_label(row: dict) -> str:
        completed = str(row.get("completed_at") or row.get("started_at") or "Unknown")
        completed = completed.replace("T", " ")
        severity = str(row.get("overall_severity") or "UNKNOWN").upper()
        count = int(row.get("issue_count") or 0)
        ai = "AI" if row.get("ai_analysis") else "No AI"
        name = str(row.get("report_name") or "Saved report")
        return f"{completed}\n{name}\n{severity}  •  {count} issues  •  {ai}"

    def _selected(self, current, previous=None):
        if current is None:
            self.detail_title.setText("Select a saved report")
            self.details.clear()
            self._set_action_state(False)
            return
        row = current.data(Qt.ItemDataRole.UserRole) or {}
        result = load_result(row)
        report_path = Path(str(row.get("report_path") or ""))
        data_path = Path(str(row.get("result_json_path") or ""))
        self.detail_title.setText(str(row.get("report_name") or "Saved Report"))

        completed = row.get("completed_at") or row.get("started_at") or "Unknown"
        severity = str(row.get("overall_severity") or "UNKNOWN").upper()
        count = int(row.get("issue_count") or 0)
        ai = row.get("ai_analysis") or (result or {}).get("ai_analysis")
        ai_status = "Analyzed" if ai else "Not analyzed"

        # Friendly HTML preview instead of a plain text dump.
        fault_list = (result or {}).get("faults", []) if isinstance(result, dict) else []
        hardware_faults = len(
            [f for f in fault_list if isinstance(f, dict) and f.get("hardware")]
        ) if isinstance(fault_list, list) else 0
        cards = [
            ("Overall severity", html.escape(severity)),
            ("Issues detected", str(count)),
            ("Hardware faults", str(hardware_faults)),
            ("AI analysis", html.escape(ai_status)),
        ]
        stat_html = "".join(
            f'<td style="padding:8px 10px;border:1px solid #243246;border-radius:8px;">'
            f'<div style="font-size:12px;color:#94a5bf">{label}</div>'
            f'<div style="font-size:18px;font-weight:700;margin-top:3px">{value}</div></td>'
            for label, value in cards
        )

        ai_preview = ""
        if ai:
            ai_text = html.escape(str(ai)).replace("\n", "<br>")
            ai_preview = (
                '<h3 style="margin-top:20px;color:#79b8ff">✦ FixMate AI Analysis</h3>'
                f'<div style="padding:14px;border:1px solid #284160;border-radius:12px;line-height:1.55">{ai_text}</div>'
            )
        else:
            ai_preview = (
                '<div style="margin-top:18px;padding:12px;border-radius:10px;'
                'background:#121b2a;color:#94a5bf">FixMate AI analysis has not been run for this diagnosis.</div>'
            )

        self.details.setHtml(
            '<div style="font-family:Segoe UI;font-size:14px;line-height:1.45">'
            f'<div style="color:#94a5bf">Completed</div><div style="font-size:15px;margin-bottom:14px">{html.escape(str(completed).replace("T", " "))}</div>'
            f'<table width="100%" cellspacing="8" cellpadding="0"><tr>{stat_html}</tr></table>'
            f'<div style="margin-top:16px;color:#94a5bf">Saved report</div>'
            f'<div>{html.escape(str(report_path))}</div>'
            f'{ai_preview}'
            '</div>'
        )
        self._set_action_state(True, report_path.exists(), data_path.exists())

    def _set_action_state(self, selected: bool, report_exists: bool = False, data_exists: bool = False):
        self.open_btn.setEnabled(selected and report_exists)
        self.open_data_btn.setEnabled(selected and data_exists)
        self.delete_btn.setEnabled(selected)

    def _current_row(self):
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _open_report(self):
        row = self._current_row()
        if not row:
            return
        path = Path(str(row.get("report_path") or ""))
        if not path.exists():
            QMessageBox.warning(self, "Report Not Found", "The saved report file is no longer available.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_data(self):
        row = self._current_row()
        if not row:
            return
        path = Path(str(row.get("result_json_path") or ""))
        if not path.exists():
            QMessageBox.warning(self, "Diagnosis Data Not Found", "The saved diagnosis data is no longer available.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _delete_current(self):
        row = self._current_row()
        if not row:
            return
        report_name = str(row.get("report_name") or "this report")
        reply = QMessageBox.question(
            self,
            "Delete Report",
            f"Delete {report_name} and its saved diagnosis data?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if not delete_diagnosis(int(row.get("id"))):
            QMessageBox.warning(self, "Delete Failed", "The report could not be deleted.")
            return
        self.refresh()
