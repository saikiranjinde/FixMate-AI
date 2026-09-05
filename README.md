# FixMate-AI — Full No-Auth Recovery Build

This recovery build keeps the current no-auth product line. Authentication is intentionally excluded.

## Included
- Windows PC diagnostics and deterministic Fault/Severity/Recommendation engines
- Dashboard with merged expandable System Information frame
- System information auto-fetch on startup
- CPU/Windows/RAM/Storage details
- Full Diagnosis workspace with expandable/resizable Diagnosis panel
- FixMate AI workspace with optional OpenRouter integration
- API key check before AI analysis, Cancel, streaming/typing output, AI Help
- Local Diagnosis History and Reports
- Light/Dark theme
- FixMate-AI logo and scan-specific Qt animations
- Previous painter/enum fixes

## Install
```powershell
python -m pip install -r requirements.txt
python app.py
```

## Optional OpenRouter
Without an API key, local diagnosis works normally and AI shows `AI not configured`.
Configure the key in AI Settings or set:
```powershell
$env:FIXMATE_OPENROUTER_API_KEY="YOUR_KEY"
```
Never commit a real key to source control.
