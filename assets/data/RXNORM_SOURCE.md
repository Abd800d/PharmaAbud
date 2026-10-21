# RxNorm offline terminology: source and scope

- Source: U.S. National Library of Medicine RxNorm / RxNav: <https://rxnav.nlm.nih.gov/>.
- Snapshot: `2026-06-22T00:44:15.018Z`, recorded in `rxnorm_catalog_meta.json`.
- The app catalogue is a compact selection of the public-domain normalized terminology layer from NLM RxNorm, not the UMLS-licensed full release.
- Source snapshot: `@cyanheads/medical-codes-mcp-server@0.4.1` (npm); its published README attributes the included public-domain subset to RxNav/NLM. The source SQLite database is about 129 MB and is not stored in this repository.
- Catalogue: 19,594 ingredient/combination records and 9,629 branded product/form terms. The APH seed contains 338 clinically curated generics and 692 products. Text terms are for search/terminology only.
- RxNorm does not provide APH's 18-body-system therapeutic classification, Yemen distributors, or local registration details. Imported records are assigned to a review queue; they do not receive invented clinical fields, manufacturer, country, or Yemen agent.
- No official dose, indications, contraindications, clinical summaries, or Yemen distribution claims are added by this import. The curated APH records remain separate.

To regenerate when an equivalent SQLite snapshot is available:

```bash
npm pack @cyanheads/medical-codes-mcp-server@0.4.1 --pack-destination /tmp
mkdir -p /tmp/aph-rxnorm
# Extract the package tarball into /tmp/aph-rxnorm, then:
python3 tools/import_rxnorm_catalog.py /tmp/aph-rxnorm/package/data/medical-codes.db
python3 tools/verify_seed.py
```
