import 'dart:convert';
import 'package:flutter/services.dart' show rootBundle;
import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';
import '../models/drug_models.dart';

/// قاعدة SQLite محلية دائمة — تعمل دون إنترنت بالكامل.
/// عند أول تشغيل تُزرع قاعدة APH الحقيقية من assets/data/drugs_seed.json
class DBHelper {
  DBHelper._();
  static final DBHelper instance = DBHelper._();
  Database? _db;

  Future<Database> get db async {
    _db ??= await _open();
    return _db!;
  }

  Future<Database> _open() async {
    final path = p.join(await getDatabasesPath(), 'abdulmajeedpharma.db');
    return openDatabase(path, version: 5, onCreate: (d, v) async {
      await d.execute('''CREATE TABLE generics(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name_en TEXT NOT NULL,
        name_ar TEXT, system_id TEXT, subgroup_en TEXT, subgroup_ar TEXT,
        atc_code TEXT, introduction TEXT, mechanism TEXT, indications TEXT,
        dosage TEXT, interactions TEXT, warnings TEXT, pregnancy TEXT,
        image_path TEXT, source TEXT)''');
      await d.execute('''CREATE TABLE products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        generic_id INTEGER NOT NULL REFERENCES generics(id) ON DELETE CASCADE,
        brand_name TEXT NOT NULL, manufacturer TEXT, country TEXT,
        strength TEXT, dosage_form TEXT, agent_yemen TEXT,
        image_path TEXT, source TEXT, verified INTEGER DEFAULT 0)''');
      await d.execute('''CREATE TABLE messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT, author TEXT, body TEXT,
        is_admin INTEGER DEFAULT 0, created_at INTEGER, source_id TEXT)''');
      await d.execute('CREATE TABLE favorites(generic_id INTEGER PRIMARY KEY)');
      await d.execute('''CREATE TABLE aph_meta(
        key TEXT PRIMARY KEY, value TEXT NOT NULL)''');
    }, onUpgrade: (d, oldV, newV) async {
      // Upgrade legacy message tables additively; never drop user/admin messages.
      final messageTable = await d.rawQuery(
          "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'");
      if (messageTable.isEmpty) {
        await d.execute('''CREATE TABLE messages(
          id INTEGER PRIMARY KEY AUTOINCREMENT, author TEXT, body TEXT,
          is_admin INTEGER DEFAULT 0, created_at INTEGER, source_id TEXT)''');
      } else {
        final info = await d.rawQuery('PRAGMA table_info(messages)');
        final columns = info.map((row) => row['name'].toString()).toSet();
        const additions = <String, String>{
          'author': 'TEXT',
          'body': 'TEXT',
          'is_admin': 'INTEGER DEFAULT 0',
          'created_at': 'INTEGER',
          'source_id': 'TEXT',
        };
        for (final entry in additions.entries) {
          if (!columns.contains(entry.key)) {
            await d.execute('ALTER TABLE messages ADD COLUMN ${entry.key} ${entry.value}');
          }
        }
      }
      await d.execute(
          'CREATE TABLE IF NOT EXISTS favorites(generic_id INTEGER PRIMARY KEY)');
      if (oldV < 5) {
        await d.execute('''CREATE TABLE IF NOT EXISTS aph_meta(
          key TEXT PRIMARY KEY, value TEXT NOT NULL)''');
      }
    });
  }

  /// Seed the small curated catalog first; the optional RxNorm import may run
  /// after the screen opens so a large first install never looks frozen.
  static String lastSeedError = '';
  static int lastSeedCount = 0;
  Future<void> seedIfEmpty({bool includeLargeCatalog = true}) async {
    try {
      await _seed(includeLargeCatalog: includeLargeCatalog);
    } catch (e) {
      lastSeedError = e.toString();
      try {
        lastSeedCount = await countGenerics();
      } catch (_) {
        lastSeedCount = 0;
      }
    }
  }

  Future<void> _seed({required bool includeLargeCatalog}) async {
    final d = await db;
    final count = Sqflite.firstIntValue(
        await d.rawQuery('SELECT COUNT(*) FROM generics')) ?? 0;
    if (count > 0) {
      lastSeedError = '';
      if (includeLargeCatalog) await ensureLargeCatalog();
      lastSeedCount = await countGenerics();
      return;
    }
    await d.execute('''CREATE TABLE IF NOT EXISTS aph_meta(
      key TEXT PRIMARY KEY, value TEXT NOT NULL)''');
    // A cleared core DB must also clear the import marker.
    await d.delete('aph_meta', where: 'key=?', whereArgs: ['rxnorm_snapshot']);
    final raw = await rootBundle.loadString('assets/data/drugs_seed.json');
    final data = jsonDecode(raw) as Map<String, dynamic>;
    final drugs = (data['drugs'] as List? ?? const []).cast<Map<String, dynamic>>();
    await d.transaction((txn) async {
      final batch = txn.batch();
      for (final g in drugs) {
        final gid = await txn.insert('generics', {
          'name_en': g['genericEn'] ?? '', 'name_ar': g['genericAr'] ?? '',
          'system_id': g['systemId'] ?? 'misc',
          'subgroup_en': g['subgroupEn'] ?? 'General',
          'subgroup_ar': g['subgroupAr'] ?? 'عام', 'atc_code': g['atc'] ?? '',
          'introduction': g['introduction'] ?? '', 'mechanism': g['mechanism'] ?? '',
          'indications': g['indications'] ?? '', 'dosage': g['dosage'] ?? '',
          'interactions': g['interactions'] ?? '', 'warnings': g['warnings'] ?? '',
          'pregnancy': g['pregnancy'] ?? '', 'image_path': g['image'] ?? '',
          'source': g['source'] ?? 'APH seed',
        });
        for (final pr in (g['products'] as List? ?? const [])) {
          final pm = (pr as Map).cast<String, dynamic>();
          batch.insert('products', {
            'generic_id': gid, 'brand_name': pm['brand'] ?? '',
            'manufacturer': pm['manufacturer'] ?? '', 'country': pm['country'] ?? '',
            'strength': pm['strength'] ?? '', 'dosage_form': pm['form'] ?? '',
            'agent_yemen': pm['agentYemen'] ?? '', 'image_path': pm['image'] ?? '',
            'source': pm['source'] ?? '',
            'verified': (pm['verified'] == true) ? 1 : 0,
          });
        }
      }
      await batch.commit(noResult: true);
    });
    if (includeLargeCatalog) await ensureLargeCatalog();
    lastSeedCount = await countGenerics();
    lastSeedError = '';
  }

  Future<void>? _catalogImport;
  Future<void> ensureLargeCatalog() {
    final active = _catalogImport;
    if (active != null) return active;
    final future = _loadLargeCatalog();
    _catalogImport = future;
    return future.whenComplete(() {
      if (identical(_catalogImport, future)) _catalogImport = null;
    });
  }

  Future<void> _loadLargeCatalog() async {
    await _ensureRxNormCatalog();
    lastSeedCount = await countGenerics();
    lastSeedError = '';
  }

  Future<void> _ensureRxNormCatalog() async {
    final d = await db;
    await d.execute('''CREATE TABLE IF NOT EXISTS aph_meta(
      key TEXT PRIMARY KEY, value TEXT NOT NULL)''');
    final meta = jsonDecode(await rootBundle.loadString(
        'assets/data/rxnorm_catalog_meta.json')) as Map<String, dynamic>;
    final snapshot = (meta['snapshot'] ?? 'unknown').toString();
    final marker = await d.query('aph_meta', columns: ['value'],
        where: 'key=?', whereArgs: ['rxnorm_snapshot'], limit: 1);
    if (marker.isNotEmpty && marker.first['value'] == snapshot) return;

    final catalog = jsonDecode(await rootBundle.loadString(
        'assets/data/rxnorm_catalog.json')) as Map<String, dynamic>;
    if (catalog['snapshot'] != snapshot) {
      throw StateError('RxNorm catalogue and metadata snapshots differ');
    }
    final sourceNote = 'NLM RxNorm $snapshot; names only, not clinical guidance; '
        'classification is unreviewed.';
    await d.transaction((txn) async {
      final nameRows = await txn.query('generics', columns: ['id', 'name_en']);
      final ids = <String, int>{};
      for (final row in nameRows) {
        final name = (row['name_en'] ?? '').toString().trim().toLowerCase();
        if (name.isNotEmpty) ids.putIfAbsent(name, () => row['id'] as int);
      }
      final productRows = await txn.query('products', columns: [
        'generic_id', 'brand_name', 'strength', 'dosage_form'
      ]);
      final maxId = Sqflite.firstIntValue(
              await txn.rawQuery('SELECT COALESCE(MAX(id),0) FROM generics')) ?? 0;
      var nextId = maxId;
      var batch = txn.batch();
      var pending = 0;
      String productKey(int id, String brand, String strength, String form) =>
          '$id|${brand.trim().toLowerCase()}|${strength.trim().toLowerCase()}|${form.trim().toLowerCase()}';
      final existingProducts = <String>{};
      for (final row in productRows) {
        existingProducts.add(productKey(row['generic_id'] as int,
            (row['brand_name'] ?? '').toString(), (row['strength'] ?? '').toString(),
            (row['dosage_form'] ?? '').toString()));
      }
      Future<void> flush() async {
        if (pending < 500) return;
        await batch.commit(noResult: true);
        batch = txn.batch();
        pending = 0;
      }
      for (final rawDrug in (catalog['drugs'] as List? ?? const [])) {
        if (rawDrug is! Map) continue;
        final drug = rawDrug.cast<String, dynamic>();
        final name = (drug['genericEn'] ?? '').toString().trim();
        if (name.isEmpty) continue;
        final normalized = name.toLowerCase();
        var genericId = ids[normalized];
        if (genericId == null) {
          genericId = ++nextId;
          final isCombo = drug['kind'] == 'combination';
          batch.insert('generics', {
            'id': genericId, 'name_en': name, 'name_ar': '', 'system_id': 'misc',
            'subgroup_en': isCombo ? 'RxNorm combination — review classification' : 'RxNorm ingredient — review classification',
            'subgroup_ar': isCombo ? 'تركيبة RxNorm — بحاجة إلى مراجعة التصنيف' : 'مادة RxNorm — بحاجة إلى مراجعة التصنيف',
            'atc_code': '', 'introduction': '', 'mechanism': '', 'indications': '',
            'dosage': '', 'interactions': '', 'warnings': '', 'pregnancy': '',
            'image_path': '', 'source': sourceNote,
          });
          ids[normalized] = genericId;
          pending++;
          await flush();
        }
        for (final rawProduct in (drug['products'] as List? ?? const [])) {
          if (rawProduct is! Map) continue;
          final product = rawProduct.cast<String, dynamic>();
          final brand = (product['brand'] ?? '').toString().trim();
          if (brand.isEmpty) continue;
          final strength = (product['strength'] ?? '').toString().trim();
          final form = (product['form'] ?? '').toString().trim();
          if (!existingProducts.add(productKey(genericId, brand, strength, form))) continue;
          batch.insert('products', {
            'generic_id': genericId, 'brand_name': brand, 'manufacturer': '',
            'country': '', 'strength': strength, 'dosage_form': form,
            'agent_yemen': '', 'image_path': '',
            'source': 'NLM RxNorm $snapshot; brand/form terminology only; '
                'manufacturer, country and Yemen agent not supplied.',
            'verified': 0,
          });
          pending++;
          await flush();
        }
      }
      if (pending > 0) await batch.commit(noResult: true);
    });
    await d.insert('aph_meta', {'key': 'rxnorm_snapshot', 'value': snapshot},
        conflictAlgorithm: ConflictAlgorithm.replace);
  }

  // ---------- Generics ----------
  Future<List<GenericDrug>> allGenerics() async {
    final rows = await (await db).query('generics', orderBy: 'name_en');
    return rows.map(GenericDrug.fromMap).toList();
  }

  Future<List<GenericDrug>> bySystem(String systemId) async {
    final rows = await (await db)
        .query('generics', where: 'system_id=?', whereArgs: [systemId],
            orderBy: 'subgroup_en, name_en');
    return rows.map(GenericDrug.fromMap).toList();
  }

  Future<int> countGenerics() async => Sqflite.firstIntValue(
          await (await db).rawQuery('SELECT COUNT(*) FROM generics')) ?? 0;
  Future<int> countProducts() async => Sqflite.firstIntValue(
          await (await db).rawQuery('SELECT COUNT(*) FROM products')) ?? 0;

  /// معاملة واحدة للاستيراد الضخم (أسرع بمئات المرات من إدخال سجل سجل)
  Future<T> transaction<T>(Future<T> Function(Transaction txn) action) async =>
      (await db).transaction(action);

  Future<int> insertGeneric(GenericDrug g, [DatabaseExecutor? ex]) async =>
      (ex ?? await db).insert('generics', g.toMap()..remove('id'));
  Future<void> updateGeneric(GenericDrug g) async => (await db)
      .update('generics', g.toMap(), where: 'id=?', whereArgs: [g.id]);
  Future<void> deleteGeneric(int id) async {
    final d = await db;
    await d.delete('products', where: 'generic_id=?', whereArgs: [id]);
    await d.delete('generics', where: 'id=?', whereArgs: [id]);
  }

  // ---------- Products ----------
  Future<List<TradeProduct>> productsOf(int genericId) async {
    final rows = await (await db).query('products',
        where: 'generic_id=?', whereArgs: [genericId], orderBy: 'brand_name');
    return rows.map(TradeProduct.fromMap).toList();
  }

  Future<List<TradeProduct>> allProducts() async {
    final rows = await (await db).query('products', orderBy: 'brand_name');
    return rows.map(TradeProduct.fromMap).toList();
  }

  Future<int> insertTrade(TradeProduct t, [DatabaseExecutor? ex]) async =>
      (ex ?? await db).insert('products', t.toMap()..remove('id'));
  Future<void> updateTrade(TradeProduct t) async => (await db)
      .update('products', t.toMap(), where: 'id=?', whereArgs: [t.id]);
  Future<void> deleteTrade(int id) async =>
      (await db).delete('products', where: 'id=?', whereArgs: [id]);

  // ---------- Favorites ----------
  Future<Set<int>> favorites() async {
    final rows = await (await db).query('favorites');
    return rows.map((r) => r['generic_id'] as int).toSet();
  }

  Future<void> toggleFavorite(int genericId, bool fav) async {
    final d = await db;
    if (fav) {
      await d.insert('favorites', {'generic_id': genericId},
          conflictAlgorithm: ConflictAlgorithm.ignore);
    } else {
      await d.delete('favorites',
          where: 'generic_id=?', whereArgs: [genericId]);
    }
  }

  // ---------- Messages (لوحة رسائل داخل التطبيق) ----------
  Future<List<ChatMessage>> messages() async {
    final rows = await (await db)
        .query('messages', orderBy: 'created_at DESC', limit: 300);
    return rows.map(ChatMessage.fromMap).toList();
  }

  Future<void> addMessage(ChatMessage m) async =>
      (await db).insert('messages', m.toMap()..remove('id'));

  /// كل المنتجات مجمّعة حسب الدواء (استعلام واحد بدل استعلام لكل دواء)
  Future<Map<int, List<TradeProduct>>> productsGroupedByGeneric() async {
    final rows = await (await db).query('products', orderBy: 'brand_name');
    final out = <int, List<TradeProduct>>{};
    for (final r in rows) {
      final p = TradeProduct.fromMap(r);
      out.putIfAbsent(p.genericId, () => <TradeProduct>[]).add(p);
    }
    return out;
  }

  // ---------- أدوات المزامنة مع لوحة التحكم على الويب ----------
  /// يبحث عن اسم علمي بالاسم الإنجليزي (غير حساس لحالة الأحرف)
  Future<GenericDrug?> genericByName(String nameEn) async {
    final rows = await (await db).query('generics',
        where: 'LOWER(name_en)=?', whereArgs: [nameEn.trim().toLowerCase()],
        limit: 1);
    if (rows.isEmpty) return null;
    return GenericDrug.fromMap(rows.first);
  }

  Future<List<TradeProduct>> productsByGeneric(int genericId) =>
      productsOf(genericId);

  /// هل هذا المنتج موجوداً بنفس (الاسم التجاري + القوة + الشكل + الشركة)؟
  Future<bool> productExists(int genericId, String brand, String strength,
      String form, String manufacturer) async {
    final n = Sqflite.firstIntValue(await (await db).query('products',
        columns: ['COUNT(*) AS c'],
        where:
            'generic_id=? AND LOWER(brand_name)=? AND LOWER(strength)=? AND LOWER(dosage_form)=? AND LOWER(manufacturer)=?',
        whereArgs: [
          genericId,
          brand.trim().toLowerCase(),
          strength.trim().toLowerCase(),
          form.trim().toLowerCase(),
          manufacturer.trim().toLowerCase(),
        ]));
    return (n ?? 0) > 0;
  }

  Future<bool> messageExists(String sourceId) async {
    final n = Sqflite.firstIntValue(await (await db).query('messages',
        columns: ['COUNT(*) AS c'],
        where: 'source_id=?',
        whereArgs: [sourceId]));
    return (n ?? 0) > 0;
  }

  Future<void> resetAll() async {
    final d = await db;
    await d.delete('products');
    await d.delete('generics');
    await d.delete('favorites');
    await seedIfEmpty();
  }
}
