import 'dart:convert';
import 'dart:io';
import 'package:csv/csv.dart';
import 'package:excel/excel.dart';
import 'package:file_picker/file_picker.dart';
import '../db/db_helper.dart';
import '../models/drug_models.dart';
import 'search_service.dart' show norm;

/// استيراد دائم لقواعد بيانات كبيرة: CSV / Excel (.xlsx) / JSON
/// الأعمدة: genericEn,genericAr,systemId,subgroupEn,subgroupAr,atc,
/// introduction,mechanism,indications,dosage,interactions,warnings,pregnancy,
/// brand,strength,form,manufacturer,country,agentYemen,image
class ImportResult {
  final int drugs, products;
  final String message;
  const ImportResult(this.drugs, this.products, this.message);
}

class ImportService {
  static Future<ImportResult?> pickAndImport() async {
    final picked = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['csv', 'json', 'xlsx', 'xls'],
      withData: true,
    );
    if (picked == null || picked.files.isEmpty) return null;
    final file = picked.files.first;
    final name = file.name.toLowerCase();
    final bytes = file.bytes ??
        (file.path != null ? await File(file.path!).readAsBytes() : null);
    if (bytes == null) return const ImportResult(0, 0, 'تعذر قراءة الملف');
    if (name.endsWith('.json')) return _importJson(bytes);
    if (name.endsWith('.csv')) return _importRows(_parseCsv(utf8.decode(bytes)));
    return _importRows(_parseExcel(bytes));
  }

  static List<Map<String, String>> _parseCsv(String text) {
    final rows = const CsvToListConverter(eol: '\n').convert(text);
    if (rows.isEmpty) return [];
    final head = rows.first.map((e) => e.toString().trim()).toList();
    return rows.skip(1).where((r) => r.any((c) => c.toString().trim().isNotEmpty)).map((r) {
      final m = <String, String>{};
      for (var i = 0; i < head.length; i++) {
        m[head[i]] = i < r.length ? r[i].toString().trim() : '';
      }
      return m;
    }).toList();
  }

  static List<Map<String, String>> _parseExcel(List<int> bytes) {
    final xl = Excel.decodeBytes(bytes);
    if (xl.tables.isEmpty) return [];
    final sheet = xl.tables[xl.tables.keys.first]!;
    if (sheet.rows.isEmpty) return [];
    final head = sheet.rows.first
        .map((c) => c?.value?.toString().trim() ?? '')
        .toList();
    return sheet.rows.skip(1).map((r) {
      final m = <String, String>{};
      for (var i = 0; i < head.length; i++) {
        m[head[i]] = i < r.length ? (r[i]?.value?.toString().trim() ?? '') : '';
      }
      return m;
    }).where((m) => m.values.any((v) => v.isNotEmpty)).toList();
  }

  static String _g(Map<String, String> r, List<String> keys) {
    for (final k in keys) {
      final v = r[k] ?? r[k.toLowerCase()];
      if (v != null && v.trim().isNotEmpty) return v.trim();
    }
    // بحث غير حساس لحالة الأحرف في مفاتيح الصف
    final lower = {for (final e in r.entries) e.key.toLowerCase(): e.value};
    for (final k in keys) {
      final v = lower[k.toLowerCase()];
      if (v != null && v.trim().isNotEmpty) return v.trim();
    }
    return '';
  }

  static Future<ImportResult> _importJson(List<int> bytes) async {
    final decoded = jsonDecode(utf8.decode(bytes));
    final db = DBHelper.instance;
    var drugs = 0, prods = 0;
    final existing = await db.allGenerics();
    final byName = {for (final g in existing) norm(g.nameEn): g};

    Future<void> addDrug(Map<String, dynamic> g) async {
      final en = (g['genericEn'] ?? g['name_en'] ?? '').toString();
      if (en.isEmpty) return;
      GenericDrug? drug = byName[norm(en)];
      if (drug == null) {
        final id = await db.insertGeneric(GenericDrug.fromMap({
          ...g,
          'name_en': en,
          'system_id': g['systemId'] ?? g['system_id'] ?? 'misc',
        }));
        drug = (await db.allGenerics()).firstWhere((x) => x.id == id);
        byName[norm(en)] = drug;
        drugs++;
      }
      for (final pr in (g['products'] as List? ?? [])) {
        final pm = (pr as Map).cast<String, dynamic>();
        await db.insertTrade(TradeProduct.fromMap({...pm, 'generic_id': drug.id}));
        prods++;
      }
    }

    if (decoded is Map && decoded['drugs'] is List) {
      for (final g in (decoded['drugs'] as List)) {
        await addDrug((g as Map).cast<String, dynamic>());
      }
    } else if (decoded is List) {
      for (final g in decoded) {
        if (g is Map) await addDrug(g.cast<String, dynamic>());
      }
    }
    return ImportResult(drugs, prods, 'تم استيراد JSON وحفظه دائماً');
  }

  static Future<ImportResult> _importRows(List<Map<String, String>> rows) async {
    final db = DBHelper.instance;
    var drugs = 0, prods = 0;
    final existing = await db.allGenerics();
    final byName = {for (final g in existing) norm(g.nameEn): g};
    for (final r in rows) {
      final en = _g(r, ['genericEn', 'generic_name_en', 'nameEn', 'Generic EN']);
      if (en.isEmpty) continue;
      var drug = byName[norm(en)];
      if (drug == null) {
        final sysId = _g(r, ['systemId', 'system_id', 'system']);
        final sys = kSystems.any((s) => s.id == sysId)
            ? systemById(sysId)
            : kSystems.last;
        final id = await db.insertGeneric(GenericDrug(
          nameEn: en,
          nameAr: _g(r, ['genericAr', 'generic_name_ar', 'nameAr']),
          systemId: sys.id,
          subgroupEn: _g(r, ['subgroupEn', 'subgroup_en']),
          subgroupAr: _g(r, ['subgroupAr', 'subgroup_ar']),
          atc: _g(r, ['atc', 'atcCode', 'atc_code']),
          introduction: _g(r, ['introduction']),
          mechanism: _g(r, ['mechanism', 'mechanismOfAction']),
          indications: _g(r, ['indications']),
          dosage: _g(r, ['dosage']),
          interactions: _g(r, ['interactions', 'drugInteractions']),
          warnings: _g(r, ['warnings']),
          pregnancy: _g(r, ['pregnancy']),
          imagePath: _g(r, ['image', 'imagePath', 'image_path']),
          source: 'Imported file',
        ));
        drug = GenericDrug(id: id, nameEn: en);
        byName[norm(en)] = drug;
        drugs++;
      }
      final brand = _g(r, ['brand', 'brandName', 'brand_name']);
      if (brand.isNotEmpty && drug.id != null) {
        await db.insertTrade(TradeProduct(
          genericId: drug.id!,
          brandName: brand,
          strength: _g(r, ['strength']),
          dosageForm: _g(r, ['form', 'dosageForm', 'dosage_form']),
          manufacturer: _g(r, ['manufacturer']),
          country: _g(r, ['country']),
          agentYemen: _g(r, ['agentYemen', 'agent_yemen']),
          imagePath: _g(r, ['productImage', 'product_image']),
          source: 'Imported file',
        ));
        prods++;
      }
    }
    return ImportResult(drugs, prods, 'تم الاستيراد والحفظ الدائم في قاعدة الجهاز');
  }

  /// تصدير القاعدة كاملة JSON (للنشر من لوحة التحكم / النسخ الاحتياطي)
  static Future<String> exportJson() async {
    final db = DBHelper.instance;
    final generics = await db.allGenerics();
    final out = <Map<String, dynamic>>[];
    for (final g in generics) {
      final products = await db.productsOf(g.id!);
      out.add({
        'genericEn': g.nameEn, 'genericAr': g.nameAr, 'systemId': g.systemId,
        'subgroupEn': g.subgroupEn, 'subgroupAr': g.subgroupAr, 'atc': g.atc,
        'introduction': g.introduction, 'mechanism': g.mechanism,
        'indications': g.indications, 'dosage': g.dosage,
        'interactions': g.interactions, 'warnings': g.warnings,
        'pregnancy': g.pregnancy, 'image': g.imagePath, 'source': g.source,
        'products': products
            .map((p) => {
                  'brand': p.brandName, 'strength': p.strength,
                  'form': p.dosageForm, 'manufacturer': p.manufacturer,
                  'country': p.country, 'agentYemen': p.agentYemen,
                  'image': p.imagePath, 'verified': p.verified,
                })
            .toList(),
      });
    }
    return const JsonEncoder.withIndent(' ')
        .convert({'app': 'AbdulmajeedPharma (APH)', 'version': 3, 'drugs': out});
  }
}
