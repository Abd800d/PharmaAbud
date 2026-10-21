import 'dart:async';
import 'package:flutter/material.dart';
import 'app_settings.dart';
import 'db/db_helper.dart';
import 'screens/home_screen.dart';
import 'services/sync_service.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const PharmaApp());
}

class PharmaApp extends StatelessWidget {
  const PharmaApp({super.key});
  @override
  Widget build(BuildContext context) => ValueListenableBuilder<bool>(
        valueListenable: AppSettings.isArabic,
        builder: (_, ar, __) => MaterialApp(
          title: 'AbdulmajeedPharma',
          debugShowCheckedModeBanner: false,
          locale: Locale(ar ? 'ar' : 'en'),
          theme: ThemeData(
            useMaterial3: true,
            brightness: Brightness.dark,
            colorSchemeSeed: const Color(0xFF14C8B4),
            scaffoldBackgroundColor: const Color(0xFF071923),
            appBarTheme: const AppBarTheme(
              backgroundColor: Color(0xFF0B3B4F), foregroundColor: Colors.white),
            cardColor: const Color(0xFF0E2F40),
          ),
          builder: (_, child) => Directionality(
            textDirection: ar ? TextDirection.rtl : TextDirection.ltr,
            child: child!,
          ),
          home: const AppBootstrap(),
        ),
      );
}

class AppBootstrap extends StatefulWidget {
  const AppBootstrap({super.key});
  @override
  State<AppBootstrap> createState() => _AppBootstrapState();
}

class _AppBootstrapState extends State<AppBootstrap> {
  bool _ready = false;
  bool _busy = false;
  bool _openAnyway = false;
  bool _catalogLoading = false;
  int _count = 0;
  String _error = '';

  @override
  void initState() {
    super.initState();
    _initialize();
  }

  Future<void> _initialize() async {
    try {
      await AppSettings.load();
    } catch (e) {
      _error = 'Settings: $e';
    }
    // Insert the small curated seed first; expand the larger RxNorm catalog in
    // the background so first launch doesn't look stuck on a spinner.
    await DBHelper.instance.seedIfEmpty(includeLargeCatalog: false);
    if (DBHelper.lastSeedError.isNotEmpty) _error = DBHelper.lastSeedError;
    try {
      _count = await DBHelper.instance.countGenerics();
    } catch (e) {
      _error = e.toString();
      _count = 0;
    }
    if (mounted) setState(() => _ready = true);
    if (_count > 0) {
      unawaited(_loadLargeCatalog());
    } else if (AppSettings.autoSync.value) {
      await _syncNow(quiet: true);
    }
  }

  Future<void> _loadLargeCatalog() async {
    if (_catalogLoading) return;
    _catalogLoading = true;
    try {
      await DBHelper.instance.ensureLargeCatalog();
      final count = await DBHelper.instance.countGenerics();
      if (mounted) setState(() => _count = count);
      AppSettings.bumpDb();
    } catch (e) {
      DBHelper.lastSeedError = e.toString();
      if (mounted) setState(() => _error = e.toString());
    } finally {
      _catalogLoading = false;
    }
    if (AppSettings.autoSync.value) {
      final result = await SyncService.pull().catchError(
          (_) => const SyncResult(ok: false));
      if (result.ok) AppSettings.bumpDb();
    }
  }

  Future<void> _retry() async {
    setState(() { _busy = true; _error = ''; });
    DBHelper.lastSeedError = '';
    await DBHelper.instance.seedIfEmpty(includeLargeCatalog: false);
    if (DBHelper.lastSeedError.isNotEmpty) _error = DBHelper.lastSeedError;
    final count = await DBHelper.instance.countGenerics().catchError((_) => 0);
    if (!mounted) return;
    setState(() { _count = count; _busy = false; });
    if (count > 0) unawaited(_loadLargeCatalog());
  }

  Future<void> _syncNow({bool quiet = false}) async {
    if (!quiet && mounted) setState(() => _busy = true);
    final result = await SyncService.pull().catchError(
        (_) => const SyncResult(ok: false));
    final count = await DBHelper.instance.countGenerics().catchError((_) => 0);
    if (!mounted) return;
    setState(() {
      _count = count;
      _busy = false;
      _error = result.ok ? '' : result.message;
    });
    if (count > 0) unawaited(_loadLargeCatalog());
  }

  @override
  Widget build(BuildContext context) {
    if (!_ready) {
      return Scaffold(body: Center(child: Column(
        mainAxisSize: MainAxisSize.min, children: [
          const Text('APH', style: TextStyle(fontSize: 42,
              fontWeight: FontWeight.w900, color: Color(0xFF14C8B4))),
          const SizedBox(height: 8),
          const Text('AbdulmajeedPharma', style: TextStyle(fontWeight: FontWeight.bold)),
          Text(S.t('Opening offline drug database…', 'يجري فتح قاعدة الأدوية المحلية…'),
              style: const TextStyle(fontSize: 12, color: Colors.white70)),
          const SizedBox(height: 16),
          const CircularProgressIndicator(),
        ],
      )));
    }
    if (_count > 0 || _openAnyway) return const HomeScreen();
    return Scaffold(
      appBar: AppBar(title: const Text('APH — AbdulmajeedPharma')),
      body: ListView(padding: const EdgeInsets.all(20), children: [
        const Icon(Icons.inventory_2_outlined, size: 52, color: Colors.orangeAccent),
        const SizedBox(height: 12),
        Text(S.t('The drug database could not be opened', 'تعذّر فتح قاعدة الأدوية'),
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        Text(S.t('Retry the built-in database. Internet is only needed for sync.',
            'أعد تحميل القاعدة المدمجة. الإنترنت مطلوب للمزامنة فقط.'),
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 12, color: Colors.white70)),
        const SizedBox(height: 16),
        FilledButton.icon(onPressed: _busy ? null : _retry,
            icon: const Icon(Icons.refresh),
            label: Text(S.t('Retry database', 'إعادة تحميل القاعدة'))),
        const SizedBox(height: 8),
        OutlinedButton.icon(onPressed: _busy ? null : () => _syncNow(),
            icon: const Icon(Icons.cloud_download),
            label: Text(S.t('Try online sync', 'محاولة المزامنة عبر الإنترنت'))),
        if (_busy) const Padding(padding: EdgeInsets.all(16),
            child: Center(child: CircularProgressIndicator())),
        if (_error.isNotEmpty) ...[
          const SizedBox(height: 12),
          SelectableText(_error, textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 11, color: Color(0xFFFDE68A))),
        ],
        TextButton(onPressed: () => setState(() => _openAnyway = true),
            child: Text(S.t('Open anyway', 'افتح على أي حال'))),
      ]),
    );
  }
}
