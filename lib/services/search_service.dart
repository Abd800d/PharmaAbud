import '../models/drug_models.dart';

/// بحث ضبابي: يجد الدواء حتى لو كُتب الاسم بخطأ بسيط
/// (مطابقة جزئية + مسافة ليفنشتاين + بحث في الاسم التجاري والشركة)
String norm(String s) => s
    .toLowerCase()
    .replaceAll(RegExp(r'[ً-ٰٟ]'), '')
    .replaceAll(RegExp(r'[إأآ]'), 'ا')
    .replaceAll('ة', 'ه')
    .replaceAll('ى', 'ي')
    .replaceAll(RegExp(r'[^a-z0-9\u0600-\u06FF ]'), ' ')
    .replaceAll(RegExp(r'\s+'), ' ')
    .trim();

int levenshtein(String a, String b) {
  if ((a.length - b.length).abs() > 3) return 9;
  final d = List.generate(a.length + 1, (i) => List.filled(b.length + 1, 0));
  for (var i = 0; i <= a.length; i++) d[i][0] = i;
  for (var j = 0; j <= b.length; j++) d[0][j] = j;
  for (var i = 1; i <= a.length; i++) {
    for (var j = 1; j <= b.length; j++) {
      final cost = a[i - 1] == b[j - 1] ? 0 : 1;
      var best = d[i - 1][j] + 1;
      if (d[i][j - 1] + 1 < best) best = d[i][j - 1] + 1;
      if (d[i - 1][j - 1] + cost < best) best = d[i - 1][j - 1] + cost;
      d[i][j] = best;
    }
  }
  return d[a.length][b.length];
}

double scoreText(String query, String text) {
  final q = norm(query), t = norm(text);
  if (q.isEmpty || t.isEmpty) return 0;
  if (t.contains(q)) return 100 - (t.length / 10).clamp(0, 20);
  var total = 0.0;
  final tw = t.split(' ');
  for (final w in q.split(' ')) {
    var best = 0.0;
    for (final token in tw) {
      if (token.startsWith(w)) {
        best = best > 70 ? best : 70;
      } else {
        final dd = levenshtein(w, token);
        if (dd == 1 && best < 55) best = 55;
        if (dd == 2 && w.length > 4 && best < 38) best = 38;
      }
    }
    total += best;
  }
  return total / q.split(' ').length;
}

class SearchHit {
  final GenericDrug drug;
  final double score;
  final String matchedBrand;
  const SearchHit(this.drug, this.score, [this.matchedBrand = '']);
}

const _alias = {
  'بنادول': 'panadol', 'بندول': 'panadol', 'بروفين': 'brufen',
  'فولتارين': 'voltaren', 'كتافلام': 'cataflam', 'اوجمنتين': 'augmentin',
  'اوغمنتين': 'augmentin', 'فلاجيل': 'flagyl', 'زيرتك': 'zyrtec',
  'لازيكس': 'lasix', 'كونكور': 'concor', 'نورفاسك': 'norvasc',
  'فياجرا': 'viagra', 'ترامال': 'tramal', 'ليريكا': 'lyrica',
  'نيكسيوم': 'nexium', 'بلافيكس': 'plavix', 'زاريلتو': 'xarelto',
  'اماريل': 'amaryl', 'جلوكوفاج': 'glucophage',
};

List<SearchHit> fuzzySearch(String query, List<GenericDrug> generics,
    List<TradeProduct> products) {
  if (norm(query).isEmpty) return [];
  for (final e in _alias.entries) {
    if (norm(query).contains(e.key)) { query = e.value; break; }
  }
  final byGeneric = <int, String>{};
  for (final p in products) {
    final s = [scoreText(query, p.brandName), scoreText(query, p.manufacturer)]
        .reduce((a, b) => a > b ? a : b);
    if (s >= 35) {
      final prev = byGeneric[p.genericId];
      if (prev == null || s > scoreText(query, prev)) {
        byGeneric[p.genericId] = p.brandName;
      }
    }
  }
  final hits = <SearchHit>[];
  for (final g in generics) {
    var s = scoreText(query, g.nameEn);
    final sAr = scoreText(query, g.nameAr);
    if (sAr > s) s = sAr;
    final sAtc = scoreText(query, g.atc);
    if (sAtc > s) s = sAtc;
    var brand = '';
    if (byGeneric.containsKey(g.id)) {
      final bs = scoreText(query, byGeneric[g.id]!);
      if (bs > s) s = bs;
      brand = byGeneric[g.id]!;
    }
    if (s >= 35) hits.add(SearchHit(g, s, brand));
  }
  hits.sort((a, b) => b.score.compareTo(a.score));
  return hits.take(40).toList();
}
