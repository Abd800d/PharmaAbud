import 'dart:convert';
import 'package:http/http.dart' as http;
import '../app_settings.dart';
import '../db/db_helper.dart';
import '../models/drug_models.dart';

/// نتيجة المزامنة
class SyncResult {
  final bool ok;
  final int newDrugs, updatedDrugs, newProducts, updatedProducts, announcements;
  final String message;
  final String source;
  const SyncResult({
    required this.ok,
    this.newDrugs = 0,
    this.updatedDrugs = 0,
    this.newProducts = 0,
    this.updatedProducts = 0,
    this.announcements = 0,
    this.message = '',
    this.source = '',
  });
}

/// مزامنة قاعدة APH مع «موقع التحكم» الذي يديره د. عبدالمجيد:
/// يسحب ملف aph-database.json المنشور (GitHub / أي رابط HTTPS) ويدمجه في
/// قاعدة الجهاز — فيرى كل مستخدم أي دواء أو منتج أو وكيل أو إعلان يُحدَّث.
/// يعمل فقط عند توفر الإنترنت، ولا يمسّ بيانات المستخدم عند انقطاعه.
class SyncService {
  /// روابط بديلة تُجرّب بالترتيب إذا فشل الرابط الأساسي
  static List<String> get urls {
    final main = AppSettings.syncUrl.value.trim();
    final list = <String>[main];
    final gh = 'Abd800d/PharmaAbud';
    if (!main.contains('jsdelivr')) {
      list.add('https://cdn.jsdelivr.net/gh/$gh@main/webapp/aph-database.json');
    }
    if (!main.contains('raw.githubusercontent')) {
      list.add(
          'https://raw.githubusercontent.com/$gh/main/webapp/aph-database.json');
    }
    return list.where((u) => u.startsWith('http')).toList();
  }

  static Future<SyncResult> pull() async {
    Map<String, dynamic>? data;
    var used = '';
    String lastError = '';
    for (final u in urls) {
      try {
        final res = await http
            .get(Uri.parse(u), headers: {'Accept': 'application/json'})
            .timeout(const Duration(seconds: 35));
        if (res.statusCode != 200) {
          lastError = 'HTTP ${res.statusCode}';
          continue;
        }
        final decoded = jsonDecode(utf8.decode(res.bodyBytes));
        if (decoded is Map<String, dynamic> && decoded['drugs'] is List) {
          data = decoded;
          used = u;
          break;
        }
        lastError = S.t('File format is not an APH database',
            'صيغة الملف ليست قاعدة APH');
      } catch (e) {
        lastError = e.toString();
      }
    }
    if (data == null) {
      return SyncResult(
          ok: false,
          message: S.t('No internet or the published database is unavailable. ',
                  'لا يوجد إنترنت أو أن القاعدة المنشورة غير متاحة. ') +
              lastError);
    }
    return _merge(data, used);
  }

  static Future<SyncResult> _merge(Map<String, dynamic> data, String source) async {
    final db = DBHelper.instance;
    final drugs = (data['drugs'] as List).cast<dynamic>();
    var newD = 0, upD = 0, newP = 0, upP = 0, ann = 0;

    for (final raw in drugs) {
      if (raw is! Map) continue;
      final g = raw.cast<String, dynamic>();
      final nameEn = (g['genericEn'] ?? '').toString().trim();
      if (nameEn.isEmpty) continue;
      final existing = await db.genericByName(nameEn);
      int gid;
      if (existing == null) {
        gid = await db.insertGeneric(GenericDrug(
          nameEn: nameEn,
          nameAr: (g['genericAr'] ?? '').toString(),
          systemId: (g['systemId'] ?? 'misc').toString(),
          subgroupEn: (g['subgroupEn'] ?? 'General').toString(),
          subgroupAr: (g['subgroupAr'] ?? 'عام').toString(),
          atc: (g['atc'] ?? '').toString(),
          introduction: (g['introduction'] ?? '').toString(),
          mechanism: (g['mechanism'] ?? '').toString(),
          indications: (g['indications'] ?? '').toString(),
          dosage: (g['dosage'] ?? '').toString(),
          interactions: (g['interactions'] ?? '').toString(),
          warnings: (g['warnings'] ?? '').toString(),
          pregnancy: (g['pregnancy'] ?? '').toString(),
          imagePath: (g['image'] ?? '').toString(),
          source: (g['source'] ?? 'APH sync').toString(),
        ));
        newD++;
      } else {
        gid = existing.id ?? 0;
        final merged = GenericDrug(
          id: gid,
          nameEn: existing.nameEn,
          nameAr: _fill(existing.nameAr, g['genericAr']),
          systemId: _fill(existing.systemId, g['systemId'], fallback: 'misc'),
          subgroupEn: _fill(existing.subgroupEn, g['subgroupEn'],
              fallback: 'General'),
          subgroupAr:
              _fill(existing.subgroupAr, g['subgroupAr'], fallback: 'عام'),
          atc: _fill(existing.atc, g['atc']),
          introduction: _fill(existing.introduction, g['introduction']),
          mechanism: _fill(existing.mechanism, g['mechanism']),
          indications: _fill(existing.indications, g['indications']),
          dosage: _fill(existing.dosage, g['dosage']),
          interactions: _fill(existing.interactions, g['interactions']),
          warnings: _fill(existing.warnings, g['warnings']),
          pregnancy: _fill(existing.pregnancy, g['pregnancy']),
          imagePath: existing.imagePath.isEmpty
              ? (g['image'] ?? '').toString()
              : existing.imagePath,
          source: existing.source.isEmpty
              ? (g['source'] ?? 'APH sync').toString()
              : existing.source,
        );
        await db.updateGeneric(merged);
        upD++;
      }

      final prods = (g['products'] as List? ?? []).cast<dynamic>();
      for (final praw in prods) {
        if (praw is! Map) continue;
        final pm = praw.cast<String, dynamic>();
        final brand = (pm['brand'] ?? '').toString().trim();
        if (brand.isEmpty) continue;
        final strength = (pm['strength'] ?? '').toString();
        final form = (pm['form'] ?? '').toString();
        final manuf = (pm['manufacturer'] ?? '').toString();
        final country = (pm['country'] ?? '').toString();
        final agent = (pm['agentYemen'] ?? '').toString();
        final verified = pm['verified'] == true || pm['verified'] == 1;
        final exists =
            await db.productExists(gid, brand, strength, form, manuf);
        if (!exists) {
          await db.insertTrade(TradeProduct(
            genericId: gid,
            brandName: brand,
            manufacturer: manuf,
            country: country,
            strength: strength,
            dosageForm: form,
            agentYemen: agent,
            imagePath: (pm['image'] ?? '').toString(),
            source: (pm['source'] ?? 'APH sync').toString(),
            verified: verified,
          ));
          newP++;
        } else {
          // تحديث الوكيل/الدولة/التوثيق إن كانت ناقصة محلياً
          final local = (await db.productsOf(gid)).where((p) =>
              p.brandName.toLowerCase() == brand.toLowerCase() &&
              p.strength.toLowerCase() == strength.toLowerCase() &&
              p.dosageForm.toLowerCase() == form.toLowerCase());
          for (final p in local) {
            if (p.agentYemen.isNotEmpty && p.country.isNotEmpty && p.verified) {
              continue;
            }
            await db.updateTrade(TradeProduct(
              id: p.id,
              genericId: gid,
              brandName: p.brandName,
              manufacturer: p.manufacturer.isEmpty ? manuf : p.manufacturer,
              country: p.country.isEmpty ? country : p.country,
              strength: p.strength,
              dosageForm: p.dosageForm,
              agentYemen: p.agentYemen.isEmpty ? agent : p.agentYemen,
              imagePath: p.imagePath.isEmpty
                  ? (pm['image'] ?? '').toString()
                  : p.imagePath,
              source: p.source.isEmpty ? 'APH sync' : p.source,
              verified: p.verified || verified,
            ));
            upP++;
          }
        }
      }
    }

    // إعلانات وردود الإدارة المنشورة من موقع التحكم → تظهر عند كل المستخدمين
    final msgs = (data['announcements'] as List? ?? data['messages'] as List? ?? [])
        .cast<dynamic>();
    for (final mraw in msgs) {
      if (mraw is! Map) continue;
      final m = mraw.cast<String, dynamic>();
      final body = (m['body'] ?? m['text'] ?? '').toString().trim();
      if (body.isEmpty) continue;
      final sid = (m['id'] ?? m['ts'] ?? body.hashCode).toString();
      if (await db.messageExists(sid)) continue;
      final ts = m['ts'] is int
          ? m['ts'] as int
          : int.tryParse((m['ts'] ?? '').toString()) ??
              DateTime.now().millisecondsSinceEpoch;
      await db.addMessage(ChatMessage(
        author: (m['author'] ?? m['name'] ?? 'APH Admin').toString(),
        body: body,
        isAdmin: m['admin'] != false,
        createdAt: ts,
        sourceId: sid,
      ));
      ann++;
    }

    await AppSettings.setLastSync(DateTime.now().millisecondsSinceEpoch);
    AppSettings.bumpDb();
    return SyncResult(
      ok: true,
      newDrugs: newD,
      updatedDrugs: upD,
      newProducts: newP,
      updatedProducts: upP,
      announcements: ann,
      source: source,
      message: S.t(
          '+$newD drugs, +$newP products, $upD updated, $ann announcements',
          '+$newD دواء، +$newP منتج، تحديث $upD، و $ann إعلان'),
    );
  }

  /// لا يستبدل بيانات حرّرها المستخدم محلياً — يملأ الفارغ فقط
  static String _fill(String local, Object? remote, {String fallback = ''}) {
    final r = (remote ?? '').toString().trim();
    if (local.trim().isNotEmpty) return local;
    return r.isEmpty ? fallback : r;
  }
}
