/// Drug monograph screen (§14, §89): 19 collapsible sections, verification
/// badge, products (equivalents), therapeutic alternatives, sources.
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../app_state.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/theme/app_theme.dart';
import '../../core/database/local_database.dart';
import '../../shared/models/models.dart';
import '../../shared/repositories/aph_repository.dart';
import '../../shared/widgets/cards.dart';
import '../../shared/widgets/common.dart';
import '../../shared/widgets/states.dart';
import '../products/product_detail_screen.dart';

class DrugDetailScreen extends StatefulWidget {
  const DrugDetailScreen({super.key, required this.drugId});

  final String drugId;

  @override
  State<DrugDetailScreen> createState() => _DrugDetailScreenState();
}

class _DrugDetailScreenState extends State<DrugDetailScreen> {
  DrugModel? _drug;
  List<Map<String, dynamic>> _products = const [];
  bool _loading = true;
  String _error = '';
  bool _isFavorite = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final app = context.read<AppState>();
    setState(() { _loading = true; _error = ''; });
    try {
      final drug = await app.repository.getDrug(widget.drugId, offline: !app.isOnline);
      final products = await app.repository.getDrugProducts(widget.drugId);
      final fav = await LocalDatabase.instance.isFavorite('drug', widget.drugId);
      setState(() { _drug = drug; _products = products; _isFavorite = fav; _loading = false; });
    } catch (e) {
      setState(() { _loading = false; _error = e.toString(); });
    }
  }

  Future<void> _toggleFavorite() async {
    final db = LocalDatabase.instance;
    if (_isFavorite) {
      await db.removeFavorite('drug', widget.drugId);
      await db.enqueueSync(entityType: 'favorite', entityId: widget.drugId, operation: 'favorite_remove');
    } else {
      await db.addFavorite('drug', widget.drugId);
      await db.enqueueSync(entityType: 'favorite', entityId: widget.drugId, operation: 'favorite_add');
    }
    setState(() => _isFavorite = !_isFavorite);
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final app = context.watch<AppState>();
    final isAr = app.isArabic;

    if (_loading) return const Scaffold(body: LoadingSkeleton());
    if (_error.isNotEmpty || _drug == null) {
      return Scaffold(
        appBar: AppHeader(showBrand: false, title: t.tr('error')),
        body: ErrorState(message: _error, onRetry: _load),
      );
    }

    final drug = _drug!;
    final sectionText = (String en, String ar) => isAr && ar.isNotEmpty ? ar : (en.isNotEmpty ? en : t.tr('notAvailable'));

    return Scaffold(
      appBar: AppHeader(
        showBrand: false,
        title: drug.genericNameEn,
        actions: [
          IconButton(
            icon: Icon(_isFavorite ? Icons.favorite : Icons.favorite_border,
                color: _isFavorite ? AphColors.red : null),
            onPressed: _toggleFavorite,
          ),
        ],
      ),
      body: Column(children: [
        OfflineBanner(visible: !app.isOnline),
        Expanded(
          child: ListView(padding: const EdgeInsets.all(AphSpacing.md), children: [
            // ---- header -------------------------------------------------
            Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(drug.genericNameEn,
                      style: Theme.of(context).textTheme.headlineSmall),
                  if (drug.genericNameAr.isNotEmpty)
                    Text(drug.genericNameAr,
                        textDirection: TextDirection.rtl,
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(color: AphColors.textSecondary)),
                  const SizedBox(height: 6),
                  Wrap(spacing: 8, runSpacing: 6, children: [
                    if (drug.pharmacologicalClassName.isNotEmpty)
                      Chip(label: Text(drug.pharmacologicalClassName, style: const TextStyle(fontSize: 11))),
                    if (drug.atcCode.isNotEmpty)
                      Chip(label: Text('ATC ${drug.atcCode}', style: const TextStyle(fontSize: 11))),
                  ]),
                ]),
              ),
              Column(children: [
                VerificationBadge(status: drug.verificationStatus),
                if (drug.isDemo) ...[const SizedBox(height: 6), const DemoBadge()],
              ]),
            ]),
            if (drug.isDemo)
              Container(
                margin: const EdgeInsets.only(top: 12),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AphColors.amber.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(AphSpacing.radiusSm),
                  border: Border.all(color: AphColors.amber.withValues(alpha: 0.4)),
                ),
                child: Text(t.tr('demoWarning'), style: const TextStyle(fontSize: 12, color: AphColors.amber)),
              ),

            // ---- sections ----------------------------------------------
            _Section(title: t.tr('overview'), body: sectionText(drug.overviewEn, drug.overviewAr)),
            _Section(
              title: t.tr('classification'),
              body: [
                drug.drugClass,
                drug.pharmacologicalClassName,
                drug.therapeuticClassName,
                drug.atcCode.isNotEmpty ? 'ATC: ${drug.atcCode}' : '',
              ].where((s) => s.isNotEmpty).join('\n'),
            ),
            _Section(title: t.tr('mechanism'), body: sectionText(drug.mechanismEn, drug.mechanismAr)),
            _Section(
              title: t.tr('indications'),
              body: _joinEntries(drug.indications, t, isAr, offLabelAware: true),
            ),
            _Section(
              title: t.tr('dosage'),
              body: drug.dosages.isEmpty
                  ? t.tr('notAvailable')
                  : drug.dosages.map((d) {
                      final label = (d['population'] ?? '').toString();
                      final text = isAr && (d['text_ar'] ?? '').toString().isNotEmpty
                          ? d['text_ar']
                          : d['text_en'];
                      return '• ${label.toUpperCase()}: $text';
                    }).join('\n'),
            ),
            _Section(title: t.tr('contraindications'), body: _joinEntries(drug.contraindications, t, isAr)),
            _Section(title: t.tr('warnings'), body: _joinEntries(drug.warnings, t, isAr)),
            _Section(title: t.tr('precautions'), body: _joinEntries(drug.precautions, t, isAr)),
            _Section(title: t.tr('adverseEffects'), body: _joinEntries(drug.sideEffects, t, isAr)),
            _Section(title: t.tr('interactions'), body: _joinEntries(drug.interactions, t, isAr)),
            _Section(
              title: t.tr('pregnancy'),
              body: drug.pregnancy == null
                  ? t.tr('notAvailable')
                  : sectionText((drug.pregnancy!['text_en'] ?? '').toString(),
                      (drug.pregnancy!['text_ar'] ?? '').toString()),
            ),
            _Section(
              title: t.tr('lactation'),
              body: drug.lactation == null
                  ? t.tr('notAvailable')
                  : sectionText((drug.lactation!['text_en'] ?? '').toString(),
                      (drug.lactation!['text_ar'] ?? '').toString()),
            ),
            _Section(title: t.tr('administration'), body: _joinEntries(drug.administration, t, isAr)),
            _Section(title: t.tr('monitoring'), body: _joinEntries(drug.monitoring, t, isAr)),
            _Section(
              title: t.tr('overdose'),
              body: drug.overdose == null
                  ? t.tr('notAvailable')
                  : sectionText((drug.overdose!['text_en'] ?? '').toString(),
                      (drug.overdose!['text_ar'] ?? '').toString()),
            ),

            // ---- products (equivalents, §11) ---------------------------
            _Section(
              title: '${t.tr('products')} — ${t.tr('equivalentProduct')}',
              defaultOpen: true,
              custom: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(t.tr('equivalentProduct') + ' · ' + t.tr('genericName'),
                      style: const TextStyle(fontSize: 11, color: AphColors.textSecondary)),
                  const SizedBox(height: 8),
                  if (_products.isEmpty)
                    Text(t.tr('notAvailable'), style: const TextStyle(color: AphColors.textSecondary))
                  else
                    ..._products.map((p) => Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: ProductCard(
                            nameEn: (p['brand_name_en'] ?? '').toString(),
                            nameAr: (p['brand_name_ar'] ?? '').toString(),
                            details: '${p['strength'] ?? ''} ${p['dosage_form'] ?? ''}',
                            verificationStatus: (p['verification_status'] ?? 'draft').toString(),
                            isDemo: (p['is_demo'] == true),
                            onTap: () => Navigator.push(
                              context,
                              MaterialPageRoute(
                                  builder: (_) => ProductDetailScreen(productId: (p['id'] ?? '').toString())),
                            ),
                          ),
                        )),
                ],
              ),
            ),

            // ---- sources ----------------------------------------------
            _Section(
              title: t.tr('sources'),
              defaultOpen: true,
              custom: Column(
                children: drug.sources.isEmpty
                    ? [Text(t.tr('notAvailable'), style: const TextStyle(color: AphColors.textSecondary))]
                    : drug.sources
                        .map((s) => SourceCard(
                              name: (s['name'] ?? '').toString(),
                              url: (s['url'] as String?)?.isEmpty == true ? null : s['url'] as String?,
                              section: (s['section'] ?? '').toString(),
                              sourceType: (s['source_type'] ?? '').toString(),
                            ))
                        .toList(),
              ),
            ),

            // ---- last verified ----------------------------------------
            Padding(
              padding: const EdgeInsets.symmetric(vertical: AphSpacing.md),
              child: Text(
                '${t.tr('lastVerified')}: ${t.tr('notAvailable')}',
                style: const TextStyle(fontSize: 12, color: AphColors.textSecondary),
              ),
            ),

            // ---- medical disclaimer (§44) ------------------------------
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: AphColors.navy.withValues(alpha: 0.04),
                borderRadius: BorderRadius.circular(AphSpacing.radiusSm),
                border: Border.all(color: AphColors.border),
              ),
              child: Text(t.tr('aiDisclaimer'), style: const TextStyle(fontSize: 11, height: 1.5)),
            ),
          ]),
        ),
      ]),
    );
  }

  String _joinEntries(List<Map<String, dynamic>> entries, AppLocalizations t, bool isAr,
      {bool offLabelAware = false}) {
    if (entries.isEmpty) return t.tr('notAvailable');
    return entries.map((e) {
      final en = (e['text_en'] ?? '').toString();
      final ar = (e['text_ar'] ?? '').toString();
      final text = isAr && ar.isNotEmpty ? ar : (en.isNotEmpty ? en : t.tr('notAvailable'));
      final offLabel = offLabelAware && e['is_off_label'] == true ? ' [off-label]' : '';
      return '• $text$offLabel';
    }).join('\n');
  }
}

class _Section extends StatelessWidget {
  const _Section({required this.title, this.body = '', this.custom, this.defaultOpen = false});

  final String title;
  final String body;
  final Widget? custom;
  final bool defaultOpen;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: AphColors.surface,
        borderRadius: BorderRadius.circular(AphSpacing.radiusSm),
        border: Border.all(color: AphColors.border),
      ),
      child: ExpansionTile(
        initiallyExpanded: defaultOpen,
        shape: const Border(),
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
            child: custom ??
                Text(body, style: const TextStyle(height: 1.55, fontSize: 13)),
          ),
        ],
      ),
    );
  }
}
