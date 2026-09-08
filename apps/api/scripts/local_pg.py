"""Start local embedded Postgres for ContentOS (no Docker/Supabase required).

Usage (from apps/api):
  .venv\\Scripts\\python scripts\\local_pg.py
"""
from __future__ import annotations

import time
from pathlib import Path

from pg0 import Pg0, Pg0AlreadyRunningError, list_instances

PORT = 5433
NAME = "contentos"


def main() -> None:
    existing = [i for i in list_instances() if i.name == NAME and i.running]
    if existing:
        inst = existing[0]
        print(f"Local Postgres already running on 127.0.0.1:{inst.port} (pid {inst.pid})")
        print(f"URI: {inst.uri}")
        print("Keep this process open, or leave the existing instance running.")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            print("Exiting (Postgres instance left running).")
        return

    pg = Pg0(
        name=NAME,
        port=PORT,
        username="postgres",
        password="secret",
        database="contentos",
    )
    try:
        info = pg.start()
    except Pg0AlreadyRunningError:
        print(f"Local Postgres already running on port {PORT}")
        info = None
    uri = getattr(pg, "uri", None) or (getattr(info, "uri", None) if info else None)
    print(f"Local Postgres ready on 127.0.0.1:{PORT}")
    if uri:
        print(f"URI: {uri}")
    print("Keep this process running. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("Stopping…")
        try:
            pg.stop()
        except Exception:
            pass


if __name__ == "__main__":
    main()
