/// AbdulmajeedPharma (APH) — موسوعة عبدالمجيد للأدوية
/// Professional Pharmaceutical Drug Encyclopedia
/// © Dr. Abdulmajeed Abdullah Almakhedhi
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'app.dart';
import 'app_state.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  final appState = AppState();
  appState.loadSettings();
  runApp(
    ChangeNotifierProvider<AppState>(
      create: (_) => appState,
      child: const AphApp(),
    ),
  );
}
