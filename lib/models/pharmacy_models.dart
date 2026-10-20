class PharmacyProduct {
  final int id;
  final int genericId;
  final String genericName;
  final String genericNameAr;
  final String brand;
  final String strength;
  final String form;
  final String barcode;
  final int availableQuantity;
  final double suggestedPrice;

  const PharmacyProduct({
    required this.id,
    required this.genericId,
    required this.genericName,
    required this.genericNameAr,
    required this.brand,
    required this.strength,
    required this.form,
    required this.barcode,
    required this.availableQuantity,
    required this.suggestedPrice,
  });

  factory PharmacyProduct.fromMap(Map<String, Object?> row) => PharmacyProduct(
        id: row['id'] as int,
        genericId: row['generic_id'] as int,
        genericName: (row['generic_name'] ?? '').toString(),
        genericNameAr: (row['generic_name_ar'] ?? '').toString(),
        brand: (row['brand_name'] ?? '').toString(),
        strength: (row['strength'] ?? '').toString(),
        form: (row['dosage_form'] ?? '').toString(),
        barcode: (row['barcode'] ?? '').toString(),
        availableQuantity: (row['available_quantity'] as num? ?? 0).toInt(),
        suggestedPrice: (row['suggested_price'] as num? ?? 0).toDouble(),
      );

  String get displayName => [brand, strength, form]
      .where((part) => part.trim().isNotEmpty)
      .join(' ');
}

class PharmacyBatch {
  final int id;
  final int productId;
  final String genericName;
  final String brand;
  final String strength;
  final String form;
  final String batchNumber;
  final String barcode;
  final int quantity;
  final int minimumStock;
  final double purchasePrice;
  final double salePrice;
  final int? expiryMillis;
  final String supplier;
  final String location;

  const PharmacyBatch({
    required this.id,
    required this.productId,
    required this.genericName,
    required this.brand,
    required this.strength,
    required this.form,
    required this.batchNumber,
    required this.barcode,
    required this.quantity,
    required this.minimumStock,
    required this.purchasePrice,
    required this.salePrice,
    required this.expiryMillis,
    required this.supplier,
    required this.location,
  });

  factory PharmacyBatch.fromMap(Map<String, Object?> row) => PharmacyBatch(
        id: row['id'] as int,
        productId: row['product_id'] as int,
        genericName: (row['generic_name'] ?? '').toString(),
        brand: (row['brand_name'] ?? '').toString(),
        strength: (row['strength'] ?? '').toString(),
        form: (row['dosage_form'] ?? '').toString(),
        batchNumber: (row['batch_number'] ?? '').toString(),
        barcode: (row['barcode'] ?? '').toString(),
        quantity: (row['quantity'] as num? ?? 0).toInt(),
        minimumStock: (row['minimum_stock'] as num? ?? 0).toInt(),
        purchasePrice: (row['purchase_price'] as num? ?? 0).toDouble(),
        salePrice: (row['sale_price'] as num? ?? 0).toDouble(),
        expiryMillis: (row['expiry_at'] as num?)?.toInt(),
        supplier: (row['supplier'] ?? '').toString(),
        location: (row['location'] ?? '').toString(),
      );

  DateTime? get expiry => expiryMillis == null
      ? null
      : DateTime.fromMillisecondsSinceEpoch(expiryMillis!);
}

class PharmacySale {
  final int id;
  final String receiptNumber;
  final int createdAt;
  final double subtotal;
  final double discount;
  final double total;
  final double paid;
  final String paymentMethod;
  final String customer;

  const PharmacySale({
    required this.id,
    required this.receiptNumber,
    required this.createdAt,
    required this.subtotal,
    required this.discount,
    required this.total,
    required this.paid,
    required this.paymentMethod,
    required this.customer,
  });

  factory PharmacySale.fromMap(Map<String, Object?> row) => PharmacySale(
        id: row['id'] as int,
        receiptNumber: (row['receipt_number'] ?? '').toString(),
        createdAt: (row['created_at'] as num? ?? 0).toInt(),
        subtotal: (row['subtotal'] as num? ?? 0).toDouble(),
        discount: (row['discount'] as num? ?? 0).toDouble(),
        total: (row['total'] as num? ?? 0).toDouble(),
        paid: (row['paid'] as num? ?? 0).toDouble(),
        paymentMethod: (row['payment_method'] ?? 'cash').toString(),
        customer: (row['customer'] ?? '').toString(),
      );

  double get due => (total - paid).clamp(0, double.infinity).toDouble();
}
