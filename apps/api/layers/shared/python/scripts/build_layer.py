#!/usr/bin/env python3
"""Build ArcForge Python Lambda layer zip (installs into python/ for /opt/python)."""
from __future__ import annotations
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]  # api root (python-cloud-arc/api)
LAYER = Path(__file__).resolve().parents[1]  # layers/shared/python
OUT = LAYER / "bundled" / "python"
REQ = ROOT / "requirements-layer.txt"

def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    # Copy shared source
    src = LAYER / "src"
    for name in ("config", "database", "decorators", "core", "middleware", "utils"):
        shutil.copytree(src / name, OUT / name)
    # Optional: pip install deps into OUT
    if REQ.exists():
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", str(REQ),
            "-t", str(OUT), "--quiet",
        ])
    print(f"Layer built at {OUT}")

if __name__ == "__main__":
    main()
