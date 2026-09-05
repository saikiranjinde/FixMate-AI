# ============================================================
# FIXMATE-AI
# Report UI Layer V3
# ============================================================
#
# Goals:
# 1. Better UI / UX
# 2. Easy-to-understand labels
# 3. Light / Dark theme with remembered preference
#
# Backend diagnosis data is consumed as-is.
# No external frontend dependency is required.
# ============================================================

from __future__ import annotations

from datetime import datetime
from html import escape
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


SEVERITY_ORDER = {
    "NORMAL": 0,
    "LOW": 1,
    "MODERATE": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}

SEVERITY_LABELS = {
    "NORMAL": "Healthy",
    "LOW": "Low",
    "MODERATE": "Moderate",
    "HIGH": "High",
    "CRITICAL": "Critical",
    "UNKNOWN": "Unknown",
}


def _text(value: Any, default: str = "N/A") -> str:
    if value is None:
        return default

    value = str(value).strip()

    return value if value else default


def _severity(value: Any) -> str:
    return _text(
        value,
        "UNKNOWN"
    ).upper()


def _severity_class(value: Any) -> str:
    severity = _severity(value).lower()

    if severity not in {
        "normal",
        "low",
        "moderate",
        "high",
        "critical",
        "unknown",
    }:
        return "unknown"

    return severity


def _severity_label(value: Any) -> str:
    severity = _severity(value)

    return SEVERITY_LABELS.get(
        severity,
        severity.title()
    )


def _safe_list(value: Any) -> List[Any]:
    return (
        value
        if isinstance(value, list)
        else []
    )


def _summary_count(
    summary: Dict[str, Any],
    key: str,
) -> int:

    try:
        return int(
            summary.get(
                key,
                0
            )
        )

    except (
        TypeError,
        ValueError
    ):
        return 0


def _human_fault_type(
    fault_type: Any
) -> str:

    key = _text(
        fault_type,
        "unknown"
    ).lower()

    mapping = {
        "resource_pressure":
            "System Resource Pressure",

        "application_resource_usage":
            "Application Resource Usage",

        "driver_problem":
            "Driver / Device Problem",

        "driver_warning":
            "Driver / Device Warning",

        "windows_system_issue":
            "Windows System Integrity",

        "windows_configuration":
            "Windows Configuration",

        "network_configuration":
            "Network Configuration",

        "network_connectivity":
            "Internet Connectivity",

        "dns_resolution":
            "DNS Resolution",

        "startup_configuration":
            "Startup Configuration",

        "startup_problem":
            "Startup Problem",
    }

    return mapping.get(
        key,
        key.replace(
            "_",
            " "
        ).title()
    )


def _friendly_component(
    component: Any
) -> str:

    value = _text(
        component,
        "Unknown Component"
    )

    prefixes = (
        "Application: ",
        "Driver: ",
        "Windows: ",
        "Startup: ",
        "Startup Task: ",
    )

    for prefix in prefixes:

        if value.startswith(prefix):
            return value[len(prefix):]

    return value


def _priority_text(
    severity: str
) -> str:

    severity = _severity(
        severity
    )

    if severity == "CRITICAL":
        return "Needs immediate attention."

    if severity == "HIGH":
        return "High-priority issue detected."

    if severity == "MODERATE":
        return "Review recommended."

    if severity == "LOW":
        return "Minor condition detected."

    if severity == "NORMAL":
        return "Operating normally."

    return "Further review may be required."


def _summary_cards(
    summary: Dict[str, Any]
) -> str:

    items = [
        (
            "Hardware",
            "hardware_faults",
            "hardware",
        ),
        (
            "Applications",
            "application_issues",
            "application",
        ),
        (
            "System Resources",
            "system_resource_issues",
            "resource",
        ),
        (
            "Driver Problems",
            "driver_problems",
            "driver",
        ),
        (
            "Driver Warnings",
            "driver_warnings",
            "warning",
        ),
        (
            "Windows System",
            "windows_system_issues",
            "windows",
        ),
        (
            "Windows Config",
            "windows_configuration_issues",
            "windows",
        ),
        (
            "Network",
            "network_issues",
            "network",
        ),
        (
            "Startup",
            "startup_issues",
            "startup",
        ),
        (
            "Other",
            "other_issues",
            "other",
        ),
    ]

    cards = []

    for label, key, icon in items:

        count = _summary_count(
            summary,
            key
        )

        cards.append(
            f"""
            <div class="metric-card metric-{escape(icon)}">
              <div class="metric-icon" aria-hidden="true">
                <span></span>
              </div>
              <div class="metric-copy">
                <span>{escape(label)}</span>
                <strong>{count}</strong>
              </div>
            </div>
            """
        )

    return "".join(cards)


def _status_card(
    label: str,
    status: str,
    detail: str = "",
) -> str:

    normalized = _severity(
        status
    )

    if normalized in (
        "HEALTHY",
        "OK",
        "NORMAL",
        "EXCELLENT",
    ):
        status_class = "healthy"

    elif normalized in (
        "LOW",
        "MINOR",
        "ADVISORY",
        "MODERATE",
        "WARNING",
    ):
        status_class = "warning"

    elif normalized in (
        "HIGH",
        "PROBLEM",
        "CRITICAL",
    ):
        status_class = "danger"

    else:
        status_class = "unknown"

    return f"""
    <div class="status-card {status_class}">
      <div class="status-dot"></div>
      <div class="status-copy">
        <span>{escape(label)}</span>
        <strong>{escape(status)}</strong>
        {f"<small>{escape(detail)}</small>" if detail else ""}
      </div>
    </div>
    """


def _fault_card(
    fault: Dict[str, Any],
    index: int,
    initially_open: bool = False,
) -> str:

    component_raw = _text(
        fault.get(
            "component"
        ),
        "Unknown Component"
    )

    component = escape(
        _friendly_component(
            component_raw
        )
    )

    severity = _severity(
        fault.get(
            "severity"
        )
    )

    severity_label = _severity_label(
        severity
    )

    fault_type = escape(
        _human_fault_type(
            fault.get(
                "fault_type"
            )
        )
    )

    confidence = escape(
        _text(
            fault.get(
                "confidence"
            ),
            "UNKNOWN"
        )
    )

    hardware = (
        "Detected"
        if fault.get(
            "hardware_fault",
            False
        )
        else "Not detected"
    )

    problem = escape(
        _text(
            fault.get(
                "problem"
            ),
            "No problem description available."
        )
    )

    evidence = escape(
        _text(
            fault.get(
                "evidence"
            ),
            "No evidence recorded."
        )
    )

    assessment = escape(
        _text(
            fault.get(
                "assessment"
            ),
            "No assessment recorded."
        )
    )

    causes = _safe_list(
        fault.get(
            "causes",
            fault.get(
                "possible_causes",
                []
            )
        )
    )

    recommendations = _safe_list(
        fault.get(
            "recommendations",
            []
        )
    )

    causes_html = "".join(
        f"<li>{escape(_text(item, 'N/A'))}</li>"
        for item in causes
    )

    recs_html = "".join(
        f"<li>{escape(_text(item, 'N/A'))}</li>"
        for item in recommendations
    )

    open_attr = (
        " open"
        if initially_open
        else ""
    )

    return f"""
    <details class="fault-card {_severity_class(severity)}"{open_attr}>
      <summary>
        <div class="fault-summary-left">
          <div class="priority-marker"></div>

          <div>
            <div class="fault-component">
              {component}
            </div>

            <div class="fault-type">
              {fault_type}
            </div>

            <div class="fault-short">
              {escape(_priority_text(severity))}
            </div>
          </div>
        </div>

        <div class="fault-summary-right">
          <span class="badge {_severity_class(severity)}">
            {escape(severity_label)}
          </span>

          <span class="chevron">
            ▾
          </span>
        </div>
      </summary>

      <div class="fault-body">

        <div class="meta-grid">
          <div class="meta-item">
            <span>Confidence</span>
            <strong>{confidence}</strong>
          </div>

          <div class="meta-item">
            <span>Hardware fault</span>
            <strong>{escape(hardware)}</strong>
          </div>
        </div>

        <section>
          <h4>What happened?</h4>
          <p>{problem}</p>
        </section>

        <section>
          <h4>Why it matters</h4>
          <p>{assessment}</p>
        </section>

        <section>
          <h4>Evidence</h4>
          <div class="evidence-box">
            {evidence}
          </div>
        </section>

        <section>
          <h4>Possible causes</h4>
          <ul>
            {causes_html or "<li>No causes recorded.</li>"}
          </ul>
        </section>

        <section>
          <h4>What should you do?</h4>
          <ol class="action-list">
            {recs_html or "<li>No recommended actions recorded.</li>"}
          </ol>
        </section>

      </div>
    </details>
    """


def _ai_report_section(ai_analysis: Any = None) -> str:
    """Render a dedicated FixMate AI section for the standalone HTML report.

    The section is always present so reports have a stable place for AI output.
    A later AI run can replace the same marker without rebuilding the report.
    """
    raw = str(ai_analysis or "").strip()
    if not raw:
        return """
        <section id="fixmate-ai-analysis" class="ai-report-section ai-pending">
          <div class="ai-report-head">
            <div class="ai-report-icon">✦</div>
            <div>
              <div class="ai-kicker">FIXMATE AI</div>
              <h2>AI Diagnostic Analysis</h2>
              <p>AI analysis has not been run for this diagnosis yet.</p>
            </div>
            <span class="ai-state">Not analyzed</span>
          </div>
          <div class="ai-report-note">
            Run <strong>Analyze with FixMate AI</strong> in the app to add an
            evidence-based explanation and step-by-step guidance here.
          </div>
        </section>
        """

    # Keep AI text safe while preserving line breaks. The report updater can
    # later replace this entire section with the same marker.
    escaped = escape(raw).replace("\n", "<br>")
    return f"""
    <section id="fixmate-ai-analysis" class="ai-report-section ai-ready">
      <div class="ai-report-head">
        <div class="ai-report-icon">✦</div>
        <div>
          <div class="ai-kicker">FIXMATE AI</div>
          <h2>AI Diagnostic Analysis</h2>
          <p>AI interpretation of the diagnostic evidence from this scan.</p>
        </div>
        <span class="ai-state">Analysis ready</span>
      </div>
      <div class="ai-report-body">{escaped}</div>
    </section>
    """


def build_html_report(
    report: Dict[str, Any],
    system: Optional[Dict[str, Any]] = None,
    scan_metadata: Optional[Dict[str, Any]] = None,
    status_overview: Optional[Dict[str, Any]] = None,
    ai_analysis: Optional[str] = None,
) -> str:
    """
    Build a standalone FixMate HTML dashboard with light/dark theme and subtle motion.

    Existing diagnosis data is preserved. The optional
    status_overview dictionary can provide friendly quick-status
    values for CPU, Memory, GPU, Storage, Battery, Drivers,
    Network, Windows and Startup.
    """

    system = (
        system
        if isinstance(
            system,
            dict
        )
        else {}
    )

    scan_metadata = (
        scan_metadata
        if isinstance(
            scan_metadata,
            dict
        )
        else {}
    )

    status_overview = (
        status_overview
        if isinstance(
            status_overview,
            dict
        )
        else {}
    )

    overall = _severity(
        report.get(
            "overall_severity",
            "UNKNOWN"
        )
    )

    fault_list = _safe_list(
        report.get(
            "faults",
            []
        )
    )

    faults = [
        fault
        for fault in fault_list
        if isinstance(
            fault,
            dict
        )
    ]

    faults.sort(
        key=lambda item:
            SEVERITY_ORDER.get(
                _severity(
                    item.get(
                        "severity"
                    )
                ),
                -1
            ),
        reverse=True
    )

    fault_count = report.get(
        "fault_count",
        len(faults)
    )

    try:
        fault_count = int(
            fault_count
        )
    except (
        TypeError,
        ValueError
    ):
        fault_count = len(
            faults
        )

    summary = report.get(
        "summary",
        {}
    )

    if not isinstance(
        summary,
        dict
    ):
        summary = {}

    assessment = escape(
        _text(
            report.get(
                "assessment"
            ),
            "No overall assessment available."
        )
    )

    generated_at = _text(
        scan_metadata.get(
            "generated_at"
        ),
        datetime.now()
        .astimezone()
        .strftime(
            "%Y-%m-%d %H:%M:%S %Z"
        )
    )

    computer_name = _text(
        system.get(
            "Computer Name",
            system.get(
                "computer_name"
            )
        ),
        "Unknown PC"
    )

    os_name = _text(
        system.get(
            "OS"
        ),
        "Windows"
    )

    os_version = _text(
        system.get(
            "OS Version",
            system.get(
                "os_version"
            )
        ),
        "N/A"
    )

    physical_cores = _text(
        system.get(
            "Physical Cores",
            system.get(
                "physical_cores"
            )
        )
    )

    logical_cores = _text(
        system.get(
            "Logical Cores",
            system.get(
                "logical_cores"
            )
        )
    )

    ram = _text(
        system.get(
            "RAM",
            system.get(
                "ram"
            )
        )
    )

    cpu_status = _text(
        status_overview.get(
            "cpu"
        ),
        "Available"
    )

    memory_status = _text(
        status_overview.get(
            "memory"
        ),
        "Available"
    )

    gpu_status = _text(
        status_overview.get(
            "gpu"
        ),
        "Available"
    )

    storage_status = _text(
        status_overview.get(
            "storage"
        ),
        "Available"
    )

    battery_status = _text(
        status_overview.get(
            "battery"
        ),
        "Available"
    )

    driver_status = _text(
        status_overview.get(
            "drivers"
        ),
        "Available"
    )

    network_status = _text(
        status_overview.get(
            "network"
        ),
        "Available"
    )

    windows_status = _text(
        status_overview.get(
            "windows"
        ),
        "Available"
    )

    startup_status = _text(
        status_overview.get(
            "startup"
        ),
        "Available"
    )

    priority_faults = [
        fault
        for fault in faults
        if _severity(
            fault.get(
                "severity"
            )
        ) in (
            "CRITICAL",
            "HIGH"
        )
    ]

    priority_faults = priority_faults[:3]

    priority_html = ""

    for index, fault in enumerate(
        priority_faults
    ):

        priority_html += _fault_card(
            fault,
            index=index + 1,
            initially_open=True
        )

    if not priority_html:

        priority_html = """
        <div class="success-banner">
          <div class="success-icon">✓</div>
          <div>
            <strong>No high-priority issues detected.</strong>
            <span>FixMate did not identify any Critical or High severity finding.</span>
          </div>
        </div>
        """

    detailed_faults = "".join(
        _fault_card(
            fault,
            index=index + 1,
            initially_open=False
        )
        for index, fault in enumerate(
            faults
        )
    )

    if not detailed_faults:

        detailed_faults = """
        <div class="success-banner">
          <div class="success-icon">✓</div>
          <div>
            <strong>No diagnostic issues recorded.</strong>
            <span>The current report contains no faults.</span>
          </div>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta
  name="viewport"
  content="width=device-width, initial-scale=1.0"
>
<meta
  name="color-scheme"
  content="light dark"
>

<title>FixMate-AI Diagnostic Report</title>

<style>
:root {{
  --bg: #f4f6f9;
  --surface: #ffffff;
  --surface-2: #f8fafc;
  --text: #182230;
  --muted: #687386;
  --border: #e2e7ee;
  --shadow: 0 10px 30px rgba(20, 30, 45, 0.08);

  --healthy-bg: #eaf8ef;
  --healthy-text: #176638;

  --low-bg: #edf4ff;
  --low-text: #2c5e9e;

  --moderate-bg: #fff5dc;
  --moderate-text: #896300;

  --high-bg: #ffeadb;
  --high-text: #9a4a00;

  --critical-bg: #ffe2e2;
  --critical-text: #9a2020;

  --accent: #2563eb;
}}

html[data-theme="dark"] {{
  --bg: #0f141b;
  --surface: #171d26;
  --surface-2: #111720;
  --text: #edf2f7;
  --muted: #9aa7b7;
  --border: #2a3442;
  --shadow: 0 14px 32px rgba(0, 0, 0, 0.24);

  --healthy-bg: #123b25;
  --healthy-text: #8ae0ab;

  --low-bg: #142943;
  --low-text: #96bcff;

  --moderate-bg: #443711;
  --moderate-text: #f2d67b;

  --high-bg: #4b2a12;
  --high-text: #ffbc82;

  --critical-bg: #4d1c1c;
  --critical-text: #ff9e9e;

  --accent: #79a7ff;
}}

/* ==============================
   V3 Motion & Interaction Layer
   ============================== */

@keyframes pageEnter {{
  from {{
    opacity: 0;
    transform: translateY(10px);
  }}
  to {{
    opacity: 1;
    transform: translateY(0);
  }}
}}

@keyframes cardEnter {{
  from {{
    opacity: 0;
    transform: translateY(12px) scale(0.985);
  }}
  to {{
    opacity: 1;
    transform: translateY(0) scale(1);
  }}
}}

@keyframes pulseDot {{
  0%, 100% {{
    box-shadow: 0 0 0 0 rgba(213, 166, 35, 0);
  }}
  50% {{
    box-shadow: 0 0 0 5px rgba(213, 166, 35, 0.14);
  }}
}}

@keyframes dangerPulse {{
  0%, 100% {{
    box-shadow: 0 0 0 0 rgba(209, 75, 75, 0);
  }}
  50% {{
    box-shadow: 0 0 0 5px rgba(209, 75, 75, 0.14);
  }}
}}

@keyframes badgeGlow {{
  0%, 100% {{
    transform: scale(1);
  }}
  50% {{
    transform: scale(1.025);
  }}
}}

@keyframes detailsReveal {{
  from {{
    opacity: 0;
    transform: translateY(-5px);
  }}
  to {{
    opacity: 1;
    transform: translateY(0);
  }}
}}

* {{
  box-sizing: border-box;
}}

html {{
  scroll-behavior: smooth;
}}

body {{
  margin: 0;
  background:
    radial-gradient(
      circle at top right,
      rgba(37, 99, 235, 0.08),
      transparent 30%
    ),
    var(--bg);
  color: var(--text);
  font-family:
    "Segoe UI",
    Inter,
    system-ui,
    -apple-system,
    Arial,
    sans-serif;
  line-height: 1.55;
}}

button {{
  font: inherit;
}}

.page {{
  width: min(
    1240px,
    calc(100% - 32px)
  );
  margin: 0 auto;
  padding: 22px 0 60px;
  animation: pageEnter 0.55s ease both;
}}

.topbar {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
  margin-bottom: 16px;
}}

.brand {{
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 800;
  letter-spacing: 0.10em;
  text-transform: uppercase;
}}

.brand-mark {{
  width: 30px;
  height: 30px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  color: white;
  background: var(--accent);
  font-size: 15px;
  letter-spacing: 0;
}}

.toolbar {{
  display: flex;
  align-items: center;
  gap: 8px;
}}

.theme-toggle {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  padding: 9px 12px;
  border-radius: 11px;
  cursor: pointer;
  box-shadow: var(--shadow);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}}

.theme-toggle:hover {{
  transform: translateY(-2px);
  box-shadow: 0 14px 30px rgba(20, 30, 45, 0.12);
}}

.theme-toggle:active {{
  transform: translateY(0) scale(0.98);
}}

.hero {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 22px;
  padding: 28px;
  box-shadow: var(--shadow);
  transition: transform 0.25s ease, box-shadow 0.25s ease;
}}

.hero:hover {{
  transform: translateY(-2px);
  box-shadow: 0 18px 40px rgba(20, 30, 45, 0.10);
}}

.hero-row {{
  display: flex;
  justify-content: space-between;
  gap: 25px;
  align-items: flex-start;
}}

h1 {{
  margin: 0;
  font-size: clamp(
    29px,
    4vw,
    40px
  );
  letter-spacing: -0.02em;
}}

.subtitle {{
  color: var(--muted);
  margin: 7px 0 0;
  max-width: 680px;
}}

.overall-panel {{
  min-width: 190px;
  text-align: right;
}}

.overall-panel span {{
  display: block;
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 7px;
}}

.overall-badge {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 10px 16px;
  border-radius: 999px;
  font-weight: 900;
  letter-spacing: 0.04em;
  animation: badgeGlow 2.8s ease-in-out infinite;
}}

.overall-badge.normal,
.overall-badge.low {{
  background: var(--healthy-bg);
  color: var(--healthy-text);
}}

.overall-badge.moderate {{
  background: var(--moderate-bg);
  color: var(--moderate-text);
}}

.overall-badge.high {{
  background: var(--high-bg);
  color: var(--high-text);
}}

.overall-badge.critical {{
  background: var(--critical-bg);
  color: var(--critical-text);
}}

.overall-badge.unknown {{
  background: var(--surface-2);
  color: var(--muted);
}}

.info-grid {{
  display: grid;
  grid-template-columns:
    repeat(
      auto-fit,
      minmax(180px, 1fr)
    );
  gap: 10px;
  margin-top: 23px;
}}

.info-item {{
  border: 1px solid var(--border);
  background: var(--surface-2);
  border-radius: 13px;
  padding: 13px;
  animation: cardEnter 0.5s ease both;
  transition: transform 0.2s ease, border-color 0.2s ease;
}}

.info-item:hover {{
  transform: translateY(-2px);
  border-color: var(--accent);
}}

.info-item:nth-child(1) {{ animation-delay: 0.08s; }}
.info-item:nth-child(2) {{ animation-delay: 0.12s; }}
.info-item:nth-child(3) {{ animation-delay: 0.16s; }}
.info-item:nth-child(4) {{ animation-delay: 0.20s; }}
.info-item:nth-child(5) {{ animation-delay: 0.24s; }}
.info-item:nth-child(6) {{ animation-delay: 0.28s; }}

.info-item span {{
  display: block;
  color: var(--muted);
  font-size: 11px;
  margin-bottom: 3px;
}}

.info-item strong {{
  font-size: 14px;
}}

.status-grid {{
  display: grid;
  grid-template-columns:
    repeat(
      auto-fit,
      minmax(155px, 1fr)
    );
  gap: 10px;
  margin-top: 18px;
}}

.status-card {{
  display: flex;
  gap: 10px;
  align-items: center;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 13px;
  padding: 12px;
  box-shadow: var(--shadow);
  animation: cardEnter 0.5s ease both;
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}}

.status-card:hover {{
  transform: translateY(-2px);
  border-color: var(--accent);
  box-shadow: 0 12px 28px rgba(20, 30, 45, 0.10);
}}

.status-card:nth-child(1) {{ animation-delay: 0.10s; }}
.status-card:nth-child(2) {{ animation-delay: 0.14s; }}
.status-card:nth-child(3) {{ animation-delay: 0.18s; }}
.status-card:nth-child(4) {{ animation-delay: 0.22s; }}
.status-card:nth-child(5) {{ animation-delay: 0.26s; }}
.status-card:nth-child(6) {{ animation-delay: 0.30s; }}
.status-card:nth-child(7) {{ animation-delay: 0.34s; }}
.status-card:nth-child(8) {{ animation-delay: 0.38s; }}
.status-card:nth-child(9) {{ animation-delay: 0.42s; }}

.status-dot {{
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex: 0 0 auto;
  background: var(--muted);
}}

.status-card.healthy .status-dot {{
  background: #2ea85d;
}}

.status-card.warning .status-dot {{
  background: #d5a623;
  animation: pulseDot 2.4s ease-in-out infinite;
}}

.status-card.danger .status-dot {{
  background: #d14b4b;
  animation: dangerPulse 1.8s ease-in-out infinite;
}}

.status-copy span {{
  display: block;
  color: var(--muted);
  font-size: 11px;
}}

.status-copy strong {{
  display: block;
  font-size: 13px;
  margin-top: 1px;
}}

.status-copy small {{
  display: block;
  margin-top: 2px;
  color: var(--muted);
  font-size: 10px;
}}

.section-title-row {{
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 15px;
  margin: 30px 0 12px;
}}

.section-title {{
  margin: 0;
  font-size: 23px;
}}

.section-subtitle {{
  margin: 2px 0 0;
  color: var(--muted);
  font-size: 13px;
}}

.metrics {{
  display: grid;
  grid-template-columns:
    repeat(
      auto-fit,
      minmax(170px, 1fr)
    );
  gap: 11px;
}}

.metric-card {{
  display: flex;
  gap: 12px;
  align-items: center;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 15px;
  padding: 14px;
  box-shadow: var(--shadow);
  animation: cardEnter 0.5s ease both;
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}}

.metric-card:hover {{
  transform: translateY(-3px);
  border-color: var(--accent);
  box-shadow: 0 14px 30px rgba(20, 30, 45, 0.11);
}}

.metric-card:nth-child(1) {{ animation-delay: 0.08s; }}
.metric-card:nth-child(2) {{ animation-delay: 0.12s; }}
.metric-card:nth-child(3) {{ animation-delay: 0.16s; }}
.metric-card:nth-child(4) {{ animation-delay: 0.20s; }}
.metric-card:nth-child(5) {{ animation-delay: 0.24s; }}
.metric-card:nth-child(6) {{ animation-delay: 0.28s; }}
.metric-card:nth-child(7) {{ animation-delay: 0.32s; }}
.metric-card:nth-child(8) {{ animation-delay: 0.36s; }}
.metric-card:nth-child(9) {{ animation-delay: 0.40s; }}
.metric-card:nth-child(10) {{ animation-delay: 0.44s; }}

.metric-icon {{
  width: 36px;
  height: 36px;
  border-radius: 11px;
  display: grid;
  place-items: center;
  background: var(--surface-2);
}}

.metric-icon span {{
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--accent);
}}

.metric-copy span {{
  display: block;
  color: var(--muted);
  font-size: 11px;
}}

.metric-copy strong {{
  display: block;
  font-size: 24px;
  line-height: 1.1;
  margin-top: 2px;
}}

.assessment {{
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 15px;
  padding: 17px;
  box-shadow: var(--shadow);
  animation: cardEnter 0.5s ease both;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}}

.assessment:hover {{
  transform: translateY(-2px);
  box-shadow: 0 15px 32px rgba(20, 30, 45, 0.10);
}}

.assessment-mark {{
  width: 34px;
  height: 34px;
  border-radius: 11px;
  display: grid;
  place-items: center;
  background: var(--low-bg);
  color: var(--low-text);
  font-weight: 900;
}}

.success-banner {{
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--healthy-bg);
  color: var(--healthy-text);
  border: 1px solid var(--border);
  border-radius: 15px;
  padding: 15px 17px;
}}

.success-banner strong {{
  display: block;
}}

.success-banner span {{
  display: block;
  margin-top: 2px;
  opacity: 0.85;
  font-size: 13px;
}}

.success-icon {{
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  background: rgba(255,255,255,0.22);
  font-weight: 900;
}}

.fault-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 4px solid var(--border);
  border-radius: 16px;
  margin: 11px 0;
  overflow: hidden;
  box-shadow: var(--shadow);
  animation: cardEnter 0.48s ease both;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}}

.fault-card:hover {{
  transform: translateY(-2px);
  box-shadow: 0 16px 34px rgba(20, 30, 45, 0.11);
}}

.fault-card:nth-child(1) {{ animation-delay: 0.06s; }}
.fault-card:nth-child(2) {{ animation-delay: 0.10s; }}
.fault-card:nth-child(3) {{ animation-delay: 0.14s; }}
.fault-card:nth-child(4) {{ animation-delay: 0.18s; }}
.fault-card:nth-child(5) {{ animation-delay: 0.22s; }}
.fault-card:nth-child(6) {{ animation-delay: 0.26s; }}
.fault-card:nth-child(7) {{ animation-delay: 0.30s; }}
.fault-card:nth-child(8) {{ animation-delay: 0.34s; }}
.fault-card:nth-child(9) {{ animation-delay: 0.38s; }}
.fault-card:nth-child(10) {{ animation-delay: 0.42s; }}

.fault-card.high {{
  border-left-color: #d4772f;
}}

.fault-card.critical {{
  border-left-color: #ce4f4f;
}}

.fault-card.moderate {{
  border-left-color: #c79b2d;
}}

.fault-card.low {{
  border-left-color: #5f8fd9;
}}

.fault-card.normal {{
  border-left-color: #4fa973;
}}

.fault-card summary {{
  list-style: none;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 15px;
  cursor: pointer;
  padding: 17px;
}}

.fault-card summary::-webkit-details-marker {{
  display: none;
}}

.fault-summary-left {{
  display: flex;
  gap: 12px;
  align-items: flex-start;
  min-width: 0;
}}

.priority-marker {{
  width: 8px;
  height: 8px;
  margin-top: 8px;
  border-radius: 50%;
  flex: 0 0 auto;
  background: var(--muted);
}}

.fault-card.high .priority-marker {{
  background: #d4772f;
}}

.fault-card.critical .priority-marker {{
  background: #ce4f4f;
}}

.fault-card.moderate .priority-marker {{
  background: #c79b2d;
}}

.fault-card.low .priority-marker {{
  background: #5f8fd9;
}}

.fault-component {{
  font-size: 17px;
  font-weight: 800;
}}

.fault-type {{
  color: var(--muted);
  font-size: 12px;
  margin-top: 2px;
}}

.fault-short {{
  color: var(--muted);
  font-size: 12px;
  margin-top: 7px;
}}

.fault-summary-right {{
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 0 0 auto;
}}

.badge {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 900;
}}

.badge.normal {{
  background: var(--healthy-bg);
  color: var(--healthy-text);
}}

.badge.low {{
  background: var(--low-bg);
  color: var(--low-text);
}}

.badge.moderate {{
  background: var(--moderate-bg);
  color: var(--moderate-text);
}}

.badge.high {{
  background: var(--high-bg);
  color: var(--high-text);
}}

.badge.critical {{
  background: var(--critical-bg);
  color: var(--critical-text);
}}

.badge.unknown {{
  background: var(--surface-2);
  color: var(--muted);
}}

.chevron {{
  color: var(--muted);
  transition: transform 0.18s ease;
}}

.fault-card[open] .chevron {{
  transform: rotate(180deg);
}}

.fault-card[open] .fault-body {{
  animation: detailsReveal 0.24s ease both;
}}

.fault-body {{
  padding: 0 17px 19px;
  border-top: 1px solid var(--border);
}}

.meta-grid {{
  display: grid;
  grid-template-columns:
    repeat(
      2,
      minmax(150px, 1fr)
    );
  gap: 10px;
  margin-top: 15px;
}}

.meta-item {{
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 11px;
  padding: 10px 12px;
}}

.meta-item span {{
  display: block;
  color: var(--muted);
  font-size: 10px;
}}

.meta-item strong {{
  display: block;
  margin-top: 2px;
  font-size: 12px;
}}

.fault-body section {{
  margin-top: 18px;
}}

.fault-body h4 {{
  margin: 0 0 6px;
  font-size: 13px;
}}

.fault-body p {{
  margin: 0;
}}

.fault-body ul,
.fault-body ol {{
  margin: 7px 0 0 20px;
}}

.evidence-box {{
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 11px;
  padding: 11px 12px;
  font-family:
    Consolas,
    "Courier New",
    monospace;
  font-size: 12px;
  overflow-wrap: anywhere;
}}

.action-list li {{
  margin-bottom: 5px;
}}

.footer {{
  margin-top: 30px;
  text-align: center;
  color: var(--muted);
  font-size: 11px;
}}

@media (max-width: 760px) {{
  .page {{
    width: min(
      100% - 20px,
      1240px
    );
    padding-top: 12px;
  }}

  .hero-row {{
    flex-direction: column;
  }}

  .overall-panel {{
    min-width: 0;
    text-align: left;
  }}

  .theme-toggle span {{
    display: none;
  }}

  .fault-card summary {{
    align-items: flex-start;
  }}
}}

@media (prefers-reduced-motion: reduce) {{
  html {{
    scroll-behavior: auto;
  }}

  *,
  *::before,
  *::after {{
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }}

  .chevron {{
    transition: none;
  }}
}}

.ai-report-section {{
  margin-top: 34px;
  padding: 22px;
  border: 1px solid var(--border);
  border-radius: 20px;
  background: linear-gradient(145deg, var(--surface), var(--surface-2));
  box-shadow: var(--shadow);
  position: relative;
  overflow: hidden;
}}

.ai-report-section::before {{
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: var(--accent);
}}

.ai-report-head {{
  display: flex;
  align-items: center;
  gap: 14px;
}}

.ai-report-icon {{
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border-radius: 14px;
  background: var(--low-bg);
  color: var(--accent);
  font-size: 22px;
  font-weight: 800;
  flex: 0 0 auto;
}}

.ai-kicker {{
  font-size: 11px;
  font-weight: 800;
  letter-spacing: .14em;
  color: var(--accent);
  margin-bottom: 4px;
}}

.ai-report-head h2 {{
  margin: 0;
  font-size: 22px;
}}

.ai-report-head p {{
  margin: 4px 0 0;
  color: var(--muted);
  font-size: 13px;
}}

.ai-state {{
  margin-left: auto;
  padding: 7px 10px;
  border-radius: 999px;
  background: var(--low-bg);
  color: var(--low-text);
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}}

.ai-ready .ai-state {{
  background: var(--healthy-bg);
  color: var(--healthy-text);
}}

.ai-report-note, .ai-report-body {{
  margin-top: 18px;
  padding: 16px 18px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--surface-2);
  color: var(--text);
  line-height: 1.7;
}}

.ai-report-body {{
  white-space: normal;
  overflow-wrap: anywhere;
}}

.ai-report-body br + br {{
  display: block;
  content: "";
  margin-top: 8px;
}}

@media (max-width: 760px) {{
  .ai-report-head {{
    align-items: flex-start;
    flex-wrap: wrap;
  }}
  .ai-state {{
    margin-left: 58px;
  }}
}}
</style>
</head>

<body>

<div class="page">

  <div class="topbar">

    <div class="brand">
      <div class="brand-mark">F</div>
      <span>FixMate-AI</span>
    </div>

    <div class="toolbar">
      <button
        type="button"
        class="theme-toggle"
        id="themeToggle"
        aria-label="Toggle light and dark theme"
      >
        <span id="themeIcon">🌙</span>
        <span id="themeText">Dark</span>
      </button>
    </div>

  </div>


  <header class="hero">

    <div class="hero-row">

      <div>
        <h1>Diagnostic Report</h1>

        <p class="subtitle">
          A clear summary of your PC's condition, detected issues,
          evidence and recommended actions.
        </p>
      </div>

      <div class="overall-panel">

        <span>Overall Health</span>

        <div class="overall-badge {_severity_class(overall)}">
          {escape(_severity_label(overall))}
        </div>

      </div>

    </div>


    <div class="info-grid">

      <div class="info-item">
        <span>Computer</span>
        <strong>{escape(computer_name)}</strong>
      </div>

      <div class="info-item">
        <span>Operating System</span>
        <strong>{escape(os_name)} {escape(os_version)}</strong>
      </div>

      <div class="info-item">
        <span>CPU</span>
        <strong>
          {escape(physical_cores)} physical /
          {escape(logical_cores)} logical
        </strong>
      </div>

      <div class="info-item">
        <span>Memory</span>
        <strong>{escape(ram)}</strong>
      </div>

      <div class="info-item">
        <span>Scan Time</span>
        <strong>{escape(generated_at)}</strong>
      </div>

      <div class="info-item">
        <span>Issues Found</span>
        <strong>{fault_count}</strong>
      </div>

    </div>


    <div class="status-grid">

      {_status_card("CPU", cpu_status)}
      {_status_card("Memory", memory_status)}
      {_status_card("GPU", gpu_status)}
      {_status_card("Storage", storage_status)}
      {_status_card("Battery", battery_status)}
      {_status_card("Drivers", driver_status)}
      {_status_card("Network", network_status)}
      {_status_card("Windows", windows_status)}
      {_status_card("Startup", startup_status)}

    </div>

  </header>


  <div class="section-title-row">

    <div>
      <h2 class="section-title">
        Issue Summary
      </h2>

      <p class="section-subtitle">
        Counts grouped by problem type.
      </p>
    </div>

  </div>


  <div class="metrics">
    {_summary_cards(summary)}
  </div>


  <div class="section-title-row">

    <div>
      <h2 class="section-title">
        Overall Assessment
      </h2>
    </div>

  </div>


  <div class="assessment">

    <div class="assessment-mark">
      !
    </div>

    <div>
      {assessment}
    </div>

  </div>


  <div class="section-title-row">

    <div>
      <h2 class="section-title">
        Priority Issues
      </h2>

      <p class="section-subtitle">
        Critical and High severity findings are shown first.
      </p>
    </div>

  </div>


  <div>
    {priority_html}
  </div>


  <div class="section-title-row">

    <div>
      <h2 class="section-title">
        All Detected Issues
      </h2>

      <p class="section-subtitle">
        Open an issue to view evidence, causes and recommended actions.
      </p>
    </div>

  </div>


  <div>
    {detailed_faults}
  </div>


  {_ai_report_section(ai_analysis)}


  <div class="footer">
    Generated by FixMate-AI Report UI V3.
  </div>

</div>


<script>
(function () {{
  const root = document.documentElement;
  const button = document.getElementById("themeToggle");
  const icon = document.getElementById("themeIcon");
  const text = document.getElementById("themeText");

  function setTheme(theme) {{
    root.setAttribute("data-theme", theme);

    const dark = theme === "dark";

    icon.textContent = dark ? "☀️" : "🌙";
    text.textContent = dark ? "Light" : "Dark";

    try {{
      localStorage.setItem(
        "fixmate-theme",
        theme
      );
    }} catch (error) {{}}
  }}

  function initialTheme() {{
    try {{
      const saved =
        localStorage.getItem(
          "fixmate-theme"
        );

      if (
        saved === "dark"
        || saved === "light"
      ) {{
        return saved;
      }}
    }} catch (error) {{}}

    if (
      window.matchMedia
      && window.matchMedia(
        "(prefers-color-scheme: dark)"
      ).matches
    ) {{
      return "dark";
    }}

    return "light";
  }}

  setTheme(
    initialTheme()
  );

  button.addEventListener(
    "click",
    function () {{
      const current =
        root.getAttribute(
          "data-theme"
        );

      setTheme(
        current === "dark"
          ? "light"
          : "dark"
      );
    }}
  );
}})();
</script>

</body>
</html>
"""

    return html


def save_html_report(
    report: Dict[str, Any],
    output_path: str | Path,
    system: Optional[Dict[str, Any]] = None,
    scan_metadata: Optional[Dict[str, Any]] = None,
    status_overview: Optional[Dict[str, Any]] = None,
) -> Path:

    path = Path(
        output_path
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    html = build_html_report(
        report=report,
        system=system,
        scan_metadata=scan_metadata,
        status_overview=status_overview,
    )

    path.write_text(
        html,
        encoding="utf-8"
    )

    return path


if __name__ == "__main__":

    sample_report = {
        "overall_severity": "HIGH",
        "fault_count": 3,
        "assessment": (
            "Windows and device diagnostics detected "
            "conditions that should be reviewed."
        ),
        "summary": {
            "hardware_faults": 0,
            "application_issues": 1,
            "system_resource_issues": 1,
            "driver_problems": 1,
            "driver_warnings": 0,
            "windows_system_issues": 0,
            "windows_configuration_issues": 0,
            "network_issues": 0,
            "startup_issues": 0,
            "other_issues": 0,
        },
        "faults": [
            {
                "component":
                    "Application: Visual Studio Code",
                "severity":
                    "HIGH",
                "fault_type":
                    "application_resource_usage",
                "confidence":
                    "HIGH",
                "hardware_fault":
                    False,
                "problem":
                    "Application is consuming a high amount of system memory.",
                "evidence":
                    "Visual Studio Code is using 3.7 GB RAM.",
                "assessment":
                    "The application is contributing to memory pressure.",
                "causes": [
                    "Multiple application processes are active."
                ],
                "recommendations": [
                    "Close unused Visual Studio Code windows.",
                    "Review unnecessary extensions.",
                    "Restart Visual Studio Code if memory usage grows."
                ],
            },
            {
                "component":
                    "Driver: Example Device",
                "severity":
                    "HIGH",
                "fault_type":
                    "driver_problem",
                "confidence":
                    "HIGH",
                "hardware_fault":
                    False,
                "problem":
                    "Windows reports a device configuration problem.",
                "evidence":
                    "Windows Problem Code: 10.",
                "assessment":
                    "The evidence indicates a driver/device configuration issue.",
                "causes": [
                    "Driver initialization may have failed."
                ],
                "recommendations": [
                    "Check Device Manager.",
                    "Reinstall the compatible driver if required."
                ],
            },
            {
                "component":
                    "Memory",
                "severity":
                    "MODERATE",
                "fault_type":
                    "resource_pressure",
                "confidence":
                    "MEDIUM",
                "hardware_fault":
                    False,
                "problem":
                    "Moderate system memory pressure detected.",
                "evidence":
                    "RAM usage is above the configured moderate threshold.",
                "assessment":
                    "This points toward system resource pressure rather than RAM hardware failure.",
                "causes": [
                    "Several applications are running."
                ],
                "recommendations": [
                    "Close applications that are not required."
                ],
            },
        ],
    }

    sample_system = {
        "Computer Name": "FixMate-PC",
        "OS": "Windows",
        "OS Version": "11",
        "Physical Cores": 14,
        "Logical Cores": 20,
        "RAM": "15.73 GB",
    }

    sample_status = {
        "cpu": "Normal",
        "memory": "Moderate",
        "gpu": "Normal",
        "storage": "Normal",
        "battery": "Excellent",
        "drivers": "2 High problems",
        "network": "Normal",
        "windows": "High",
        "startup": "Healthy",
    }

    output = save_html_report(
        report=sample_report,
        output_path="fixmate_diagnostic_report_v2.html",
        system=sample_system,
        status_overview=sample_status,
    )

    print(
        f"Report created: {output.resolve()}"
    )
