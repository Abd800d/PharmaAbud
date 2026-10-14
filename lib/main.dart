import 'package:flutter/material.dart';
import 'app_settings.dart';
import 'db/db_helper.dart';
import 'screens/home_screen.dart';

/// AbdulmajeedPharma (APH) — © Dr. Abdulmajeed Abdullah Almakhedhi
void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const PharmaApp());
}

class PharmaApp extends StatelessWidget {
  const PharmaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<bool>(
      valueListenable: AppSettings.isArabic,
      builder: (_, ar, __) {
        return MaterialApp(
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
          builder: (context, child) => Directionality(
            textDirection: ar ? TextDirection.rtl : TextDirection.ltr,
            child: child!,
          ),
          home: const AppBootstrap(),
        );
      },
    );
  }
}

class AppBootstrap extends StatefulWidget {
  const AppBootstrap({super.key});
  @override
  State<AppBootstrap> createState() => _AppBootstrapState();
}

class _AppBootstrapState extends State<AppBootstrap> {
  bool _ready = false;

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    await AppSettings.load();
    await DBHelper.instance.seedIfEmpty(); // قاعدة APH الحقيقية — مرة واحدة
    if (mounted) setState(() => _ready = true);
  }

  @override
  Widget build(BuildContext context) {
    if (!_ready) {
      return const Scaffold(
        body: Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Text('APH', style: TextStyle(fontSize: 42, fontWeight: FontWeight.w900, color: Color(0xFF14C8B4))),
            SizedBox(height: 8),
            Text('AbdulmajeedPharma', style: TextStyle(fontWeight: FontWeight.bold)),
            SizedBox(height: 16),
            CircularProgressIndicator(),
          ]),
        ),
      );
    }
    return const HomeScreen();
  }
}
