# APH Mobile — Flutter Application

Professional pharmaceutical reference app — **AbdulmajeedPharma (APH)** / **موسوعة عبدالمجيد للأدوية**.
© Dr. Abdulmajeed Abdullah Almakhedhi

## Architecture (§50–§51)

```
lib/
  main.dart                 # entry point
  app.dart                  # MaterialApp, l10n, theming, bottom navigation
  app_state.dart            # global settings + connectivity + DI
  core/
    config/                 # environment configuration (no secrets in client)
    constants/
    errors/                 # typed failures — friendly messages only
    network/                # REST client (versioned API, auth header)
    database/               # offline SQLite (drugs, products, FTS, sync queue)
    security/               # token storage
    localization/           # English + Arabic (RTL), full string tables
    theme/                  # APH design system (navy/cyan/emerald)
    utils/
  shared/
    models/                 # DrugModel, ProductModel, SearchHit, BodySystem
    widgets/                # AppHeader, SearchBar, DrugCard, ProductCard,
                            # SystemCard, VerificationBadge, SourceCard,
                            # EmptyState, ErrorState, LoadingSkeleton,
                            # OfflineBanner, SyncStatus, SectionHeader…
    repositories/           # AphRepository (API + offline fallback)
  features/
    auth/                   # login + AuthRepository
    home/                   # dashboard, 18 systems, quick actions
    systems/                # systems grid + system detail (groups/classes)
    search/                 # instant search, suggestions, no-result guidance
    drugs/                  # full monograph (19 collapsible sections)
    products/               # commercial product detail + gallery
    scan/                   # barcode (mobile_scanner) + OCR-ready pipeline
    favorites/              # offline favorites
    recent/                 # recent searches (local, clearable)
    settings/               # language, theme, datasets, about, support
    ai/                     # APH AI Assistant (RAG, citations, disclaimer)
    sync/                   # sync engine client + on-device sync queue
    profile/                # "More" tab
test/
  models_test.dart
  sync_queue_test.dart
```

## Build (§79)

```bash
cd mobile
flutter create --platforms=android,ios .   # generates platform scaffolding
flutter pub get
flutter test
flutter run                                 # dev
flutter build apk --release                 # APK
flutter build appbundle --release           # AAB (Play Store)
```

The GitHub Actions workflow (`.github/workflows/build-apk.yml`) builds the APK
in the cloud — no local Flutter installation required.

Configure the API base per environment (never hard-code secrets):

```bash
flutter build apk --dart-define=APH_API_BASE=https://api.your-domain.com/api/v1
```

## Offline-first (§30–§33)

- SQLite stores downloaded drugs/products/systems, search indexes, favorites,
  recent searches, sync metadata and the **sync queue**.
- Dataset modes: **Essential** / **Selected Systems** / **Full** (§31).
- Sync: incremental pull by watermark, push through the queue with retry and
  conflict detection — newer server data is never overwritten blindly.
- When offline: search downloaded data, open monographs, browse systems,
  use favorites and recents. An amber banner indicates offline status.

## Localization (§3, §71)

- English (LTR) and Arabic (RTL) with full string tables — no hard-coded UI text.
- RTL layouts, Arabic typography, Arabic drug names and Arabic search.
- Language switch lives in Settings and on the home header.

## Medical disclaimer (§44)

APH is intended for educational and professional reference purposes. It does
not replace official prescribing information, clinical judgment, or advice
from a qualified healthcare professional.
