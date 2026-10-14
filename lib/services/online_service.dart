import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';

/// خدمات الإنترنت الحقيقية: openFDA + RxNorm + Google/DailyMed/Lens/WhatsApp
/// كلها اختيارية — التطبيق يعمل دون إنترنت، وتُستخدم فقط عند الاتصال.
class OnlineService {
  static Future<void> openUrl(String url) async {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  static String googleSearch(String q) =>
      'https://www.google.com/search?q=${Uri.encodeComponent('$q drug uses dose')}';
  static String googleImages(String q) =>
      'https://www.google.com/search?tbm=isch&q=${Uri.encodeComponent('$q medicine packaging')}';
  static const String googleLens = 'https://lens.google.com';
  static String dailyMed(String q) =>
      'https://dailymed.nlm.nih.gov/dailymed/search.cfm?query=${Uri.encodeComponent(q)}';

  /// جلب النشرة الرسمية الأمريكية من openFDA لدواء ناقص البيانات
  static Future<Map<String, String>?> fetchFdaLabel(String genericEn) async {
    try {
      final uri = Uri.parse(
          'https://api.fda.gov/drug/label.json?search=openfda.generic_name:"${Uri.encodeComponent(genericEn)}"&limit=1');
      final res = await http.get(uri).timeout(const Duration(seconds: 15));
      if (res.statusCode != 200) return null;
      final results = (jsonDecode(res.body)['results'] as List?);
      if (results == null || results.isEmpty) return null;
      final l = (results.first as Map).cast<String, dynamic>();
      String g(String k) {
        final v = l[k];
        if (v is List && v.isNotEmpty) return v.first.toString();
        return '';
      }

      return {
        'indications': g('indications_and_usage'),
        'dosage': g('dosage_and_administration'),
        'warnings': g('warnings'),
        'interactions': g('drug_interactions'),
      };
    } catch (_) {
      return null; // غير متصل أو الخدمة غير متاحة — القاعدة المحلية تكفي
    }
  }

  /// التحقق من الاسم العلمي عبر RxNorm (NIH) عند توفر الإنترنت
  static Future<String?> fetchRxNormName(String genericEn) async {
    try {
      final uri = Uri.parse(
          'https://rxnav.nlm.nih.gov/REST/rxcui.json?name=${Uri.encodeComponent(genericEn)}');
      final res = await http.get(uri).timeout(const Duration(seconds: 12));
      if (res.statusCode != 200) return null;
      final ids = jsonDecode(res.body)['idGroup']?['rxnormId'];
      if (ids is List && ids.isNotEmpty) return 'RxCUI ${ids.first}';
      return null;
    } catch (_) {
      return null;
    }
  }
}
