$ErrorActionPreference = "Stop"

Write-Host "=== FixMate-AI EXE Build ===" -ForegroundColor Cyan

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Virtual environment not found. Create .venv first." -ForegroundColor Yellow
    exit 1
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pyinstaller
& ".\.venv\Scripts\python.exe" -m py_compile `
    ".\app.py" `
    ".\ui\main_window.py" `
    ".\ui\history_dialog.py" `
    ".\ui\scan_visual.py" `
    ".\ai\openrouter_client.py" `
    ".\ai\prompt_builder.py" `
    ".\ai\diagnostic_analyzer.py" `
    ".\storage\history.py" `
    ".\diagnosis\report_ui.py"

if ($LASTEXITCODE -ne 0) {
    throw "Python compilation check failed."
}

if (Test-Path ".\build") { Remove-Item ".\build" -Recurse -Force }
if (Test-Path ".\dist\FixMate-AI") { Remove-Item ".\dist\FixMate-AI" -Recurse -Force }
if (Test-Path ".\dist\FixMate-AI.exe") { Remove-Item ".\dist\FixMate-AI.exe" -Force }

& ".\.venv\Scripts\python.exe" -m PyInstaller --clean --noconfirm ".\FixMate-AI.spec"

Write-Host ""
Write-Host "Build complete." -ForegroundColor Green
Write-Host "Output: .\dist\FixMate-AI.exe" -ForegroundColor Green
