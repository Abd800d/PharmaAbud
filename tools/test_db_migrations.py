#!/usr/bin/env python3
"""SQLite regression checks for DBHelper schema versions 2–5.
Uses on-disk SQLite databases and verifies data after close/reopen. SQL statements
mirror DBHelper.onCreate/onUpgrade; this is not a Flutter plugin integration test.
"""
import sqlite3
import tempfile
from pathlib import Path

GENERIC = """CREATE TABLE generics(
 id INTEGER PRIMARY KEY AUTOINCREMENT, name_en TEXT NOT NULL, name_ar TEXT,
 system_id TEXT, subgroup_en TEXT, subgroup_ar TEXT, atc_code TEXT,
 introduction TEXT, mechanism TEXT, indications TEXT, dosage TEXT,
 interactions TEXT, warnings TEXT, pregnancy TEXT, image_path TEXT, source TEXT)"""
PRODUCT = """CREATE TABLE products(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 generic_id INTEGER NOT NULL REFERENCES generics(id) ON DELETE CASCADE,
 brand_name TEXT NOT NULL, manufacturer TEXT, country TEXT, strength TEXT,
 dosage_form TEXT, agent_yemen TEXT, image_path TEXT, source TEXT,
 verified INTEGER DEFAULT 0)"""
META = "CREATE TABLE IF NOT EXISTS aph_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)"


def fresh_v5(path):
    db = sqlite3.connect(path)
    db.execute(GENERIC)
    db.execute(PRODUCT)
    db.execute("CREATE TABLE messages(id INTEGER PRIMARY KEY AUTOINCREMENT, author TEXT, body TEXT, is_admin INTEGER DEFAULT 0, created_at INTEGER, source_id TEXT)")
    db.execute("CREATE TABLE favorites(generic_id INTEGER PRIMARY KEY)")
    db.execute(META)
    db.execute("INSERT INTO generics(name_en) VALUES('Metformin')")
    db.execute("INSERT INTO products(generic_id, brand_name) VALUES(1,'Glucophage')")
    db.execute("INSERT INTO messages(author,body) VALUES('admin','keep')")
    db.execute("INSERT INTO aph_meta VALUES('rxnorm_snapshot','test')")
    db.commit()
    db.close()
    db = sqlite3.connect(path)
    assert db.execute('SELECT name_en FROM generics').fetchone() == ('Metformin',)
    assert db.execute('SELECT brand_name FROM products').fetchone() == ('Glucophage',)
    assert db.execute('SELECT body FROM messages').fetchone() == ('keep',)
    assert db.execute("SELECT value FROM aph_meta WHERE key='rxnorm_snapshot'").fetchone() == ('test',)
    assert 'source_id' in {r[1] for r in db.execute('PRAGMA table_info(messages)')}
    db.close()


def migrate(db, old_version):
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'messages' not in tables:
        db.execute("CREATE TABLE messages(id INTEGER PRIMARY KEY AUTOINCREMENT, author TEXT, body TEXT, is_admin INTEGER DEFAULT 0, created_at INTEGER, source_id TEXT)")
    else:
        columns = {row[1] for row in db.execute('PRAGMA table_info(messages)')}
        additions = {
            'author': 'TEXT', 'body': 'TEXT', 'is_admin': 'INTEGER DEFAULT 0',
            'created_at': 'INTEGER', 'source_id': 'TEXT',
        }
        for name, sql_type in additions.items():
            if name not in columns:
                db.execute(f'ALTER TABLE messages ADD COLUMN {name} {sql_type}')
    db.execute('CREATE TABLE IF NOT EXISTS favorites(generic_id INTEGER PRIMARY KEY)')
    if old_version < 5:
        db.execute(META)


def old_db(path, version):
    db = sqlite3.connect(path)
    db.execute(GENERIC)
    db.execute(PRODUCT)
    db.execute("INSERT INTO generics(name_en) VALUES('Metformin')")
    db.execute("INSERT INTO products(generic_id, brand_name) VALUES(1,'Glucophage')")
    if version == 2:
        db.execute("CREATE TABLE messages(id INTEGER PRIMARY KEY, author TEXT, body TEXT, created_at INTEGER)")
    elif version == 3:
        db.execute("CREATE TABLE messages(id INTEGER PRIMARY KEY, author TEXT, body TEXT, is_admin INTEGER, created_at INTEGER)")
    else:
        db.execute("CREATE TABLE messages(id INTEGER PRIMARY KEY, author TEXT, body TEXT, is_admin INTEGER, created_at INTEGER, source_id TEXT)")
    db.execute("INSERT INTO messages(author, body, created_at) VALUES('admin','keep',123)")
    db.execute('CREATE TABLE favorites(generic_id INTEGER PRIMARY KEY)')
    db.execute('INSERT INTO favorites VALUES(1)')
    db.commit()
    return db


with tempfile.TemporaryDirectory(prefix='aph-sqlite-') as directory:
    root = Path(directory)
    fresh_v5(root / 'fresh-v5.db')
    for version in (2, 3, 4):
        path = root / f'legacy-v{version}.db'
        db = old_db(path, version)
        migrate(db, version)
        db.commit()
        db.close()
        # Confirm the upgraded on-disk database remains valid after reopening.
        db = sqlite3.connect(path)
        assert db.execute('SELECT name_en FROM generics WHERE id=1').fetchone() == ('Metformin',)
        assert db.execute('SELECT brand_name FROM products WHERE generic_id=1').fetchone() == ('Glucophage',)
        assert db.execute('SELECT generic_id FROM favorites').fetchone() == (1,)
        assert db.execute('SELECT body,created_at FROM messages').fetchone() == ('keep', 123)
        assert 'source_id' in {r[1] for r in db.execute('PRAGMA table_info(messages)')}
        assert 'is_admin' in {r[1] for r in db.execute('PRAGMA table_info(messages)')}
        assert db.execute("SELECT name FROM sqlite_master WHERE name='aph_meta'").fetchone() == ('aph_meta',)
        db.close()

print('SQLite on-disk regression passed: fresh v5 durability and legacy v2/v3/v4 upgrades preserve drug/product/message data.')
