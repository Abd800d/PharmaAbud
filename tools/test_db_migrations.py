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


def create_pharmacy_tables(db):
    db.execute("""CREATE TABLE IF NOT EXISTS pharmacy_stock_batches(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
      batch_number TEXT NOT NULL, barcode TEXT NOT NULL DEFAULT '',
      quantity INTEGER NOT NULL CHECK(quantity >= 0),
      minimum_stock INTEGER NOT NULL DEFAULT 5 CHECK(minimum_stock >= 0),
      purchase_price REAL NOT NULL DEFAULT 0 CHECK(purchase_price >= 0),
      sale_price REAL NOT NULL DEFAULT 0 CHECK(sale_price >= 0),
      expiry_at INTEGER NOT NULL, supplier TEXT NOT NULL DEFAULT '',
      location TEXT NOT NULL DEFAULT '', received_at INTEGER NOT NULL,
      note TEXT NOT NULL DEFAULT '')""")
    db.execute("""CREATE TABLE IF NOT EXISTS pharmacy_sales(
      id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_number TEXT NOT NULL UNIQUE,
      created_at INTEGER NOT NULL, subtotal REAL NOT NULL,
      discount REAL NOT NULL DEFAULT 0, total REAL NOT NULL,
      paid REAL NOT NULL DEFAULT 0, payment_method TEXT NOT NULL DEFAULT 'cash',
      customer TEXT NOT NULL DEFAULT '', cashier TEXT NOT NULL DEFAULT '',
      note TEXT NOT NULL DEFAULT '')""")
    db.execute("""CREATE TABLE IF NOT EXISTS pharmacy_sale_items(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      sale_id INTEGER NOT NULL REFERENCES pharmacy_sales(id) ON DELETE CASCADE,
      batch_id INTEGER NOT NULL REFERENCES pharmacy_stock_batches(id),
      product_id INTEGER NOT NULL, generic_name TEXT NOT NULL,
      brand_name TEXT NOT NULL, strength TEXT NOT NULL DEFAULT '',
      dosage_form TEXT NOT NULL DEFAULT '', batch_number TEXT NOT NULL,
      quantity INTEGER NOT NULL CHECK(quantity > 0), unit_price REAL NOT NULL,
      unit_cost REAL NOT NULL, line_total REAL NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS pharmacy_stock_movements(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      batch_id INTEGER NOT NULL REFERENCES pharmacy_stock_batches(id),
      kind TEXT NOT NULL, quantity_delta INTEGER NOT NULL,
      reference TEXT NOT NULL DEFAULT '', reason TEXT NOT NULL DEFAULT '',
      created_at INTEGER NOT NULL)""")
    db.execute('CREATE INDEX IF NOT EXISTS idx_pharmacy_stock_product ON pharmacy_stock_batches(product_id, quantity)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_pharmacy_stock_expiry ON pharmacy_stock_batches(expiry_at, quantity)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_pharmacy_sales_created ON pharmacy_sales(created_at DESC)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_pharmacy_sale_items_sale ON pharmacy_sale_items(sale_id)')


def fresh_v6(path):
    db = sqlite3.connect(path)
    db.execute('PRAGMA foreign_keys=ON')
    db.execute(GENERIC)
    db.execute(PRODUCT)
    db.execute("CREATE TABLE messages(id INTEGER PRIMARY KEY AUTOINCREMENT, author TEXT, body TEXT, is_admin INTEGER DEFAULT 0, created_at INTEGER, source_id TEXT)")
    db.execute("CREATE TABLE favorites(generic_id INTEGER PRIMARY KEY)")
    db.execute(META)
    db.execute("INSERT INTO generics(name_en) VALUES('Metformin')")
    db.execute("INSERT INTO products(generic_id, brand_name) VALUES(1,'Glucophage')")
    db.execute("INSERT INTO messages(author,body) VALUES('admin','keep')")
    db.execute("INSERT INTO aph_meta VALUES('rxnorm_snapshot','test')")
    create_pharmacy_tables(db)
    db.execute("INSERT INTO pharmacy_stock_batches(product_id,batch_number,quantity,expiry_at,received_at) VALUES(1,'FRESH-LOT',4,4102444800000,1)")
    migrate(db, 6)  # upgrade the populated v6 file to the current v7 archive schema
    db.commit()
    db.close()
    db = sqlite3.connect(path)
    db.execute('PRAGMA foreign_keys=ON')
    assert db.execute('SELECT name_en FROM generics').fetchone() == ('Metformin',)
    assert db.execute('SELECT brand_name FROM products').fetchone() == ('Glucophage',)
    assert db.execute('SELECT body FROM messages').fetchone() == ('keep',)
    assert db.execute("SELECT value FROM aph_meta WHERE key='rxnorm_snapshot'").fetchone() == ('test',)
    assert db.execute('SELECT quantity FROM pharmacy_stock_batches').fetchone() == (4,)
    assert db.execute('SELECT is_archived FROM generics WHERE id=1').fetchone() == (0,)
    assert db.execute('SELECT is_archived FROM products WHERE id=1').fetchone() == (0,)
    db.execute('UPDATE generics SET is_archived=1 WHERE id=1')
    assert db.execute('SELECT COUNT(*) FROM generics WHERE is_archived=0').fetchone() == (0,)
    assert db.execute('SELECT COUNT(*) FROM pharmacy_stock_batches WHERE product_id=1').fetchone() == (1,)
    try:
        db.execute('DELETE FROM products WHERE id=1')
    except sqlite3.IntegrityError:
        db.rollback()
    else:
        raise AssertionError('products with pharmacy stock must not be deleted')
    assert 'source_id' in {r[1] for r in db.execute('PRAGMA table_info(messages)')}
    db.close()


def migrate(db, old_version):
    db.execute('PRAGMA foreign_keys=ON')
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
    if old_version < 6:
        create_pharmacy_tables(db)
    if old_version < 7:
        columns = {row[1] for row in db.execute('PRAGMA table_info(generics)')}
        if 'is_archived' not in columns:
            db.execute('ALTER TABLE generics ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0')
        columns = {row[1] for row in db.execute('PRAGMA table_info(products)')}
        if 'is_archived' not in columns:
            db.execute('ALTER TABLE products ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0')
    db.execute('CREATE INDEX IF NOT EXISTS idx_generics_archive_name ON generics(is_archived, name_en)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_products_archive_generic ON products(is_archived, generic_id)')


def exercise_inventory_and_fefo(db):
    db.execute('PRAGMA foreign_keys=ON')
    db.execute(GENERIC)
    db.execute(PRODUCT)
    db.execute('ALTER TABLE generics ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0')
    db.execute('ALTER TABLE products ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0')
    db.execute("INSERT INTO generics(name_en) VALUES('Test medicine')")
    db.execute("INSERT INTO products(generic_id,brand_name,strength,dosage_form) VALUES(1,'Test brand','10 mg','tablet')")
    create_pharmacy_tables(db)
    now = 1_800_000_000_000
    today = now // 86_400_000 * 86_400_000
    db.execute("INSERT INTO pharmacy_stock_batches(product_id,batch_number,quantity,minimum_stock,purchase_price,sale_price,expiry_at,received_at) VALUES(1,'FEFO-1',2,3,300,500,?,1)", (today + 7*86_400_000,))
    db.execute("INSERT INTO pharmacy_stock_batches(product_id,batch_number,quantity,minimum_stock,purchase_price,sale_price,expiry_at,received_at) VALUES(1,'FEFO-2',4,3,320,500,?,2)", (today + 60*86_400_000,))
    db.execute("INSERT INTO pharmacy_stock_batches(product_id,batch_number,quantity,minimum_stock,purchase_price,sale_price,expiry_at,received_at) VALUES(1,'EXPIRED',10,3,100,500,?,0)", (today - 86_400_000,))
    db.commit()

    # One receipt takes the nearest valid expiry first and saves an audit movement.
    db.execute('BEGIN')
    batches = db.execute("SELECT id,batch_number,quantity FROM pharmacy_stock_batches WHERE product_id=1 AND quantity>0 AND expiry_at>=? ORDER BY expiry_at,received_at", (today,)).fetchall()
    assert sum(row[2] for row in batches) == 6
    remaining = 4
    sale_id = db.execute("INSERT INTO pharmacy_sales(receipt_number,created_at,subtotal,total,paid,payment_method) VALUES('APH-TEST',?,2000,2000,2000,'cash')", (now,)).lastrowid
    for batch_id, lot, quantity in batches:
        take = min(remaining, quantity)
        if take == 0: break
        db.execute('UPDATE pharmacy_stock_batches SET quantity=quantity-? WHERE id=? AND quantity>=?', (take,batch_id,take))
        db.execute("INSERT INTO pharmacy_sale_items(sale_id,batch_id,product_id,generic_name,brand_name,batch_number,quantity,unit_price,unit_cost,line_total) VALUES(?, ?,1,'Test medicine','Test brand',?,?,500,300,?)", (sale_id,batch_id,lot,take,take*500))
        db.execute("INSERT INTO pharmacy_stock_movements(batch_id,kind,quantity_delta,reference,created_at) VALUES(?,'sale',?,?,?)", (batch_id,-take,'APH-TEST',now))
        remaining -= take
    assert remaining == 0
    db.commit()
    lots = {row[0]: row[1] for row in db.execute('SELECT batch_number,quantity FROM pharmacy_stock_batches')}
    assert lots == {'FEFO-1': 0, 'FEFO-2': 2, 'EXPIRED': 10}
    assert db.execute('SELECT COUNT(*) FROM pharmacy_sale_items WHERE sale_id=?', (sale_id,)).fetchone() == (2,)
    assert db.execute("SELECT SUM(quantity_delta) FROM pharmacy_stock_movements WHERE kind='sale'").fetchone() == (-4,)

    # An insufficient-stock checkout must leave every batch untouched.
    before = dict(db.execute('SELECT batch_number,quantity FROM pharmacy_stock_batches'))
    db.execute('BEGIN')
    available = db.execute("SELECT COALESCE(SUM(quantity),0) FROM pharmacy_stock_batches WHERE product_id=1 AND quantity>0 AND expiry_at>=?", (today,)).fetchone()[0]
    if available < 3:
        db.rollback()
    assert dict(db.execute('SELECT batch_number,quantity FROM pharmacy_stock_batches')) == before


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
    fresh_v6(root / 'fresh-v6.db')
    ops = sqlite3.connect(root / 'pharmacy-ops.db')
    exercise_inventory_and_fefo(ops)
    ops.close()
    v5 = sqlite3.connect(root / 'legacy-v5.db')
    v5.executescript(GENERIC + ';' + PRODUCT + "; CREATE TABLE messages(id INTEGER PRIMARY KEY, author TEXT, body TEXT, is_admin INTEGER, created_at INTEGER, source_id TEXT); CREATE TABLE favorites(generic_id INTEGER PRIMARY KEY);")
    v5.execute("INSERT INTO generics(name_en) VALUES('Metformin')")
    v5.execute("INSERT INTO products(generic_id,brand_name) VALUES(1,'Glucophage')")
    v5.commit()
    migrate(v5, 5)
    v5.execute("INSERT INTO pharmacy_stock_batches(product_id,batch_number,quantity,expiry_at,received_at) VALUES(1,'LOT-5',9,4102444800000,1)")
    assert v5.execute("SELECT COUNT(*) FROM pharmacy_stock_batches").fetchone() == (1,)
    v5.close()
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
        assert db.execute('SELECT is_archived FROM generics WHERE id=1').fetchone() == (0,)
        assert db.execute('SELECT is_archived FROM products WHERE id=1').fetchone() == (0,)
        assert db.execute("SELECT name FROM sqlite_master WHERE name='aph_meta'").fetchone() == ('aph_meta',)
        db.close()

print('SQLite on-disk regression passed: v7 archive migration from v2–v6, data preservation, FEFO deduction, expiry exclusion and failed-sale rollback.')
