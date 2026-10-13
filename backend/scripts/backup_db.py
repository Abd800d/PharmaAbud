#!/usr/bin/env python3
"""Database backup helper (§60).

PostgreSQL: wraps pg_dump with a timestamped, compressed file and applies the
retention policy (keep N most recent backups).
SQLite: copies the database file (safe via sqlite3 backup API).

Usage:
    python scripts/backup_db.py --out ./backups --retain 14
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings  # noqa: E402


def backup_sqlite(url: str, out_dir: str) -> str:
    path = url.replace("sqlite:///", "").replace("sqlite://", "")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = os.path.join(out_dir, f"aph-sqlite-{stamp}.db")
    src = sqlite3.connect(path)
    dst = sqlite3.connect(out)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    return out


def backup_postgres(url: str, out_dir: str) -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = os.path.join(out_dir, f"aph-pg-{stamp}.dump")
    subprocess.run(["pg_dump", "--format=custom", "--file", out, url], check=True)
    return out


def apply_retention(out_dir: str, retain: int, prefix: str = "aph-") -> None:
    backups = sorted(
        f for f in os.listdir(out_dir) if f.startswith(prefix)
    )
    excess = len(backups) - retain
    for f in backups[: max(0, excess)]:
        os.remove(os.path.join(out_dir, f))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="./backups")
    parser.add_argument("--retain", type=int, default=14)
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    settings = get_settings()
    url = settings.database_url

    if url.startswith("sqlite"):
        path = backup_sqlite(url, args.out)
    else:
        path = backup_postgres(url, args.out)

    apply_retention(args.out, args.retain)
    print(f"Backup written: {path}")


if __name__ == "__main__":
    main()
