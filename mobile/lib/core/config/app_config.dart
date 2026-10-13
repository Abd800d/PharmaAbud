/// Environment configuration (§80). Secrets NEVER live in the client.
class AppConfig {
  AppConfig._();

  /// Development default. Production builds override via --dart-define=APH_API_BASE=...
  static const String apiBase = String.fromEnvironment(
    'APH_API_BASE',
    defaultValue: 'http://10.0.2.2:8000/api/v1',
  );

  static const String appName = 'AbdulmajeedPharma';
  static const String appNameAr = 'موسوعة عبدالمجيد للأدوية';
  static const String brandShort = 'APH';
  static const String owner = 'Dr. Abdulmajeed Abdullah Almakhedhi';
  static const String copyright = '© Dr. Abdulmajeed Abdullah Almakhedhi';
  static const String appVersion = '1.0.0';

  /// Support (§63) — external actions only fire on explicit user tap.
  static const String supportWhatsApp = '781733795';
  static const String supportEmail = '7a8b1d@gmail.com';

  static const Duration searchDebounce = Duration(milliseconds: 300);
  static const Duration syncInterval = Duration(minutes: 15);
  static const int pageSize = 25;
}
