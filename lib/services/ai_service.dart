import '../db/db_helper.dart';
import '../models/drug_models.dart';
import 'search_service.dart';

/// مساعد دوائي ذكي: يجيب من قاعدة APH المحلية (بحث ضبابي + فهم قصد السؤال)
/// ويشير لمصادر FDA/DailyMed الرسمية للتحقق. يعمل دون إنترنت.
class AiService {
  static Future<String> answer(String question) async {
    final db = DBHelper.instance;
    final generics = await db.allGenerics();
    final products = await db.allProducts();
    final q = norm(question);
    final ar = RegExp(r'[\u0600-\u06FF]').hasMatch(question);

    // أسئلة تصنيفية: "أدوية الضغط"
    if (q.contains('الضغط') || q.contains('hypertension') || q.contains('pressure')) {
      final list = generics.where((g) => g.systemId == 'cardiovascular').take(12);
      return '${ar ? 'أدوية القلب والضغط في قاعدة APH' : 'Cardiovascular drugs in APH'}:\n'
          '${list.map((g) => '• ${g.nameEn} (${g.nameAr})').join('\n')}\n'
          '${ar ? 'افتح أي دواء لعرض جرعته وتحذيراته ومنتجاته التجارية ووكلائه في اليمن.' : 'Open any drug for dose, warnings and Yemen agents.'}';
    }

    final hits = fuzzySearch(question, generics, products);
    if (hits.isEmpty) {
      return ar
          ? 'لم أجد دواءً مطابقاً في القاعدة المحلية. جرّب الاسم العلمي بالإنجليزية، أو استخدم بحث Google / DailyMed / openFDA من صفحة البحث للوصول لمصدر عالمي موثوق.'
          : 'No match in the local database. Try the English generic name, or use Google / DailyMed / openFDA from the search page.';
    }
    final d = hits.first.drug;
    final prods = products.where((p) => p.genericId == d.id).toList();
    final wantsDose = q.contains('جرع') || q.contains('dose') || q.contains('dosage');
    final wantsInter = q.contains('تداخل') || q.contains('interaction');
    final wantsPreg = q.contains('حمل') || q.contains('pregnan');
    final wantsWarn = q.contains('تحذير') || q.contains('warning') || q.contains('اعراض') || q.contains('side');
    final wantsAlt = q.contains('بديل') || q.contains('بدائل') || q.contains('alternative');

    final b = StringBuffer('💊 ${d.nameEn} — ${d.nameAr}\n');
    if (wantsDose) {
      b.writeln('${ar ? 'الجرعة المعتادة' : 'Usual dose'}: ${d.dosage.isEmpty ? '—' : d.dosage}');
    } else if (wantsInter) {
      b.writeln('${ar ? 'التداخلات' : 'Interactions'}: ${d.interactions.isEmpty ? '—' : d.interactions}');
    } else if (wantsPreg) {
      b.writeln('${ar ? 'الحمل والرضاعة' : 'Pregnancy'}: ${d.pregnancy.isEmpty ? '—' : d.pregnancy}');
    } else if (wantsWarn) {
      b.writeln('${ar ? 'تحذيرات' : 'Warnings'}: ${d.warnings.isEmpty ? '—' : d.warnings}');
    } else {
      b.writeln('${ar ? 'الاستخدامات' : 'Indications'}: ${d.indications.isEmpty ? '—' : d.indications}');
      b.writeln('${ar ? 'الجرعة' : 'Dose'}: ${d.dosage.isEmpty ? '—' : d.dosage}');
    }
    if (prods.isNotEmpty) {
      b.writeln(ar ? 'المنتجات التجارية (اليمن/العرب):' : 'Trade products:');
      for (final p in prods.take(6)) {
        b.writeln('• ${p.brandName} ${p.strength} ${p.dosageForm} — ${p.manufacturer}, ${p.country} — وكيل اليمن: ${p.agentYemen.isEmpty ? '—' : p.agentYemen}');
      }
    }
    if (wantsAlt) {
      final alts = generics
          .where((g) => g.id != d.id && g.systemId == d.systemId &&
              g.subgroupEn == d.subgroupEn)
          .take(6);
      b.writeln('${ar ? 'بدائل في نفس المجموعة' : 'Alternatives (same group)'}: '
          '${alts.isEmpty ? '—' : alts.map((g) => g.nameEn).join('، ')}');
    }
    b.writeln(ar
        ? '\n📚 للتحقق الرسمي: DailyMed و openFDA من صفحة الدواء. معلومات تعليمية ولا تغني عن الطبيب أو الصيدلي.'
        : '\n📚 Verify officially via DailyMed / openFDA on the drug page. Educational only.');
    return b.toString();
  }
}
