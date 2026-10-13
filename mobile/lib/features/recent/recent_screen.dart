/// Recent searches (§35) — stored locally, clearable, privacy-respecting.
import 'package:flutter/material.dart';

import '../../core/database/local_database.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/theme/app_theme.dart';
import '../../shared/widgets/common.dart';
import '../../shared/widgets/states.dart';
import '../search/search_screen.dart';

class RecentScreen extends StatefulWidget {
  const RecentScreen({super.key});

  @override
  State<RecentScreen> createState() => _RecentScreenState();
}

class _RecentScreenState extends State<RecentScreen> {
  List<String> _searches = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final rows = await LocalDatabase.instance.recentSearches(limit: 50);
    setState(() => _searches = rows);
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppHeader(
        showBrand: false,
        title: t.tr('recentSearches'),
        actions: [
          if (_searches.isNotEmpty)
            TextButton(
              onPressed: () async {
                await LocalDatabase.instance.clearRecentSearches();
                _load();
              },
              child: Text(t.tr('clearAll')),
            ),
        ],
      ),
      body: _searches.isEmpty
          ? EmptyState(message: t.tr('noResults'), icon: Icons.history)
          : ListView.separated(
              padding: const EdgeInsets.all(AphSpacing.md),
              itemCount: _searches.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (context, i) {
                final q = _searches[i];
                return ListTile(
                  leading: const Icon(Icons.history, color: AphColors.textSecondary),
                  title: Text(q),
                  trailing: IconButton(
                    icon: const Icon(Icons.close, size: 18),
                    onPressed: () async {
                      await LocalDatabase.instance.removeRecentSearch(q);
                      _load();
                    },
                  ),
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => SearchScreen(initialQuery: q)),
                  ),
                );
              },
            ),
    );
  }
}
