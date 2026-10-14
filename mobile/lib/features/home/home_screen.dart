/// Home dashboard (§12): search, quick actions, 18 body systems, recents.
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../app_state.dart';
import '../../core/config/app_config.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/theme/app_theme.dart';
import '../../shared/models/models.dart';
import '../../shared/repositories/aph_repository.dart';
import '../../shared/widgets/cards.dart';
import '../../shared/widgets/common.dart';
import '../../shared/widgets/states.dart';
import '../drugs/drug_detail_screen.dart';
import '../scan/scan_screen.dart';
import '../search/search_screen.dart';
import '../systems/systems_screens.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late Future<List<BodySystemModel>> _systemsFuture;
  List<String> _recentSearches = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final app = context.read<AppState>();
    setState(() {
      _systemsFuture = app.repository.getSystems(offline: !app.isOnline);
      _recentSearches = const [];
    });
    _recentSearches = await app.repositorySearchHistory();
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final app = context.watch<AppState>();

    return Scaffold(
      appBar: AppHeader(actions: [
        SyncStatusChip(isOnline: app.isOnline, syncing: app.syncing, onTap: app.syncNow),
        IconButton(
          icon: const Icon(Icons.language),
          tooltip: t.tr('language'),
          onPressed: app.toggleLanguage,
        ),
      ]),
      body: Column(children: [
        OfflineBanner(visible: !app.isOnline),
        Expanded(
          child: RefreshIndicator(
            onRefresh: _load,
            child: ListView(padding: const EdgeInsets.all(AphSpacing.md), children: [
              // ---- main search ------------------------------------------
              AphSearchBar(
                onSubmitted: (q) => _openSearch(q),
                onScanTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ScanScreen())),
              ),
              const SizedBox(height: AphSpacing.md),

              // ---- quick actions ---------------------------------------
              Row(children: [
                _QuickAction(icon: Icons.search, label: t.tr('search'), onTap: () => _openSearch('')),
                const SizedBox(width: 10),
                _QuickAction(icon: Icons.qr_code_scanner, label: t.tr('barcode'), onTap: () {
                  Navigator.push(context, MaterialPageRoute(builder: (_) => const ScanScreen()));
                }),
                const SizedBox(width: 10),
                _QuickAction(icon: Icons.favorite_outline, label: t.tr('favorites'), onTap: () {
                  final shell = context.findAncestorStateOfType<State>();
                  if (shell != null) app.goToTab(4);
                }),
              ]),
              const SizedBox(height: AphSpacing.sm),

              // ---- body systems ----------------------------------------
              SectionHeader(title: t.tr('bodySystems')),
              FutureBuilder<List<BodySystemModel>>(
                future: _systemsFuture,
                builder: (context, snap) {
                  if (snap.connectionState != ConnectionState.done) return const LoadingSkeleton(lines: 2);
                  final systems = snap.data ?? const [];
                  if (systems.isEmpty) return EmptyState(message: t.tr('noResults'));
                  return GridView.builder(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 2,
                      mainAxisSpacing: 10,
                      crossAxisSpacing: 10,
                      childAspectRatio: 1.55,
                    ),
                    itemCount: systems.length,
                    itemBuilder: (context, i) {
                      final s = systems[i];
                      return SystemCard(
                        nameEn: s.nameEn,
                        nameAr: s.nameAr,
                        drugCount: s.drugCount,
                        onTap: () => Navigator.push(
                          context,
                          MaterialPageRoute(builder: (_) => SystemDetailScreen(system: s)),
                        ),
                      );
                    },
                  );
                },
              ),

              // ---- recent searches -------------------------------------
              if (_recentSearches.isNotEmpty) ...[
                SectionHeader(
                  title: t.tr('recentSearches'),
                  action: TextButton(onPressed: _clearRecents, child: Text(t.tr('clearAll'))),
                ),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: _recentSearches
                      .map((q) => ActionChip(label: Text(q), onPressed: () => _openSearch(q)))
                      .toList(),
                ),
              ],
              const SizedBox(height: AphSpacing.xl),
              Center(
                child: Text(AppConfig.copyright,
                    style: const TextStyle(fontSize: 11, color: AphColors.textSecondary)),
              ),
              const SizedBox(height: AphSpacing.lg),
            ]),
          ),
        ),
      ]),
    );
  }

  void _openSearch(String q) {
    Navigator.push(context, MaterialPageRoute(builder: (_) => SearchScreen(initialQuery: q)));
  }

  Future<void> _clearRecents() async {
    await context.read<AppState>().clearRecentSearches();
    await _load();
  }
}

class _QuickAction extends StatelessWidget {
  const _QuickAction({required this.icon, required this.label, required this.onTap});

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Material(
        color: AphColors.surface,
        borderRadius: BorderRadius.circular(AphSpacing.radius),
        child: InkWell(
          borderRadius: BorderRadius.circular(AphSpacing.radius),
          onTap: onTap,
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 14),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(AphSpacing.radius),
              border: Border.all(color: AphColors.border),
            ),
            child: Column(children: [
              Icon(icon, color: AphColors.cyan),
              const SizedBox(height: 6),
              Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
            ]),
          ),
        ),
      ),
    );
  }
}
