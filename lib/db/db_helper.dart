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
    return openDatabase(path, version: 3, onCreate: (d, v) async {
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
        is_admin INTEGER DEFAULT 0, created_at INTEGER)''');
      await d.execute('CREATE TABLE favorites(generic_id INTEGER PRIMARY KEY)');
    }, onUpgrade: (d, oldV, newV) async {
      if (oldV < 3) {
        await d.execute('DROP TABLE IF EXISTS messages');
        await d.execute('''CREATE TABLE messages(
          id INTEGER PRIMARY KEY AUTOINCREMENT, author TEXT, body TEXT,
          is_admin INTEGER DEFAULT 0, created_at INTEGER)''');
        await d.execute(
            'CREATE TABLE IF NOT EXISTS favorites(generic_id INTEGER PRIMARY KEY)');
      }
    });
  }

  /// زراعة أولية من ملف JSON الحقيقي (مرة واحدة فقط)
  Future<void> seedIfEmpty() async {
    final d = await db;
    final c = Sqflite.firstIntValue(
        await d.rawQuery('SELECT COUNT(*) FROM generics'));
    if (c != null && c > 0) return;
    final raw = await rootBundle.loadString('assets/data/drugs_seed.json');
    final data = jsonDecode(raw) as Map<String, dynamic>;
    final drugs = (data['drugs'] as List).cast<Map<String, dynamic>>();
    await d.transaction((txn) async {
      for (final g in drugs) {
        final gid = await txn.insert('generics', {
          'name_en': g['genericEn'] ?? '', 'name_ar': g['genericAr'] ?? '',
          'system_id': g['systemId'] ?? 'misc',
          'subgroup_en': g['subgroupEn'] ?? 'General',
          'subgroup_ar': g['subgroupAr'] ?? 'عام', 'atc_code': g['atc'] ?? '',
          'introduction': g['introduction'] ?? '',
          'mechanism': g['mechanism'] ?? '',
          'indications': g['indications'] ?? '', 'dosage': g['dosage'] ?? '',
          'interactions': g['interactions'] ?? '',
          'warnings': g['warnings'] ?? '', 'pregnancy': g['pregnancy'] ?? '',
          'image_path': g['image'] ?? '', 'source': g['source'] ?? 'APH seed',
        });
        for (final pr in (g['products'] as List? ?? [])) {
          final pm = (pr as Map).cast<String, dynamic>();
          await txn.insert('products', {
            'generic_id': gid, 'brand_name': pm['brand'] ?? '',
            'manufacturer': pm['manufacturer'] ?? '',
            'country': pm['country'] ?? '', 'strength': pm['strength'] ?? '',
            'dosage_form': pm['form'] ?? '',
            'agent_yemen': pm['agentYemen'] ?? '',
            'image_path': pm['image'] ?? '', 'source': pm['source'] ?? '',
            'verified': (pm['verified'] == true) ? 1 : 0,
          });
        }
      }
    });
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

  Future<int> insertGeneric(GenericDrug g) async =>
      (await db).insert('generics', g.toMap()..remove('id'));
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

  Future<int> insertTrade(TradeProduct t) async =>
      (await db).insert('products', t.toMap()..remove('id'));
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

  Future<void> resetAll() async {
    final d = await db;
    await d.delete('products');
    await d.delete('generics');
    await d.delete('favorites');
    await seedIfEmpty();
  }
}
