#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APH CI check — يتأكد أن قاعدة الأدوية المولّدة سليمة ومتسقة قبل بناء APK."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SEED = ROOT / "assets/data/drugs_seed.json"
PUBLISHED = ROOT / "webapp/aph-database.json"


def main() -> int:
    if not SEED.exists():
        print("ERROR: assets/data/drugs_seed.json is missing")
        return 1
    d = json.loads(SEED.read_text(encoding="utf-8"))
    drugs = d.get("drugs", [])
    systems = {s["id"] for s in d.get("systems", [])}
    prods = sum(len(x.get("products", [])) for x in drugs)

    problems = []
    if not drugs:
        problems.append("no drugs in seed")
    if len(systems) != 18:
        problems.append(f"expected 18 body systems, found {len(systems)}")

    names = {}
    for dr in drugs:
        name = (dr.get("genericEn") or "").strip()
        if not name:
            problems.append("drug with empty genericEn")
            continue
        if dr.get("systemId") not in systems:
            problems.append(f"{name}: unknown systemId {dr.get('systemId')}")
        if not dr.get("dosage"):
            problems.append(f"{name}: missing dosage")
        low = name.lower()
        names[low] = names.get(low, 0) + 1
        for pr in dr.get("products", []):
            if not (pr.get("brand") or "").strip():
                problems.append(f"{name}: product without brand name")
            if not (pr.get("manufacturer") or "").strip():
                problems.append(f"{name}: product without manufacturer")

    dupes = [n for n, c in names.items() if c > 1]
    if dupes:
        problems.append(f"duplicate generics: {', '.join(dupes[:10])}")

    if PUBLISHED.exists():
        pj = json.loads(PUBLISHED.read_text(encoding="utf-8"))
        if len(pj.get("drugs", [])) != len(drugs):
            problems.append("webapp/aph-database.json is out of sync with the seed")

    print(f"seed: {len(drugs)} generics, {prods} trade products, {len(systems)} systems")
    if problems:
        print(f"FAILED with {len(problems)} problem(s):")
        for p in problems[:40]:
            print(" -", p)
        return 1
    print("seed integrity OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
