import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// إعدادات عامة: اللغة (AR/EN) + وضع الإدارة — تُحفظ دائماً
class AppSettings {
  static final ValueNotifier<bool> isArabic = ValueNotifier<bool>(true);
  static final ValueNotifier<bool> isAdmin = ValueNotifier<bool>(false);
  static String get adminPinKey => 'aph_pin';

  static Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    isArabic.value = p.getBool('aph_arabic') ?? true;
    isAdmin.value = p.getBool('aph_admin') ?? false;
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
}

/// نصوص واجهة EN/AR — S.t('English', 'العربية')
class S {
  static bool get ar => AppSettings.isArabic.value;
  static String t(String en, String arText) => ar ? arText : en;
}

const String kWhatsAppUrl =
    'https://wa.me/967781733795?text=مرحباً، عندي استفسار عن تطبيق APH';
const String kEmail = '7a8b1d@gmail.com';
const String kOwnerEn = 'Abdulmajeed Almakhedhi';
const String kCopyright = '© Dr. Abdulmajeed Abdullah Almakhedhi';
