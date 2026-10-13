/// Repositories (Clean Architecture — data layer).
/// Online: REST API. Offline: SQLite fallback for downloaded data (§30).
import '../../core/database/local_database.dart';
import '../../core/network/api_client.dart';
import '../models/models.dart';

class AphRepository {
  AphRepository({ApiClient? api, LocalDatabase? db})
      : _api = api ?? ApiClient(),
        _db = db ?? LocalDatabase.instance;

  final ApiClient _api;
  final LocalDatabase _db;

  // ------------------------------------------------------------- systems
  Future<List<BodySystemModel>> getSystems({bool offline = false}) async {
    if (!offline) {
      try {
        final data = await _api.get('/systems');
        return (data['items'] as List).map((e) => BodySystemModel.fromJson(e)).toList();
      } catch (_) {
        // fall through to local
      }
    }
    final rows = await (await _db.database).query('body_systems', orderBy: 'sort_order');
    return rows
        .map((r) => BodySystemModel.fromJson({
              'id': r['id'], 'slug': r['slug'], 'name_en': r['name_en'], 'name_ar': r['name_ar'],
            }))
        .toList();
  }

  // ------------------------------------------------------------- search
  Future<SearchResultBundle> search(String query, {bool offline = false, int limit = 25}) async {
    if (!offline) {
      try {
        final data = await _api.get('/search', query: {'q': query, 'limit': '$limit'});
        final hits = (data['items'] as List).map((e) => SearchHitModel.fromJson(e)).toList();
        return SearchResultBundle(
          hits: hits,
          total: (data['total'] as num?)?.toInt() ?? hits.length,
          suggestions: (data['suggestions'] as List?)?.cast<String>() ?? const [],
        );
      } catch (_) {
        // offline fallback
      }
    }
    final rows = await _db.searchLocal(query, limit: limit);
    final hits = rows
        .map((r) => SearchHitModel.fromJson({
              'kind': r['kind'], 'id': r['id'],
              'name_en': r['name_en'], 'name_ar': r['name_ar'] ?? '',
              'subtitle': r['subtitle'] ?? '', 'match_type': 'local',
              'score': 0,
              'verification_status': r['verification_status'] ?? 'draft',
              'is_demo': (r['is_demo'] as int? ?? 1) == 1,
            }))
        .toList();
    return SearchResultBundle(hits: hits, total: hits.length, suggestions: const []);
  }

  // ------------------------------------------------------------- drugs
  Future<DrugModel> getDrug(String id, {bool offline = false}) async {
    if (!offline) {
      try {
        final data = await _api.get('/drugs/$id');
        await _db.addRecentDrug(id);
        return DrugModel.fromJson(data);
      } catch (_) {
        // offline fallback below
      }
    }
    final rows = await (await _db.database).query('drugs', where: 'id = ?', whereArgs: [id], limit: 1);
    if (rows.isEmpty) throw Exception('Drug not found in downloaded dataset.');
    final r = rows.first;
    final sections = await (await _db.database)
        .query('drug_sections', where: 'drug_id = ?', whereArgs: [id]);
    String sec(String name) =>
        sections.firstWhere((s) => s['section'] == name, orElse: () => const {})['text_en'] as String? ?? '';
    return DrugModel.fromJson({
      'id': r['id'], 'generic_name_en': r['generic_name_en'], 'generic_name_ar': r['generic_name_ar'],
      'scientific_name': r['scientific_name'], 'drug_class': r['drug_class'],
      'pharmacological_class_name': r['pharmacological_class_name'], 'atc_code': r['atc_code'],
      'overview_en': r['overview_en'], 'overview_ar': r['overview_ar'],
      'mechanism_en': r['mechanism_en'], 'mechanism_ar': r['mechanism_ar'],
      'verification_status': r['verification_status'],
      'is_demo': (r['is_demo'] as int? ?? 1) == 1,
      'record_version': r['record_version'],
      'indications': [
        {'text_en': sec('indications'), 'text_ar': ''}
      ],
    });
  }

  Future<List<Map<String, dynamic>>> getDrugProducts(String drugId) async {
    try {
      final data = await _api.get('/drugs/$drugId/products');
      return (data['items'] as List).cast<Map<String, dynamic>>();
    } catch (_) {
      final rows = await (await _db.database)
          .query('products', where: 'drug_id = ?', whereArgs: [drugId], limit: 50);
      return rows.map((r) => {
            'id': r['id'], 'brand_name_en': r['brand_name_en'], 'brand_name_ar': r['brand_name_ar'],
            'strength': r['strength'], 'dosage_form': r['dosage_form'],
            'verification_status': r['verification_status'],
          }).toList();
    }
  }

  // ------------------------------------------------------------- products
  Future<ProductModel> getProduct(String id, {bool offline = false}) async {
    if (!offline) {
      try {
        final data = await _api.get('/products/$id');
        return ProductModel.fromJson(data);
      } catch (_) {}
    }
    final rows = await (await _db.database).query('products', where: 'id = ?', whereArgs: [id], limit: 1);
    if (rows.isEmpty) throw Exception('Product not found in downloaded dataset.');
    final r = rows.first;
    return ProductModel.fromJson({
      'id': r['id'], 'drug_id': r['drug_id'], 'brand_name_en': r['brand_name_en'],
      'brand_name_ar': r['brand_name_ar'], 'strength': r['strength'],
      'dosage_form': r['dosage_form'], 'route': r['route'],
      'manufacturer_name': r['manufacturer_name'], 'barcode': r['barcode'],
      'registration_number': r['registration_number'],
      'verification_status': r['verification_status'],
      'is_demo': (r['is_demo'] as int? ?? 1) == 1,
    });
  }

  Future<ProductModel?> findByBarcode(String barcode) async {
    try {
      final data = await _api.post('/search/barcode', body: {'barcode': barcode});
      final items = data['items'] as List? ?? const [];
      if (items.isEmpty) return null;
      return getProduct(items.first['id'] as String);
    } catch (_) {
      // local barcode lookup (§18): unknown barcodes yield null — never invented data
      final rows = await (await _db.database)
          .query('products', where: 'barcode = ?', whereArgs: [barcode], limit: 1);
      if (rows.isEmpty) return null;
      return getProduct(rows.first['id'] as String, offline: true);
    }
  }

  // ------------------------------------------------------------- AI (RAG)
  Future<Map<String, dynamic>> askAi(String question, {String language = 'en', String? conversationId}) async {
    return _api.post('/ai/ask', body: {
      'question': question,
      'language': language,
      if (conversationId != null) 'conversation_id': conversationId,
    });
  }
}

class SearchResultBundle {
  const SearchResultBundle({required this.hits, required this.total, required this.suggestions});
  final List<SearchHitModel> hits;
  final int total;
  final List<String> suggestions;
}
