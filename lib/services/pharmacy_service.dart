import 'package:sqflite/sqflite.dart';
import '../db/db_helper.dart';
import '../models/pharmacy_models.dart';

class PharmacyService {
  PharmacyService._();
  static final PharmacyService instance = PharmacyService._();
  Future<Database> get _db => DBHelper.instance.db;

  static int _dayStart([DateTime? value]) {
    final now = value ?? DateTime.now();
    return DateTime(now.year, now.month, now.day).millisecondsSinceEpoch;
  }

  Future<Map<String, num>> summary() async {
    final d = await _db;
    final today = _dayStart();
    final stock = await d.rawQuery('''
      SELECT
        COALESCE(SUM(CASE WHEN expiry_at >= ? THEN quantity ELSE 0 END),0) AS units,
        COALESCE(SUM(quantity * purchase_price),0) AS inventory_value,
        COALESCE(SUM(CASE WHEN quantity > 0 AND expiry_at < ? THEN quantity ELSE 0 END),0) AS expired_units,
        COALESCE(SUM(CASE WHEN quantity > 0 AND expiry_at >= ? AND expiry_at < ? THEN quantity ELSE 0 END),0) AS expiring_units
      FROM pharmacy_stock_batches
    ''', [today, today, today, today + const Duration(days: 31).inMilliseconds]);
    final low = await d.rawQuery('''
      SELECT COUNT(*) AS count FROM (
        SELECT product_id,
          SUM(CASE WHEN expiry_at >= ? THEN quantity ELSE 0 END) AS usable,
          MAX(minimum_stock) AS minimum
        FROM pharmacy_stock_batches GROUP BY product_id
        HAVING minimum > 0 AND usable <= minimum
      )
    ''', [today]);
    final sales = await d.rawQuery('''
      SELECT COALESCE(SUM(total),0) AS amount, COUNT(*) AS count
      FROM pharmacy_sales WHERE created_at >= ? AND created_at < ?
    ''', [today, today + const Duration(days: 1).inMilliseconds]);
    final profit = await d.rawQuery('''
      SELECT COALESCE(SUM((i.unit_price-i.unit_cost)*i.quantity),0) AS amount
      FROM pharmacy_sale_items i JOIN pharmacy_sales s ON s.id=i.sale_id
      WHERE s.created_at >= ? AND s.created_at < ?
    ''', [today, today + const Duration(days: 1).inMilliseconds]);
    final s = stock.first;
    final l = low.first;
    final t = sales.first;
    final p = profit.first;
    return {
      'units': (s['units'] as num? ?? 0),
      'inventory_value': (s['inventory_value'] as num? ?? 0),
      'expired_units': (s['expired_units'] as num? ?? 0),
      'expiring_units': (s['expiring_units'] as num? ?? 0),
      'low_products': (l['count'] as num? ?? 0),
      'today_sales': (t['amount'] as num? ?? 0),
      'today_profit': (p['amount'] as num? ?? 0),
      'today_receipts': (t['count'] as num? ?? 0),
    };
  }

  Future<List<Map<String, Object?>>> searchProducts(String query,
      {int limit = 50, bool allowArchivedWithStock = false}) async {
    final d = await _db;
    final q = query.trim();
    final like = '%$q%';
    final today = _dayStart();
    return d.rawQuery('''
      SELECT p.id, p.generic_id, g.name_en AS generic_name,
        g.name_ar AS generic_name_ar, p.brand_name, p.strength,
        p.dosage_form, COALESCE((
          SELECT SUM(b.quantity) FROM pharmacy_stock_batches b
          WHERE b.product_id=p.id AND b.expiry_at >= ?
        ),0) AS available_quantity,
        COALESCE((
          SELECT b.sale_price FROM pharmacy_stock_batches b
          WHERE b.product_id=p.id AND b.quantity>0 AND b.expiry_at >= ?
          ORDER BY b.expiry_at ASC, b.received_at ASC LIMIT 1
        ),0) AS suggested_price,
        COALESCE((
          SELECT b.barcode FROM pharmacy_stock_batches b
          WHERE b.product_id=p.id AND b.barcode<>''
          ORDER BY b.received_at DESC LIMIT 1
        ),'') AS barcode
      FROM products p JOIN generics g ON g.id=p.generic_id
      WHERE ((p.is_archived=0 AND g.is_archived=0) OR (?=1 AND EXISTS (
        SELECT 1 FROM pharmacy_stock_batches a WHERE a.product_id=p.id AND a.quantity>0
      ))) AND (?='' OR p.brand_name LIKE ? OR g.name_en LIKE ? OR
        g.name_ar LIKE ? OR p.strength LIKE ? OR p.dosage_form LIKE ? OR
        EXISTS (SELECT 1 FROM pharmacy_stock_batches b
          WHERE b.product_id=p.id AND b.barcode LIKE ?))
      ORDER BY g.name_en COLLATE NOCASE, p.brand_name COLLATE NOCASE
      LIMIT ?
    ''', [today, today, allowArchivedWithStock ? 1 : 0, q, like, like, like, like, like, like, limit]);
  }

  Future<List<Map<String, Object?>>> stockBatches({String query = '',
      String filter = 'all'}) async {
    final d = await _db;
    final q = query.trim();
    final like = '%$q%';
    final today = _dayStart();
    final expiring = today + const Duration(days: 31).inMilliseconds;
    String extra = '';
    if (filter == 'low') {
      extra = '''AND b.minimum_stock>0 AND
        (SELECT COALESCE(SUM(CASE WHEN x.expiry_at >= $today THEN x.quantity ELSE 0 END),0)
          FROM pharmacy_stock_batches x WHERE x.product_id=b.product_id) <=
        (SELECT MAX(x.minimum_stock) FROM pharmacy_stock_batches x WHERE x.product_id=b.product_id)''';
    }
    if (filter == 'expired') extra = 'AND b.expiry_at < $today';
    if (filter == 'expiring') extra = 'AND b.expiry_at >= $today AND b.expiry_at < $expiring';
    return d.rawQuery('''
      SELECT b.*, p.brand_name, p.generic_id, p.strength, p.dosage_form,
        g.name_en AS generic_name, g.name_ar AS generic_name_ar
      FROM pharmacy_stock_batches b
      JOIN products p ON p.id=b.product_id
      JOIN generics g ON g.id=p.generic_id
      WHERE b.quantity>0 $extra AND (?='' OR p.brand_name LIKE ? OR
        g.name_en LIKE ? OR g.name_ar LIKE ? OR b.batch_number LIKE ? OR
        b.barcode LIKE ? OR b.supplier LIKE ?)
      ORDER BY b.expiry_at ASC, g.name_en COLLATE NOCASE
      LIMIT 500
    ''', [q, like, like, like, like, like, like]);
  }

  Future<void> addStockBatch({
    required int productId,
    required String batchNumber,
    required String barcode,
    required int quantity,
    required int minimumStock,
    required double purchasePrice,
    required double salePrice,
    required DateTime expiry,
    required String supplier,
    required String location,
    String note = '',
  }) async {
    if (batchNumber.trim().isEmpty) throw const FormatException('Batch/lot number is required.');
    if (quantity <= 0) throw const FormatException('Quantity must be greater than zero.');
    if (minimumStock < 0 || !purchasePrice.isFinite || !salePrice.isFinite ||
        purchasePrice < 0 || salePrice < 0) {
      throw const FormatException('Stock, minimum and prices must be valid non-negative values.');
    }
    final expiryDay = DateTime(expiry.year, expiry.month, expiry.day);
    if (expiryDay.isBefore(DateTime(DateTime.now().year, DateTime.now().month, DateTime.now().day))) {
      throw const FormatException('Cannot receive a batch that has already expired.');
    }
    final d = await _db;
    await d.transaction((txn) async {
      final product = await txn.query('products', columns: ['id'],
          where: 'id=?', whereArgs: [productId], limit: 1);
      if (product.isEmpty) throw StateError('Selected catalogue product no longer exists.');
      final now = DateTime.now().millisecondsSinceEpoch;
      final batchId = await txn.insert('pharmacy_stock_batches', {
        'product_id': productId,
        'batch_number': batchNumber.trim(),
        'barcode': barcode.trim(),
        'quantity': quantity,
        'minimum_stock': minimumStock,
        'purchase_price': purchasePrice,
        'sale_price': salePrice,
        'expiry_at': expiryDay.millisecondsSinceEpoch,
        'supplier': supplier.trim(),
        'location': location.trim(),
        'received_at': now,
        'note': note.trim(),
      });
      await txn.insert('pharmacy_stock_movements', {
        'batch_id': batchId, 'kind': 'receive', 'quantity_delta': quantity,
        'reference': 'GRN-$batchId', 'reason': 'Stock received', 'created_at': now,
      });
    });
  }

  Future<void> setBatchQuantity({required int batchId,
      required int newQuantity, required String reason}) async {
    if (newQuantity < 0) throw const FormatException('Quantity cannot be negative.');
    if (reason.trim().isEmpty) throw const FormatException('Enter an adjustment reason.');
    final d = await _db;
    await d.transaction((txn) async {
      final rows = await txn.query('pharmacy_stock_batches',
          columns: ['quantity'], where: 'id=?', whereArgs: [batchId], limit: 1);
      if (rows.isEmpty) throw StateError('Stock batch not found.');
      final oldQuantity = (rows.first['quantity'] as num).toInt();
      final delta = newQuantity - oldQuantity;
      if (delta == 0) return;
      await txn.update('pharmacy_stock_batches', {'quantity': newQuantity},
          where: 'id=?', whereArgs: [batchId]);
      await txn.insert('pharmacy_stock_movements', {
        'batch_id': batchId, 'kind': 'adjust', 'quantity_delta': delta,
        'reference': 'ADJ-$batchId-${DateTime.now().microsecondsSinceEpoch}',
        'reason': reason.trim(),
        'created_at': DateTime.now().millisecondsSinceEpoch,
      });
    });
  }

  Future<Map<String, Object?>> createSale({
    required List<Map<String, Object?>> lines,
    required double discount,
    required double paid,
    required String paymentMethod,
    String customer = '',
    String cashier = '',
    String note = '',
  }) async {
    if (lines.isEmpty) throw const FormatException('Add at least one item to the cart.');
    if (!discount.isFinite || !paid.isFinite || discount < 0 || paid < 0) {
      throw const FormatException('Discount and payment must be finite non-negative amounts.');
    }
    final d = await _db;
    final today = _dayStart();
    final now = DateTime.now().millisecondsSinceEpoch;
    final receipt = 'APH-${DateTime.now().microsecondsSinceEpoch}';
    return d.transaction((txn) async {
      final requested = <int, Map<String, Object?>>{};
      for (final line in lines) {
        final productId = (line['productId'] as num).toInt();
        final quantity = (line['quantity'] as num).toInt();
        final unitPrice = (line['unitPrice'] as num).toDouble();
        if (quantity <= 0 || !unitPrice.isFinite || unitPrice < 0) {
          throw const FormatException('Invalid cart quantity or price.');
        }
        final previous = requested[productId];
        if (previous == null) {
          requested[productId] = {'quantity': quantity, 'unitPrice': unitPrice};
        } else {
          previous['quantity'] = (previous['quantity'] as int) + quantity;
        }
      }

      var subtotal = 0.0;
      final products = <int, Map<String, Object?>>{};
      final batchesByProduct = <int, List<Map<String, Object?>>>{};
      for (final entry in requested.entries) {
        final product = await txn.rawQuery('''
          SELECT p.id, p.brand_name, p.generic_id, p.strength, p.dosage_form,
            g.name_en AS generic_name
          FROM products p JOIN generics g ON g.id=p.generic_id WHERE p.id=?
        ''', [entry.key]);
        if (product.isEmpty) throw StateError('A product in the cart was removed.');
        products[entry.key] = product.first;
        final batches = await txn.query('pharmacy_stock_batches',
            where: 'product_id=? AND quantity>0 AND expiry_at>=?',
            whereArgs: [entry.key, today],
            orderBy: 'expiry_at ASC, received_at ASC');
        final wanted = entry.value['quantity'] as int;
        final available = batches.fold<int>(0,
            (sum, batch) => sum + (batch['quantity'] as num).toInt());
        if (available < wanted) {
          final expired = await txn.rawQuery('''
            SELECT COALESCE(SUM(quantity),0) AS qty FROM pharmacy_stock_batches
            WHERE product_id=? AND quantity>0 AND expiry_at<?
          ''', [entry.key, today]);
          final expiredQty = (expired.first['qty'] as num? ?? 0).toInt();
          throw StateError(available == 0 && expiredQty > 0
              ? 'No sellable stock: all remaining units are expired.'
              : 'Insufficient stock. Available: $available, requested: $wanted.');
        }
        batchesByProduct[entry.key] = batches;
        subtotal += wanted * (entry.value['unitPrice'] as double);
      }
      subtotal = _money(subtotal);
      if (discount > subtotal) throw const FormatException('Discount cannot exceed subtotal.');
      final total = _money(subtotal - discount);
      final saleId = await txn.insert('pharmacy_sales', {
        'receipt_number': receipt, 'created_at': now, 'subtotal': subtotal,
        'discount': _money(discount), 'total': total, 'paid': _money(paid),
        'payment_method': paymentMethod, 'customer': customer.trim(),
        'cashier': cashier.trim(), 'note': note.trim(),
      });
      final savedItems = <Map<String, Object?>>[];
      for (final entry in requested.entries) {
        var remaining = entry.value['quantity'] as int;
        final unitPrice = entry.value['unitPrice'] as double;
        final product = products[entry.key]!;
        for (final batch in batchesByProduct[entry.key]!) {
          if (remaining == 0) break;
          final batchQty = (batch['quantity'] as num).toInt();
          final take = batchQty < remaining ? batchQty : remaining;
          final updated = await txn.rawUpdate('''
            UPDATE pharmacy_stock_batches SET quantity=quantity-?
            WHERE id=? AND quantity>=?
          ''', [take, batch['id'], take]);
          if (updated != 1) throw StateError('Stock changed during checkout; retry the sale.');
          final lineTotal = _money(take * unitPrice);
          final item = <String, Object?>{
            'sale_id': saleId,
            'batch_id': batch['id'],
            'product_id': entry.key,
            'generic_name': product['generic_name'],
            'brand_name': product['brand_name'],
            'strength': product['strength'] ?? '',
            'dosage_form': product['dosage_form'] ?? '',
            'batch_number': batch['batch_number'],
            'quantity': take,
            'unit_price': unitPrice,
            'unit_cost': batch['purchase_price'],
            'line_total': lineTotal,
          };
          final itemId = await txn.insert('pharmacy_sale_items', item);
          savedItems.add({'id': itemId, ...item});
          await txn.insert('pharmacy_stock_movements', {
            'batch_id': batch['id'], 'kind': 'sale', 'quantity_delta': -take,
            'reference': receipt, 'reason': 'Point-of-sale sale', 'created_at': now,
          });
          remaining -= take;
        }
      }
      return {
        'id': saleId,
        'receipt_number': receipt,
        'created_at': now,
        'subtotal': subtotal,
        'discount': _money(discount),
        'total': total,
        'paid': _money(paid),
        'due': _money((total - paid).clamp(0, double.infinity).toDouble()),
        'change': _money((paid - total).clamp(0, double.infinity).toDouble()),
        'payment_method': paymentMethod,
        'customer': customer.trim(),
        'items': savedItems,
      };
    });
  }

  Future<List<PharmacySale>> recentSales({int limit = 100}) async {
    final d = await _db;
    final rows = await d.query('pharmacy_sales', orderBy: 'created_at DESC', limit: limit);
    return rows.map(PharmacySale.fromMap).toList();
  }

  Future<Map<String, Object?>> saleDetails(int saleId) async {
    final d = await _db;
    final headers = await d.query('pharmacy_sales',
        where: 'id=?', whereArgs: [saleId], limit: 1);
    if (headers.isEmpty) throw StateError('Receipt not found.');
    final items = await d.query('pharmacy_sale_items',
        where: 'sale_id=?', whereArgs: [saleId], orderBy: 'id ASC');
    return {'sale': headers.first, 'items': items};
  }

  Future<List<Map<String, Object?>>> batchMovements(int batchId) async {
    final d = await _db;
    return d.query('pharmacy_stock_movements',
        where: 'batch_id=?', whereArgs: [batchId], orderBy: 'created_at DESC');
  }

  static double _money(double value) => (value * 100).roundToDouble() / 100;
}
