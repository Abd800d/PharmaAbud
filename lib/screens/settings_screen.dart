import 'package:flutter/material.dart';
import '../app_settings.dart';
import '../db/db_helper.dart';
import '../services/ai_client.dart';
import '../services/online_service.dart';
import '../services/sync_service.dart';

/// إعدادات APH: الذكاء الاصطناعي الحقيقي (Gemini / OpenAI)، المزامنة مع
/// موقع التحكم، اللغة، PIN الإدارة، والتواصل مع د. عبدالمجيد.
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _gemini;
  late final TextEditingController _openai;
  late final TextEditingController _gmodel;
  late final TextEditingController _omodel;
  late final TextEditingController _url;
  bool _busy = false;
  String _status = '';
  String _stats = '';

  @override
  void initState() {
    super.initState();
    _gemini = TextEditingController(text: AppSettings.geminiKey.value);
    _openai = TextEditingController(text: AppSettings.openAiKey.value);
    _gmodel = TextEditingController(text: AppSettings.geminiModel.value);
    _omodel = TextEditingController(text: AppSettings.openAiModel.value);
    _url = TextEditingController(text: AppSettings.syncUrl.value);
    _loadStats();
  }

  Future<void> _loadStats() async {
    final g = await DBHelper.instance.countGenerics();
    final p = await DBHelper.instance.countProducts();
    if (mounted) {
      setState(() => _stats = '$g ${S.t('generics', 'دواء علمي')} • '
          '$p ${S.t('trade products', 'منتج تجاري')}');
    }
  }

  @override
  void dispose() {
    _gemini.dispose();
    _openai.dispose();
    _gmodel.dispose();
    _omodel.dispose();
    _url.dispose();
    super.dispose();
  }

  void _toast(String m) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(m), duration: const Duration(seconds: 4)));
  }

  Future<void> _saveKeys() async {
    await AppSettings.setGeminiKey(_gemini.text);
    await AppSettings.setOpenAiKey(_openai.text);
    await AppSettings.setGeminiModel(_gmodel.text);
    await AppSettings.setOpenAiModel(_omodel.text);
    await AppSettings.setSyncUrl(_url.text);
    _toast(S.t('Saved on this device ✓', 'حُفظ على هذا الجهاز ✓'));
    if (mounted) setState(() {});
  }

  Future<void> _test() async {
    await _saveKeys();
    setState(() {
      _busy = true;
      _status = S.t('Testing connection…', 'يختبر الاتصال…');
    });
    final r = await AiClient.testConnection();
    if (!mounted) return;
    setState(() {
      _busy = false;
      _status = r.text;
    });
  }

  Future<void> _sync() async {
    await _saveKeys();
    setState(() {
      _busy = true;
      _status = S.t('Downloading the published APH database…',
          'ينزّل قاعدة APH المنشورة…');
    });
    final r = await SyncService.pull();
    await _loadStats();
    if (!mounted) return;
    setState(() {
      _busy = false;
      _status = r.ok ? '✅ ${r.message}\n${r.source}' : '⚠️ ${r.message}';
    });
  }

  @override
  Widget build(BuildContext context) {
    final provider = AppSettings.activeProvider;
    return Scaffold(
      appBar: AppBar(
        title: Text(S.t('Settings', 'الإعدادات')),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(26),
          child: Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text('$_stats   |   $kCopyright',
                style: const TextStyle(fontSize: 10, color: Colors.white60)),
          ),
        ),
      ),
      body: ListView(padding: const EdgeInsets.all(14), children: [
        // ---------------- AI ----------------
        Card(child: Padding(padding: const EdgeInsets.all(14), child: Column(
          crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              const Icon(Icons.smart_toy, color: Color(0xFF14C8B4)),
              const SizedBox(width: 8),
              Text(S.t('AI Drug Assistant (real cloud AI)',
                      'المساعد الدوائي الذكي (ذكاء اصطناعي حقيقي)'),
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
            ]),
            const SizedBox(height: 6),
            Text(S.t('Active now: $provider', 'المزوّد الحالي: $provider'),
                style: TextStyle(
                    color: provider == 'offline'
                        ? Colors.orangeAccent
                        : const Color(0xFF14C8B4),
                    fontWeight: FontWeight.bold, fontSize: 12)),
            const SizedBox(height: 10),
            Text(S.t('AI provider', 'مزوّد الذكاء الاصطناعي'),
                style: const TextStyle(fontSize: 12, color: Colors.white70)),
            const SizedBox(height: 6),
            Wrap(spacing: 8, runSpacing: 8, children: [
              for (final opt in const [
                ['auto', 'Auto', 'تلقائي'],
                ['gemini', 'Google Gemini', 'Google Gemini'],
                ['openai', 'OpenAI GPT', 'OpenAI GPT'],
                ['offline', 'Offline DB', 'دون إنترنت'],
              ])
                ChoiceChip(
                  label: Text(S.ar ? opt[2] : opt[1]),
                  selected: AppSettings.aiProvider.value == opt[0],
                  onSelected: (_) async {
                    await AppSettings.setAiProvider(opt[0]);
                    if (mounted) setState(() {});
                  },
                ),
            ]),
            const SizedBox(height: 10),
            TextField(controller: _gemini, obscureText: true,
                decoration: InputDecoration(
                    labelText: 'Google AI Studio (Gemini) API key',
                    hintText: 'AIza…', border: const OutlineInputBorder())),
            const SizedBox(height: 8),
            TextField(controller: _gmodel,
                decoration: InputDecoration(
                    labelText: S.t('Gemini model', 'نموذج Gemini'),
                    border: const OutlineInputBorder())),
            const SizedBox(height: 12),
            TextField(controller: _openai, obscureText: true,
                decoration: InputDecoration(
                    labelText: 'OpenAI API key',
                    hintText: 'sk-…', border: const OutlineInputBorder())),
            const SizedBox(height: 8),
            TextField(controller: _omodel,
                decoration: InputDecoration(
                    labelText: S.t('OpenAI model', 'نموذج OpenAI'),
                    border: const OutlineInputBorder())),
            const SizedBox(height: 12),
            Wrap(spacing: 8, runSpacing: 8, children: [
              FilledButton.icon(icon: const Icon(Icons.save, size: 16),
                  label: Text(S.t('Save', 'حفظ')),
                  onPressed: _busy ? null : _saveKeys),
              OutlinedButton.icon(icon: const Icon(Icons.bolt, size: 16),
                  label: Text(S.t('Test connection', 'اختبار الاتصال')),
                  onPressed: _busy ? null : _test),
              OutlinedButton.icon(icon: const Icon(Icons.key, size: 16),
                  label: Text(S.t('Get a free Gemini key', 'احصل على مفتاح Gemini مجاني')),
                  onPressed: () => OnlineService.openUrl(
                      'https://aistudio.google.com/app/apikey')),
            ]),
            const SizedBox(height: 8),
            Text(S.t(
                '🔒 Your keys are stored on THIS device only and are never uploaded to the app '
                'database or shared. If a key was ever sent in a chat or committed to a public '
                'repository, revoke it and create a new one.',
                '🔒 مفاتيحك تُحفظ على هذا الجهاز فقط ولا تُرفع لقاعدة التطبيق ولا تُشارك. '
                'إذا أرسلت مفتاحاً في محادثة أو نشرته في مستودع عام، فألغه وأنشئ مفتاحاً جديداً.'),
                style: const TextStyle(fontSize: 11, color: Color(0xFFFDE68A), height: 1.7)),
            if (_status.isNotEmpty) ...[
              const SizedBox(height: 8),
              Container(padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(color: Colors.black26,
                      borderRadius: BorderRadius.circular(10)),
                  child: SelectableText(_status,
                      style: const TextStyle(fontSize: 12, height: 1.6))),
            ],
          ]))),

        // ---------------- Sync ----------------
        Card(child: Padding(padding: const EdgeInsets.all(14), child: Column(
          crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              const Icon(Icons.cloud_sync, color: Color(0xFF14C8B4)),
              const SizedBox(width: 8),
              Text(S.t('Sync with the admin control site',
                      'المزامنة مع موقع التحكم'),
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
            ]),
            const SizedBox(height: 6),
            Text(S.t(
                'Every drug, product, Yemen agent or announcement that Dr. Abdulmajeed publishes '
                'on the control site is downloaded here and reaches every user automatically.',
                'كل دواء أو منتج أو وكيل في اليمن أو إعلان ينشره د. عبدالمجيد من موقع التحكم '
                'يُنزَّل هنا ويصل تلقائياً إلى كل المستخدمين.'),
                style: const TextStyle(fontSize: 11, color: Colors.white70, height: 1.7)),
            const SizedBox(height: 10),
            TextField(controller: _url, keyboardType: TextInputType.url,
                decoration: InputDecoration(
                    labelText: S.t('Published database URL (JSON)',
                        'رابط قاعدة البيانات المنشورة (JSON)'),
                    border: const OutlineInputBorder())),
            const SizedBox(height: 10),
            Row(children: [
              Expanded(child: FilledButton.icon(
                  icon: const Icon(Icons.download, size: 16),
                  label: Text(S.t('Sync now', 'زامن الآن')),
                  onPressed: _busy ? null : _sync)),
              const SizedBox(width: 10),
              Expanded(child: OutlinedButton.icon(
                  icon: const Icon(Icons.restore_page, size: 16),
                  label: Text(S.t('Default URL', 'الرابط الافتراضي')),
                  onPressed: () => setState(() => _url.text = kDefaultSyncUrl))),
            ]),
            SwitchListTile(contentPadding: EdgeInsets.zero,
                title: Text(S.t('Auto-sync when internet is available',
                    'مزامنة تلقائية عند توفر الإنترنت')),
                value: AppSettings.autoSync.value,
                onChanged: (v) async {
                  await AppSettings.setAutoSync(v);
                  if (mounted) setState(() {});
                }),
            Text(_lastSyncText(),
                style: const TextStyle(fontSize: 11, color: Colors.white54)),
          ]))),

        // ---------------- App ----------------
        Card(child: Column(children: [
          SwitchListTile(secondary: const Icon(Icons.language),
              title: Text(S.t('Arabic / English', 'العربية / English')),
              subtitle: Text(S.ar ? 'العربية' : 'English'),
              value: S.ar, onChanged: (v) => AppSettings.setArabic(v)),
          ListTile(leading: const Icon(Icons.lock),
              title: Text(S.t('Change admin PIN', 'تغيير PIN الإدارة')),
              subtitle: Text(S.t('Unlocks editing of every drug, product and image',
                  'يفتح تعديل كل دواء ومنتج وصورة')),
              onTap: () async {
                final c = TextEditingController();
                final v = await showDialog<String>(context: context,
                    builder: (_) => AlertDialog(
                        title: Text(S.t('New PIN (4+ digits)',
                            'PIN جديد — 4 أرقام فأكثر')),
                        content: TextField(controller: c, obscureText: true),
                        actions: [TextButton(
                            onPressed: () => Navigator.pop(context, c.text),
                            child: const Text('OK'))]));
                if (v != null && v.trim().length >= 4) {
                  await AppSettings.setAdminPin(v.trim());
                  _toast('✅');
                }
              }),
          ListTile(leading: const Icon(Icons.chat),
              title: const Text('WhatsApp 781733795'),
              subtitle: Text(S.t('Report any problem directly to Dr. Abdulmajeed',
                  'أبلغ عن أي خلل مباشرة للدكتور عبدالمجيد')),
              onTap: () => OnlineService.openUrl(kWhatsAppUrl)),
          ListTile(leading: const Icon(Icons.email),
              title: const Text(kEmail),
              onTap: () => OnlineService.openUrl('mailto:$kEmail')),
        ])),
        Center(child: Padding(padding: const EdgeInsets.all(10),
            child: Text('$kCopyright — AbdulmajeedPharma (APH) • $kOwnerEn',
                style: const TextStyle(fontSize: 11, color: Colors.white54)))),
      ]),
    );
  }

  String _lastSyncText() {
    final t = AppSettings.lastSyncAt.value;
    if (t == 0) {
      return S.t('Never synced yet.', 'لم تتم مزامنة بعد.');
    }
    final d = DateTime.fromMillisecondsSinceEpoch(t);
    return '${S.t('Last sync', 'آخر مزامنة')}: '
        '${d.year}-${_2(d.month)}-${_2(d.day)} ${_2(d.hour)}:${_2(d.minute)}';
  }

  String _2(int n) => n.toString().padLeft(2, '0');
}
