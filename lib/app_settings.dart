import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// مفاتيح الذكاء الاصطناعي يمكن حقنها وقت البناء (CI) دون كتابتها في المستودع:
///   flutter build apk --release --dart-define=APH_GEMINI_KEY=... --dart-define=APH_OPENAI_KEY=...
/// في GitHub Actions تُقرأ من Secrets: APH_GEMINI_KEY / APH_OPENAI_KEY.
/// وإن لم توجد، يدخلها المستخدم بنفسه من شاشة الإعدادات وتُحفظ على جهازه فقط.
const String kBuildGeminiKey = String.fromEnvironment('APH_GEMINI_KEY');
const String kBuildOpenAiKey = String.fromEnvironment('APH_OPENAI_KEY');
const String kBuildSyncUrl = String.fromEnvironment('APH_SYNC_URL');

/// عنوان قاعدة البيانات المنشورة (لوحة التحكم على الويب) — يسحبها التطبيق
/// عند توفر الإنترنت فتصل تعديلات الإدارة إلى كل المستخدمين.
const String kDefaultSyncUrl =
    'https://raw.githubusercontent.com/Abd800d/PharmaAbud/main/webapp/aph-database.json';

/// إعدادات عامة: اللغة (AR/EN) + وضع الإدارة + الذكاء الاصطناعي + المزامنة — تُحفظ دائماً
class AppSettings {
  static final ValueNotifier<bool> isArabic = ValueNotifier<bool>(true);
  static final ValueNotifier<bool> isAdmin = ValueNotifier<bool>(false);
  static String get adminPinKey => 'aph_pin';

  // ---- الذكاء الاصطناعي ----
  /// auto = Gemini إن وُجد مفتاح، وإلا OpenAI، وإلا الوضع المحلي دون إنترنت
  static final ValueNotifier<String> aiProvider = ValueNotifier<String>('auto');
  static final ValueNotifier<String> geminiKey = ValueNotifier<String>(kBuildGeminiKey);
  static final ValueNotifier<String> openAiKey = ValueNotifier<String>(kBuildOpenAiKey);
  static final ValueNotifier<String> geminiModel =
      ValueNotifier<String>('gemini-2.5-flash');
  static final ValueNotifier<String> openAiModel =
      ValueNotifier<String>('gpt-4o-mini');

  // ---- المزامنة (لوحة التحكم على الويب) ----
  static final ValueNotifier<String> syncUrl =
      ValueNotifier<String>(kBuildSyncUrl.isEmpty ? kDefaultSyncUrl : kBuildSyncUrl);
  static final ValueNotifier<int> lastSyncAt = ValueNotifier<int>(0);
  static final ValueNotifier<bool> autoSync = ValueNotifier<bool>(true);

  /// يزداد عند أي تغيير كبير في القاعدة (مزامنة/استيراد) فتتحدث الشاشات تلقائياً
  static final ValueNotifier<int> dbRevision = ValueNotifier<int>(0);
  static void bumpDb() => dbRevision.value = dbRevision.value + 1;

  static Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    isArabic.value = p.getBool('aph_arabic') ?? true;
    isAdmin.value = p.getBool('aph_admin') ?? false;
    aiProvider.value = p.getString('aph_ai_provider') ?? 'auto';
    final g = p.getString('aph_gemini_key');
    if (g != null && g.isNotEmpty) geminiKey.value = g;
    final o = p.getString('aph_openai_key');
    if (o != null && o.isNotEmpty) openAiKey.value = o;
    geminiModel.value = p.getString('aph_gemini_model') ?? geminiModel.value;
    openAiModel.value = p.getString('aph_openai_model') ?? openAiModel.value;
    syncUrl.value = p.getString('aph_sync_url') ?? syncUrl.value;
    lastSyncAt.value = p.getInt('aph_last_sync') ?? 0;
    autoSync.value = p.getBool('aph_auto_sync') ?? true;
  }

  static Future<void> setArabic(bool v) async {
    isArabic.value = v;
    (await SharedPreferences.getInstance()).setBool('aph_arabic', v);
  }

  static Future<void> setAdmin(bool v) async {
    isAdmin.value = v;
    (await SharedPreferences.getInstance()).setBool('aph_admin', v);
  }

  static Future<String> adminPin() async =>
      (await SharedPreferences.getInstance()).getString(adminPinKey) ?? '1234';

  static Future<void> setAdminPin(String pin) async =>
      (await SharedPreferences.getInstance()).setString(adminPinKey, pin);

  static Future<void> setAiProvider(String v) async {
    aiProvider.value = v;
    (await SharedPreferences.getInstance()).setString('aph_ai_provider', v);
  }

  /// يُحفظ المفتاح على هذا الجهاز فقط (SharedPreferences) — لا يُرفع لأي مكان.
  static Future<void> setGeminiKey(String v) async {
    geminiKey.value = v.trim();
    (await SharedPreferences.getInstance()).setString('aph_gemini_key', geminiKey.value);
  }

  static Future<void> setOpenAiKey(String v) async {
    openAiKey.value = v.trim();
    (await SharedPreferences.getInstance()).setString('aph_openai_key', openAiKey.value);
  }

  static Future<void> setGeminiModel(String v) async {
    geminiModel.value = v.trim().isEmpty ? 'gemini-2.5-flash' : v.trim();
    (await SharedPreferences.getInstance())
        .setString('aph_gemini_model', geminiModel.value);
  }

  static Future<void> setOpenAiModel(String v) async {
    openAiModel.value = v.trim().isEmpty ? 'gpt-4o-mini' : v.trim();
    (await SharedPreferences.getInstance())
        .setString('aph_openai_model', openAiModel.value);
  }

  static Future<void> setSyncUrl(String v) async {
    syncUrl.value = v.trim().isEmpty ? kDefaultSyncUrl : v.trim();
    (await SharedPreferences.getInstance()).setString('aph_sync_url', syncUrl.value);
  }

  static Future<void> setLastSync(int ms) async {
    lastSyncAt.value = ms;
    (await SharedPreferences.getInstance()).setInt('aph_last_sync', ms);
  }

  static Future<void> setAutoSync(bool v) async {
    autoSync.value = v;
    (await SharedPreferences.getInstance()).setBool('aph_auto_sync', v);
  }

  /// المزوّد الفعلي الذي سيُستخدم الآن
  static String get activeProvider {
    switch (aiProvider.value) {
      case 'gemini':
      case 'openai':
      case 'offline':
        return aiProvider.value;
      default:
        if (geminiKey.value.isNotEmpty) return 'gemini';
        if (openAiKey.value.isNotEmpty) return 'openai';
        return 'offline';
    }
  }
}

/// نصوص واجهة EN/AR — S.t('English', 'العربية')
class S {
  static bool get ar => AppSettings.isArabic.value;
  static String t(String en, String arText) => ar ? arText : en;
}

const String kWhatsAppUrl =
    'https://wa.me/967781733795?text=مرحباً، عندي استفسار عن تطبيق APH';
const String kWhatsAppNumber = '967781733795';
const String kEmail = '7a8b1d@gmail.com';
const String kOwnerEn = 'Abdulmajeed Almakhedhi';
const String kCopyright = '© Dr. Abdulmajeed Abdullah Almakhedhi';
String whatsappWith(String message) =>
    'https://wa.me/$kWhatsAppNumber?text=${Uri.encodeComponent(message)}';
