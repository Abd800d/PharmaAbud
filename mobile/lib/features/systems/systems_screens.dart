/// Body Systems list (§13) and System detail with therapeutic groups/classes.
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../app_state.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/network/api_client.dart';
import '../../core/theme/app_theme.dart';
import '../../shared/models/models.dart';
import '../../shared/widgets/cards.dart';
import '../../shared/widgets/common.dart';
import '../../shared/widgets/states.dart';
import '../drugs/drug_detail_screen.dart';

class SystemsScreen extends StatefulWidget {
  const SystemsScreen({super.key});

  @override
  State<SystemsScreen> createState() => _SystemsScreenState();
}

class _SystemsScreenState extends State<SystemsScreen> {
  late Future<List<BodySystemModel>> _future;

  @override
  void initState() {
    super.initState();
    _future = context.read<AppState>().repository.getSystems();
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppHeader(showBrand: false, title: t.tr('bodySystems')),
      body: FutureBuilder<List<BodySystemModel>>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) return const LoadingSkeleton(lines: 2);
          final systems = snap.data ?? const [];
          if (systems.isEmpty) return EmptyState(message: t.tr('noResults'));
          return GridView.builder(
            padding: const EdgeInsets.all(AphSpacing.md),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              mainAxisSpacing: 10,
              crossAxisSpacing: 10,
              childAspectRatio: 1.5,
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
    );
  }
}

class SystemDetailScreen extends StatefulWidget {
  const SystemDetailScreen({super.key, required this.system});

  final BodySystemModel system;

  @override
  State<SystemDetailScreen> createState() => _SystemDetailScreenState();
}

class _SystemDetailScreenState extends State<SystemDetailScreen> {
  List<dynamic> _groups = const [];
  List<dynamic> _drugs = const [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final app = context.read<AppState>();
    try {
      final api = ApiClient();
      final groups = await api.get('/systems/${widget.system.id}/groups');
      final drugs = await api.get('/search', query: {
        'q': '',
        'system_id': widget.system.id,
        'kinds': 'drug',
        'limit': '50',
      });
      setState(() {
        _groups = groups['items'] as List;
        _drugs = (drugs['items'] as List).where((h) => h['kind'] == 'drug').toList();
        _loading = false;
      });
    } catch (_) {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final isAr = context.watch<AppState>().isArabic;

    return Scaffold(
      appBar: AppHeader(showBrand: false, title: isAr ? widget.system.nameAr : widget.system.nameEn),
      body: _loading
          ? const LoadingSkeleton()
          : ListView(padding: const EdgeInsets.all(AphSpacing.md), children: [
              Text(
                isAr ? widget.system.nameAr : widget.system.nameEn,
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 4),
              Text('${widget.system.drugCount} ${t.tr('products')}',
                  style: const TextStyle(color: AphColors.textSecondary)),
              const SizedBox(height: AphSpacing.md),

              // hierarchy: Therapeutic Group -> Pharmacological Class (§70)
              ..._groups.map((g) => Card(
                    margin: const EdgeInsets.only(bottom: 10),
                    child: ExpansionTile(
                      shape: const Border(),
                      title: Text((isAr ? (g['name_ar'] ?? '') : (g['name_en'] ?? '')).toString(),
                          style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
                      children: [
                        Padding(
                          padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                          child: Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: ((g['pharmacological_classes'] as List?) ?? const [])
                                .map((c) => Chip(
                                      label: Text(
                                        (isAr ? (c['name_ar'] ?? '') : (c['name_en'] ?? '')).toString(),
                                        style: const TextStyle(fontSize: 11),
                                      ),
                                    ))
                                .toList(),
                          ),
                        ),
                      ],
                    ),
                  )),

              SectionHeader(title: t.tr('genericDrug')),
              ..._drugs.map((hit) => Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: DrugCard(
                      nameEn: (hit['name_en'] ?? '').toString(),
                      nameAr: (hit['name_ar'] ?? '').toString(),
                      subtitle: (hit['subtitle'] ?? '').toString(),
                      verificationStatus: (hit['verification_status'] ?? 'draft').toString(),
                      isDemo: hit['is_demo'] == true,
                      onTap: () => Navigator.push(
                        context,
                        MaterialPageRoute(
                            builder: (_) => DrugDetailScreen(drugId: (hit['id'] ?? '').toString())),
                      ),
                    ),
                  )),
            ]),
    );
  }
}
