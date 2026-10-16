import 'dart:convert';
import 'dart:io';
import 'dart:math' show min;
import 'package:csv/csv.dart';
import 'package:excel/excel.dart';
import 'package:file_picker/file_picker.dart';
import '../app_settings.dart';
import '../db/db_helper.dart';
import '../models/drug_models.dart';
import 'search_service.dart' show norm;

/// استيراد دائم لقواعد بيانات كبيرة جداً: CSV / Excel (.xlsx) / JSON / JSONL
/// الأعمدة: genericEn,genericAr,systemId,subgroupEn,subgroupAr,atc,
/// introduction,mechanism,indications,dosage,interactions,warnings,pregnancy,
/// brand,strength,form,manufacturer,country,agentYemen,image
///
/// الأداء: كل دفعة (5000 سجل) تُكتب في معاملة واحدة — أسرع بمئات المرات من
/// الإدخال سجلاً سجلاً، وهذا ما يسمح باستيراد قواعد بمئات الآلاف أو ملايين السجلات.
/// للملفات الضخمة جداً يُنصح بصيغة JSONL (سطر JSON واحد لكل دواء) لأنها تُقرأ سطراً سطراً.
class ImportResult {
  final int drugs, products;
  final String message;
  const ImportResult(this.drugs, this.products, this.message);
}

class _Tally {
  int drugs = 0;
  int products = 0;
}

class ImportService {
  static const int _chunk = 5000;

  static Future<ImportResult?> pickAndImport() async {
    final picked = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['csv', 'json', 'jsonl', 'ndjson', 'xlsx', 'xls'],
      withData: true,
      allowMultiple: false,
    );
    if (picked == null || picked.files.isEmpty) return null;
    final file = picked.files.first;
    final name = file.name.toLowerCase();
    final bytes = file.bytes ??
        (file.path != null ? await File(file.path!).readAsBytes() : null);
    if (bytes == null) {
      return const ImportResult(0, 0, 'تعذر قراءة الملف / Could not read the file');
    }
    if (name.endsWith('.jsonl') || name.endsWith('.ndjson')) {
      return _importJsonLines(utf8.decode(bytes));
    }
    if (name.endsWith('.json')) return _importJson(bytes);
    if (name.endsWith('.csv')) return _importRows(_parseCsv(utf8.decode(bytes)));
    return _importRows(_parseExcel(bytes));
  }

  static List<Map<String, String>> _parseCsv(String text) {
    final rows = const CsvToListConverter(eol: '\n').convert(text);
    if (rows.isEmpty) return [];
    final head = rows.first.map((e) => e.toString().trim()).toList();
    return rows
        .skip(1)
        .where((r) => r.any((c) => c.toString().trim().isNotEmpty))
        .map((r) {
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
    final head =
        sheet.rows.first.map((c) => c?.value?.toString().trim() ?? '').toList();
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
    final lower = {for (final e in r.entries) e.key.toLowerCase(): e.value};
    for (final k in keys) {
      final v = lower[k.toLowerCase()];
      if (v != null && v.trim().isNotEmpty) return v.trim();
    }
    return '';
  }

  /// خريطة الأسماء الموجودة مسبقاً → id (تُبنى مرة واحدة، لا في كل سجل)
  static Future<Map<String, int>> _existingIds() async {
    final existing = await DBHelper.instance.allGenerics();
    return {for (final g in existing) norm(g.nameEn): g.id!};
  }

  // ---------------- JSON ----------------
  static Future<ImportResult> _importJson(List<int> bytes) async {
    final text = utf8.decode(bytes);
    dynamic decoded;
    try {
      decoded = jsonDecode(text);
    } catch (_) {
      // قد يكون الملف بصيغة JSONL رغم امتداده .json
      return _importJsonLines(text);
    }
    final list = <Map<String, dynamic>>[];
    if (decoded is Map && decoded['drugs'] is List) {
      for (final g in (decoded['drugs'] as List)) {
        if (g is Map) list.add(g.cast<String, dynamic>());
      }
    } else if (decoded is List) {
      for (final g in decoded) {
        if (g is Map) list.add(g.cast<String, dynamic>());
      }
    } else if (decoded is Map) {
      list.add(decoded.cast<String, dynamic>());
    }
    return _upsertJsonDrugs(list);
  }

  /// JSON Lines: سطر واحد لكل دواء — يُعالج على دفعات دون تحميل الكل في الذاكرة
  static Future<ImportResult> _importJsonLines(String text) async {
    final byName = await _existingIds();
    final tally = _Tally();
    var buffer = <Map<String, dynamic>>[];
    for (final line in const LineSplitter().convert(text)) {
      final s = line.trim();
      if (s.isEmpty) continue;
      dynamic j;
      try {
        j = jsonDecode(s);
      } catch (_) {
        continue;
      }
      if (j is Map) {
        buffer.add(j.cast<String, dynamic>());
      } else if (j is List) {
        for (final e in j) {
          if (e is Map) buffer.add(e.cast<String, dynamic>());
        }
      }
      if (buffer.length >= _chunk) {
        await _writeJsonChunk(buffer, byName, tally);
        buffer = <Map<String, dynamic>>[];
      }
    }
    if (buffer.isNotEmpty) await _writeJsonChunk(buffer, byName, tally);
    AppSettings.bumpDb();
    return ImportResult(tally.drugs, tally.products,
        'JSONL — ${S.t('imported and saved permanently', 'استُورد وحُفظ دائماً')}');
  }

  static Future<ImportResult> _upsertJsonDrugs(
      List<Map<String, dynamic>> list) async {
    final byName = await _existingIds();
    final tally = _Tally();
    for (var i = 0; i < list.length; i += _chunk) {
      await _writeJsonChunk(list.sublist(i, min(i + _chunk, list.length)),
          byName, tally);
    }
    AppSettings.bumpDb();
    return ImportResult(tally.drugs, tally.products,
        S.t('Imported and saved permanently on the device',
            'تم الاستيراد والحفظ الدائم في قاعدة الجهاز'));
  }

  static Future<void> _writeJsonChunk(List<Map<String, dynamic>> chunkData,
      Map<String, int> byName, _Tally tally) async {
    final db = DBHelper.instance;
    await db.transaction<void>((txn) async {
      for (final g in chunkData) {
        final en = (g['genericEn'] ?? g['name_en'] ?? g['generic'] ?? '')
            .toString()
            .trim();
        if (en.isEmpty) continue;
        final key = norm(en);
        var gid = byName[key];
        if (gid == null) {
          gid = await db.insertGeneric(
              GenericDrug.fromMap({
                ...g,
                'name_en': en,
                'system_id': g['systemId'] ?? g['system_id'] ?? 'misc',
              }),
              txn);
          byName[key] = gid;
          tally.drugs++;
        }
        final prods = (g['products'] as List? ?? g['tradeProducts'] as List? ?? []);
        for (final pr in prods) {
          if (pr is! Map) continue;
          final pm = pr.cast<String, dynamic>();
          final brand =
              (pm['brand'] ?? pm['brandName'] ?? pm['brand_name'] ?? '').toString().trim();
          if (brand.isEmpty) continue;
          await db.insertTrade(
              TradeProduct.fromMap({...pm, 'generic_id': gid}), txn);
          tally.products++;
        }
      }
    });
  }

  // ---------------- CSV / Excel ----------------
  static Future<ImportResult> _importRows(List<Map<String, String>> rows) async {
    final db = DBHelper.instance;
    final byName = await _existingIds();
    final tally = _Tally();
    for (var start = 0; start < rows.length; start += _chunk) {
      final part = rows.sublist(start, min(start + _chunk, rows.length));
      await db.transaction<void>((txn) async {
        for (final r in part) {
          final en =
              _g(r, ['genericEn', 'generic_name_en', 'nameEn', 'Generic EN']);
          if (en.isEmpty) continue;
          final key = norm(en);
          var gid = byName[key];
          if (gid == null) {
            final sysId = _g(r, ['systemId', 'system_id', 'system']);
            final sys =
                kSystems.any((s) => s.id == sysId) ? systemById(sysId) : kSystems.last;
            gid = await db.insertGeneric(
                GenericDrug(
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
                ),
                txn);
            byName[key] = gid;
            tally.drugs++;
          }
          final brand = _g(r, ['brand', 'brandName', 'brand_name']);
          if (brand.isNotEmpty) {
            await db.insertTrade(
                TradeProduct(
                  genericId: gid,
                  brandName: brand,
                  strength: _g(r, ['strength']),
                  dosageForm: _g(r, ['form', 'dosageForm', 'dosage_form']),
                  manufacturer: _g(r, ['manufacturer']),
                  country: _g(r, ['country']),
                  agentYemen: _g(r, ['agentYemen', 'agent_yemen']),
                  imagePath: _g(r, ['productImage', 'product_image']),
                  source: 'Imported file',
                ),
                txn);
            tally.products++;
          }
        }
      });
    }
    AppSettings.bumpDb();
    return ImportResult(tally.drugs, tally.products,
        S.t('Imported and saved permanently on the device',
            'تم الاستيراد والحفظ الدائم في قاعدة الجهاز'));
  }

  /// تصدير القاعدة كاملة JSON (للنشر من لوحة التحكم / النسخ الاحتياطي)
  static Future<String> exportJson() async {
    final db = DBHelper.instance;
    final generics = await db.allGenerics();
    final grouped = await db.productsGroupedByGeneric();
    final out = <Map<String, dynamic>>[];
    for (final g in generics) {
      final products = grouped[g.id] ?? const <TradeProduct>[];
      out.add({
        'id': g.id,
        'genericEn': g.nameEn,
        'genericAr': g.nameAr,
        'systemId': g.systemId,
        'systemEn': systemById(g.systemId).en,
        'systemAr': systemById(g.systemId).ar,
        'subgroupEn': g.subgroupEn,
        'subgroupAr': g.subgroupAr,
        'atc': g.atc,
        'introduction': g.introduction,
        'mechanism': g.mechanism,
        'indications': g.indications,
        'dosage': g.dosage,
        'interactions': g.interactions,
        'warnings': g.warnings,
        'pregnancy': g.pregnancy,
        'image': g.imagePath,
        'source': g.source,
        'products': products
            .map((p) => {
                  'brand': p.brandName,
                  'strength': p.strength,
                  'form': p.dosageForm,
                  'manufacturer': p.manufacturer,
                  'country': p.country,
                  'agentYemen': p.agentYemen,
                  'image': p.imagePath,
                  'verified': p.verified,
                })
            .toList(),
      });
    }
    // نفس بنية ملف المزامنة aph-database.json حتى يُنشر مباشرة من لوحة التحكم
    return const JsonEncoder.withIndent(' ').convert({
      'app': 'AbdulmajeedPharma (APH)',
      'version': 4,
      'copyright': '© Dr. Abdulmajeed Abdullah Almakhedhi',
      'updatedAt': DateTime.now().toUtc().toIso8601String(),
      'systems': [
        for (final s in kSystems) {'id': s.id, 'en': s.en, 'ar': s.ar}
      ],
      'announcements': [],
      'drugs': out,
    });
  }
}
