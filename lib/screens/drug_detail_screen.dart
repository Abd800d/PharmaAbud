import 'package:flutter/material.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:image_picker/image_picker.dart';
import '../app_settings.dart';
import '../db/db_helper.dart';
import '../models/drug_models.dart';
import '../services/image_store.dart';
import '../services/online_service.dart';
import '../widgets/drug_image.dart';
import 'add_drug_screen.dart';

/// صفحة الدواء: الاسم العلمي أولاً + كل المنتجات التجارية (شركة/دولة/وكيل اليمن)
/// + البدائل + جلب البيانات الناقصة من openFDA عند الاتصال
class DrugDetailScreen extends StatefulWidget {
  final GenericDrug drug;
  const DrugDetailScreen({super.key, required this.drug});
  @override
  State<DrugDetailScreen> createState() => _DrugDetailScreenState();
}

class _DrugDetailScreenState extends State<DrugDetailScreen> {
  late GenericDrug _drug;
  List<TradeProduct> _products = [];
  List<GenericDrug> _alts = [];
  bool _fav = false, _loading = true;

  @override
  void initState() {
    super.initState();
    _drug = widget.drug;
    _load();
  }

  Future<void> _load() async {
    final db = DBHelper.instance;
    final prods = await db.productsOf(_drug.id!);
    final all = await db.allGenerics();
    var alts = all.where((g) => g.id != _drug.id &&
        g.systemId == _drug.systemId && g.subgroupEn == _drug.subgroupEn).toList();
    if (alts.length < 3) {
      alts = [...alts, ...all.where((g) =>
          g.id != _drug.id && g.systemId == _drug.systemId && !alts.contains(g))].take(6).toList();
    }
    final favs = await db.favorites();
    if (mounted) {
      setState(() {
        _products = prods; _alts = alts; _fav = favs.contains(_drug.id);
        _loading = false;
      });
    }
  }

  Future<void> _fetchOnline() async {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(S.t('Contacting openFDA (official FDA labels)…', 'جارٍ الاتصال بـ openFDA الرسمي…'))));
    final label = await OnlineService.fetchFdaLabel(_drug.nameEn);
    if (!mounted) return;
    if (label == null) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(S.t('No FDA label found / offline. Local data is complete offline.',
              'لا نشرة مطابقة أو لا اتصال — بياناتك المحلية تعمل كاملة دون إنترنت.'))));
      return;
    }
    String cut(String s) => s.length > 1200 ? s.substring(0, 1200) : s;
    final updated = GenericDrug(
      id: _drug.id, nameEn: _drug.nameEn, nameAr: _drug.nameAr,
      systemId: _drug.systemId, subgroupEn: _drug.subgroupEn,
      subgroupAr: _drug.subgroupAr, atc: _drug.atc,
      introduction: _drug.introduction, mechanism: _drug.mechanism,
      indications: _drug.indications.isEmpty ? cut(label['indications'] ?? '') : _drug.indications,
      dosage: _drug.dosage.isEmpty ? cut(label['dosage'] ?? '') : _drug.dosage,
      interactions: _drug.interactions.isEmpty ? cut(label['interactions'] ?? '') : _drug.interactions,
      warnings: _drug.warnings.isEmpty ? cut(label['warnings'] ?? '') : _drug.warnings,
      pregnancy: _drug.pregnancy, imagePath: _drug.imagePath,
      source: 'openFDA label (fetched online)',
    );
    await DBHelper.instance.updateGeneric(updated);
    setState(() => _drug = updated);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(S.t('Missing data saved permanently from FDA label', 'حُفظت البيانات الناقصة دائماً من نشرة FDA'))));
    }
  }

  Future<void> _changeImage({TradeProduct? product}) async {
    final source = await showModalBottomSheet<ImageSource>(
      context: context,
      builder: (_) => SafeArea(child: Column(mainAxisSize: MainAxisSize.min, children: [
        ListTile(leading: const Icon(Icons.photo_camera),
            title: Text(S.t('Camera', 'الكاميرا')),
            onTap: () => Navigator.pop(context, ImageSource.camera)),
        ListTile(leading: const Icon(Icons.photo_library),
            title: Text(S.t('Gallery / Files', 'المعرض / الملفات')),
            onTap: () => Navigator.pop(context, ImageSource.gallery)),
      ])),
    );
    if (source == null) return;
    final path = await ImageStore.pickAndPersist(source);
    if (path == null) return;
    if (product == null) {
      final u = _drug.copyWith(imagePath: path);
      await DBHelper.instance.updateGeneric(u);
      setState(() => _drug = u);
    } else {
      final u = TradeProduct(
          id: product.id, genericId: product.genericId,
          brandName: product.brandName, manufacturer: product.manufacturer,
          country: product.country, strength: product.strength,
          dosageForm: product.dosageForm, agentYemen: product.agentYemen,
          imagePath: path, source: product.source, verified: product.verified);
      await DBHelper.instance.updateTrade(u);
      _load();
    }
  }

  Widget _kv(String label, String value) {
    if (value.trim().isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 10),
      child: RichText(text: TextSpan(children: [
        TextSpan(text: '$label: ',
            style: const TextStyle(color: Color(0xFF14C8B4), fontWeight: FontWeight.bold)),
        TextSpan(text: value, style: const TextStyle(height: 1.7)),
      ])),
    );
  }

  @override
  Widget build(BuildContext context) {
    final sys = systemById(_drug.systemId);
    final admin = AppSettings.isAdmin.value;
    return Scaffold(
      appBar: AppBar(title: Text(_drug.nameEn), actions: [
        IconButton(
          icon: Icon(_fav ? Icons.star : Icons.star_border, color: Colors.amber),
          onPressed: () async {
            await DBHelper.instance.toggleFavorite(_drug.id!, !_fav);
            setState(() => _fav = !_fav);
          },
        ),
      ]),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(padding: const EdgeInsets.all(14), children: [
              Card(child: Padding(padding: const EdgeInsets.all(14), child: Column(
                crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(children: [
                    DrugImage(path: _drug.imagePath, size: 84),
                    const SizedBox(width: 12),
                    Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(_drug.nameEn, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900)),
                      Text(_drug.nameAr, style: const TextStyle(color: Colors.white70, fontSize: 16)),
                      const SizedBox(height: 6),
                      Wrap(spacing: 6, children: [
                        Chip(label: Text(S.ar ? sys.ar : sys.en)),
                        Chip(label: Text(S.ar ? _drug.subgroupAr : _drug.subgroupEn)),
                        if (_drug.atc.isNotEmpty) Chip(label: Text('ATC ${_drug.atc}')),
                      ]),
                    ])),
                  ]),
                  const SizedBox(height: 8),
                  Wrap(spacing: 8, children: [
                    OutlinedButton.icon(
                        icon: const Icon(Icons.volume_up, size: 16),
                        label: const Text('EN'),
                        onPressed: () async {
                          final tts = FlutterTts();
                          await tts.setLanguage('en-US');
                          await tts.speak(_drug.nameEn);
                        }),
                    OutlinedButton.icon(icon: const Icon(Icons.public, size: 16),
                        label: const Text('Google'),
                        onPressed: () => OnlineService.openUrl(OnlineService.googleSearch(_drug.nameEn))),
                    OutlinedButton.icon(icon: const Icon(Icons.menu_book, size: 16),
                        label: const Text('DailyMed'),
                        onPressed: () => OnlineService.openUrl(OnlineService.dailyMed(_drug.nameEn))),
                    FilledButton.icon(icon: const Icon(Icons.cloud_download, size: 16),
                        label: Text(S.t('Fetch missing (openFDA)', 'جلب الناقص (openFDA)')),
                        onPressed: _fetchOnline),
                    if (admin) OutlinedButton.icon(icon: const Icon(Icons.edit, size: 16),
                        label: Text(S.t('Edit', 'تعديل')),
                        onPressed: () async {
                          final changed = await Navigator.push<bool>(context,
                              MaterialPageRoute(builder: (_) => AddDrugScreen(edit: _drug)));
                          if (changed == true) {
                            final all = await DBHelper.instance.allGenerics();
                            setState(() => _drug = all.firstWhere((g) => g.id == _drug.id));
                            _load();
                          }
                        }),
                    if (admin) OutlinedButton.icon(icon: const Icon(Icons.image, size: 16),
                        label: Text(S.t('Drug photo', 'صورة الدواء')),
                        onPressed: () => _changeImage()),
                  ]),
                  _kv(S.t('Introduction', 'مقدمة'), _drug.introduction),
                  _kv(S.t('Mechanism', 'آلية العمل'), _drug.mechanism),
                  _kv(S.t('Indications', 'الاستخدامات'), _drug.indications),
                  _kv(S.t('Usual dose', 'الجرعة المعتادة'), _drug.dosage),
                  _kv(S.t('Interactions', 'التداخلات'), _drug.interactions),
                  _kv(S.t('Warnings', 'تحذيرات'), _drug.warnings),
                  _kv(S.t('Pregnancy', 'الحمل والرضاعة'), _drug.pregnancy),
                  const SizedBox(height: 8),
                  Text('${S.t('Source', 'المصدر')}: ${_drug.source}',
                      style: const TextStyle(color: Colors.white54, fontSize: 11)),
                ]))),
              const SizedBox(height: 8),
              Text('🏷️ ${S.t('Trade products', 'المنتجات التجارية')} (${_products.length})',
                  style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              ..._products.map((p) => Card(
                    child: ListTile(
                      leading: DrugImage(path: p.imagePath),
                      title: Text('${p.brandName}  ${p.strength}',
                          style: const TextStyle(fontWeight: FontWeight.bold)),
                      subtitle: Text(
                          '${p.dosageForm} • 🏭 ${p.manufacturer} • 🌍 ${p.country}\n🇾🇪 ${S.t('Agent in Yemen', 'الوكيل/المورد في اليمن')}: ${p.agentYemen.isEmpty ? '—' : p.agentYemen}${p.verified ? ' ✅' : ' ⚠'}'),
                      isThreeLine: true,
                      trailing: PopupMenuButton<String>(
                        onSelected: (v) {
                          if (v == 'img') OnlineService.openUrl(OnlineService.googleImages('${p.brandName} ${p.strength}'));
                          if (v == 'edit') {
                            Navigator.push<bool>(context, MaterialPageRoute(
                                builder: (_) => AddProductScreen(generic: _drug, edit: p))).then((c) { if (c == true) _load(); });
                          }
                          if (v == 'photo') _changeImage(product: p);
                          if (v == 'del') {
                            DBHelper.instance.deleteTrade(p.id!).then((_) => _load());
                          }
                        },
                        itemBuilder: (_) => [
                          PopupMenuItem(value: 'img', child: Text('🖼️ ${S.t('Product images (Google)', 'صور المنتج Google')}')),
                          if (admin) PopupMenuItem(value: 'edit', child: Text('✏️ ${S.t('Edit product', 'تعديل المنتج')}')),
                          if (admin) PopupMenuItem(value: 'photo', child: Text('🖼️ ${S.t('Product photo', 'صورة المنتج')}')),
                          if (admin) PopupMenuItem(value: 'del', child: Text('🗑 ${S.t('Delete', 'حذف')}')),
                        ],
                      ),
                    ),
                  )),
              if (admin)
                FilledButton.icon(icon: const Icon(Icons.add),
                    label: Text(S.t('Add trade product', 'إضافة منتج تجاري')),
                    onPressed: () async {
                      final c = await Navigator.push<bool>(context, MaterialPageRoute(
                          builder: (_) => AddProductScreen(generic: _drug)));
                      if (c == true) _load();
                    }),
              const SizedBox(height: 14),
              Text('🔁 ${S.t('Alternatives (same pharmacological group)', 'بدائل في نفس المجموعة الدوائية')}',
                  style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              ..._alts.map((a) => Card(child: ListTile(
                    leading: DrugImage(path: a.imagePath),
                    title: Text(a.nameEn, style: const TextStyle(fontWeight: FontWeight.bold)),
                    subtitle: Text('${a.nameAr} • ${S.ar ? a.subgroupAr : a.subgroupEn}'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => Navigator.push(context, MaterialPageRoute(
                        builder: (_) => DrugDetailScreen(drug: a))),
                  ))),
              const SizedBox(height: 10),
              Container(padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(color: const Color(0xFF2A2208),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFF6B5316))),
                child: Text(S.t(
                    'Educational information only — never use restricted medicines without a prescription and pharmacist review.',
                    'معلومات تعليمية فقط — لا تستخدم الأدوية المقيدة دون وصفة ومراجعة صيدلي.'),
                    style: const TextStyle(fontSize: 11, color: Color(0xFFFDE68A), height: 1.8)),
              ),
            ]),
    );
  }
}
