/// APH mobile application shell: localization, theming, bottom navigation
/// (Home · Systems · Search · Scan · Favorites · More).
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:provider/provider.dart';

import 'app_state.dart';
import 'core/localization/app_localizations.dart';
import 'core/theme/app_theme.dart';
import 'features/favorites/favorites_screen.dart';
import 'features/home/home_screen.dart';
import 'features/profile/more_screen.dart';
import 'features/scan/scan_screen.dart';
import 'features/search/search_screen.dart';
import 'features/systems/systems_screens.dart';

class AphApp extends StatelessWidget {
  const AphApp({super.key});

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    return MaterialApp(
      title: 'AbdulmajeedPharma',
      debugShowCheckedModeBanner: false,
      locale: app.locale,
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      theme: buildAphTheme(brightness: Brightness.light),
      darkTheme: buildAphTheme(brightness: Brightness.dark),
      themeMode: app.themeMode,
      // RTL/LTR handled by locale resolution (§3)
      home: const AppShell(),
    );
  }
}

class AppShell extends StatelessWidget {
  const AppShell({super.key});

  static const _screens = [
    HomeScreen(),
    SystemsScreen(),
    SearchScreen(),
    ScanScreen(),
    FavoritesScreen(),
    MoreScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final app = context.watch<AppState>();
    return Scaffold(
      body: IndexedStack(index: app.currentTab, children: _screens),
      bottomNavigationBar: NavigationBar(
        selectedIndex: app.currentTab,
        onDestinationSelected: app.goToTab,
        height: 64,
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        destinations: [
          NavigationDestination(icon: const Icon(Icons.home_outlined), selectedIcon: const Icon(Icons.home), label: t.tr('home')),
          NavigationDestination(icon: const Icon(Icons.monitor_heart_outlined), selectedIcon: const Icon(Icons.monitor_heart), label: t.tr('systems')),
          NavigationDestination(icon: const Icon(Icons.search_outlined), selectedIcon: const Icon(Icons.search), label: t.tr('search')),
          NavigationDestination(icon: const Icon(Icons.qr_code_scanner_outlined), selectedIcon: const Icon(Icons.qr_code_scanner), label: t.tr('scan')),
          NavigationDestination(icon: const Icon(Icons.favorite_outline), selectedIcon: const Icon(Icons.favorite), label: t.tr('favorites')),
          NavigationDestination(icon: const Icon(Icons.menu_outlined), selectedIcon: const Icon(Icons.menu), label: t.tr('more')),
        ],
      ),
    );
  }
}
