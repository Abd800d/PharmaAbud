#!/usr/bin/env python3
"""Validate APH's curated seed and compact RxNorm offline terminology asset."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
problems: list[str] = []
seed = json.loads((ROOT / 'assets/data/drugs_seed.json').read_text(encoding='utf-8'))
drugs = seed.get('drugs', [])
products = sum(len(drug.get('products', [])) for drug in drugs)
if len(drugs) != 338:
    problems.append(f'expected 338 APH curated generics, found {len(drugs)}')
if products != 692:
    problems.append(f'expected 692 APH products, found {products}')
if len(seed.get('systems', [])) != 18:
    problems.append(f'expected 18 body systems, found {len(seed.get("systems", []))}')

catalog_path = ROOT / 'assets/data/rxnorm_catalog.json'
meta_path = ROOT / 'assets/data/rxnorm_catalog_meta.json'
catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
meta = json.loads(meta_path.read_text(encoding='utf-8'))
catalog_drugs = catalog.get('drugs', [])
catalog_products = sum(len(drug.get('products', [])) for drug in catalog_drugs)
if catalog.get('snapshot') != meta.get('snapshot'):
    problems.append('catalog and metadata snapshot mismatch')
if meta.get('genericCount') != len(catalog_drugs):
    problems.append('metadata generic count mismatch')
if meta.get('brandedProductCount') != catalog_products:
    problems.append('metadata branded product count mismatch')
seen = set()
for drug in catalog_drugs:
    name = str(drug.get('genericEn', '')).strip()
    if not name:
        problems.append('empty RxNorm name')
        continue
    if name.casefold() in seen:
        problems.append(f'duplicate RxNorm term: {name}')
    seen.add(name.casefold())
    for product in drug.get('products', []):
        if not str(product.get('brand', '')).strip():
            problems.append(f'{name}: empty product brand')
        for forbidden in ('manufacturer', 'country', 'agentYemen'):
            if product.get(forbidden):
                problems.append(f'{name}: unverified {forbidden} must be empty')

# Model the exact name/product de-duplication used by DBHelper on a fresh install.
name_ids = {(d.get('genericEn') or '').strip().lower(): i + 1 for i, d in enumerate(drugs)}
product_keys = set()
for i, drug in enumerate(drugs, 1):
    for product in drug.get('products', []):
        product_keys.add((i, str(product.get('brand', '')).strip().lower(),
                          str(product.get('strength', '')).strip().lower(),
                          str(product.get('form', '')).strip().lower()))
next_id = max(name_ids.values(), default=0)
added_generic = added_product = 0
for drug in catalog_drugs:
    name = drug['genericEn'].strip().lower()
    generic_id = name_ids.get(name)
    if generic_id is None:
        next_id += 1
        generic_id = next_id
        name_ids[name] = generic_id
        added_generic += 1
    for product in drug.get('products', []):
        key = (generic_id, str(product.get('brand', '')).strip().lower(),
               str(product.get('strength', '')).strip().lower(),
               str(product.get('form', '')).strip().lower())
        if key not in product_keys:
            product_keys.add(key)
            added_product += 1

print(f'seed: {len(drugs)} curated generics, {products} products, 18 body systems')
print(f'RxNorm: {len(catalog_drugs)} terminology records, {catalog_products} branded forms')
print(f'Expected first-install net addition: {added_generic} generics, {added_product} products')
if problems:
    print('\n'.join('ERROR: ' + problem for problem in problems))
    raise SystemExit(1)
print('seed/catalog integrity OK')
