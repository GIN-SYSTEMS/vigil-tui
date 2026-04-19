# -*- mode: python ; coding: utf-8 -*-
#
# vigil.spec -- PyInstaller build descriptor
#
# Produces a single self-contained executable (--onefile equivalent).
# Tested with PyInstaller 6.x + Python 3.11/3.12.
#
# Usage:
#   pip install pyinstaller
#   pyinstaller vigil.spec --clean
#
# Output:
#   dist/vigil.exe  (Windows)
#   dist/vigil      (Linux / macOS)

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ---- Data files -------------------------------------------------------------
# vigil's own CSS theme + all of Textual's bundled CSS / assets.
datas = (
    [("src/vigil/TacticalCyberpunk.tcss", ".")]
    + collect_data_files("textual")
)

# ---- Hidden imports ---------------------------------------------------------
# Modules that PyInstaller's static analyser misses (dynamic imports,
# optional platform dependencies, Textual widget registry, etc.)
hiddenimports = (
    collect_submodules("vigil")
    + collect_submodules("textual")
    + [
        "pynvml",
        "wmi",
        "win32api",
        "win32com",
        "win32con",
        "psutil._pswindows",
        "psutil._pslinux",
        "psutil._psposix",
    ]
)

# ---- Analysis ---------------------------------------------------------------
a = Analysis(
    ["src/vigil/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "scipy",
        "PIL",
        "cv2",
        "pytest",
        "IPython",
        "notebook",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ---- Executable -------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="vigil",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,   # MUST be True -- vigil is a terminal TUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
