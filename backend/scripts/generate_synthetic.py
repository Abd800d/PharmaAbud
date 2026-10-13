#!/usr/bin/env python3
"""Generate synthetic NON-PRODUCTION test data for load/performance testing (§74).

Every generated record is marked is_demo=True and its names carry a
'SYNTH-' prefix so it can never be confused with real pharmaceutical data.

Usage:
    python scripts/generate_synthetic.py --drugs 100000 --products 100000
    python scripts/generate_synthetic.py --drugs 1000 --products 2000 --database-url sqlite:///load_test.db

DO NOT point this script at a production database.
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DATABASE_URL", "sqlite:///./load_test.db")

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.db import get_engine, session_scope  # noqa: E402
from app.models import (  # noqa: E402
    BodySystem,
    Drug,
    DrugClassification,
    Manufacturer,
    PharmacologicalClass,
    Product,
    ProductIngredient,
    TherapeuticGroup,
    VerificationStatus,
)
from app.services.normalization import normalize_text  # noqa: E402

STEMS = ["demolol", "demozumab", "democillin", "demostatin", "demopril",
         "democaine", "demoxacin", "demodipine", "demoglit", "demotrex"]
SUFFIXES = ["", "ex", "in", "ol", "ide", "ate", "one", "zumab", "vir", "mycin"]
FORMS = ["tablet", "capsule", "injection", "syrup", "cream", "inhaler", "oral_solution"]


def synth_name(i: int) -> str:
    return f"SYNTH-{random.choice(STEMS).capitalize()}{random.choice(SUFFIXES)}-{i}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic load-test data")
    parser.add_argument("--drugs", type=int, default=100_000)
    parser.add_argument("--products", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    random.seed(args.seed)

    settings = get_settings()
    if "prod" in settings.database_url.lower():
        print("REFUSING to generate synthetic data against a production-looking database_url.")
        sys.exit(1)

    from app.models import Base

    Base.metadata.create_all(get_engine())

    started = time.time()
    with session_scope() as db:
        systems = list(db.scalars(select(BodySystem)).all())
        if not systems:
            print("Run `python -m app.db.init_db` first (needs the 18 body systems).")
            sys.exit(1)

        # taxonomy groups/classes (synthetic)
        groups = {}
        classes = {}
        for system in systems:
            group = TherapeuticGroup(
                body_system_id=system.id,
                slug=f"synth-group-{system.slug}",
                name_en=f"SYNTH Group {system.slug}",
                name_ar=f"مجموعة تجريبية {system.slug}",
            )
            db.add(group)
            db.flush()
            groups[system.id] = group
            cls = PharmacologicalClass(
                therapeutic_group_id=group.id,
                slug=f"synth-class-{system.slug}",
                name_en=f"SYNTH Class {system.slug}",
                name_ar=f"صنف تجريبي {system.slug}",
            )
            db.add(cls)
            db.flush()
            classes[system.id] = cls

        manu = Manufacturer(name_en="SYNTH Manufacturer (NON-PRODUCTION TEST DATA)")
        db.add(manu)
        db.flush()

        drug_ids = []
        batch = 2000
        for i in range(args.drugs):
            name = synth_name(i)
            drug = Drug(
                generic_name_en=name,
                generic_name_ar=f"سينث-{i}",
                drug_class="SYNTH (non-production test data)",
                overview_en="SYNTHETIC RECORD — generated for load testing only. NOT pharmaceutical data.",
                is_demo=True,
                verification_status=VerificationStatus.DRAFT.value,
                search_text=normalize_text(name),
                search_text_ar=f"سينث {i}",
            )
            db.add(drug)
            if i % batch == 0:
                db.flush()
            drug_ids.append(drug)
            system = systems[i % len(systems)]
            db.flush()
            db.add(DrugClassification(
                drug_id=drug.id,
                pharmacological_class_id=classes[system.id].id,
                body_system_id=system.id,
                therapeutic_group_id=groups[system.id].id,
                is_primary=True,
            ))
            if i % batch == 0:
                print(f"  drugs: {i + 1}/{args.drugs}")
        db.flush()

        for i in range(args.products):
            drug = drug_ids[i % len(drug_ids)]
            brand = f"SYNTH-Brand-{i}"
            product = Product(
                drug_id=drug.id,
                brand_name_en=brand,
                brand_name_ar=f"سينث براند {i}",
                strength=f"{random.choice([5, 10, 20, 25, 50, 100, 250, 500])} mg",
                dosage_form=random.choice(FORMS),
                route="oral",
                manufacturer_id=manu.id,
                barcode=f"SYNTH{100000000 + i}",
                is_demo=True,
                verification_status=VerificationStatus.DRAFT.value,
                search_text=normalize_text(brand),
            )
            db.add(product)
            if i % batch == 0:
                db.flush()
                print(f"  products: {i + 1}/{args.products}")

    elapsed = time.time() - started
    print(f"Done in {elapsed:.1f}s — {args.drugs} SYNTH drugs, {args.products} SYNTH products.")
    print("These are NON-PRODUCTION test records (names prefixed SYNTH-, is_demo=true).")


if __name__ == "__main__":
    main()
