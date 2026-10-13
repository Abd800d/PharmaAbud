/// Global app state (dependency injection + settings + connectivity).
/// Uses ChangeNotifierProvider — a stable, minimal state-management choice.
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'core/database/local_database.dart';
import 'core/localization/app_localizations.dart';
import 'core/network/api_client.dart';
import 'features/sync/sync_service.dart';
import 'shared/repositories/aph_repository.dart';

class AppState extends ChangeNotifier {
  AppState({AphRepository? repository, SyncService? sync, ApiClient? api})
      : repository = repository ?? AphRepository(),
        sync = sync ?? SyncService(),
        _api = api ?? ApiClient() {
    _initConnectivity();
  }

  final AphRepository repository;
  final SyncService sync;
  final ApiClient _api;

  Locale _locale = const Locale('en');
  ThemeMode _themeMode = ThemeMode.system;
  bool _isOnline = true;
  bool _syncing = false;
  int _currentTab = 0;

  Locale get locale => _locale;
  ThemeMode get themeMode => _themeMode;
  bool get isOnline => _isOnline;
  bool get syncing => _syncing;
  int get currentTab => _currentTab;
  bool get isArabic => _locale.languageCode == 'ar';

  Future<void> loadSettings() async {
    final prefs = await SharedPreferences.getInstance();
    final lang = prefs.getString('language') ?? 'en';
    final theme = prefs.getString('theme') ?? 'system';
    _locale = Locale(lang);
    _themeMode = switch (theme) {
      'light' => ThemeMode.light,
      'dark' => ThemeMode.dark,
      _ => ThemeMode.system,
    };
    notifyListeners();
  }

  Future<void> setLanguage(String code) async {
    _locale = Locale(code);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('language', code);
    notifyListeners();
  }

  void toggleLanguage() => setLanguage(isArabic ? 'en' : 'ar');

  Future<void> setThemeMode(ThemeMode mode) async {
    _themeMode = mode;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('theme', switch (mode) {
      ThemeMode.light => 'light',
      ThemeMode.dark => 'dark',
      _ => 'system',
    });
    notifyListeners();
  }

  void goToTab(int index) {
    _currentTab = index;
    notifyListeners();
  }

  void _initConnectivity() {
    Connectivity().onConnectivityChanged.listen((results) {
      final offline = results.every((r) => r == ConnectivityResult.none);
      if (offline != !_isOnline) {
        _isOnline = !offline;
        notifyListeners();
      }
    });
  }

  Future<void> syncNow() async {
    if (_syncing) return;
    _syncing = true;
    notifyListeners();
    await sync.sync();
    _syncing = false;
    notifyListeners();
  }

  // ------------------------------------------------------------- recents
  Future<List<String>> repositorySearchHistory() =>
      LocalDatabase.instance.recentSearches();

  Future<void> addRecentSearch(String query) =>
      LocalDatabase.instance.addRecentSearch(query);

  Future<void> clearRecentSearches() =>
      LocalDatabase.instance.clearRecentSearches();
}
