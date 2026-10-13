/// Settings (§61): language, theme, offline dataset, privacy, about, support.
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../app_state.dart';
import '../../core/config/app_config.dart';
import '../../core/database/local_database.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/theme/app_theme.dart';
import '../../shared/widgets/common.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  String _datasetMode = 'essential';

  @override
  void initState() {
    super.initState();
    _loadDatasetMode();
  }

  Future<void> _loadDatasetMode() async {
    final state = await LocalDatabase.instance.syncState();
    setState(() => _datasetMode = (state?['dataset_mode'] as String?) ?? 'essential');
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final app = context.watch<AppState>();

    return Scaffold(
      appBar: AppHeader(showBrand: false, title: t.tr('settings')),
      body: ListView(padding: const EdgeInsets.all(AphSpacing.md), children: [
        // ---- language -------------------------------------------------
        Card(
          child: Column(children: [
            ListTile(
              leading: const Icon(Icons.language, color: AphColors.cyan),
              title: Text(t.tr('language')),
              subtitle: Text(app.isArabic ? 'العربية (RTL)' : 'English (LTR)'),
              trailing: SegmentedButton<String>(
                segments: const [
                  ButtonSegment(value: 'en', label: Text('EN')),
                  ButtonSegment(value: 'ar', label: Text('ع')),
                ],
                selected: {app.locale.languageCode},
                onSelectionChanged: (s) => app.setLanguage(s.first),
              ),
            ),
            const Divider(height: 1),
            // ---- theme -------------------------------------------------
            ListTile(
              leading: const Icon(Icons.dark_mode_outlined, color: AphColors.navy),
              title: Text(t.tr('theme')),
              trailing: DropdownButton<ThemeMode>(
                value: app.themeMode,
                underline: const SizedBox.shrink(),
                items: [
                  DropdownMenuItem(value: ThemeMode.light, child: Text(t.tr('themeLight'))),
                  DropdownMenuItem(value: ThemeMode.dark, child: Text(t.tr('themeDark'))),
                  DropdownMenuItem(value: ThemeMode.system, child: Text(t.tr('themeSystem'))),
                ],
                onChanged: (m) => m != null ? app.setThemeMode(m) : null,
              ),
            ),
          ]),
        ),

        const SizedBox(height: AphSpacing.md),
        // ---- offline dataset (§31) ------------------------------------
        Card(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            ListTile(
              leading: const Icon(Icons.download_for_offline_outlined, color: AphColors.emerald),
              title: Text(t.tr('offlineDataset')),
              subtitle: Text(t.tr('downloads')),
            ),
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.all(AphSpacing.md),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                RadioListTile<String>(
                  value: 'essential',
                  groupValue: _datasetMode,
                  title: Text(t.tr('datasetEssential')),
                  dense: true,
                  onChanged: (v) => _setDataset(v!),
                ),
                RadioListTile<String>(
                  value: 'system',
                  groupValue: _datasetMode,
                  title: Text(t.tr('datasetSystem')),
                  dense: true,
                  onChanged: (v) => _setDataset(v!),
                ),
                RadioListTile<String>(
                  value: 'full',
                  groupValue: _datasetMode,
                  title: Text(t.tr('datasetFull')),
                  dense: true,
                  onChanged: (v) => _setDataset(v!),
                ),
                const SizedBox(height: 8),
                Row(children: [
                  Expanded(child: Text('${t.tr('lastSync')}: ${t.tr('notAvailable')}',
                      style: const TextStyle(fontSize: 12, color: AphColors.textSecondary))),
                  FilledButton(
                    onPressed: app.syncNow,
                    child: Text(app.syncing ? t.tr('syncing') : t.tr('syncNow')),
                  ),
                ]),
              ]),
            ),
          ]),
        ),

        const SizedBox(height: AphSpacing.md),
        // ---- about / support / disclaimer (§44, §62–§63) ---------------
        Card(
          child: Column(children: [
            ListTile(
              leading: const Icon(Icons.info_outline, color: AphColors.cyan),
              title: Text(t.tr('about')),
              subtitle: const Text('${AppConfig.appName} · ${AppConfig.appNameAr}\n${AppConfig.copyright}'),
              isThreeLine: true,
              onTap: () => _showAbout(t),
            ),
            const Divider(height: 1),
            ListTile(
              leading: const Icon(Icons.health_and_safety_outlined, color: AphColors.amber),
              title: Text(t.tr('disclaimer')),
              onTap: () => _showDisclaimer(t),
            ),
            const Divider(height: 1),
            ListTile(
              leading: const Icon(Icons.support_agent_outlined, color: AphColors.emerald),
              title: Text(t.tr('support')),
              onTap: () => _showSupport(t),
            ),
            const Divider(height: 1),
            ListTile(
              leading: const Icon(Icons.privacy_tip_outlined, color: AphColors.navy),
              title: Text(t.tr('privacy')),
              onTap: () => _showPrivacy(t),
            ),
          ]),
        ),
        const SizedBox(height: AphSpacing.xl),
        Center(
          child: Text('${t.tr('version')} ${AppConfig.appVersion}\n${AppConfig.copyright}',
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 11, color: AphColors.textSecondary)),
        ),
        const SizedBox(height: AphSpacing.xl),
      ]),
    );
  }

  Future<void> _setDataset(String mode) async {
    setState(() => _datasetMode = mode);
    await LocalDatabase.instance.setSyncState(datasetMode: mode);
  }

  void _showAbout(AppLocalizations t) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('AbdulmajeedPharma (APH)'),
        content: Text(
          '${AppConfig.appNameAr}\n\nProfessional Pharmaceutical Drug Encyclopedia\n\n'
          '${AppConfig.owner}\n${AppConfig.copyright}\n\n'
          '${t.tr('version')}: ${AppConfig.appVersion}',
        ),
        actions: [TextButton(onPressed: () => Navigator.pop(context), child: Text(t.tr('cancel')))],
      ),
    );
  }

  void _showDisclaimer(AppLocalizations t) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(t.tr('disclaimer')),
        content: Text(t.tr('aiDisclaimer')),
        actions: [TextButton(onPressed: () => Navigator.pop(context), child: Text(t.tr('cancel')))],
      ),
    );
  }

  void _showSupport(AppLocalizations t) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(t.tr('support')),
        content: Text('WhatsApp: ${AppConfig.supportWhatsApp}\nEmail: ${AppConfig.supportEmail}'),
        actions: [
          // External actions fire ONLY on explicit user tap (§63).
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(t.tr('contactWhatsApp')),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(t.tr('contactEmail')),
          ),
        ],
      ),
    );
  }

  void _showPrivacy(AppLocalizations t) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(t.tr('privacy')),
        content: Text(t.tr('aiDisclaimer')),
        actions: [TextButton(onPressed: () => Navigator.pop(context), child: Text(t.tr('cancel')))],
      ),
    );
  }
}
