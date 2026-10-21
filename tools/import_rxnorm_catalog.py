#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create a compact offline RxNorm terminology asset from a source SQLite DB.
The input database is never copied into this repository. This catalogue contains
names and branded forms only, not clinical advice or manufacturer/distributor data.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sqlite3
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "assets/data/rxnorm_catalog.json"
DEFAULT_META = ROOT / "assets/data/rxnorm_catalog_meta.json"
SOURCE = "NLM RxNorm public-domain normalized terminology (US catalog)"
STRENGTH_RE = re.compile(
    r"(?<![A-Za-z])\d+(?:\.\d+)?\s*(?:MCG/ACTUAT|MG/ACTUAT|MCG/ML|MG/ML|"
    r"MCI/ML|MEQ/ML|MMOL/ML|G/ML|UNT/ML|MG/5ML|MCG|UG|MG|G|ML|MCI|"
    r"MEQ|MMOL|UNT|UNITS?|IU|%)\b", re.IGNORECASE)


def key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def parse_brand(description: str) -> tuple[str, str]:
    match = re.search(r"\s+\[([^\[\]]+)\]\s*$", description)
    if not match:
        return "", description.strip()
    return match.group(1).strip(), description[:match.start()].strip()


def parse_strength_form(description: str) -> tuple[str, str]:
    matches = list(STRENGTH_RE.finditer(description))
    strengths = []
    for match in matches:
        value = re.sub(r"\s+", " ", match.group(0)).strip()
        if not strengths or value.casefold() != strengths[-1].casefold():
            strengths.append(value)
    strength = " / ".join(strengths)
    form = description[matches[-1].end():].strip(" /,-") if matches else description.strip()
    return strength, form


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=pathlib.Path)
    parser.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    parser.add_argument("--meta-out", type=pathlib.Path, default=DEFAULT_META)
    args = parser.parse_args()
    if not args.database.is_file():
        parser.error(f"source database does not exist: {args.database}")

    con = sqlite3.connect(f"file:{args.database.resolve()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        concepts = list(con.execute(
            "SELECT code, long_desc, chapter FROM codes "
            "WHERE system='RXNORM' AND chapter IN ('IN','PIN') "
            "ORDER BY CASE chapter WHEN 'IN' THEN 0 ELSE 1 END, code"))
        drugs: dict[str, dict] = {}
        by_cui: dict[str, str] = {}
        by_name: dict[str, str] = {}
        for row in concepts:
            name = (row["long_desc"] or "").strip()
            normalized = key(name)
            if not normalized:
                continue
            ident = by_name.get(normalized)
            if ident is None:
                ident = normalized
                by_name[normalized] = ident
                drugs[ident] = {"genericEn": name, "kind": "ingredient", "products": []}
            by_cui[row["code"]] = ident

        relations: dict[str, list[str]] = {}
        for row in con.execute("SELECT rxcui, target FROM rxnorm_rel WHERE rel='has_ingredient'"):
            if row["target"] in by_cui:
                relations.setdefault(row["rxcui"], []).append(row["target"])

        seen_products: set[tuple[str, str, str, str]] = set()
        branded = con.execute(
            "SELECT code, long_desc FROM codes "
            "WHERE system='RXNORM' AND chapter='SBD' ORDER BY code")
        for row in branded:
            targets = sorted(set(relations.get(row["code"], [])))
            ingredient_keys = sorted({by_cui[c] for c in targets if c in by_cui})
            if not ingredient_keys:
                continue
            if len(ingredient_keys) == 1:
                drug_key = ingredient_keys[0]
            else:
                drug_key = "combo:" + "+".join(ingredient_keys)
                if drug_key not in drugs:
                    names = [drugs[k]["genericEn"] for k in ingredient_keys]
                    drugs[drug_key] = {
                        "genericEn": " + ".join(names),
                        "kind": "combination",
                        "products": [],
                    }
            brand, description = parse_brand(row["long_desc"] or "")
            if not brand:
                continue
            strength, form = parse_strength_form(description)
            signature = (drug_key, key(brand), key(strength), key(form))
            if signature in seen_products:
                continue
            seen_products.add(signature)
            drugs[drug_key]["products"].append({"brand": brand, "strength": strength, "form": form})

        build = con.execute(
            "SELECT built_at FROM build_meta WHERE system='RXNORM' LIMIT 1").fetchone()
        snapshot = build["built_at"] if build else "unknown"
    finally:
        con.close()

    records = sorted(drugs.values(), key=lambda item: key(item["genericEn"]))
    for item in records:
        item["products"].sort(key=lambda product: (
            key(product["brand"]), key(product["strength"]), key(product["form"])))
    product_count = sum(len(item["products"]) for item in records)
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "source": SOURCE,
        "sourceUrl": "https://rxnav.nlm.nih.gov/",
        "snapshot": snapshot,
        "generatedAt": generated,
        "notice": "Names and product terminology only; no clinical guidance, manufacturer, country, or Yemen agent.",
        "drugs": records,
    }
    metadata = {
        "source": SOURCE,
        "sourceUrl": "https://rxnav.nlm.nih.gov/",
        "snapshot": snapshot,
        "generatedAt": generated,
        "genericCount": len(records),
        "brandedProductCount": product_count,
        "catalogFile": args.out.name,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.meta_out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    args.meta_out.write_text(json.dumps(metadata, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Snapshot {snapshot}: {len(records):,} ingredient/combination terms, {product_count:,} branded forms")
    print(f"Wrote {args.out} ({args.out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
