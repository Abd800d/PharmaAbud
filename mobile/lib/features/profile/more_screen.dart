/// "More" tab (§102): Recent, Settings, Downloads, AI Assistant, About,
/// Support, Disclaimer.
import 'package:flutter/material.dart';

import '../../core/config/app_config.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/theme/app_theme.dart';
import '../../shared/widgets/common.dart';
import '../ai/ai_assistant_screen.dart';
import '../recent/recent_screen.dart';
import '../settings/settings_screen.dart';

class MoreScreen extends StatelessWidget {
  const MoreScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppHeader(showBrand: false, title: t.tr('more')),
      body: ListView(padding: const EdgeInsets.all(AphSpacing.md), children: [
        Card(
          child: Column(children: [
            ListTile(
              leading: const Icon(Icons.history, color: AphColors.cyan),
              title: Text(t.tr('recentSearches')),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const RecentScreen())),
            ),
            const Divider(height: 1),
            ListTile(
              leading: const Icon(Icons.smart_toy_outlined, color: AphColors.emerald),
              title: Text(t.tr('aiAssistant')),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const AiAssistantScreen())),
            ),
            const Divider(height: 1),
            ListTile(
              leading: const Icon(Icons.download_for_offline_outlined, color: AphColors.navy),
              title: Text(t.tr('downloads')),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const SettingsScreen())),
            ),
            const Divider(height: 1),
            ListTile(
              leading: const Icon(Icons.settings_outlined, color: AphColors.textSecondary),
              title: Text(t.tr('settings')),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const SettingsScreen())),
            ),
          ]),
        ),
        const SizedBox(height: AphSpacing.md),
        Card(
          child: Column(children: [
            ListTile(
              leading: const Icon(Icons.info_outline, color: AphColors.cyan),
              title: Text(t.tr('about')),
              subtitle: const Text('AbdulmajeedPharma (APH)\n${AppConfig.appNameAr}'),
              isThreeLine: true,
              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const SettingsScreen())),
            ),
            const Divider(height: 1),
            ListTile(
              leading: const Icon(Icons.health_and_safety_outlined, color: AphColors.amber),
              title: Text(t.tr('disclaimer')),
              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const SettingsScreen())),
            ),
            const Divider(height: 1),
            ListTile(
              leading: const Icon(Icons.support_agent_outlined, color: AphColors.emerald),
              title: Text(t.tr('support')),
              subtitle: Text('WhatsApp: ${AppConfig.supportWhatsApp} · ${AppConfig.supportEmail}',
                  style: const TextStyle(fontSize: 11)),
              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const SettingsScreen())),
            ),
          ]),
        ),
        const SizedBox(height: AphSpacing.xl),
        Center(
          child: Text('${AppConfig.copyright}\n${t.tr('version')} ${AppConfig.appVersion}',
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 11, color: AphColors.textSecondary)),
        ),
      ]),
    );
  }
}
