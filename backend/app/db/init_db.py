"""Initialize the database schema and seed baseline data.

Usage:
    python -m app.db.init_db            # create schema + RBAC + demo dataset
    python -m app.db.init_db --no-demo  # schema + RBAC only (production bootstrap)
"""
from __future__ import annotations

import argparse

from app.core.logging import setup_logging
from app.db.session import get_engine, session_scope
from app.models import Base  # noqa: F401 — registers all models


def init_db(with_demo: bool = True) -> None:
    from app.db.seed import seed_database

    setup_logging()
    engine = get_engine()
    Base.metadata.create_all(engine)
    with session_scope() as db:
        counts = seed_database(db, with_demo=with_demo)
        print(f"Database initialized: {counts}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize APH database")
    parser.add_argument("--no-demo", action="store_true", help="skip demo dataset")
    args = parser.parse_args()
    init_db(with_demo=not args.no_demo)


if __name__ == "__main__":
    main()
