# PyInstaller spec: `make app` (or `pyinstaller desktop/aurora.spec`).
# Output: dist/Aurora/ (a folder with the Aurora program), plus dist/Aurora.app on macOS.
# One folder rather than one file: it starts in seconds instead of unpacking pandas each time.

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).parent

datas = [(str(ROOT / "templates"), "templates"), (str(ROOT / "static"), "static")]
binaries, hidden = [], []
for package in ("django", "whitenoise", "environ", "openpyxl", "anthropic"):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hidden += h
# Our own packages, listed from the files: importing them here would need Django set up.
for package in ("config", "ledger", "web", "ai", "insights"):
    for path in (ROOT / package).rglob("*.py"):
        if "tests" not in path.parts:
            module = path.relative_to(ROOT).with_suffix("").parts
            hidden.append(".".join(module[:-1] if module[-1] == "__init__" else module))

a = Analysis(
    [str(ROOT / "desktop" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden + ["waitress"],
    excludes=["pytest", "IPython", "matplotlib", "tkinter", "notebook"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Aurora",
    console=True,  # the window shows where the data is; closing it stops Aurora
)
coll = COLLECT(exe, a.binaries, a.datas, name="Aurora")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Aurora.app",
        bundle_identifier="io.github.lordbalouch.aurora",
        info_plist={"CFBundleShortVersionString": "1.0.0", "LSBackgroundOnly": False},
    )
