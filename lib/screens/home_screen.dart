import 'dart:io';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';
import '../app_settings.dart';
import '../db/db_helper.dart';
import '../models/drug_models.dart';
import '../services/ai_client.dart';
import '../services/import_service.dart';
import '../services/online_service.dart';
import '../services/search_service.dart';
import '../services/sync_service.dart';
import '../widgets/drug_image.dart';
import 'add_drug_screen.dart';
import 'drug_detail_screen.dart';
import 'pharmacy_screen.dart';
import 'settings_screen.dart';

const _sysIcons = <String, IconData>{
  'nervous': Icons.psychology, 'cardiovascular': Icons.favorite,
  'blood': Icons.water_drop, 'respiratory': Icons.air,
  'gi': Icons.medication_liquid, 'hepatobiliary': Icons.science,
  'endocrine': Icons.monitor_heart, 'renal': Icons.cleaning_services,
  'reproductive': Icons.wc, 'musculoskeletal': Icons.accessibility_new,
  'skin': Icons.healing, 'eye': Icons.visibility, 'ent': Icons.hearing,
  'immune': Icons.shield, 'antiinfective': Icons.bug_report,
  'oncology': Icons.biotech, 'emergency': Icons.emergency,
  'misc': Icons.vaccines,
};

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _tab = 0;
  bool _online = true;

  @override
  void initState() {
    super.initState();
    Connectivity().onConnectivityChanged.listen((r) {
      if (mounted) setState(() => _online = !r.contains(ConnectivityResult.none));
    });
    Connectivity().checkConnectivity().then((r) {
      if (mounted) setState(() => _online = !r.contains(ConnectivityResult.none));
    });
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      _HomeTab(onOpenSystems: () => setState(() => _tab = 1)),
      const _SystemsTab(),
      const _AiTab(),
      const _MessagesTab(),
      const _MoreTab(),
    ];
    return Scaffold(
      appBar: AppBar(
        title: Row(children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
            decoration: BoxDecoration(color: const Color(0xFF14C8B4),
                borderRadius: BorderRadius.circular(10)),
            child: const Text('APH',
                style: TextStyle(fontWeight: FontWeight.w900, color: Color(0xFF04222B))),
          ),
          const SizedBox(width: 9),
          const Expanded(child: Text('AbdulmajeedPharma',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold))),
          Text(kOwnerEn,
              style: const TextStyle(fontSize: 9, color: Color(0xFFFFB020))),
        ]),
        actions: [
          Center(child: Text(_online ? '🟢 Online' : '🔴 Offline',
              style: const TextStyle(fontSize: 10))),
          IconButton(
            icon: Text(S.ar ? 'EN' : 'عربي',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
            onPressed: () => AppSettings.setArabic(!S.ar),
          ),
          IconButton(
            tooltip: S.t('Settings — AI & sync', 'الإعدادات — الذكاء الاصطناعي والمزامنة'),
            icon: const Icon(Icons.tune),
            onPressed: () => Navigator.push(context,
                MaterialPageRoute(builder: (_) => const SettingsScreen())),
          ),
        ],
      ),
      body: pages[_tab],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() => _tab = i),
        destinations: [
          NavigationDestination(icon: const Icon(Icons.home),
              label: S.t('Home', 'الرئيسية')),
          NavigationDestination(icon: const Icon(Icons.grid_view),
              label: S.t('Systems', 'التصنيفات')),
          NavigationDestination(icon: const Icon(Icons.smart_toy),
              label: S.t('AI Assistant', 'المساعد الذكي')),
          NavigationDestination(icon: const Icon(Icons.forum),
              label: S.t('Messages', 'الرسائل')),
          NavigationDestination(icon: const Icon(Icons.more_horiz),
              label: S.t('More', 'المزيد')),
        ],
      ),
    );
  }
}

class _DrugTile extends StatelessWidget {
  final GenericDrug drug;
  final String matchedBrand;

  /// المنتجات التجارية لهذا الدواء — تُعرض مقسّمة حسب الشركة المصنعة
  /// وتحتها الوكيل والدولة (كما طلب د. عبدالمجيد في قائمة البحث)
  final List<TradeProduct> products;
  const _DrugTile(
      {required this.drug, this.matchedBrand = '', this.products = const []});

  @override
  Widget build(BuildContext context) {
    final sys = systemById(drug.systemId);
    final title = Text(drug.nameEn,
        style: const TextStyle(fontWeight: FontWeight.bold));
    final subtitle = Text(
        '${drug.nameAr} • ${S.ar ? sys.ar : sys.en} • ${S.ar ? drug.subgroupAr : drug.subgroupEn}'
        '${matchedBrand.isNotEmpty ? '\n↳ ${S.t('matched product', 'طابق منتجاً')}: $matchedBrand' : ''}');
    if (products.isEmpty) {
      return Card(child: ListTile(
        leading: DrugImage(path: drug.imagePath),
        title: title,
        subtitle: subtitle,
        trailing: const Icon(Icons.chevron_right),
        onTap: () => Navigator.push(context,
            MaterialPageRoute(builder: (_) => DrugDetailScreen(drug: drug))),
      ));
    }
    final groups = <String, List<TradeProduct>>{};
    for (final pr in products) {
      final key = pr.manufacturer.isEmpty
          ? S.t('Unknown manufacturer', 'شركة غير محددة')
          : pr.manufacturer;
      groups.putIfAbsent(key, () => <TradeProduct>[]).add(pr);
    }
    return Card(
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          leading: DrugImage(path: drug.imagePath),
          title: title,
          subtitle: subtitle,
          childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 10),
          onExpansionChanged: (_) {},
          children: [
            Align(
              alignment: AlignmentDirectional.centerStart,
              child: Text(
                  '${S.t('Trade products', 'المنتجات التجارية')} (${products.length})',
                  style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      color: Color(0xFF14C8B4))),
            ),
            const SizedBox(height: 4),
            for (final g in groups.entries) ...[
              Align(
                alignment: AlignmentDirectional.centerStart,
                child: Padding(
                  padding: const EdgeInsets.only(top: 6, bottom: 2),
                  child: Text('🏭 ${g.key}',
                      style: const TextStyle(
                          fontSize: 12, fontWeight: FontWeight.bold)),
                ),
              ),
              for (final pr in g.value)
                Align(
                  alignment: AlignmentDirectional.centerStart,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 3),
                    child: Text(
                        '• ${pr.brandName} ${pr.strength} — ${pr.dosageForm}\n'
                        '   ${S.t('Country', 'الدولة')}: ${pr.country.isEmpty ? '—' : pr.country}   |   '
                        '${S.t('Yemen agent', 'وكيل اليمن')}: ${pr.agentYemen.isEmpty ? S.t('needs verification', 'يحتاج توثيق') : pr.agentYemen} '
                        '${pr.verified ? '✅' : '⚠️'}',
                        style: const TextStyle(fontSize: 11.5, height: 1.6)),
                  ),
                ),
            ],
            const SizedBox(height: 4),
            Align(
              alignment: AlignmentDirectional.centerStart,
              child: TextButton.icon(
                icon: const Icon(Icons.open_in_new, size: 15),
                label: Text(S.t('Open full drug file', 'فتح الملف الكامل للدواء')),
                onPressed: () => Navigator.push(context,
                    MaterialPageRoute(builder: (_) => DrugDetailScreen(drug: drug))),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ---------------- Home Tab ----------------
class _HomeTab extends StatefulWidget {
  final VoidCallback onOpenSystems;
  const _HomeTab({required this.onOpenSystems});
  @override
  State<_HomeTab> createState() => _HomeTabState();
}

class _HomeTabState extends State<_HomeTab> {
  final _q = TextEditingController();
  List<GenericDrug> _all = [];
  List<TradeProduct> _products = [];
  List<SearchHit> _hits = [];
  bool _searched = false;

  @override
  void initState() {
    super.initState();
    _load();
    AppSettings.dbRevision.addListener(_load);
  }

  @override
  void dispose() {
    AppSettings.dbRevision.removeListener(_load);
    _q.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final a = await DBHelper.instance.allGenerics();
    final p = await DBHelper.instance.allProducts();
    if (mounted) setState(() { _all = a; _products = p; });
  }

  void _search() {
    setState(() {
      _hits = fuzzySearch(_q.text, _all, _products);
      _searched = true;
    });
  }

  @override
  Widget build(BuildContext context) {
    final favIdsFuture = DBHelper.instance.favorites();
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(padding: const EdgeInsets.all(14), children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(22),
              gradient: const LinearGradient(
                  colors: [Color(0xFF0F766E), Color(0xFF155E75), Color(0xFF7C2D12)])),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(S.t('Search any medicine…', 'ابحث عن أي دواء…'),
                style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900)),
            Text(S.t('Generic, brand or company — even with a small typo we find the right drug with alternatives and Yemen products.',
                    'بالاسم العلمي أو التجاري أو الشركة — حتى بخطأ بسيط نجد الدواء الصحيح مع البدائل والمنتجات في اليمن.'),
                style: const TextStyle(fontSize: 12, color: Color(0xFFD7F3EE))),
            const SizedBox(height: 12),
            Row(children: [
              Expanded(child: TextField(
                controller: _q,
                onSubmitted: (_) => _search(),
                decoration: InputDecoration(
                    hintText: S.t('e.g. Paracetamol, Panadol…', 'مثال: باراسيتامول، Panadol…'),
                    filled: true, fillColor: Colors.black38,
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(14))),
              )),
              const SizedBox(width: 8),
              FilledButton(onPressed: _search, child: Text(S.t('Search', 'بحث'))),
            ]),
            const SizedBox(height: 10),
            Wrap(spacing: 8, children: [
              OutlinedButton.icon(icon: const Icon(Icons.camera_alt, size: 15),
                  label: Text(S.t('Search by photo (Google Lens)', 'بحث بصورة الدواء')),
                  onPressed: () => OnlineService.openUrl(OnlineService.googleLens)),
              OutlinedButton.icon(icon: const Icon(Icons.add, size: 15),
                  label: Text(S.t('Add drug', 'إضافة دواء')),
                  onPressed: () async {
                    final c = await Navigator.push<bool>(context,
                        MaterialPageRoute(builder: (_) => const AddDrugScreen()));
                    if (c == true) _load();
                  }),
            ]),
          ]),
        ),
        if (_searched) ...[
          const SizedBox(height: 12),
          Text('🔎 ${S.t('Results', 'النتائج')} (${_hits.length})',
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
          const SizedBox(height: 6),
          if (_hits.isEmpty)
            Card(child: Padding(padding: const EdgeInsets.all(14), child: Column(children: [
              Text(S.t('No close local match. Try online trusted search:', 'لا مطابقة محلية قريبة. جرّب البحث العالمي الموثوق:')),
              const SizedBox(height: 8),
              Wrap(spacing: 8, children: [
                OutlinedButton(child: const Text('Google'),
                    onPressed: () => OnlineService.openUrl(OnlineService.googleSearch(_q.text))),
                OutlinedButton(child: const Text('openFDA'),
                    onPressed: () => OnlineService.openUrl('https://api.fda.gov/drug/label.json?search=${Uri.encodeComponent(_q.text)}')),
              ]),
            ])))
          else
            ..._hits.map((h) => _DrugTile(
                drug: h.drug,
                matchedBrand: h.matchedBrand,
                products: _products
                    .where((p) => p.genericId == h.drug.id)
                    .toList())),
        ],
        const SizedBox(height: 14),
        FutureBuilder<Set<int>>(
          future: favIdsFuture,
          builder: (_, snap) {
            final favs = _all.where((g) => (snap.data ?? {}).contains(g.id)).toList();
            if (favs.isEmpty) return const SizedBox.shrink();
            return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('⭐ ${S.t('Favorites', 'المفضلة')}',
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
              const SizedBox(height: 6),
              ...favs.map((g) => _DrugTile(drug: g)),
              const SizedBox(height: 10),
            ]);
          },
        ),
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Text('🏥 ${S.t('Drugs by body system', 'الأدوية حسب أجهزة الجسم')}',
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
          TextButton(onPressed: widget.onOpenSystems,
              child: Text(S.t('All 18 systems', 'كل الأجهزة (18)'))),
        ]),
        GridView.count(
          crossAxisCount: 3, shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: 8, crossAxisSpacing: 8, childAspectRatio: 0.92,
          children: kSystems.map((s) {
            final n = _all.where((g) => g.systemId == s.id).length;
            return InkWell(
              onTap: () => Navigator.push(context, MaterialPageRoute(
                  builder: (_) => _SystemDrugsScreen(system: s))),
              borderRadius: BorderRadius.circular(16),
              child: Card(child: Padding(padding: const EdgeInsets.all(8), child: Column(
                mainAxisAlignment: MainAxisAlignment.center, children: [
                  Icon(_sysIcons[s.id] ?? Icons.medication, size: 26, color: const Color(0xFF14C8B4)),
                  const SizedBox(height: 6),
                  Text(S.ar ? s.ar : s.en, textAlign: TextAlign.center,
                      maxLines: 2, overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
                  Text('$n ${S.t('drugs', 'دواء')}',
                      style: const TextStyle(fontSize: 10, color: Color(0xFF14C8B4))),
                ]))),
            );
          }).toList(),
        ),
        const SizedBox(height: 12),
        Text('🆕 ${S.t('Popular medicines', 'أدوية شائعة')}',
            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
        const SizedBox(height: 6),
        ..._all.take(8).map((g) => _DrugTile(drug: g)),
        const SizedBox(height: 14),
        Center(child: Text('$kCopyright — AbdulmajeedPharma (APH)',
            style: const TextStyle(fontSize: 11, color: Colors.white54))),
        Center(child: Text(S.t('Educational only — not a substitute for medical advice.',
                'معلومات تعليمية فقط ولا تغني عن استشارة الطبيب أو الصيدلي.'),
            style: const TextStyle(fontSize: 10, color: Colors.white38))),
      ]),
    );
  }
}

// ---------------- Systems Tab ----------------
class _SystemsTab extends StatelessWidget {
  const _SystemsTab();
  @override
  Widget build(BuildContext context) {
    return ListView(padding: const EdgeInsets.all(14), children: [
      Text(S.t('Classification of medicines by body system (Pharmacology)',
              'تصنيف الأدوية حسب أجهزة الجسم — فارماكولوجي'),
          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
      const SizedBox(height: 10),
      ...kSystems.map((s) => Card(child: ListTile(
            leading: Icon(_sysIcons[s.id] ?? Icons.medication, color: const Color(0xFF14C8B4)),
            title: Text(S.ar ? s.ar : s.en, style: const TextStyle(fontWeight: FontWeight.bold)),
            subtitle: Text(S.ar ? s.en : s.ar),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.push(context,
                MaterialPageRoute(builder: (_) => _SystemDrugsScreen(system: s))),
          ))),
    ]);
  }
}

class _SystemDrugsScreen extends StatefulWidget {
  final BodySystem system;
  const _SystemDrugsScreen({required this.system});
  @override
  State<_SystemDrugsScreen> createState() => _SystemDrugsScreenState();
}

class _SystemDrugsScreenState extends State<_SystemDrugsScreen> {
  List<GenericDrug> _drugs = [];
  String? _sub;
  @override
  void initState() { super.initState(); _load(); }
  Future<void> _load() async {
    final d = await DBHelper.instance.bySystem(widget.system.id);
    if (mounted) setState(() => _drugs = d);
  }

  @override
  Widget build(BuildContext context) {
    final subs = <String>{for (final d in _drugs) S.ar ? d.subgroupAr : d.subgroupEn}.toList()..sort();
    final shown = _sub == null
        ? _drugs
        : _drugs.where((d) => (S.ar ? d.subgroupAr : d.subgroupEn) == _sub).toList();
    // تجميع حسب المجموعة الدوائية
    final groups = <String, List<GenericDrug>>{};
    for (final d in shown) {
      groups.putIfAbsent(S.ar ? d.subgroupAr : d.subgroupEn, () => []).add(d);
    }
    return Scaffold(
      appBar: AppBar(title: Text('${S.ar ? widget.system.ar : widget.system.en} (${_drugs.length})')),
      body: ListView(padding: const EdgeInsets.all(12), children: [
        SizedBox(height: 42, child: ListView(scrollDirection: Axis.horizontal, children: [
          Padding(padding: const EdgeInsetsDirectional.only(end: 6),
              child: ChoiceChip(label: Text(S.t('All', 'الكل')),
                  selected: _sub == null, onSelected: (_) => setState(() => _sub = null))),
          ...subs.map((s) => Padding(
              padding: const EdgeInsetsDirectional.only(end: 6),
              child: ChoiceChip(label: Text(s), selected: _sub == s,
                  onSelected: (_) => setState(() => _sub = s)))),
        ])),
        for (final e in groups.entries) ...[
          Padding(padding: const EdgeInsets.only(top: 14, bottom: 6),
              child: Text('💊 ${e.key} (${e.value.length})',
                  style: const TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF14C8B4)))),
          ...e.value.map((g) => _DrugTile(drug: g)),
        ],
        if (shown.isEmpty)
          Padding(padding: const EdgeInsets.all(24),
              child: Center(child: Text(S.t('No drugs yet in this group — add or import.',
                  'لا أدوية بعد في هذه المجموعة — أضف أو استورد.')))),
      ]),
    );
  }
}

// ---------------- AI Tab ----------------
class _ChatMsg {
  final bool me;
  final String text;
  final String tag;
  final GenericDrug? openDrug;
  const _ChatMsg({required this.me, required this.text, this.tag = '', this.openDrug});
}

class _AiTab extends StatefulWidget {
  const _AiTab();
  @override
  State<_AiTab> createState() => _AiTabState();
}

class _AiTabState extends State<_AiTab> {
  final _q = TextEditingController();
  final List<_ChatMsg> _log = [];
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _log.add(_ChatMsg(me: false, text: S.t(
        'Welcome to the APH drug assistant 🤖\n'
        'Ask about a dose, interactions, pregnancy, alternatives or Yemeni trade products — '
        'e.g. "Metformin dose" or "بدائل الأوجمنتين".\n'
        'You can also photograph a medicine pack and I will read it for you 📷.',
        'مرحباً بك في مساعد APH الدوائي 🤖\n'
        'اسألني عن جرعة دواء أو تداخلاته أو الحمل أو البدائل أو المنتجات التجارية في اليمن — '
        'مثال: «جرعة الميتفورمين» أو «بدائل الأوجمنتين».\n'
        'ويمكنك تصوير علبة الدواء وسأقرأها لك 📷.')));
  }

  String _providerLabel(AiReply r) {
    if (!r.online) return S.t('📴 Local APH database', '📴 قاعدة APH المحلية');
    return r.provider == 'gemini' ? '☁ Gemini (Google AI)' : '☁ OpenAI GPT';
  }

  Future<void> _ask([String? preset]) async {
    final q = (preset ?? _q.text).trim();
    if (q.isEmpty || _busy) return;
    _q.clear();
    setState(() {
      _log.add(_ChatMsg(me: true, text: q));
      _busy = true;
    });
    final r = await AiClient.ask(q);
    if (!mounted) return;
    setState(() {
      _busy = false;
      _log.add(_ChatMsg(
          me: false,
          text: r.error.isNotEmpty && !r.online
              ? '${r.text}\n\n⚠️ ${r.error}'
              : r.text,
          tag: _providerLabel(r)));
    });
  }

  /// البحث بالصورة: نموذج رؤية حقيقي يقرأ العلبة ثم يبحث عنها في قاعدة APH
  Future<void> _askImage(ImageSource src) async {
    if (_busy) return;
    final picked = await ImagePicker()
        .pickImage(source: src, maxWidth: 1200, imageQuality: 82);
    if (picked == null) return;
    final bytes = await picked.readAsBytes();
    final lower = picked.path.toLowerCase();
    final mime = lower.endsWith('.png')
        ? 'image/png'
        : (lower.endsWith('.webp') ? 'image/webp' : 'image/jpeg');
    setState(() {
      _log.add(_ChatMsg(
          me: true, text: S.t('📷 Photo of a medicine pack', '📷 صورة علبة دواء')));
      _busy = true;
    });
    final r = await AiClient.identifyImage(bytes, mime: mime);
    GenericDrug? found;
    var extra = '';
    if (r.online) {
      final text = r.text.toLowerCase();
      try {
        final generics = await DBHelper.instance.allGenerics();
        for (final g in generics) {
          if (g.nameEn.length > 3 && text.contains(g.nameEn.toLowerCase())) {
            found = g;
            break;
          }
        }
        if (found != null) {
          extra = S.t(
              '\n\n✅ Found in the APH database: ${found.nameEn} — open the file below for '
              'trade products, manufacturers and Yemen agents.',
              '\n\n✅ موجود في قاعدة APH: ${found.nameEn} — افتح الملف أدناه لعرض المنتجات '
              'التجارية والشركات المصنعة ووكلاء اليمن.');
        }
      } catch (_) {}
    }
    if (!mounted) return;
    setState(() {
      _busy = false;
      _log.add(_ChatMsg(
          me: false,
          text: r.text + extra,
          tag: _providerLabel(r),
          openDrug: found));
    });
  }

  Future<void> _pickImageSheet() async {
    final src = await showModalBottomSheet<ImageSource>(
      context: context,
      builder: (_) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          ListTile(leading: const Icon(Icons.camera_alt),
              title: Text(S.t('Take a photo of the medicine', 'التقاط صورة للدواء')),
              onTap: () => Navigator.pop(context, ImageSource.camera)),
          ListTile(leading: const Icon(Icons.photo_library),
              title: Text(S.t('Choose from gallery', 'اختيار من المعرض')),
              onTap: () => Navigator.pop(context, ImageSource.gallery)),
          ListTile(leading: const Icon(Icons.travel_explore),
              title: Text(S.t('Search the pack on Google Lens', 'بحث عن العلبة في Google Lens')),
              onTap: () {
                Navigator.pop(context);
                OnlineService.openUrl(OnlineService.googleLens);
              }),
        ]),
      ),
    );
    if (src != null) await _askImage(src);
  }

  @override
  Widget build(BuildContext context) {
    final provider = AppSettings.activeProvider;
    return Column(children: [
      InkWell(
        onTap: () => Navigator.push(context,
            MaterialPageRoute(builder: (_) => const SettingsScreen())),
        child: Container(
          margin: const EdgeInsets.fromLTRB(12, 12, 12, 0),
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
              color: provider == 'offline'
                  ? const Color(0xFF2A2208)
                  : const Color(0xFF08303A),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                  color: provider == 'offline'
                      ? const Color(0xFF6B5316)
                      : const Color(0xFF14C8B4))),
          child: Row(children: [
            Icon(provider == 'offline' ? Icons.wifi_off : Icons.cloud_done,
                size: 18,
                color: provider == 'offline'
                    ? const Color(0xFFFDE68A)
                    : const Color(0xFF14C8B4)),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                  provider == 'offline'
                      ? S.t(
                          'Offline mode — answers come from local APH data. The owner must configure the secure AI Worker URL.',
                          'وضع محلي — الإجابات من قاعدة APH. يجب على المالك ضبط رابط وسيط الذكاء الاصطناعي الآمن.')
                      : S.t(
                          'Cloud AI active ($provider) — grounded on the APH database. '
                          'Verify officially via openFDA / DailyMed. Tap for settings.',
                          'الذكاء السحابي مفعّل ($provider) — مرتبط بقاعدة APH. '
                          'تحقق رسمياً عبر openFDA / DailyMed. اضغط للإعدادات.'),
                  style: TextStyle(
                      fontSize: 11,
                      height: 1.5,
                      color: provider == 'offline'
                          ? const Color(0xFFFDE68A)
                          : const Color(0xFFC9F5EF))),
            ),
          ]),
        ),
      ),
      Expanded(child: ListView.builder(
        padding: const EdgeInsets.all(12),
        itemCount: _log.length + (_busy ? 1 : 0),
        itemBuilder: (_, i) {
          if (_busy && i == _log.length) {
            return const Align(
              alignment: AlignmentDirectional.centerStart,
              child: Padding(
                padding: EdgeInsets.all(10),
                child: SizedBox(width: 20, height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2)),
              ),
            );
          }
          final m = _log[i];
          return Align(
            alignment: m.me ? AlignmentDirectional.centerEnd : AlignmentDirectional.centerStart,
            child: Container(
              margin: const EdgeInsets.only(bottom: 8),
              padding: const EdgeInsets.all(11),
              constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.88),
              decoration: BoxDecoration(
                  color: m.me ? const Color(0xFF0F766E) : const Color(0xFF123A4F),
                  borderRadius: BorderRadius.circular(15)),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                if (m.tag.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Text(m.tag,
                        style: const TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                            color: Color(0xFF14C8B4))),
                  ),
                SelectableText(m.text, style: const TextStyle(height: 1.8, fontSize: 13)),
                if (m.openDrug != null)
                  TextButton.icon(
                    icon: const Icon(Icons.medication, size: 16),
                    label: Text(S.t('Open ${m.openDrug!.nameEn} in APH',
                        'فتح ${m.openDrug!.nameEn} في APH')),
                    onPressed: () => Navigator.push(context,
                        MaterialPageRoute(
                            builder: (_) => DrugDetailScreen(drug: m.openDrug!))),
                  ),
              ]),
            ),
          );
        },
      )),
      SingleChildScrollView(scrollDirection: Axis.horizontal, child: Row(children: [
        for (final s in [S.t('Paracetamol dose', 'جرعة الباراسيتامول'),
          S.t('Ibuprofen alternatives', 'بدائل الإيبوبروفين'),
          S.t('Warfarin interactions', 'تداخلات الوارفارين'),
          S.t('Hypertension drugs', 'أدوية الضغط'),
          S.t('Amoxicillin products in Yemen', 'منتجات الأموكسيسيلين في اليمن')])
          Padding(padding: const EdgeInsetsDirectional.only(start: 8),
              child: ActionChip(label: Text(s), onPressed: _busy ? null : () => _ask(s))),
      ])),
      Padding(padding: const EdgeInsets.all(10), child: Row(children: [
        IconButton.filledTonal(
          tooltip: S.t('Identify a medicine from its photo', 'التعرف على الدواء من صورته'),
          icon: const Icon(Icons.photo_camera), onPressed: _busy ? null : _pickImageSheet),
        const SizedBox(width: 8),
        Expanded(child: TextField(controller: _q, onSubmitted: (_) => _ask(),
            decoration: InputDecoration(hintText: S.t('Ask about any drug…', 'اسأل عن أي دواء…'),
                border: const OutlineInputBorder()))),
        const SizedBox(width: 8),
        FilledButton(onPressed: _busy ? null : () => _ask(),
            child: Text(S.t('Ask', 'اسأل'))),
      ])),
    ]);
  }
}

// ---------------- Messages Tab ----------------
class _MessagesTab extends StatefulWidget {
  const _MessagesTab();
  @override
  State<_MessagesTab> createState() => _MessagesTabState();
}

class _MessagesTabState extends State<_MessagesTab> {
  final _name = TextEditingController(), _body = TextEditingController();
  List<ChatMessage> _msgs = [];

  @override
  void initState() { super.initState(); _load(); }
  Future<void> _load() async {
    final m = await DBHelper.instance.messages();
    if (mounted) setState(() => _msgs = m);
  }

  Future<void> _post(bool admin) async {
    var body = _body.text.trim();
    if (admin) {
      final pin = await AppSettings.adminPin();
      final entered = await showDialog<String>(context: context, builder: (_) {
        final c = TextEditingController();
        return AlertDialog(title: const Text('Admin PIN'),
          content: TextField(controller: c, obscureText: true,
              decoration: const InputDecoration(hintText: 'PIN')),
          actions: [TextButton(onPressed: () => Navigator.pop(context, c.text),
              child: const Text('OK'))]);
      });
      if (entered != pin) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('PIN ❌')));
        return;
      }
      final c = TextEditingController();
      final reply = await showDialog<String>(context: context, builder: (_) => AlertDialog(
        title: Text(S.t('Official admin reply', 'رد الإدارة الرسمي')),
        content: TextField(controller: c, maxLines: 3),
        actions: [TextButton(onPressed: () => Navigator.pop(context, c.text),
            child: Text(S.t('Post', 'نشر')))]));
      if (reply == null || reply.trim().isEmpty) return;
      body = reply.trim();
    }
    if (body.isEmpty) return;
    await DBHelper.instance.addMessage(ChatMessage(
      author: admin ? 'APH Admin' : (_name.text.trim().isEmpty ? S.t('User', 'مستخدم') : _name.text.trim()),
      body: body, isAdmin: admin,
      createdAt: DateTime.now().millisecondsSinceEpoch,
    ));
    _body.clear();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return ListView(padding: const EdgeInsets.all(14), children: [
      Text('💬 ${S.t('Community & admin messages', 'رسائل المستخدمين والإدارة')}',
          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
      Text(S.t('Report any bug or question — Dr. Abdulmajeed replies from the admin panel and replies appear for everyone (server sync: see FIREBASE_SYNC.md).',
              'اكتب أي خلل أو استفسار — يرد د. عبدالمجيد من لوحة التحكم ويظهر الرد للجميع (للمزامنة عبر الأجهزة: راجع FIREBASE_SYNC.md).'),
          style: const TextStyle(fontSize: 11, color: Colors.white60)),
      const SizedBox(height: 10),
      Card(child: Padding(padding: const EdgeInsets.all(12), child: Column(children: [
        TextField(controller: _name, decoration: InputDecoration(
            labelText: S.t('Your name', 'الاسم'), border: const OutlineInputBorder())),
        const SizedBox(height: 8),
        TextField(controller: _body, maxLines: 3, decoration: InputDecoration(
            labelText: S.t('Your message…', 'اكتب رسالتك…'), border: const OutlineInputBorder())),
        const SizedBox(height: 8),
        Row(children: [
          Expanded(child: FilledButton(onPressed: () => _post(false),
              child: Text(S.t('Send', 'إرسال')))),
          const SizedBox(width: 8),
          Expanded(child: OutlinedButton.icon(icon: const Icon(Icons.shield, size: 16),
              label: Text(S.t('Admin reply', 'رد الإدارة')), onPressed: () => _post(true))),
        ]),
      ]))),
      ..._msgs.map((m) => Card(
            child: ListTile(
              leading: Icon(m.isAdmin ? Icons.shield : Icons.person,
                  color: m.isAdmin ? const Color(0xFF14C8B4) : null),
              title: Text(m.isAdmin ? '🛡️ APH Admin — د. عبدالمجيد' : m.author,
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
              subtitle: Text(m.body, style: const TextStyle(height: 1.7)),
            ),
          )),
      if (_msgs.isEmpty)
        Padding(padding: const EdgeInsets.all(18),
            child: Center(child: Text(S.t('No messages yet', 'لا رسائل بعد')))),
    ]);
  }
}

// ---------------- More / Admin Tab ----------------
class _MoreTab extends StatefulWidget {
  const _MoreTab();
  @override
  State<_MoreTab> createState() => _MoreTabState();
}

class _MoreTabState extends State<_MoreTab> {
  String _stats = '';

  @override
  void initState() { super.initState(); _loadStats(); }
  Future<void> _loadStats() async {
    final g = await DBHelper.instance.countGenerics();
    final p = await DBHelper.instance.countProducts();
    if (mounted) setState(() => _stats = '$g ${S.t('generics', 'دواء علمي')} • $p ${S.t('trade products', 'منتج تجاري')} • 18 ${S.t('systems', 'أجهزة')}');
  }

  Future<void> _toggleAdmin() async {
    if (AppSettings.isAdmin.value) {
      await AppSettings.setAdmin(false);
    } else {
      final pin = await AppSettings.adminPin();
      final c = TextEditingController();
      final entered = await showDialog<String>(context: context, builder: (_) => AlertDialog(
        title: Text(S.t('Admin mode', 'وضع الإدارة')),
        content: TextField(controller: c, obscureText: true,
            decoration: InputDecoration(hintText: S.t('PIN (default 1234)', 'PIN — الافتراضي 1234'))),
        actions: [TextButton(onPressed: () => Navigator.pop(context, c.text),
            child: const Text('OK'))]));
      if (entered == pin) {
        await AppSettings.setAdmin(true);
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(S.t('Admin ON — you can edit every drug, product and image', 'وضع الإدارة مفعّل — يمكنك تعديل كل دواء ومنتج وصورة'))));
      } else if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('PIN ❌')));
      }
    }
    setState(() {});
  }

  Future<void> _syncNow() async {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(S.t('Downloading the published APH database…',
            'ينزّل قاعدة APH المنشورة من موقع التحكم…'))));
    final r = await SyncService.pull();
    await _loadStats();
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        duration: const Duration(seconds: 6),
        content: Text(r.ok ? '✅ ${r.message}' : '⚠️ ${r.message}')));
  }

  Future<void> _shareExport() async {
    final json = await ImportService.exportJson();
    final dir = await getApplicationDocumentsDirectory();
    final f = File('${dir.path}/aph-database.json');
    await f.writeAsString(json);
    await Clipboard.setData(ClipboardData(text: json));
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(S.t('Exported to aph-database.json and copied to clipboard',
              'صُدّرت القاعدة إلى aph-database.json ونُسخت للحافظة'))));
    }
  }

  @override
  Widget build(BuildContext context) {
    final admin = AppSettings.isAdmin.value;
    return ListView(padding: const EdgeInsets.all(14), children: [
      Card(child: Padding(padding: const EdgeInsets.all(14), child: Column(
        crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('AbdulmajeedPharma (APH)', style: TextStyle(fontWeight: FontWeight.w900, fontSize: 16)),
          Text(_stats, style: const TextStyle(color: Colors.white70, fontSize: 12)),
          const SizedBox(height: 6),
          Text('$kCopyright\n$kOwnerEn • WhatsApp 781733795 • $kEmail',
              style: const TextStyle(fontSize: 11, color: Colors.white54, height: 1.8)),
          const SizedBox(height: 10),
          Wrap(spacing: 8, children: [
            FilledButton.icon(icon: const Icon(Icons.chat, size: 16),
                label: const Text('WhatsApp 781733795'),
                onPressed: () => OnlineService.openUrl(kWhatsAppUrl)),
            OutlinedButton.icon(icon: const Icon(Icons.email, size: 16),
                label: const Text(kEmail),
                onPressed: () => OnlineService.openUrl('mailto:$kEmail')),
          ]),
        ]))),
      Card(child: ListTile(
        leading: const CircleAvatar(backgroundColor: Color(0xFF14C8B4),
            child: Icon(Icons.local_pharmacy, color: Color(0xFF04222B))),
        title: Text(S.t('Pharmacy operations', 'إدارة الصيدلية'),
            style: const TextStyle(fontWeight: FontWeight.bold)),
        subtitle: Text(S.t('Stock batches, expiry alerts, point of sale and receipts',
            'دفعات المخزون وتنبيهات الصلاحية ونقطة البيع والفواتير')),
        trailing: const Icon(Icons.chevron_right),
        onTap: () => Navigator.push(context,
            MaterialPageRoute(builder: (_) => const PharmacyScreen())),
      )),
      Card(child: Column(children: [
        ListTile(leading: const Icon(Icons.language),
            title: Text(S.t('Language: English / العربية', 'اللغة: العربية / English')),
            trailing: Switch(value: S.ar,
                onChanged: (v) => AppSettings.setArabic(v)),
            subtitle: Text(S.ar ? 'العربية' : 'English')),
        ListTile(leading: const Icon(Icons.admin_panel_settings),
            title: Text(S.t('Admin mode (edit data & images)', 'وضع الإدارة — تعديل البيانات والصور')),
            subtitle: Text(admin ? (S.t('Enabled', 'مفعّل ✅')) : S.t('Disabled (PIN)', 'غير مفعّل')),
            trailing: Switch(value: admin, onChanged: (_) => _toggleAdmin())),
        ListTile(leading: const Icon(Icons.key),
            title: Text(S.t('Change admin PIN', 'تغيير PIN الإدارة')),
            onTap: () async {
              final c = TextEditingController();
              final v = await showDialog<String>(context: context, builder: (_) => AlertDialog(
                title: Text(S.t('New PIN (4+ digits)', 'PIN جديد — 4 أرقام فأكثر')),
                content: TextField(controller: c, obscureText: true),
                actions: [TextButton(onPressed: () => Navigator.pop(context, c.text),
                    child: const Text('OK'))]));
              if (v != null && v.length >= 4) {
                await AppSettings.setAdminPin(v);
                if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('✅')));
              }
            }),
      ])),
      Card(child: Column(children: [
        ListTile(leading: const Icon(Icons.smart_toy, color: Color(0xFF14C8B4)),
            title: Text(S.t('AI assistant settings (Gemini / OpenAI)',
                'إعدادات المساعد الذكي (Gemini / OpenAI)')),
            subtitle: Text(S.t('Provider: ${AppSettings.activeProvider} — configure the secure Worker URL',
                'المزوّد: ${AppSettings.activeProvider} — اضبط رابط وسيط AI الآمن')),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.push(context,
                MaterialPageRoute(builder: (_) => const SettingsScreen()))),
        ListTile(leading: const Icon(Icons.cloud_sync, color: Color(0xFF14C8B4)),
            title: Text(S.t('Sync database from the control site',
                'مزامنة القاعدة من موقع التحكم')),
            subtitle: Text(S.t('Get every drug, product, Yemen agent and announcement published by Dr. Abdulmajeed',
                'استلم كل دواء ومنتج ووكيل في اليمن وكل إعلان ينشره د. عبدالمجيد')),
            trailing: const Icon(Icons.download),
            onTap: _syncNow),
        ListTile(leading: const Icon(Icons.upload_file),
            title: Text(S.t('Import database (CSV / Excel / JSON)', 'استيراد قاعدة بيانات CSV / Excel / JSON')),
            subtitle: Text(S.t('Large files supported — saved permanently on device', 'يدعم ملفات كبيرة — يُحفظ دائماً على الجهاز')),
            onTap: () async {
              final r = await ImportService.pickAndImport();
              if (r != null && mounted) {
                ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                    content: Text('✅ ${r.drugs} + ${r.products} — ${r.message}')));
                _loadStats();
              }
            }),
        ListTile(leading: const Icon(Icons.download),
            title: Text(S.t('Export database (JSON) — for admin panel / backup', 'تصدير القاعدة JSON — للوحة التحكم / نسخة احتياطية')),
            onTap: _shareExport),
        ListTile(leading: const Icon(Icons.copy),
            title: Text(S.t('Copy import template (CSV header)', 'نسخ قالب الاستيراد CSV')),
            onTap: () {
              Clipboard.setData(const ClipboardData(
                  text: 'genericEn,genericAr,systemId,subgroupEn,subgroupAr,atc,indications,dosage,warnings,brand,strength,form,manufacturer,country,agentYemen'));
              ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('✅ CSV header copied')));
            }),
        ListTile(leading: const Icon(Icons.camera_alt),
            title: Text(S.t('Search medicine by photo — Google Lens', 'البحث عن دواء بصورته — Google Lens')),
            subtitle: Text(S.t('Photograph the pack and search globally', 'صوّر العلبة وابحث عالمياً')),
            onTap: () async {
              final img = await ImagePicker().pickImage(source: ImageSource.camera);
              if (img != null) await OnlineService.openUrl(OnlineService.googleLens);
            }),
        ListTile(leading: const Icon(Icons.restore, color: Colors.redAccent),
            title: Text(S.t('Reset starter database', 'استعادة قاعدة البداية'),
                style: const TextStyle(color: Colors.redAccent)),
            onTap: () async {
              final ok = await showDialog<bool>(context: context, builder: (_) => AlertDialog(
                title: Text(S.t('Reset?', 'استعادة؟')),
                content: Text(S.t('Catalogue edits will be removed. Pharmacy stock and sales are protected and will block reset.',
                    'ستُحذف تعديلات قاعدة الأدوية؛ المخزون والمبيعات محمية وستمنع الاستعادة.')),
                actions: [
                  TextButton(onPressed: () => Navigator.pop(context, false), child: Text(S.t('Cancel', 'إلغاء'))),
                  TextButton(onPressed: () => Navigator.pop(context, true), child: Text(S.t('Reset', 'استعادة'))),
                ]));
              if (ok == true) {
                try {
                  await DBHelper.instance.resetAll();
                  _loadStats();
                } catch (e) {
                  if (mounted) ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text(e.toString())));
                }
              }
            }),
      ])),
      Card(child: Padding(padding: const EdgeInsets.all(14), child: Column(
        crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('🌐 ${S.t('Trusted online sources', 'مصادر موثوقة على الإنترنت')}',
              style: const TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 6),
          Wrap(spacing: 8, children: [
            OutlinedButton(child: const Text('openFDA'), onPressed: () => OnlineService.openUrl('https://open.fda.gov/apis/drug/label/')),
            OutlinedButton(child: const Text('DailyMed'), onPressed: () => OnlineService.openUrl('https://dailymed.nlm.nih.gov')),
            OutlinedButton(child: const Text('RxNorm (NIH)'), onPressed: () => OnlineService.openUrl('https://rxnav.nlm.nih.gov')),
            OutlinedButton(child: const Text('Google Lens'), onPressed: () => OnlineService.openUrl(OnlineService.googleLens)),
          ]),
          const SizedBox(height: 8),
          Text(S.t('Works fully offline. Online features activate automatically when connected.',
                  'يعمل بالكامل دون إنترنت، وتتفعّل مزايا الإنترنت تلقائياً عند الاتصال.'),
              style: const TextStyle(fontSize: 11, color: Colors.white60, height: 1.8)),
        ]))),
    ]);
  }
}
