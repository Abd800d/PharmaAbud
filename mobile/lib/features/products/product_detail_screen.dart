/// Product detail screen (§15): commercial record + gallery + provenance.
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../app_state.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/theme/app_theme.dart';
import '../../shared/models/models.dart';
import '../../shared/widgets/common.dart';
import '../../shared/widgets/states.dart';
import '../drugs/drug_detail_screen.dart';

class ProductDetailScreen extends StatefulWidget {
  const ProductDetailScreen({super.key, required this.productId});

  final String productId;

  @override
  State<ProductDetailScreen> createState() => _ProductDetailScreenState();
}

class _ProductDetailScreenState extends State<ProductDetailScreen> {
  ProductModel? _product;
  bool _loading = true;
  String _error = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final app = context.read<AppState>();
    setState(() { _loading = true; _error = ''; });
    try {
      final p = await app.repository.getProduct(widget.productId, offline: !app.isOnline);
      setState(() { _product = p; _loading = false; });
    } catch (e) {
      setState(() { _loading = false; _error = e.toString(); });
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final app = context.watch<AppState>();

    if (_loading) return const Scaffold(body: LoadingSkeleton());
    if (_error.isNotEmpty || _product == null) {
      return Scaffold(
        appBar: AppHeader(showBrand: false, title: t.tr('error')),
        body: ErrorState(message: _error, onRetry: _load),
      );
    }

    final p = _product!;
    row(String label, String value) => Padding(
          padding: const EdgeInsets.symmetric(vertical: 6),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            SizedBox(width: 130, child: Text(label, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13))),
            Expanded(child: Text(value.isEmpty ? '—' : value, style: const TextStyle(fontSize: 13))),
          ]),
        );

    return Scaffold(
      appBar: AppHeader(showBrand: false, title: p.brandNameEn),
      body: Column(children: [
        OfflineBanner(visible: !app.isOnline),
        Expanded(
          child: ListView(padding: const EdgeInsets.all(AphSpacing.md), children: [
            Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(p.brandNameEn, style: Theme.of(context).textTheme.headlineSmall),
                  if (p.brandNameAr.isNotEmpty)
                    Text(p.brandNameAr,
                        textDirection: TextDirection.rtl,
                        style: const TextStyle(color: AphColors.textSecondary, fontSize: 15)),
                  const SizedBox(height: 8),
                  Wrap(spacing: 8, children: [
                    VerificationBadge(status: p.verificationStatus),
                    if (p.isDemo) const DemoBadge(),
                  ]),
                ]),
              ),
            ]),
            const SizedBox(height: AphSpacing.md),

            // image gallery placeholder wired to stored product_images (§16)
            if (p.images.isNotEmpty)
              SizedBox(
                height: 160,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  itemCount: p.images.length,
                  separatorBuilder: (_, __) => const SizedBox(width: 10),
                  itemBuilder: (context, i) {
                    final img = p.images[i];
                    return ClipRRect(
                      borderRadius: BorderRadius.circular(AphSpacing.radiusSm),
                      child: Container(
                        width: 160,
                        color: AphColors.border,
                        alignment: Alignment.center,
                        child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                          const Icon(Icons.image_outlined, color: AphColors.textSecondary),
                          const SizedBox(height: 6),
                          Text((img['kind'] ?? '').toString(),
                              style: const TextStyle(fontSize: 11, color: AphColors.textSecondary)),
                        ]),
                      ),
                    );
                  },
                ),
              )
            else
              Container(
                height: 120,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: AphColors.border.withValues(alpha: 0.4),
                  borderRadius: BorderRadius.circular(AphSpacing.radiusSm),
                ),
                child: const Icon(Icons.inventory_2_outlined, size: 40, color: AphColors.textSecondary),
              ),
            const SizedBox(height: AphSpacing.md),

            Card(
              child: Padding(
                padding: const EdgeInsets.all(AphSpacing.md),
                child: Column(children: [
                  row(t.tr('genericName'), (p.drug?['generic_name_en'] ?? '') as String),
                  row(t.tr('strength'), p.strength),
                  row(t.tr('dosageForm'), p.dosageForm),
                  row(t.tr('route'), p.route),
                  row(t.tr('manufacturer'), p.manufacturerName ?? ''),
                  row(t.tr('package'), (p.packages.isNotEmpty ? (p.packages.first['package_size'] ?? '') : '') as String),
                  row(t.tr('barcode'), p.barcode),
                  row(t.tr('registrationNumber'), p.registrationNumber),
                  row(t.tr('productStatus'), p.status),
                  if (p.ingredients.isNotEmpty)
                    row(t.tr('genericName') + ' (ingredients)',
                        p.ingredients.map((i) => (i['ingredient_name_en'] ?? '') as String).join(' + ')),
                ]),
              ),
            ),

            if (p.drug != null) ...[
              const SizedBox(height: AphSpacing.md),
              FilledButton.icon(
                onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                      builder: (_) => DrugDetailScreen(drugId: (p.drug!['id'] ?? '') as String)),
                ),
                icon: const Icon(Icons.medication_outlined),
                label: Text(t.tr('genericDrug') + ': ' + ((p.drug!['generic_name_en'] ?? '') as String)),
              ),
            ],

            const SizedBox(height: AphSpacing.lg),
            Text(t.tr('disclaimer'),
                style: const TextStyle(fontSize: 11, color: AphColors.textSecondary)),
            const SizedBox(height: 6),
            Text(t.tr('aiDisclaimer'),
                style: const TextStyle(fontSize: 11, height: 1.5, color: AphColors.textSecondary)),
          ]),
        ),
      ]),
    );
  }
}
