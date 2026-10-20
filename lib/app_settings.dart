import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Only the public Worker URL may be compiled into the APK. Provider API keys
/// belong exclusively in server-side Worker Secrets.
const String kBuildAiProxy = String.fromEnvironment('APH_AI_PROXY');
const String kBuildSyncUrl = String.fromEnvironment('APH_SYNC_URL');
const String kDefaultSyncUrl =
    'https://raw.githubusercontent.com/Abd800d/PharmaAbud/main/webapp/aph-database.json';

class AppSettings {
  static final ValueNotifier<bool> isArabic = ValueNotifier<bool>(true);
  static final ValueNotifier<bool> isAdmin = ValueNotifier<bool>(false);
  static String get adminPinKey => 'aph_pin';

  static final ValueNotifier<String> aiProvider = ValueNotifier<String>('auto');
  static final ValueNotifier<String> geminiModel =
      ValueNotifier<String>('gemini-2.5-flash');
  static final ValueNotifier<String> openAiModel =
      ValueNotifier<String>('gpt-4o-mini');
  static final ValueNotifier<String> aiProxyUrl =
      ValueNotifier<String>(kBuildAiProxy);

  static final ValueNotifier<String> syncUrl = ValueNotifier<String>(
      kBuildSyncUrl.isEmpty ? kDefaultSyncUrl : kBuildSyncUrl);
  static final ValueNotifier<int> lastSyncAt = ValueNotifier<int>(0);
  static final ValueNotifier<bool> autoSync = ValueNotifier<bool>(true);
  static final ValueNotifier<int> dbRevision = ValueNotifier<int>(0);
  static void bumpDb() => dbRevision.value = dbRevision.value + 1;

  /// Accept only an HTTPS proxy URL; reject API-key-like values and URL params.
  static bool isSafeAiProxyUrl(String value) {
    final v = value.trim();
    if (v.isEmpty) return true;
    final uri = Uri.tryParse(v);
    if (uri == null || uri.scheme != 'https' || uri.host.isEmpty ||
        uri.userInfo.isNotEmpty || uri.hasQuery || uri.hasFragment) {
      return false;
    }
    return !RegExp(r'(AIza[0-9A-Za-z_-]{12,}|sk-[A-Za-z0-9_-]{12,})')
        .hasMatch(v);
  }

  static Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    isArabic.value = prefs.getBool('aph_arabic') ?? true;
    isAdmin.value = prefs.getBool('aph_admin') ?? false;
    aiProvider.value = prefs.getString('aph_ai_provider') ?? 'auto';

    // Remove any keys saved by older versions; never read or retain them.
    await prefs.remove('aph_gemini_key');
    await prefs.remove('aph_openai_key');

    geminiModel.value = prefs.getString('aph_gemini_model') ?? geminiModel.value;
    openAiModel.value = prefs.getString('aph_openai_model') ?? openAiModel.value;
    final savedProxy = prefs.getString('aph_ai_proxy');
    if (savedProxy != null && isSafeAiProxyUrl(savedProxy)) {
      if (savedProxy.trim().isNotEmpty) aiProxyUrl.value = savedProxy.trim();
    } else {
      await prefs.remove('aph_ai_proxy');
      aiProxyUrl.value = kBuildAiProxy;
    }
    if (!isSafeAiProxyUrl(aiProxyUrl.value)) aiProxyUrl.value = '';
    syncUrl.value = prefs.getString('aph_sync_url') ?? syncUrl.value;
    lastSyncAt.value = prefs.getInt('aph_last_sync') ?? 0;
    autoSync.value = prefs.getBool('aph_auto_sync') ?? true;
  }

  static Future<void> setArabic(bool value) async {
    isArabic.value = value;
    await (await SharedPreferences.getInstance()).setBool('aph_arabic', value);
  }

  static Future<void> setAdmin(bool value) async {
    isAdmin.value = value;
    await (await SharedPreferences.getInstance()).setBool('aph_admin', value);
  }

  static Future<String> adminPin() async =>
      (await SharedPreferences.getInstance()).getString(adminPinKey) ?? '1234';

  static Future<void> setAdminPin(String pin) async =>
      (await SharedPreferences.getInstance()).setString(adminPinKey, pin);

  static Future<void> setAiProvider(String value) async {
    aiProvider.value = value;
    await (await SharedPreferences.getInstance())
        .setString('aph_ai_provider', value);
  }

  static Future<void> setGeminiModel(String value) async {
    geminiModel.value = value.trim().isEmpty ? 'gemini-2.5-flash' : value.trim();
    await (await SharedPreferences.getInstance())
        .setString('aph_gemini_model', geminiModel.value);
  }

  static Future<void> setOpenAiModel(String value) async {
    openAiModel.value = value.trim().isEmpty ? 'gpt-4o-mini' : value.trim();
    await (await SharedPreferences.getInstance())
        .setString('aph_openai_model', openAiModel.value);
  }

  static Future<void> setAiProxy(String value) async {
    final url = value.trim();
    if (!isSafeAiProxyUrl(url)) {
      throw const FormatException(
          'Enter only a public HTTPS Worker URL. API keys are never accepted.');
    }
    aiProxyUrl.value = url;
    await (await SharedPreferences.getInstance())
        .setString('aph_ai_proxy', url);
  }

  static Future<void> setSyncUrl(String value) async {
    syncUrl.value = value.trim().isEmpty ? kDefaultSyncUrl : value.trim();
    await (await SharedPreferences.getInstance())
        .setString('aph_sync_url', syncUrl.value);
  }

  static Future<void> setLastSync(int milliseconds) async {
    lastSyncAt.value = milliseconds;
    await (await SharedPreferences.getInstance())
        .setInt('aph_last_sync', milliseconds);
  }

  static Future<void> setAutoSync(bool value) async {
    autoSync.value = value;
    await (await SharedPreferences.getInstance())
        .setBool('aph_auto_sync', value);
  }

  static String get activeProvider {
    switch (aiProvider.value) {
      case 'offline':
        return 'offline';
      case 'openai':
        return aiProxyUrl.value.trim().isEmpty ? 'offline' : 'openai';
      case 'gemini':
        return aiProxyUrl.value.trim().isEmpty ? 'offline' : 'gemini';
      default:
        return aiProxyUrl.value.trim().isEmpty ? 'offline' : 'gemini';
    }
  }
}

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
