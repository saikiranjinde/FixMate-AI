# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

project = Path(SPEC).parent

hiddenimports = []
for pkg in ("ai", "core", "diagnosis", "storage", "ui"):
    try:
        hiddenimports += collect_submodules(pkg)
    except Exception:
        pass

datas = []
for rel in [
    ("assets", "assets"),
    ("ui/help_assets", "ui/help_assets"),
]:
    src = project / rel[0]
    if src.exists():
        datas.append((str(src), rel[1]))

a = Analysis(
    [str(project / "app.py")],
    pathex=[str(project)],
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
)
