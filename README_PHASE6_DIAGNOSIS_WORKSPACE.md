# FixMate-AI Phase 6 — Diagnosis Workspace Update

Updated without touching core diagnostic engine files.

Changes:
- Free storage space and free/available memory shown in merged System Information.
- CPU identity/generation parsing corrected for common Intel and AMD Ryzen names.
- Run Diagnosis is now a vertically scrollable workspace.
- Each diagnostic stage appears as its own expandable result bar.
- Result bars show summary, severity, cause, evidence, and cure/process.
- Active scan stage changes to `Checking` while the scan is running.
- FixMate AI bar remains the final bar in the diagnosis workspace.
- Previous AI/manual-analysis, History/Reports, themes and scan animation code are preserved.

Replace only `ui/main_window.py` and `system_info.py` from this patch in the current no-auth build.
