"""Diagnosis history and report persistence for FixMate-AI."""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from storage.database import DB_PATH, initialize_database, get_connection

APP_DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "FixMate-AI"
REPORTS_DIR = APP_DATA_DIR / "reports"
DATA_DIR = APP_DATA_DIR / "diagnosis_data"


def _ensure_schema() -> None:
    initialize_database()
    with get_connection() as conn:
        # Safe upgrades for the original Phase-1 diagnosis_history table.
        cols = {row[1] for row in conn.execute("PRAGMA table_info(diagnosis_history)").fetchall()}
        if "result_json_path" not in cols:
            conn.execute("ALTER TABLE diagnosis_history ADD COLUMN result_json_path TEXT")
        if "report_name" not in cols:
            conn.execute("ALTER TABLE diagnosis_history ADD COLUMN report_name TEXT")
        if "ai_analysis" not in cols:
            conn.execute("ALTER TABLE diagnosis_history ADD COLUMN ai_analysis TEXT")


def save_diagnosis(result: dict[str, Any], started_at: str | None = None) -> dict[str, Any]:
    """Persist a completed diagnosis and copy its HTML report into app storage."""
    _ensure_schema()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    completed = datetime.now().astimezone()
    completed_iso = completed.isoformat(timespec="seconds")
    stamp = completed.strftime("%Y-%m-%d_%H-%M-%S")

    report_path = str(result.get("html_report_path") or "").strip()
    report_dest = REPORTS_DIR / f"FixMate-AI_Report_{stamp}.html"
    if report_path and Path(report_path).exists():
        try:
            shutil.copy2(report_path, report_dest)
        except OSError:
            report_dest = Path(report_path)
    elif report_path:
        report_dest = Path(report_path)
    else:
        report_dest = REPORTS_DIR / f"FixMate-AI_Report_{stamp}.html"

    json_dest = DATA_DIR / f"FixMate-AI_Diagnosis_{stamp}.json"
    try:
        json_dest.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    except OSError:
        json_dest = DATA_DIR / f"FixMate-AI_Diagnosis_{stamp}.json"

    severity = result.get("severity", {})
    overall = "UNKNOWN"
    if isinstance(severity, dict):
        overall = str(
            severity.get("overall_severity")
            or severity.get("overall")
            or severity.get("severity")
            or "UNKNOWN"
        )
    faults = result.get("faults", [])
    issue_count = len(faults) if isinstance(faults, list) else 0
    started = started_at or completed_iso
    report_name = report_dest.name

    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO diagnosis_history
               (user_id, started_at, completed_at, overall_severity, issue_count,
                report_path, status, result_json_path, report_name)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (None, started, completed_iso, overall, issue_count, str(report_dest),
             "completed", str(json_dest), report_name),
        )
        row_id = int(cur.lastrowid)

    return {
        "id": row_id,
        "completed_at": completed_iso,
        "overall_severity": overall,
        "issue_count": issue_count,
        "report_path": str(report_dest),
        "result_json_path": str(json_dest),
        "report_name": report_name,
    }


def list_diagnoses(limit: int = 100) -> list[dict[str, Any]]:
    _ensure_schema()
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, started_at, completed_at, overall_severity, issue_count,
                      report_path, status, result_json_path, report_name
               FROM diagnosis_history ORDER BY id DESC LIMIT ?""",
            (max(1, min(int(limit), 500)),),
        ).fetchall()
    return [dict(row) for row in rows]


def load_result(row: dict[str, Any]) -> dict[str, Any] | None:
    path = str(row.get("result_json_path") or "").strip()
    if not path or not Path(path).exists():
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def update_ai_analysis(row_id: int, ai_analysis: str, conversation: list[dict[str, Any]] | None = None) -> bool:
    """Attach the completed AI analysis/chat context to an existing diagnosis record."""
    _ensure_schema()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT result_json_path, report_path FROM diagnosis_history WHERE id = ?",
            (int(row_id),),
        ).fetchone()
        if row is None:
            return False

        json_path = str(row[0] or "").strip()
        report_path = str(row[1] or "").strip()

        # Update the structured diagnosis JSON first.
        if json_path:
            path = Path(json_path)
            try:
                data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
                data["ai_analysis"] = ai_analysis
                if conversation:
                    data["ai_conversation"] = conversation
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
            except (OSError, json.JSONDecodeError):
                pass

        # Keep the human-readable HTML report synchronized with the AI result.
        if report_path:
            report = Path(report_path)
            if report.exists():
                try:
                    import html
                    from re import match

                    raw = str(ai_analysis or "").strip()
                    escaped = html.escape(raw).replace("\n", "<br>")
                    existing_html = report.read_text(encoding="utf-8")
                    marker = '<section id="fixmate-ai-analysis"'

                    section = (
                        '<section id="fixmate-ai-analysis" class="ai-report-section ai-ready">'
                        '<div class="ai-report-head">'
                        '<div class="ai-report-icon">✦</div>'
                        '<div>'
                        '<div class="ai-kicker">FIXMATE AI</div>'
                        '<h2>AI Diagnostic Analysis</h2>'
                        '<p>AI interpretation of the diagnostic evidence from this scan.</p>'
                        '</div>'
                        '<span class="ai-state">Analysis ready</span>'
                        '</div>'
                        f'<div class="ai-report-body">{escaped}</div>'
                        '</section>'
                    )

                    if marker in existing_html:
                        start = existing_html.index(marker)
                        # The generated AI section is self-contained and ends at the next closing section.
                        end = existing_html.index("</section>", start) + len("</section>")
                        existing_html = existing_html[:start] + section + existing_html[end:]
                    elif "</body>" in existing_html:
                        existing_html = existing_html.replace("</body>", section + "</body>", 1)
                    else:
                        existing_html += section

                    report.write_text(existing_html, encoding="utf-8")
                except (OSError, ValueError):
                    pass

        conn.execute(
            "UPDATE diagnosis_history SET ai_analysis = ? WHERE id = ?",
            (ai_analysis, int(row_id)),
        )
    return True



def delete_diagnosis(row_id: int) -> bool:
    """Delete a diagnosis record and its saved JSON/HTML files."""
    _ensure_schema()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT report_path, result_json_path FROM diagnosis_history WHERE id = ?",
            (int(row_id),),
        ).fetchone()
        if row is None:
            return False

        report_path = str(row[0] or "").strip()
        json_path = str(row[1] or "").strip()

        conn.execute("DELETE FROM diagnosis_history WHERE id = ?", (int(row_id),))

    for raw_path in (report_path, json_path):
        if not raw_path:
            continue
        try:
            path = Path(raw_path)
            if path.exists() and path.is_file():
                path.unlink()
        except OSError:
            pass

    return True
