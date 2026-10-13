/// Favorites + Recently viewed (§34–§35) — fully offline-capable.
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../app_state.dart';
import '../../core/database/local_database.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/theme/app_theme.dart';
import '../../shared/widgets/common.dart';
import '../../shared/widgets/states.dart';
import '../drugs/drug_detail_screen.dart';
import '../products/product_detail_screen.dart';

class FavoritesScreen extends StatefulWidget {
  const FavoritesScreen({super.key});

  @override
  State<FavoritesScreen> createState() => _FavoritesScreenState();
}

class _FavoritesScreenState extends State<FavoritesScreen> {
  List<Map<String, dynamic>> _favorites = const [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final rows = await LocalDatabase.instance.listFavorites();
    setState(() { _favorites = rows; _loading = false; });
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final app = context.watch<AppState>();
    return Scaffold(
      appBar: AppHeader(showBrand: false, title: t.tr('favorites')),
      body: Column(children: [
        OfflineBanner(visible: !app.isOnline),
        Expanded(
          child: _loading
              ? const LoadingSkeleton()
              : _favorites.isEmpty
                  ? EmptyState(message: t.tr('noResults'), icon: Icons.favorite_border)
                  : RefreshIndicator(
                      onRefresh: _load,
                      child: ListView.builder(
                        padding: const EdgeInsets.all(AphSpacing.md),
                        itemCount: _favorites.length,
                        itemBuilder: (context, i) {
                          final f = _favorites[i];
                          final isDrug = f['entity_type'] == 'drug';
                          return Card(
                            margin: const EdgeInsets.only(bottom: 8),
                            child: ListTile(
                              leading: Icon(
                                isDrug ? Icons.medication_outlined : Icons.inventory_2_outlined,
                                color: isDrug ? AphColors.cyan : AphColors.emerald,
                              ),
                              title: Text((f['name_en'] ?? '').toString(),
                                  style: const TextStyle(fontWeight: FontWeight.w700)),
                              subtitle: Text((f['name_ar'] ?? '').toString(), textDirection: TextDirection.rtl),
                              trailing: IconButton(
                                icon: const Icon(Icons.favorite, color: AphColors.red),
                                onPressed: () async {
                                  await LocalDatabase.instance
                                      .removeFavorite(f['entity_type'] as String, f['entity_id'] as String);
                                  await LocalDatabase.instance.enqueueSync(
                                    entityType: 'favorite',
                                    entityId: f['entity_id'] as String,
                                    operation: 'favorite_remove',
                                  );
                                  _load();
                                },
                              ),
                              onTap: () => Navigator.push(
                                context,
                                MaterialPageRoute(
                                  builder: (_) => isDrug
                                      ? DrugDetailScreen(drugId: f['entity_id'] as String)
                                      : ProductDetailScreen(productId: f['entity_id'] as String),
                                ),
                              ),
                            ),
                          );
                        },
                      ),
                    ),
        ),
      ]),
    );
  }
}
