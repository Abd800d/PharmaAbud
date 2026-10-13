/// Premium search experience (§9, §10): instant search, suggestions,
/// recent searches, generic vs commercial distinction, no-result guidance.
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../app_state.dart';
import '../../core/config/app_config.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/theme/app_theme.dart';
import '../../shared/models/models.dart';
import '../../shared/widgets/cards.dart';
import '../../shared/widgets/common.dart';
import '../../shared/widgets/states.dart';
import '../drugs/drug_detail_screen.dart';
import '../products/product_detail_screen.dart';
import '../scan/scan_screen.dart';

class SearchScreen extends StatefulWidget {
  const SearchScreen({super.key, this.initialQuery = ''});

  final String initialQuery;

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  final _controller = TextEditingController();
  Timer? _debounce;
  List<SearchHitModel> _hits = const [];
  List<String> _suggestions = const [];
  bool _loading = false;
  String _error = '';

  @override
  void initState() {
    super.initState();
    _controller.text = widget.initialQuery;
    if (widget.initialQuery.isNotEmpty) _runSearch(widget.initialQuery);
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _controller.dispose();
    super.dispose();
  }

  void _onChanged(String q) {
    _debounce?.cancel();
    _debounce = Timer(AppConfig.searchDebounce, () => _runSearch(q));
  }

  Future<void> _runSearch(String q) async {
    if (q.trim().isEmpty) {
      setState(() { _hits = const []; _suggestions = const []; _error = ''; });
      return;
    }
    setState(() { _loading = true; _error = ''; });
    final app = context.read<AppState>();
    try {
      final result = await app.repository.search(q.trim(), offline: !app.isOnline);
      await app.addRecentSearch(q.trim());
      setState(() {
        _hits = result.hits;
        _suggestions = result.suggestions;
        _loading = false;
      });
    } catch (e) {
      setState(() { _loading = false; _error = e.toString(); });
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final app = context.watch<AppState>();

    return Scaffold(
      appBar: AppHeader(showBrand: false, title: t.tr('searchResults'), actions: [
        IconButton(
          icon: const Icon(Icons.qr_code_scanner),
          tooltip: t.tr('scanBarcode'),
          onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ScanScreen())),
        ),
      ]),
      body: Column(children: [
        OfflineBanner(visible: !app.isOnline),
        Padding(
          padding: const EdgeInsets.all(AphSpacing.md),
          child: AphSearchBar(
            controller: _controller,
            onChanged: _onChanged,
            onSubmitted: _runSearch,
            onScanTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ScanScreen())),
          ),
        ),
        Expanded(child: _buildResults(t)),
      ]),
    );
  }

  Widget _buildResults(AppLocalizations t) {
    if (_error.isNotEmpty) return ErrorState(message: t.tr('networkError'), onRetry: () => _runSearch(_controller.text));
    if (_loading && _hits.isEmpty) return const LoadingSkeleton();

    if (_controller.text.trim().isEmpty) {
      return EmptyState(message: t.tr('searchHint'), icon: Icons.search);
    }

    if (_hits.isEmpty) {
      // no-result guidance (§68)
      return EmptyState(
        message: t.tr('noResults'),
        icon: Icons.search_off,
        action: Column(children: [
          Text(t.tr('checkSpelling'), style: const TextStyle(color: AphColors.textSecondary)),
          Text(t.tr('searchByIngredient'), style: const TextStyle(color: AphColors.textSecondary)),
          Text(t.tr('searchByBrand'), style: const TextStyle(color: AphColors.textSecondary)),
          Text(t.tr('searchByManufacturer'), style: const TextStyle(color: AphColors.textSecondary)),
          if (_suggestions.isNotEmpty) ...[
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              children: _suggestions
                  .map((s) => ActionChip(label: Text('${t.tr('didYouMean')} $s'), onPressed: () {
                        _controller.text = s;
                        _runSearch(s);
                      }))
                  .toList(),
            ),
          ],
          const SizedBox(height: 16),
          OutlinedButton.icon(
            onPressed: () => _showRequestDialog(t),
            icon: const Icon(Icons.add),
            label: Text(t.tr('requestNewDrug')),
          ),
        ]),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: AphSpacing.md),
      itemCount: _hits.length + 1,
      itemBuilder: (context, i) {
        if (i == 0) {
          return Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text('${_hits.length} / ${_hits.length} ${t.tr('searchResults')}',
                style: const TextStyle(color: AphColors.textSecondary, fontSize: 12)),
          );
        }
        final hit = _hits[i - 1];
        final isDrug = hit.kind == 'drug';
        return Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.only(left: 4, bottom: 2),
                child: Text(
                  isDrug ? t.tr('genericDrug') : t.tr('commercialProduct'),
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0.5,
                    color: isDrug ? AphColors.cyan : AphColors.emerald,
                  ),
                ),
              ),
              isDrug
                  ? DrugCard(
                      nameEn: hit.nameEn,
                      nameAr: hit.nameAr,
                      subtitle: hit.subtitle,
                      verificationStatus: hit.verificationStatus,
                      isDemo: hit.isDemo,
                      onTap: () => Navigator.push(context,
                          MaterialPageRoute(builder: (_) => DrugDetailScreen(drugId: hit.id))),
                    )
                  : ProductCard(
                      nameEn: hit.nameEn,
                      nameAr: hit.nameAr,
                      details: hit.subtitle,
                      verificationStatus: hit.verificationStatus,
                      isDemo: hit.isDemo,
                      onTap: () => Navigator.push(context,
                          MaterialPageRoute(builder: (_) => ProductDetailScreen(productId: hit.id))),
                    ),
            ],
          ),
        );
      },
    );
  }

  void _showRequestDialog(AppLocalizations t) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(t.tr('requestNewDrug')),
        content: Text(t.tr('aiDisclaimer')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: Text(t.tr('cancel'))),
          FilledButton(onPressed: () => Navigator.pop(context), child: Text(t.tr('save'))),
        ],
      ),
    );
  }
}
