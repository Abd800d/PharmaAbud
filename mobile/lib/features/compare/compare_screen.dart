/* Compare screen (§79–§81): side-by-side comparison of two drugs.
 *
 * CRITICAL: comparison shows differences and equivalences between records
 * only. It is NOT a therapeutic recommendation and NOT substitution advice.
 * "Equivalent Product" never means clinically interchangeable.
 */
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../app_state.dart';
import '../../core/localization/app_localizations.dart';
import '../../shared/models/models.dart';
import '../drugs/drug_detail_screen.dart';

class CompareScreen extends StatefulWidget {
  final String? initialDrugId;
  const CompareScreen({super.key, this.initialDrugId});

  @override
  State<CompareScreen> createState() => _CompareScreenState();
}

class _CompareScreenState extends State<CompareScreen> {
  DrugModel? _left;
  DrugModel? _right;
  bool _loadingInitial = false;

  @override
  void initState() {
    super.initState();
    final id = widget.initialDrugId;
    if (id != null && id.isNotEmpty) {
      _loadingInitial = true;
      context.read<AppState>().repository.getDrug(id).then((d) {
        if (mounted) setState(() { _left = d; _loadingInitial = false; });
      }).catchError((_) {
        if (mounted) setState(() { _loadingInitial = false; });
      });
    }
  }

  Future<void> _pick(bool isLeft) async {
    final state = context.read<AppState>();
    final exclude = <String>{
      if (_left != null) _left!.id,
      if (_right != null) _right!.id,
    };
    final drug = await showDrugPicker(context, state, exclude: exclude);
    if (drug != null && mounted) {
      setState(() {
        if (isLeft) {
          _left = drug;
        } else {
          _right = drug;
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final ready = _left != null && _right != null;
    return Scaffold(
      appBar: AppBar(title: Text(t.tr('compare'))),
      body: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    Expanded(child: _DrugSlot(label: 'A', drug: _left, onTap: () => _pick(true))),
                    const SizedBox(width: 8),
                    Expanded(child: _DrugSlot(label: 'B', drug: _right, onTap: () => _pick(false))),
                  ]),
                  if (_loadingInitial) const LinearProgressIndicator(),
                  const SizedBox(height: 8),
                  Text(
                    t.tr('compareDisclaimer'),
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.red.shade700),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 8),
          if (!ready)
            Padding(
              padding: const EdgeInsets.all(24),
              child: Center(child: Text(t.tr('comparePickTwo'))),
            )
          else
            _ComparisonTable(left: _left!, right: _right!),
        ],
      ),
    );
  }
}

class _DrugSlot extends StatelessWidget {
  final String label;
  final DrugModel? drug;
  final VoidCallback onTap;
  const _DrugSlot({required this.label, required this.drug, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final name = drug == null
        ? '—'
        : (drug!.genericNameEn.isNotEmpty ? drug!.genericNameEn : (drug!.genericNameAr.isNotEmpty ? drug!.genericNameAr : drug!.id));
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Container(
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Drug $label', style: Theme.of(context).textTheme.labelSmall),
            const SizedBox(height: 4),
            Text(name, maxLines: 2, overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.titleSmall),
            if (drug != null && drug!.isDemo)
              Container(
                margin: const EdgeInsets.only(top: 4),
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: Colors.orange.shade100,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: const Text('DEMO', style: TextStyle(fontSize: 10)),
              ),
          ],
        ),
      ),
    );
  }
}

class _ComparisonTable extends StatelessWidget {
  final DrugModel left;
  final DrugModel right;
  const _ComparisonTable({required this.left, required this.right});

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    String nameOf(DrugModel d) =>
        d.genericNameEn.isNotEmpty ? d.genericNameEn : (d.genericNameAr.isNotEmpty ? d.genericNameAr : d.id);
    final rows = <(String, String, String)>[
      (t.tr('genericName'), nameOf(left), nameOf(right)),
      (t.tr('genericName') + ' (AR)', left.genericNameAr.isNotEmpty ? left.genericNameAr : '—',
          right.genericNameAr.isNotEmpty ? right.genericNameAr : '—'),
      (t.tr('drugClass'), left.drugClass.isNotEmpty ? left.drugClass : '—',
          right.drugClass.isNotEmpty ? right.drugClass : '—'),
      (t.tr('mechanism'), _short(left.mechanismEn), _short(right.mechanismEn)),
      (t.tr('verificationStatus'), left.verificationStatus, right.verificationStatus),
      (t.tr('isDemo'), left.isDemo ? 'DEMO' : '—', right.isDemo ? 'DEMO' : '—'),
    ];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(t.tr('differencesAndEquivalences'),
                style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 8),
            Table(
              columnWidths: const {
                0: FlexColumnWidth(1.1),
                1: FlexColumnWidth(1.4),
                2: FlexColumnWidth(1.4),
              },
              border: TableBorder.all(
                  color: Theme.of(context).colorScheme.outlineVariant, width: 0.5),
              children: [
                TableRow(children: [
                  _cell(context, '', bold: true),
                  _cell(context, nameOf(left), bold: true),
                  _cell(context, nameOf(right), bold: true),
                ]),
                for (final (label, a, b) in rows)
                  TableRow(
                    decoration: a != b ? BoxDecoration(color: Colors.amber.shade50) : null,
                    children: [
                      _cell(context, label, bold: true),
                      _cell(context, a),
                      _cell(context, b),
                    ],
                  ),
              ],
            ),
            const SizedBox(height: 10),
            Text(t.tr('compareNotSubstitution'), style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 6),
            InkWell(
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => DrugDetailScreen(drugId: left.id)),
              ),
              child: Text(t.tr('openFullMonograph'),
                  style: TextStyle(color: Theme.of(context).colorScheme.primary)),
            ),
          ],
        ),
      ),
    );
  }

  String _short(String? s) {
    if (s == null || s.isEmpty) return '—';
    return s.length > 80 ? '${s.substring(0, 80)}…' : s;
  }

  Widget _cell(BuildContext context, String text, {bool bold = false}) => Padding(
        padding: const EdgeInsets.all(6),
        child: Text(text,
            style: bold ? const TextStyle(fontWeight: FontWeight.w600) : null),
      );
}

/// Simple search-modal to choose a drug for comparison.
Future<DrugModel?> showDrugPicker(BuildContext context, AppState state,
    {Set<String> exclude = const {}}) async {
  return showModalBottomSheet<DrugModel>(
    context: context,
    isScrollControlled: true,
    builder: (ctx) => _DrugPickerSheet(state: state, exclude: exclude),
  );
}

class _DrugPickerSheet extends StatefulWidget {
  final AppState state;
  final Set<String> exclude;
  const _DrugPickerSheet({required this.state, required this.exclude});

  @override
  State<_DrugPickerSheet> createState() => _DrugPickerSheetState();
}

class _DrugPickerSheetState extends State<_DrugPickerSheet> {
  List<SearchHitModel> _results = [];
  bool _loading = false;

  Future<void> _search(String q) async {
    if (q.trim().length < 2) {
      setState(() => _results = []);
      return;
    }
    setState(() => _loading = true);
    try {
      final bundle = await widget.state.repository.search(q.trim(), limit: 12);
      setState(() => _results = bundle.hits
          .where((r) => r.kind == 'drug' && !widget.exclude.contains(r.id))
          .toList());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return Padding(
      padding: EdgeInsets.only(
        bottom: MediaQuery.of(context).viewInsets.bottom,
        left: 12,
        right: 12,
        top: 12,
      ),
      child: SizedBox(
        height: MediaQuery.of(context).size.height * 0.6,
        child: Column(
          children: [
            TextField(
              autofocus: true,
              decoration: InputDecoration(
                labelText: t.tr('search'),
                prefixIcon: const Icon(Icons.search),
              ),
              onChanged: _search,
            ),
            const SizedBox(height: 8),
            if (_loading) const LinearProgressIndicator(),
            Expanded(
              child: ListView(
                children: [
                  for (final hit in _results)
                    ListTile(
                      title: Text(hit.nameEn.isNotEmpty ? hit.nameEn : hit.nameAr),
                      subtitle: hit.isDemo ? const Text('DEMO DATA') : Text(hit.subtitle),
                      onTap: () async {
                        final full = await widget.state.repository.getDrug(hit.id);
                        if (context.mounted) Navigator.pop(context, full);
                      },
                    ),
                  if (!_loading && _results.isEmpty)
                    Padding(
                      padding: const EdgeInsets.all(16),
                      child: Center(child: Text(t.tr('noResults'))),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
