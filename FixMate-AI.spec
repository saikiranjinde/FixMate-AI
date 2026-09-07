# -*- mode: python ; coding: utf-8 -*-
"""
FixMate-AI PyInstaller spec
Packaging fix: explicitly bundle psutil and its Windows extension modules.
"""

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

project_root = Path(SPECPATH)
assets_dir = project_root / "assets"

hiddenimports = sorted(set(
    collect_submodules("psutil") + [
        "psutil",
        "psutil._psutil_windows",
        "hardware",
        "core.hardware",
        "diagnosis",
        "core.diagnosis",
        "process_analyzer_v3",
        "core.process_analyzer_v3",
        "gpu_diagnostics",
        "core.gpu_diagnostics",
        "thermal",
        "core.thermal",
        "storage_diagnostics",
        "core.storage_diagnostics",


    ]
))

datas = collect_data_files("psutil")
if assets_dir.exists():
    datas.append((str(assets_dir), "assets"))

a = Analysis(
    ["app.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="FixMate-AI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(assets_dir / "fixmate_logo.ico")
        if (assets_dir / "fixmate_logo.ico").exists() else None,
)
