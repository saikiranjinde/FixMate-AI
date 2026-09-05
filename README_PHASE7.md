# FixMate-AI Phase 7 — Packaging Kit

This is a packaging add-on for the current no-auth FixMate-AI project.

## What it adds

- PyInstaller spec
- PowerShell build script
- Compilation validation before packaging
- GUI/no-console EXE
- Bundling for:
  - assets/
  - ui/help_assets/
  - Python submodules under ai/, core/, diagnosis/, storage/, ui/

## Before building

Use the current working FixMate-AI project as the source. Do not replace your working source files with this kit.

From the project root:

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements_packaging.txt
```

Or install PyInstaller directly:

```powershell
python -m pip install pyinstaller
```

## Build

```powershell
.\build_exe.ps1
```

Expected output:

```text
dist\FixMate-AI.exe
```

## Important

This kit does NOT merge or alter your existing diagnosis/AI/history source code.

User data should continue to live under `%LOCALAPPDATA%\FixMate-AI\` as already designed by the application.

For distribution, keep API keys out of source code and out of the packaged executable.
