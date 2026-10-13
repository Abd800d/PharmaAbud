/// Scan screen (§17–§18): barcode scanning + OCR-ready image pipeline.
/// OCR results are ALWAYS estimates — manual correction is always possible.
import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:provider/provider.dart';

import '../../app_state.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/theme/app_theme.dart';
import '../../shared/widgets/common.dart';
import '../../shared/widgets/states.dart';
import '../products/product_detail_screen.dart';

class ScanScreen extends StatefulWidget {
  const ScanScreen({super.key, this.mode = ScanMode.barcode});

  final ScanMode mode;

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

enum ScanMode { barcode, image }

class _ScanScreenState extends State<ScanScreen> {
  bool _handled = false;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppHeader(showBrand: false, title: t.tr('scanTitle')),
      body: Column(children: [
        OfflineBanner(visible: !context.watch<AppState>().isOnline),
        Expanded(
          child: widget.mode == ScanMode.barcode ? _buildBarcode(t) : _buildOcr(t),
        ),
      ]),
    );
  }

  Widget _buildBarcode(AppLocalizations t) {
    return Column(children: [
      Expanded(
        child: ClipRRect(
          borderRadius: const BorderRadius.vertical(bottom: Radius.circular(16)),
          child: MobileScanner(
            onDetect: (capture) async {
              if (_handled) return;
              final barcodes = capture.barcodes;
              if (barcodes.isEmpty) return;
              final value = barcodes.first.rawValue;
              if (value == null || value.isEmpty) return;
              _handled = true;
              await _lookupBarcode(value);
            },
          ),
        ),
      ),
      Padding(
        padding: const EdgeInsets.all(AphSpacing.md),
        child: Column(children: [
          Text(t.tr('pointCamera'), textAlign: TextAlign.center,
              style: const TextStyle(color: AphColors.textSecondary)),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () => Navigator.pushReplacement(
                    context,
                    MaterialPageRoute(
                        builder: (_) => const ScanScreen(mode: ScanMode.image))),
                icon: const Icon(Icons.document_scanner_outlined),
                label: Text(t.tr('scanImage')),
              ),
            ),
          ]),
        ]),
      ),
    ]);
  }

  Widget _buildOcr(AppLocalizations t) {
    final controller = TextEditingController();
    return Padding(
      padding: const EdgeInsets.all(AphSpacing.md),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(t.tr('ocrNote'),
            style: const TextStyle(fontSize: 12, color: AphColors.amber, height: 1.5)),
        const SizedBox(height: AphSpacing.md),
        Text(t.tr('scanImage'), style: const TextStyle(fontWeight: FontWeight.w700)),
        const SizedBox(height: 8),
        // OCR-ready architecture: on-device OCR (e.g. ML Kit) submits extracted
        // text here; the server matches candidates with confidence estimates.
        TextField(
          controller: controller,
          maxLines: 4,
          decoration: InputDecoration(hintText: t.tr('ocrNote')),
        ),
        const SizedBox(height: 12),
        FilledButton.icon(
          onPressed: () async {
            final app = context.read<AppState>();
            try {
              final result = await app.repository.askAi(controller.text, language: app.isArabic ? 'ar' : 'en');
              if (!mounted) return;
              showDialog(
                context: context,
                builder: (context) => AlertDialog(
                  title: Text(t.tr('ocrNote')),
                  content: Text((result['answer'] ?? '').toString()),
                  actions: [
                    TextButton(onPressed: () => Navigator.pop(context), child: Text(t.tr('cancel'))),
                  ],
                ),
              );
            } catch (_) {
              ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(t.tr('networkError'))));
            }
          },
          icon: const Icon(Icons.search),
          label: Text(t.tr('search')),
        ),
      ]),
    );
  }

  Future<void> _lookupBarcode(String barcode) async {
    final t = AppLocalizations.of(context);
    final app = context.read<AppState>();
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const Center(child: CircularProgressIndicator()),
    );
    final product = await app.repository.findByBarcode(barcode);
    if (!mounted) return;
    Navigator.pop(context); // close spinner

    if (product == null) {
      // unknown barcode → no invented data (§18)
      showDialog(
        context: context,
        builder: (context) => AlertDialog(
          title: Text(t.tr('barcode')),
          content: Text('${t.tr('noResults')}\n\n$barcode'),
          actions: [
            TextButton(
              onPressed: () { Navigator.pop(context); _handled = false; },
              child: Text(t.tr('retry')),
            ),
            TextButton(onPressed: () => Navigator.pop(context), child: Text(t.tr('cancel'))),
          ],
        ),
      );
      return;
    }
    await Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => ProductDetailScreen(productId: product.id)),
    );
    _handled = false;
  }
}
