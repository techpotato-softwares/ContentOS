#!/usr/bin/env python3
"""Build ContentOS Python Lambda layer (installs into python/ for /opt/python).

Lambdas run Python 3.12 on arm64. Native wheels (pydantic_core, bcrypt, Pillow,
psycopg2, etc.) MUST be manylinux aarch64 — never host macOS/x86 wheels.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]  # apps/api
LAYER = Path(__file__).resolve().parents[1]  # layers/shared/python
OUT = LAYER / "bundled" / "python"
REQ = ROOT / "requirements-layer.txt"

# Match infra LambdaConstruct: Runtime.PYTHON_3_12 + Architecture.ARM_64
DEFAULT_PYTHON = "3.12"
DEFAULT_PLATFORM = "manylinux2014_aarch64"

SHARED_PACKAGES = (
    "config",
    "database",
    "decorators",
    "core",
    "middleware",
    "utils",
    "training",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Lambda shared layer")
    parser.add_argument(
        "--python-version",
        default=DEFAULT_PYTHON,
        help="Target CPython version for wheels (default: 3.12)",
    )
    parser.add_argument(
        "--platform",
        default=DEFAULT_PLATFORM,
        help="PEP 425 platform tag (default: manylinux2014_aarch64)",
    )
    parser.add_argument(
        "--host",
        action="store_true",
        help="Install for this machine only (local debug — do NOT deploy)",
    )
    args = parser.parse_args()

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    src = LAYER / "src"
    for name in SHARED_PACKAGES:
        src_pkg = src / name
        if not src_pkg.is_dir():
            print(f"WARNING: missing shared package {src_pkg}", file=sys.stderr)
            continue
        shutil.copytree(src_pkg, OUT / name)

    if REQ.exists():
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-r",
            str(REQ),
            "-t",
            str(OUT),
            "--upgrade",
            "--quiet",
        ]
        if not args.host:
            cmd.extend(
                [
                    "--platform",
                    args.platform,
                    "--implementation",
                    "cp",
                    "--python-version",
                    args.python_version,
                    "--only-binary=:all:",
                ]
            )
            print(
                f"Installing layer deps for Lambda "
                f"(cp{args.python_version.replace('.', '')} / {args.platform})..."
            )
        else:
            print("Installing layer deps for HOST platform (not for deploy)...")

        subprocess.check_call(cmd)

    # Sanity: refuse obvious macOS pydantic wheels when targeting Lambda
    if not args.host:
        darwin = list(OUT.rglob("*darwin*.so")) + list(OUT.rglob("*darwin*.dylib"))
        if darwin:
            print(
                "ERROR: macOS native libs found in layer output — refuse deploy:\n  "
                + "\n  ".join(str(p.relative_to(OUT)) for p in darwin[:10]),
                file=sys.stderr,
            )
            sys.exit(1)
        pydantic_so = list((OUT / "pydantic_core").glob("_pydantic_core*.so"))
        if not pydantic_so:
            print(
                "ERROR: pydantic_core native module missing after install",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"OK native: {pydantic_so[0].name}")

    print(f"Layer built at {OUT}")


if __name__ == "__main__":
    main()
