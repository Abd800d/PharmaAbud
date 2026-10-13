/// Offline-first SQLite layer (§30, §66).
///
/// Stores downloaded drugs/products, search indexes (FTS5 when available,
/// LIKE fallback), favorites, recent searches, recent drugs, sync metadata
/// and the local sync queue. Fully usable with zero connectivity.
import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';

class LocalDatabase {
  LocalDatabase._();
  static final LocalDatabase instance = LocalDatabase._();

  static const _dbName = 'aph_offline.db';
  static const _dbVersion = 1;

  Database? _db;

  Future<Database> get database async {
    if (_db != null) return _db!;
    final dir = await getDatabasesPath();
    _db = await openDatabase(
      p.join(dir, _dbName),
      version: _dbVersion,
      onCreate: _createSchema,
      onConfigure: (db) => db.execute('PRAGMA foreign_keys = ON'),
    );
    return _db!;
  }

  Future<void> _createSchema(Database db, int version) async {
    // ---- downloaded content -------------------------------------------------
    await db.execute('''
      CREATE TABLE drugs (
        id TEXT PRIMARY KEY,
        generic_name_en TEXT NOT NULL,
        generic_name_ar TEXT NOT NULL DEFAULT '',
        scientific_name TEXT DEFAULT '',
        drug_class TEXT DEFAULT '',
        pharmacological_class_name TEXT DEFAULT '',
        atc_code TEXT DEFAULT '',
        overview_en TEXT DEFAULT '',
        overview_ar TEXT DEFAULT '',
        mechanism_en TEXT DEFAULT '',
        mechanism_ar TEXT DEFAULT '',
        verification_status TEXT DEFAULT 'draft',
        is_demo INTEGER DEFAULT 1,
        record_version INTEGER DEFAULT 1,
        updated_at TEXT DEFAULT '',
        search_text TEXT DEFAULT '',
        search_text_ar TEXT DEFAULT ''
      )
    ''');
    await db.execute('''
      CREATE TABLE products (
        id TEXT PRIMARY KEY,
        drug_id TEXT,
        brand_name_en TEXT NOT NULL,
        brand_name_ar TEXT DEFAULT '',
        strength TEXT DEFAULT '',
        dosage_form TEXT DEFAULT '',
        route TEXT DEFAULT '',
        manufacturer_name TEXT DEFAULT '',
        barcode TEXT DEFAULT '',
        registration_number TEXT DEFAULT '',
        verification_status TEXT DEFAULT 'draft',
        is_demo INTEGER DEFAULT 1,
        record_version INTEGER DEFAULT 1,
        updated_at TEXT DEFAULT '',
        search_text TEXT DEFAULT ''
      )
    ''');
    await db.execute('CREATE TABLE body_systems (id TEXT PRIMARY KEY, slug TEXT, name_en TEXT, name_ar TEXT, sort_order INTEGER DEFAULT 0)');
    await db.execute('''
      CREATE TABLE drug_sections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        drug_id TEXT NOT NULL,
        section TEXT NOT NULL,
        text_en TEXT DEFAULT '',
        text_ar TEXT DEFAULT '',
        UNIQUE(drug_id, section)
      )
    ''');

    // ---- local-only tables ---------------------------------------------------
    await db.execute('''
      CREATE TABLE favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        folder TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now')),
        UNIQUE(entity_type, entity_id)
      )
    ''');
    await db.execute('''
      CREATE TABLE recent_searches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query TEXT NOT NULL,
        searched_at TEXT DEFAULT (datetime('now'))
      )
    ''');
    await db.execute('''
      CREATE TABLE recent_drugs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        drug_id TEXT NOT NULL UNIQUE,
        viewed_at TEXT DEFAULT (datetime('now'))
      )
    ''');
    await db.execute('''
      CREATE TABLE sync_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_id TEXT DEFAULT '',
        operation TEXT NOT NULL,
        payload TEXT DEFAULT '{}',
        created_at TEXT DEFAULT (datetime('now')),
        retry_count INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending',
        last_error TEXT DEFAULT '',
        server_version INTEGER DEFAULT 0,
        local_version INTEGER DEFAULT 0
      )
    ''');
    await db.execute('''
      CREATE TABLE sync_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        last_synced_at TEXT,
        server_version INTEGER DEFAULT 0,
        dataset_mode TEXT DEFAULT 'essential',
        downloaded_systems TEXT DEFAULT '[]',
        status TEXT DEFAULT 'idle',
        last_error TEXT DEFAULT ''
      )
    ''');
    await db.execute('INSERT INTO sync_state (id) VALUES (1)');

    // ---- indexes (§66) -------------------------------------------------------
    for (final sql in [
      'CREATE INDEX idx_drugs_name_en ON drugs (generic_name_en)',
      'CREATE INDEX idx_drugs_name_ar ON drugs (generic_name_ar)',
      'CREATE INDEX idx_drugs_updated ON drugs (updated_at)',
      'CREATE INDEX idx_products_brand ON products (brand_name_en)',
      'CREATE INDEX idx_products_brand_ar ON products (brand_name_ar)',
      'CREATE INDEX idx_products_barcode ON products (barcode)',
      'CREATE INDEX idx_products_drug ON products (drug_id)',
      'CREATE INDEX idx_sections_drug ON drug_sections (drug_id)',
    ]) {
      await db.execute(sql);
    }

    // FTS5 virtual table when the SQLite build supports it; the LIKE-based
    // local search works regardless (§66).
    try {
      await db.execute('''
        CREATE VIRTUAL TABLE search_fts USING fts5(
          entity_type, entity_id, name_en, name_ar, extra,
          tokenize = 'unicode61 remove_diacritics 2'
        )
      ''');
    } catch (_) {
      // FTS5 unavailable — LIKE fallback is sufficient for downloaded sets.
    }
  }

  // ------------------------------------------------------------- search
  Future<List<Map<String, dynamic>>> searchLocal(String query, {int limit = 30}) async {
    final db = await database;
    final like = '%$query%';
    final drugs = await db.rawQuery(
      '''SELECT id, generic_name_en AS name_en, generic_name_ar AS name_ar,
                pharmacological_class_name AS subtitle, 'drug' AS kind,
                verification_status, is_demo
         FROM drugs
         WHERE generic_name_en LIKE ? OR generic_name_ar LIKE ?
            OR search_text LIKE ? OR search_text_ar LIKE ?
         ORDER BY generic_name_en LIMIT ?''',
      [like, like, like, like, limit],
    );
    final products = await db.rawQuery(
      '''SELECT id, brand_name_en AS name_en, brand_name_ar AS name_ar,
                strength || ' ' || dosage_form AS subtitle, 'product' AS kind,
                verification_status, is_demo
         FROM products
         WHERE brand_name_en LIKE ? OR brand_name_ar LIKE ?
            OR barcode LIKE ? OR search_text LIKE ?
         ORDER BY brand_name_en LIMIT ?''',
      [like, like, like, like, limit],
    );
    return [...drugs, ...products];
  }

  // ------------------------------------------------------------- favorites
  Future<void> addFavorite(String entityType, String entityId, {String folder = ''}) async {
    final db = await database;
    await db.insert(
      'favorites',
      {'entity_type': entityType, 'entity_id': entityId, 'folder': folder},
      conflictAlgorithm: ConflictAlgorithm.ignore,
    );
  }

  Future<void> removeFavorite(String entityType, String entityId) async {
    final db = await database;
    await db.delete('favorites', where: 'entity_type = ? AND entity_id = ?', whereArgs: [entityType, entityId]);
  }

  Future<List<Map<String, dynamic>>> listFavorites() async {
    final db = await database;
    return db.rawQuery('''
      SELECT f.entity_type, f.entity_id, f.folder,
             COALESCE(d.generic_name_en, p.brand_name_en) AS name_en,
             COALESCE(d.generic_name_ar, p.brand_name_ar) AS name_ar
      FROM favorites f
      LEFT JOIN drugs d ON f.entity_type = 'drug' AND d.id = f.entity_id
      LEFT JOIN products p ON f.entity_type = 'product' AND p.id = f.entity_id
      ORDER BY f.created_at DESC
    ''');
  }

  Future<bool> isFavorite(String entityType, String entityId) async {
    final db = await database;
    final rows = await db.query('favorites',
        where: 'entity_type = ? AND entity_id = ?', whereArgs: [entityType, entityId], limit: 1);
    return rows.isNotEmpty;
  }

  // ------------------------------------------------------------- recents
  Future<void> addRecentSearch(String query) async {
    final db = await database;
    await db.insert('recent_searches', {'query': query});
    await db.execute(
      'DELETE FROM recent_searches WHERE id NOT IN (SELECT id FROM recent_searches ORDER BY searched_at DESC LIMIT 50)',
    );
  }

  Future<void> clearRecentSearches() async {
    final db = await database;
    await db.delete('recent_searches');
  }

  Future<void> removeRecentSearch(String query) async {
    final db = await database;
    await db.delete('recent_searches', where: 'query = ?', whereArgs: [query]);
  }

  Future<List<String>> recentSearches({int limit = 10}) async {
    final db = await database;
    final rows = await db.rawQuery('SELECT DISTINCT query FROM recent_searches ORDER BY searched_at DESC LIMIT ?', [limit]);
    return rows.map((r) => r['query'] as String).toList();
  }

  Future<void> addRecentDrug(String drugId) async {
    final db = await database;
    await db.insert('recent_drugs', {'drug_id': drugId}, conflictAlgorithm: ConflictAlgorithm.replace);
    await db.execute(
      "DELETE FROM recent_drugs WHERE drug_id NOT IN (SELECT drug_id FROM recent_drugs ORDER BY viewed_at DESC LIMIT 50)",
    );
  }

  // ------------------------------------------------------------- sync queue
  Future<void> enqueueSync({
    required String entityType,
    required String entityId,
    required String operation,
    Map<String, dynamic> payload = const {},
    int localVersion = 0,
    int serverVersion = 0,
  }) async {
    final db = await database;
    await db.insert('sync_queue', {
      'entity_type': entityType,
      'entity_id': entityId,
      'operation': operation,
      'payload': payload.toString(),
      'local_version': localVersion,
      'server_version': serverVersion,
      'status': 'pending',
    });
  }

  Future<List<Map<String, dynamic>>> pendingSyncItems() async {
    final db = await database;
    return db.query('sync_queue', where: "status = 'pending'", orderBy: 'created_at ASC', limit: 100);
  }

  Future<void> markSyncItem(int id, String status, {String lastError = ''}) async {
    final db = await database;
    await db.update('sync_queue', {'status': status, 'last_error': lastError}, where: 'id = ?', whereArgs: [id]);
    if (status == 'failed') {
      await db.rawUpdate('UPDATE sync_queue SET retry_count = retry_count + 1 WHERE id = ?', [id]);
    }
  }

  Future<void> setSyncState({
    String? lastSyncedAt,
    String? status,
    String? datasetMode,
    String? lastError,
  }) async {
    final db = await database;
    await db.update('sync_state', {
      if (lastSyncedAt != null) 'last_synced_at': lastSyncedAt,
      if (status != null) 'status': status,
      if (datasetMode != null) 'dataset_mode': datasetMode,
      if (lastError != null) 'last_error': lastError,
    }, where: 'id = 1');
  }

  Future<Map<String, dynamic>?> syncState() async {
    final db = await database;
    final rows = await db.query('sync_state', where: 'id = 1', limit: 1);
    return rows.isEmpty ? null : rows.first;
  }
}
