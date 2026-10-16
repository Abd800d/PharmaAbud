import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import '../app_settings.dart';
import '../db/db_helper.dart';
import '../models/drug_models.dart';
import 'ai_service.dart';
import 'search_service.dart';

/// نتيجة سؤال للمساعد الذكي
class AiReply {
  final String text;
  final bool online; // هل أجاب نموذج سحابي حقيقي؟
  final String provider; // gemini / openai / offline
  final String error;
  const AiReply(this.text,
      {this.online = false, this.provider = 'offline', this.error = ''});
}

/// المساعد الدوائي الذكي الحقيقي في APH:
///  • Gemini (Google AI Studio) أو OpenAI عند توفر مفتاح وإنترنت
///  • تغذية راجعة من قاعدة APH المحلية (RAG بسيط) قبل إرسال السؤال
///  • تحليل صور علب الأدوية للتعرف على الدواء (Gemini vision / GPT-4o vision)
///  • وإن لم يتوفر إنترنت أو مفتاح: يجيب محلياً من القاعدة (وضع Offline)
class AiClient {
  static const String _geminiHost =
      'https://generativelanguage.googleapis.com/v1beta/models';
  static const String _openAiUrl = 'https://api.openai.com/v1/chat/completions';

  static bool get hasCloudKey =>
      AppSettings.geminiKey.value.isNotEmpty ||
      AppSettings.openAiKey.value.isNotEmpty;

  /// تعليمات النظام: صيدلي سريري مرجعي لليمن والوطن العربي
  static String get _systemPrompt => S.ar
      ? '''أنت «مساعد APH الدوائي» — صيدلي سريري مرجعي تابع لتطبيق AbdulmajeedPharma (APH)
للدكتور عبدالمجيد عبدالله الماخذي، ويخدم الصيادلة والأطباء في اليمن والوطن العربي.

القواعد:
1) اعتمد أولاً على «قاعدة APH» المرفقة في السؤال (أسماء علمية، منتجات تجارية، شركات، وكلاء اليمن).
2) إن لم توجد المعلومة في قاعدة APH استخدم معرفتك الدوائية، واذكر بوضوح أنها ليست من قاعدة APH.
3) لا تخترع أبداً اسم وكيل أو شركة في اليمن — اكتب «يحتاج توثيق من الإدارة» إذا لم يكن موجوداً.
4) أجب بلغة السائل (عربية أو إنجليزية)، بإجابة مرتبة ومختصرة: الاستخدام، الجرعة المعتادة للبالغين،
   أهم التداخلات، التحذيرات، الحمل/الرضاعة، البدائل العلاجية أو المنتجات التجارية المكافئة.
5) للأدوية عالية الخطورة (Warfarin، Insulin، Methotrexate، Digoxin، Lithium، الأفيونات، أدوية الأورام)
   أكّد على ضرورة المتابعة المخبرية وأن القرار للطبيب المعالج.
6) اختم دائماً بمصدر تحقق رسمي (DailyMed / openFDA / WHO / BNF / النشرة المحلية) وجملة:
   «معلومات تعليمية ولا تغني عن استشارة الطبيب أو الصيدلي».
7) لا تشخّص حالة مرضية بعينها ولا تصف علاجاً لمريض محدد؛ قدم معلومة دوائية مرجعية فقط.'''
      : '''You are the "APH Drug Assistant" — a reference clinical pharmacist inside the
AbdulmajeedPharma (APH) application owned by Dr. Abdulmajeed Abdullah Almakhedhi,
serving pharmacists and physicians in Yemen and the Arab world.

Rules:
1) Rely FIRST on the "APH DATABASE" context supplied with the question (generics, trade
   products, strengths, dosage forms, manufacturers, countries, Yemen agents).
2) If the answer is not in the APH context, use your pharmacology knowledge and state clearly
   that it is not from the APH database.
3) NEVER invent a Yemeni agent/distributor or manufacturer — write "needs verification by APH admin".
4) Answer in the language of the question (Arabic or English), structured and concise:
   indication, usual adult dose, key interactions, warnings, pregnancy/lactation,
   therapeutic alternatives or equivalent trade products.
5) For high-risk drugs (warfarin, insulin, methotrexate, digoxin, lithium, opioids, oncology)
   stress laboratory monitoring and that the decision belongs to the treating physician.
6) Always end with an official verification source (DailyMed / openFDA / WHO / BNF / local label)
   and the line: "Educational information — not a substitute for medical advice."
7) Do not diagnose a specific patient; provide reference drug information only.'';

  /// يبني سياقاً من قاعدة APH المحلية (أفضل 3 نتائج مطابقة + منتجاتها)
  static Future<String> buildContext(String question) async {
    try {
      final db = DBHelper.instance;
      final generics = await db.allGenerics();
      final products = await db.allProducts();
      final hits = fuzzySearch(question, generics, products).take(3).toList();
      if (hits.isEmpty) return '';
      final b = StringBuffer('APH DATABASE (local, curated):\n');
      for (final h in hits) {
        final d = h.drug;
        final sys = systemById(d.systemId);
        b.writeln('- ${d.nameEn} / ${d.nameAr} | system: ${sys.en} | group: ${d.subgroupEn} | ATC: ${d.atc}');
        if (d.indications.isNotEmpty) b.writeln('  indications: ${_clip(d.indications)}');
        if (d.dosage.isNotEmpty) b.writeln('  dose: ${_clip(d.dosage)}');
        if (d.interactions.isNotEmpty) b.writeln('  interactions: ${_clip(d.interactions)}');
        if (d.warnings.isNotEmpty) b.writeln('  warnings: ${_clip(d.warnings)}');
        if (d.pregnancy.isNotEmpty) b.writeln('  pregnancy: ${_clip(d.pregnancy)}');
        final prods = products.where((p) => p.genericId == d.id).take(8).toList();
        if (prods.isNotEmpty) {
          b.writeln('  trade products:');
          for (final p in prods) {
            b.writeln('   * ${p.brandName} ${p.strength} ${p.dosageForm} — '
                '${p.manufacturer} (${p.country}) — Yemen agent: '
                '${p.agentYemen.isEmpty ? '—' : p.agentYemen}'
                '${p.verified ? ' [verified]' : ' [unverified]'}');
          }
        }
      }
      return b.toString();
    } catch (_) {
      return '';
    }
  }

  static String _clip(String s, [int n = 400]) =>
      s.length <= n ? s : '${s.substring(0, n)}…';

  /// السؤال الرئيسي: سحابي إن توفر، وإلا محلي من القاعدة
  static Future<AiReply> ask(String question) async {
    final provider = AppSettings.activeProvider;
    if (provider == 'offline' || !hasCloudKey) {
      return AiReply(await AiService.answer(question), provider: 'offline');
    }
    final context = await buildContext(question);
    final prompt = context.isEmpty
        ? question
        : '$context\n\nQUESTION / السؤال:\n$question';
    if (provider == 'openai') {
      final r = await _askOpenAi(prompt);
      if (r.ok) return AiReply(r.text, online: true, provider: 'openai');
      // فشل OpenAI → جرّب Gemini إن وُجد مفتاحه
      if (AppSettings.geminiKey.value.isNotEmpty) {
        final g = await _askGemini(prompt);
        if (g.ok) return AiReply(g.text, online: true, provider: 'gemini');
      }
      return AiReply(await AiService.answer(question),
          provider: 'offline', error: r.error);
    }
    final g = await _askGemini(prompt);
    if (g.ok) return AiReply(g.text, online: true, provider: 'gemini');
    if (AppSettings.openAiKey.value.isNotEmpty) {
      final o = await _askOpenAi(prompt);
      if (o.ok) return AiReply(o.text, online: true, provider: 'openai');
    }
    return AiReply(await AiService.answer(question), provider: 'offline', error: g.error);
  }

  /// التعرف على دواء من صورته (علبة/شريط/أمبولة) — Gemini vision أو GPT-4o vision
  static Future<AiReply> identifyImage(Uint8List bytes,
      {String note = '', String mime = 'image/jpeg'}) async {
    final provider = AppSettings.activeProvider;
    if (provider == 'offline' || !hasCloudKey) {
      return AiReply(S.t(
          'Image identification needs internet and an AI key (Settings → AI Assistant). '
          'You can still search this pack with Google Lens from the search page.',
          'التعرف على الدواء من الصورة يحتاج إنترنت ومفتاح ذكاء اصطناعي (الإعدادات ← المساعد الذكي). '
          'يمكنك البحث عن العلبة في Google Lens من صفحة البحث.'), provider: 'offline');
    }
    final instruction = S.t(
        'Identify this medicine from the photo. Read every visible text on the pack: brand name, '
        'generic (INN) name, strength, dosage form, manufacturer and country. Then answer in this order:\n'
        '1) Brand name  2) Generic name  3) Strength & dosage form  4) Manufacturer & country  '
        '5) Main indication  6) Usual adult dose  7) Two important warnings  8) Therapeutic alternatives.\n'
        'If the image is not a medicine, say so. If text is unreadable, say what you can read only. '
        'End with: verify officially via DailyMed / openFDA. $note',
        'تعرّف على هذا الدواء من الصورة. اقرأ كل نص ظاهر على العلبة: الاسم التجاري، الاسم العلمي (INN)، '
        'القوة، الشكل الصيدلاني، الشركة المصنعة والدولة. ثم أجب بالترتيب:\n'
        '1) الاسم التجاري  2) الاسم العلمي  3) القوة والشكل الصيدلاني  4) الشركة والدولة  '
        '5) أهم دواعي الاستعمال  6) الجرعة المعتادة للبالغين  7) تحذيران مهمان  8) البدائل العلاجية.\n'
        'إن لم تكن الصورة دواءً فقل ذلك. وإن كان النص غير مقروء اذكر ما استطعت قراءته فقط. '
        'واختم بـ: تحقق رسمياً عبر DailyMed / openFDA. $note');

    if (provider == 'openai' || AppSettings.geminiKey.value.isEmpty) {
      final r = await _visionOpenAi(instruction, bytes, mime);
      if (r.ok) return AiReply(r.text, online: true, provider: 'openai');
      final g = await _visionGemini(instruction, bytes, mime);
      if (g.ok) return AiReply(g.text, online: true, provider: 'gemini');
      return AiReply(r.error.isEmpty ? g.error : r.error, provider: 'offline', error: r.error);
    }
    final g = await _visionGemini(instruction, bytes, mime);
    if (g.ok) return AiReply(g.text, online: true, provider: 'gemini');
    final o = await _visionOpenAi(instruction, bytes, mime);
    if (o.ok) return AiReply(o.text, online: true, provider: 'openai');
    return AiReply(g.error.isEmpty ? o.error : g.error,
        provider: 'offline', error: g.error);
  }

  /// اختبار الاتصال من شاشة الإعدادات
  static Future<AiReply> testConnection() async {
    final provider = AppSettings.activeProvider;
    if (provider == 'offline') {
      return const AiReply('offline mode', provider: 'offline');
    }
    final q = S.t('Reply with the single word: READY', 'أجب بكلمة واحدة فقط: READY');
    if (provider == 'openai' || AppSettings.geminiKey.value.isEmpty) {
      final r = await _askOpenAi(q, maxTokens: 20);
      if (r.ok) return AiReply('OpenAI ✓ ${r.text}', online: true, provider: 'openai');
      return AiReply('OpenAI ✗ ${r.error}', error: r.error);
    }
    final g = await _askGemini(q, maxTokens: 20);
    if (g.ok) return AiReply('Gemini ✓ ${g.text}', online: true, provider: 'gemini');
    return AiReply('Gemini ✗ ${g.error}', error: g.error);
  }

  // ---------------- Gemini ----------------
  static Future<_Res> _askGemini(String prompt, {int maxTokens = 1400}) async {
    final key = AppSettings.geminiKey.value.trim();
    if (key.isEmpty) return const _Res('', false, 'لا يوجد مفتاح Gemini');
    final model = AppSettings.geminiModel.value;
    final uri = Uri.parse('$_geminiHost/$model:generateContent?key=$key');
    final body = jsonEncode({
      'systemInstruction': {
        'parts': [ {'text': _systemPrompt} ]
      },
      'contents': [
        { 'role': 'user', 'parts': [ {'text': prompt} ] }
      ],
      'generationConfig': {
        'temperature': 0.2,
        'maxOutputTokens': maxTokens,
      },
    });
    return _post(uri, body, {'Content-Type': 'application/json'}, _parseGemini);
  }

  static Future<_Res> _visionGemini(String prompt, Uint8List bytes, String mime) async {
    final key = AppSettings.geminiKey.value.trim();
    if (key.isEmpty) return const _Res('', false, 'لا يوجد مفتاح Gemini');
    final model = AppSettings.geminiModel.value;
    final uri = Uri.parse('$_geminiHost/$model:generateContent?key=$key');
    final body = jsonEncode({
      'systemInstruction': {
        'parts': [ {'text': _systemPrompt} ]
      },
      'contents': [
        {
          'role': 'user',
          'parts': [
            {'inline_data': {'mime_type': mime, 'data': base64Encode(bytes)}},
            {'text': prompt},
          ]
        }
      ],
      'generationConfig': {'temperature': 0.1, 'maxOutputTokens': 1200},
    });
    return _post(uri, body, {'Content-Type': 'application/json'}, _parseGemini,
        timeoutSec: 75);
  }

  static String _parseGemini(Map<String, dynamic> j) {
    final cands = j['candidates'] as List?;
    if (cands == null || cands.isEmpty) return '';
    final parts = ((cands.first as Map)['content'] as Map?)?['parts'] as List?;
    if (parts == null) return '';
    final b = StringBuffer();
    for (final p in parts) {
      final t = (p as Map)['text'];
      if (t != null) b.write(t.toString());
    }
    return b.toString().trim();
  }

  // ---------------- OpenAI ----------------
  static Future<_Res> _askOpenAi(String prompt, {int maxTokens = 1400}) async {
    final key = AppSettings.openAiKey.value.trim();
    if (key.isEmpty) return const _Res('', false, 'لا يوجد مفتاح OpenAI');
    final body = jsonEncode({
      'model': AppSettings.openAiModel.value,
      'temperature': 0.2,
      'max_tokens': maxTokens,
      'messages': [
        {'role': 'system', 'content': _systemPrompt},
        {'role': 'user', 'content': prompt},
      ],
    });
    return _post(Uri.parse(_openAiUrl), body, _openAiHeaders(key), _parseOpenAi);
  }

  static Future<_Res> _visionOpenAi(
      String prompt, Uint8List bytes, String mime) async {
    final key = AppSettings.openAiKey.value.trim();
    if (key.isEmpty) return const _Res('', false, 'لا يوجد مفتاح OpenAI');
    final body = jsonEncode({
      'model': AppSettings.openAiModel.value,
      'temperature': 0.1,
      'max_tokens': 1100,
      'messages': [
        {'role': 'system', 'content': _systemPrompt},
        {
          'role': 'user',
          'content': [
            {'type': 'text', 'text': prompt},
            {
              'type': 'image_url',
              'image_url': {'url': 'data:$mime;base64,${base64Encode(bytes)}'}
            },
          ]
        },
      ],
    });
    return _post(Uri.parse(_openAiUrl), body, _openAiHeaders(key), _parseOpenAi,
        timeoutSec: 75);
  }

  static Map<String, String> _openAiHeaders(String key) => {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $key',
      };

  static String _parseOpenAi(Map<String, dynamic> j) =>
      (((j['choices'] as List?)?.first as Map?)?['message'] as Map?)?['content']
              ?.toString()
              .trim() ??
          '';

  // ---------------- shared ----------------
  static Future<_Res> _post(Uri uri, String body, Map<String, String> headers,
      String Function(Map<String, dynamic>) parse,
      {int timeoutSec = 60}) async {
    try {
      final res = await http
          .post(uri, headers: headers, body: body)
          .timeout(Duration(seconds: timeoutSec));
      if (res.statusCode != 200) {
        return _Res('', false, 'HTTP ${res.statusCode}: ${_clip(res.body, 220)}');
      }
      final j = jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
      final text = parse(j);
      if (text.isEmpty) {
        return _Res('', false, _clip(res.body, 220));
      }
      return _Res(text, true, '');
    } catch (e) {
      return _Res('', false, e.toString());
    }
  }

  /// يجلب معلومات دواء ناقصة من الإنترنت (Gemini) لتعبئة الحقول في وضع الإدارة
  static Future<Map<String, String>> enrichDrug(GenericDrug d) async {
    if (!hasCloudKey) return {};
    final q = S.ar
        ? 'أعطني معلومات دوائية مرجعية دقيقة عن المادة الفعالة «${d.nameEn}» بصيغة JSON فقط '
            'بدون أي شرح، بالمفاتيح التالية: introduction, mechanism, indications, dosage, '
            'interactions, warnings, pregnancy — وكل قيمة نص عربي مختصر ومهني.'
        : 'Give accurate reference drug information for the generic «${d.nameEn}» as JSON ONLY, '
            'no prose, with keys: introduction, mechanism, indications, dosage, interactions, '
            'warnings, pregnancy — each value a short professional English text.';
    final r = AppSettings.geminiKey.value.isNotEmpty
        ? await _askGemini(q, maxTokens: 1200)
        : await _askOpenAi(q, maxTokens: 1200);
    if (!r.ok) return {};
    return _jsonFromText(r.text);
  }

  /// يستخرج JSON من رد النموذج حتى لو كان محاطاً بعلامات ```json
  static Map<String, String> _jsonFromText(String text) {
    var t = text.trim();
    final fence = t.indexOf('```');
    if (fence >= 0) {
      t = t.substring(fence);
      t = t.replaceFirst(RegExp(r'^```[a-zA-Z]*\s*'), '');
      final end = t.indexOf('```');
      if (end > 0) t = t.substring(0, end);
    }
    final s = t.indexOf('{');
    final e = t.lastIndexOf('}');
    if (s < 0 || e <= s) return {};
    try {
      final j = jsonDecode(t.substring(s, e + 1));
      if (j is Map) {
        return j.map((k, v) => MapEntry(k.toString(), v.toString()));
      }
    } catch (_) {}
    return {};
  }
}

class _Res {
  final String text;
  final bool ok;
  final String error;
  const _Res(this.text, this.ok, this.error);
}
