import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import '../app_settings.dart';
import '../db/db_helper.dart';
import '../models/drug_models.dart';
import 'ai_service.dart';
import 'search_service.dart';

class AiReply {
  final String text;
  final bool online;
  final String provider;
  final String error;
  const AiReply(this.text,
      {this.online = false, this.provider = 'offline', this.error = ''});
}

/// Cloud requests go only to the owner's HTTPS Worker. Provider API keys are
/// never read by or transmitted from this application.
class AiClient {
  static bool get hasCloud => AppSettings.aiProxyUrl.value.trim().isNotEmpty;
  static String lastEnrichError = '';

  static String get _systemPrompt => S.ar
      ? '''أنت «مساعد APH الدوائي» — مساعد مرجعي للصيادلة والأطباء في اليمن والوطن العربي.
القواعد:
1) اعتمد أولاً على سياق قاعدة APH المرفق؛ وإذا غابت المعلومة فاذكر أنها ليست من القاعدة.
2) لا تخترع مصنعاً أو وكيلاً يمنياً؛ قل «يحتاج توثيقاً» إذا لم يرد في القاعدة.
3) أجب بلغة السائل بإيجاز منظم: الاستعمال، الجرعة المرجعية للبالغين، التداخلات والتحذيرات والحمل والبدائل.
4) للأدوية عالية الخطورة أكّد ضرورة المتابعة الطبية/المخبرية.
5) لا تشخّص مريضاً بعينه. اختم بمصدر تحقق رسمي وبأن المعلومة تعليمية وليست بديلاً عن الطبيب.'''
      : '''You are the APH medicine information assistant for pharmacists and clinicians in Yemen and the Arab world.
Use APH DATABASE context first; clearly distinguish external knowledge. Never invent a manufacturer or Yemen agent; say it needs verification when absent. Answer in the user's language with concise reference information: indication, usual adult dose, interactions, warnings, pregnancy and alternatives. Emphasize monitoring for high-risk medicines. Do not diagnose a specific patient. End with an official verification source and state this is educational, not a substitute for medical advice.''';

  static String _redact(String value) => value
      .replaceAll(RegExp(r'AIza[0-9A-Za-z_-]{10,}'), 'AIza••••')
      .replaceAll(RegExp(r'sk-[A-Za-z0-9_-]{10,}'), 'sk-••••');

  static String _clip(String value, [int length = 400]) =>
      value.length <= length ? value : '${value.substring(0, length)}…';

  static Future<String> buildContext(String question) async {
    try {
      final db = DBHelper.instance;
      final generics = await db.allGenerics();
      final products = await db.allProducts();
      final hits = fuzzySearch(question, generics, products).take(3);
      final out = StringBuffer('APH DATABASE (local):\n');
      for (final hit in hits) {
        final drug = hit.drug;
        out.writeln('- ${drug.nameEn} / ${drug.nameAr} | '
            '${systemById(drug.systemId).en} | ${drug.subgroupEn}');
        if (drug.indications.isNotEmpty) out.writeln('  Indications: ${_clip(drug.indications)}');
        if (drug.dosage.isNotEmpty) out.writeln('  Dosage reference: ${_clip(drug.dosage)}');
        if (drug.interactions.isNotEmpty) out.writeln('  Interactions: ${_clip(drug.interactions)}');
        if (drug.warnings.isNotEmpty) out.writeln('  Warnings: ${_clip(drug.warnings)}');
        final related = products.where((product) => product.genericId == drug.id).take(6);
        for (final product in related) {
          out.writeln('  Product: ${product.brandName} ${product.strength} '
              '${product.dosageForm}; manufacturer=${product.manufacturer}; '
              'country=${product.country}; Yemen agent=${product.agentYemen.isEmpty ? 'needs verification' : product.agentYemen}');
        }
      }
      return out.toString() == 'APH DATABASE (local):\n' ? '' : out.toString();
    } catch (_) {
      return '';
    }
  }

  static Future<AiReply> ask(String question) async {
    final proxy = AppSettings.aiProxyUrl.value.trim();
    if (AppSettings.activeProvider == 'offline' || proxy.isEmpty) {
      return AiReply(await AiService.answer(question), provider: 'offline');
    }
    final context = await buildContext(question);
    final prompt = context.isEmpty
        ? question
        : '$context\n\nQUESTION / السؤال:\n$question';
    // Automatic mode is Gemini-only. It must never silently trigger paid OpenAI.
    final provider = AppSettings.aiProvider.value == 'openai' ? 'openai' : 'gemini';
    final result = await _request(provider, prompt);
    if (result.ok) {
      return AiReply(result.text, online: true, provider: provider);
    }
    return AiReply(await AiService.answer(question), provider: 'offline',
        error: result.error);
  }

  static Future<AiReply> identifyImage(Uint8List bytes,
      {String note = '', String mime = 'image/jpeg'}) async {
    if (!hasCloud || AppSettings.activeProvider == 'offline') {
      return AiReply(S.t(
          'Image identification needs internet and the owner-configured secure AI server.',
          'التعرف على الصورة يحتاج الإنترنت وخادم الذكاء الاصطناعي الآمن الذي يضبطه المالك.'),
          provider: 'offline');
    }
    final prompt = S.t(
        'Identify the medicine from the image. Read visible brand, generic name, strength and dosage form. State uncertainty; do not invent manufacturer, country, or Yemen agent. Give concise reference information, important warnings, and an official source. $note',
        'تعرّف على الدواء من الصورة واقرأ الاسم التجاري والعلمي والقوة والشكل الظاهر. اذكر ما لم تستطع قراءته ولا تخترع مصنعاً أو دولة أو وكيلاً يمنياً. أعط معلومات مرجعية وتحذيرات ومصدراً رسمياً. $note');
    final provider = AppSettings.aiProvider.value == 'openai' ? 'openai' : 'gemini';
    final result = await _request(provider, prompt,
        imageBase64: base64Encode(bytes), mime: mime, maxTokens: 1200);
    return result.ok
        ? AiReply(result.text, online: true, provider: provider)
        : AiReply(result.error, provider: 'offline', error: result.error);
  }

  static Future<AiReply> testConnection() async {
    if (!hasCloud || AppSettings.activeProvider == 'offline') {
      return AiReply(S.t('AI proxy URL is not configured; local mode is active.',
          'رابط وسيط الذكاء الاصطناعي غير مضبوط؛ الوضع المحلي يعمل.'),
          provider: 'offline');
    }
    final provider = AppSettings.aiProvider.value == 'openai' ? 'openai' : 'gemini';
    final result = await _request(provider,
        S.t('Reply with the single word READY.', 'أجب بكلمة READY فقط.'),
        maxTokens: 20);
    return result.ok
        ? AiReply('Secure server ✓ ${result.text}', online: true, provider: provider)
        : AiReply('Secure server ✗ ${result.error}', error: result.error);
  }

  static Future<Map<String, String>> enrichDrug(GenericDrug drug) async {
    lastEnrichError = '';
    if (!hasCloud) {
      lastEnrichError = S.t('Secure AI server is not configured.',
          'خادم الذكاء الاصطناعي الآمن غير مضبوط.');
      return {};
    }
    final prompt = S.ar
        ? 'أعطني معلومات مرجعية دقيقة عن «${drug.nameEn}» بصيغة JSON فقط بالمفاتيح introduction, mechanism, indications, dosage, interactions, warnings, pregnancy. اترك ما لا تعرفه فارغاً ولا تخترع وكيلاً أو مصنعاً.'
        : 'Return accurate reference information for ${drug.nameEn} as JSON only with keys introduction, mechanism, indications, dosage, interactions, warnings, pregnancy. Leave unknowns blank; do not invent a manufacturer or agent.';
    final provider = AppSettings.aiProvider.value == 'openai' ? 'openai' : 'gemini';
    final result = await _request(provider, prompt, maxTokens: 1200);
    if (!result.ok) {
      lastEnrichError = result.error;
      return {};
    }
    return _jsonFromText(result.text);
  }

  static Future<_ProxyResult> _request(String provider, String prompt,
      {String? imageBase64, String? mime, int maxTokens = 1400}) async {
    final rawUrl = AppSettings.aiProxyUrl.value.trim();
    if (!AppSettings.isSafeAiProxyUrl(rawUrl)) {
      return const _ProxyResult('', false, 'Only an HTTPS proxy URL is accepted.');
    }
    final uri = Uri.tryParse(rawUrl);
    if (uri == null || uri.scheme != 'https' || uri.host.isEmpty) {
      return _ProxyResult('', false, S.t('Secure AI proxy URL is missing or invalid.',
          'رابط وسيط الذكاء الاصطناعي الآمن مفقود أو غير صالح.'));
    }
    final body = jsonEncode({
      'provider': provider,
      'model': provider == 'openai'
          ? AppSettings.openAiModel.value
          : AppSettings.geminiModel.value,
      'system': _systemPrompt,
      'prompt': prompt,
      'maxTokens': maxTokens,
      if (imageBase64 != null) 'image': imageBase64,
      if (mime != null) 'mime': mime,
    });
    try {
      final response = await http.post(uri,
          headers: const {'Content-Type': 'application/json'}, body: body)
          .timeout(Duration(seconds: imageBase64 == null ? 70 : 100));
      final text = utf8.decode(response.bodyBytes, allowMalformed: true);
      if (response.statusCode != 200) {
        String message = text;
        try {
          final decoded = jsonDecode(text);
          if (decoded is Map) message = (decoded['error'] ?? decoded['message'] ?? text).toString();
        } catch (_) {}
        return _ProxyResult('', false,
            _redact(_clip('HTTP ${response.statusCode}: $message', 260)));
      }
      final decoded = jsonDecode(text);
      if (decoded is! Map) return const _ProxyResult('', false, 'Invalid proxy response.');
      final answer = (decoded['text'] ?? decoded['output'] ?? '').toString().trim();
      if (answer.isEmpty) return const _ProxyResult('', false, 'AI provider returned an empty reply.');
      return _ProxyResult(answer, true, '');
    } catch (e) {
      final rawError = e.toString();
      final friendly = rawError.contains('SocketException') || rawError.contains('Failed host lookup')
          ? S.t('No internet or secure AI server is unreachable.',
              'لا يوجد إنترنت أو تعذّر الوصول إلى خادم الذكاء الاصطناعي الآمن.')
          : rawError.contains('TimeoutException') || rawError.contains('timed out')
              ? S.t('Secure AI server timed out.', 'انتهت مهلة خادم الذكاء الاصطناعي الآمن.')
              : rawError;
      return _ProxyResult('', false, _redact(_clip(friendly, 260)));
    }
  }

  static Map<String, String> _jsonFromText(String text) {
    var value = text.trim();
    final startFence = value.indexOf('```');
    if (startFence >= 0) {
      value = value.substring(startFence).replaceFirst(RegExp(r'^```[a-zA-Z]*\s*'), '');
      final endFence = value.indexOf('```');
      if (endFence >= 0) value = value.substring(0, endFence);
    }
    final start = value.indexOf('{');
    final end = value.lastIndexOf('}');
    if (start < 0 || end <= start) return {};
    try {
      final decoded = jsonDecode(value.substring(start, end + 1));
      if (decoded is Map) {
        return decoded.map((key, value) => MapEntry(key.toString(), value.toString()));
      }
    } catch (_) {}
    return {};
  }
}

class _ProxyResult {
  final String text;
  final bool ok;
  final String error;
  const _ProxyResult(this.text, this.ok, this.error);
}
