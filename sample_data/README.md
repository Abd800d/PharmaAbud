# APH Sample Import Data — DEMO / DEVELOPMENT DATA

**⚠️ Everything in this folder is DEMO / DEVELOPMENT DATA created to exercise
the APH import pipeline. It is NOT verified pharmaceutical information and must
never be presented as such.**

All imported rows land in `imported_pending_review` status and must pass the
pharmacist verification workflow before they can be published.

## Files

| File | Format | Purpose |
|------|--------|---------|
| `demo_import_products.csv` | CSV | Product import with column aliases, duplicates and invalid rows (exercises §19–§22) |
| `demo_import_drugs.json` | JSON | Drug import example |
| `demo_import_products.xlsx` | XLSX | Excel import example (generate via `python make_xlsx.py`) |

## Column mapping

The import engine auto-maps source columns (see `FIELD_ALIASES` in
`backend/app/services/import_engine.py`). Common columns:

`GenericName, GenericNameAR, BrandName, BrandNameAR, ActiveIngredient, Strength,
DosageForm, Route, Manufacturer, Country, MarketingCountry, BodySystem,
TherapeuticGroup, PharmacologicalClass, Mechanism, Indications, Contraindications,
Warnings, Precautions, SideEffects, Interactions, FoodInteractions, Dosage,
PediatricDosage, GeriatricDosage, RenalAdjustment, HepaticAdjustment, Pregnancy,
Lactation, Barcode, RegistrationNumber, ImageURL, SourceURL, VerificationStatus`

See `IMPORT_GUIDE.md` at the repository root for the full pipeline.

## Data rights (§84)

Only import data you have the rights to use: public-domain data, properly
licensed data, official data where permitted, or your own data. Track
source/license metadata for every import (`source_id` on the import record).
