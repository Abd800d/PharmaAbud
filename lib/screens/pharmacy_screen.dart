import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../app_settings.dart';
import '../models/pharmacy_models.dart';
import '../services/pharmacy_service.dart';

const _teal = Color(0xFF14C8B4);
const _currency = 'YER';

String _money(num value) => '${value.toStringAsFixed(value % 1 == 0 ? 0 : 2)} $_currency';

class PharmacyScreen extends StatelessWidget {
  const PharmacyScreen({super.key});

  @override
  Widget build(BuildContext context) => DefaultTabController(
        length: 4,
        child: Scaffold(
          appBar: AppBar(
            title: Text(S.t('Pharmacy operations', 'إدارة الصيدلية')),
            bottom: TabBar(isScrollable: true, tabs: [
              Tab(icon: const Icon(Icons.dashboard_outlined), text: S.t('Overview', 'الملخص')),
              Tab(icon: const Icon(Icons.inventory_2_outlined), text: S.t('Inventory', 'المخزون')),
              Tab(icon: const Icon(Icons.point_of_sale), text: S.t('New sale', 'بيع جديد')),
              Tab(icon: const Icon(Icons.receipt_long), text: S.t('Sales', 'المبيعات')),
            ]),
          ),
          body: const TabBarView(children: [
            _PharmacyOverview(),
            _InventoryTab(),
            _PointOfSaleTab(),
            _SalesTab(),
          ]),
        ),
      );
}

class _PharmacyOverview extends StatefulWidget {
  const _PharmacyOverview();
  @override
  State<_PharmacyOverview> createState() => _PharmacyOverviewState();
}

class _PharmacyOverviewState extends State<_PharmacyOverview> {
  late Future<Map<String, num>> _summary;

  @override
  void initState() {
    super.initState();
    _summary = PharmacyService.instance.summary();
  }

  void _refresh() => setState(() => _summary = PharmacyService.instance.summary());

  @override
  Widget build(BuildContext context) => RefreshIndicator(
        onRefresh: () async => _refresh(),
        child: ListView(padding: const EdgeInsets.all(14), children: [
          Card(color: const Color(0xFF0E2F40), child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                const CircleAvatar(backgroundColor: _teal,
                    child: Icon(Icons.local_pharmacy, color: Color(0xFF04222B))),
                const SizedBox(width: 10),
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(S.t('Pharmacy desk', 'لوحة الصيدلية'),
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 17)),
                  Text(S.t('Offline-first stock and point of sale',
                      'مخزون ونقطة بيع يعملان دون إنترنت'),
                      style: const TextStyle(color: Colors.white70, fontSize: 12)),
                ])),
              ]),
              const SizedBox(height: 12),
              Text(S.t('Stock, batches, expiry and sales are kept separately from the reference drug catalogue.',
                  'المخزون والدفعات والصلاحية والمبيعات محفوظة بمعزل عن قاعدة المعلومات الدوائية.'),
                  style: const TextStyle(fontSize: 11, height: 1.6, color: Colors.white70)),
            ]),
          )),
          FutureBuilder<Map<String, num>>(
            future: _summary,
            builder: (context, snapshot) {
              if (snapshot.hasError) return _errorCard(snapshot.error.toString(), _refresh);
              if (!snapshot.hasData) return const Padding(
                  padding: EdgeInsets.all(28), child: Center(child: CircularProgressIndicator()));
              final s = snapshot.data!;
              return GridView.count(
                shrinkWrap: true, physics: const NeverScrollableScrollPhysics(),
                crossAxisCount: 2, childAspectRatio: 1.5, crossAxisSpacing: 8, mainAxisSpacing: 8,
                children: [
                  _MetricCard(icon: Icons.inventory_2, color: _teal,
                      label: S.t('Sellable units', 'وحدات صالحة للبيع'), value: '${s['units']?.toInt() ?? 0}'),
                  _MetricCard(icon: Icons.warning_amber, color: Colors.orangeAccent,
                      label: S.t('Low-stock products', 'أدوية دون حدّ المخزون'), value: '${s['low_products']?.toInt() ?? 0}'),
                  _MetricCard(icon: Icons.event_busy, color: Colors.redAccent,
                      label: S.t('Expired units', 'وحدات منتهية الصلاحية'), value: '${s['expired_units']?.toInt() ?? 0}'),
                  _MetricCard(icon: Icons.hourglass_bottom, color: Colors.amber,
                      label: S.t('Expiring within 30 days', 'تنتهي خلال 30 يوماً'), value: '${s['expiring_units']?.toInt() ?? 0}'),
                  _MetricCard(icon: Icons.account_balance_wallet, color: Colors.lightBlueAccent,
                      label: S.t('Stock cost value', 'قيمة المخزون بالتكلفة'), value: _money(s['inventory_value'] ?? 0)),
                  _MetricCard(icon: Icons.trending_up, color: Colors.lightGreenAccent,
                      label: S.t("Today's gross profit", 'مجمل الربح اليوم'), value: _money(s['today_profit'] ?? 0),
                      footnote: S.t('Before expenses and tax', 'قبل المصروفات والضرائب')),
                  _MetricCard(icon: Icons.point_of_sale, color: _teal,
                      label: S.t("Today's sales", 'مبيعات اليوم'), value: _money(s['today_sales'] ?? 0),
                      footnote: '${s['today_receipts']?.toInt() ?? 0} ${S.t('receipts', 'فاتورة')}'),
                ],
              );
            },
          ),
          const SizedBox(height: 8),
          Card(child: Padding(padding: const EdgeInsets.all(12), child: Text(
            S.t('Safe dispensing reminder: verify the prescription, patient, strength, dosage form, directions, allergies and local rules. This tool does not calculate doses or replace a licensed pharmacist.',
              'تذكير للصرف الآمن: تحقّق من الوصفة والمريض والتركيز والشكل والتعليمات والحساسيات والأنظمة المحلية. لا تحسب هذه الأداة الجرعات ولا تحل محل الصيدلي المرخّص.'),
            style: const TextStyle(fontSize: 11, height: 1.7, color: Color(0xFFFDE68A)),
          ))),
          const SizedBox(height: 8),
          Wrap(spacing: 8, runSpacing: 8, children: [
            FilledButton.icon(onPressed: () => DefaultTabController.of(context).animateTo(2),
                icon: const Icon(Icons.add_shopping_cart), label: Text(S.t('Start a sale', 'بدء عملية بيع'))),
            OutlinedButton.icon(onPressed: () => DefaultTabController.of(context).animateTo(1),
                icon: const Icon(Icons.add_box_outlined), label: Text(S.t('Receive stock', 'إضافة مخزون'))),
          ]),
        ]),
      );
}

class _MetricCard extends StatelessWidget {
  final IconData icon;
  final Color color;
  final String label, value;
  final String footnote;
  const _MetricCard({required this.icon, required this.color,
      required this.label, required this.value, this.footnote = ''});
  @override
  Widget build(BuildContext context) => Card(child: Padding(
    padding: const EdgeInsets.all(11), child: Column(
      crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Row(children: [Icon(icon, color: color, size: 18), const SizedBox(width: 6),
          Expanded(child: Text(label, maxLines: 2, overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 10, color: Colors.white70))) ]),
        const SizedBox(height: 7),
        FittedBox(alignment: AlignmentDirectional.centerStart, fit: BoxFit.scaleDown,
          child: Text(value, style: TextStyle(fontSize: 19, fontWeight: FontWeight.bold, color: color))),
        if (footnote.isNotEmpty) Text(footnote, style: const TextStyle(fontSize: 9, color: Colors.white54)),
      ],
    ),
  ));
}

class _InventoryTab extends StatefulWidget {
  const _InventoryTab();
  @override
  State<_InventoryTab> createState() => _InventoryTabState();
}

class _InventoryTabState extends State<_InventoryTab> {
  final _search = TextEditingController();
  Timer? _debounce;
  List<PharmacyBatch> _rows = [];
  String _filter = 'all';
  bool _loading = true;
  String _error = '';

  @override
  void initState() { super.initState(); _load(); }
  @override
  void dispose() { _debounce?.cancel(); _search.dispose(); super.dispose(); }

  Future<void> _load() async {
    setState(() { _loading = true; _error = ''; });
    try {
      final maps = await PharmacyService.instance.stockBatches(query: _search.text, filter: _filter);
      if (mounted) setState(() { _rows = maps.map(PharmacyBatch.fromMap).toList(); _loading = false; });
    } catch (e) { if (mounted) setState(() { _error = e.toString(); _loading = false; }); }
  }

  void _searchChanged(String _) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 250), _load);
  }

  bool _requireInventoryAdmin() {
    if (AppSettings.isAdmin.value) return true;
    _snack(context, S.t('Enable Admin mode in More before receiving or adjusting stock.',
        'فعّل وضع الإدارة من «المزيد» قبل استلام المخزون أو تسويته.'));
    return false;
  }

  Future<void> _addStock() async {
    if (!_requireInventoryAdmin()) return;
    final added = await showModalBottomSheet<bool>(context: context, isScrollControlled: true,
        backgroundColor: const Color(0xFF0B2634), builder: (_) => const _AddStockSheet());
    if (added == true && mounted) await _load();
  }

  Future<void> _adjust(PharmacyBatch batch) async {
    if (!_requireInventoryAdmin()) return;
    final qty = TextEditingController(text: '${batch.quantity}');
    final reason = TextEditingController();
    final result = await showDialog<bool>(context: context, builder: (dialogContext) => AlertDialog(
      title: Text(S.t('Adjust stock', 'تسوية كمية المخزون')),
      content: Column(mainAxisSize: MainAxisSize.min, children: [
        Text('${batch.brand} • ${S.t('Batch', 'الدفعة')}: ${batch.batchNumber}'),
        TextField(controller: qty, keyboardType: TextInputType.number,
            inputFormatters: [FilteringTextInputFormatter.digitsOnly],
            decoration: InputDecoration(labelText: S.t('New physical quantity', 'الكمية الفعلية الجديدة'))),
        TextField(controller: reason, decoration: InputDecoration(labelText: S.t('Reason (required)', 'سبب التسوية (مطلوب)'))),
      ]),
      actions: [
        TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: Text(S.t('Cancel', 'إلغاء'))),
        FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: Text(S.t('Save adjustment', 'حفظ التسوية'))),
      ],
    ));
    if (result == true && mounted) {
      try {
        await PharmacyService.instance.setBatchQuantity(batchId: batch.id,
            newQuantity: int.parse(qty.text), reason: reason.text);
        await _load();
      } catch (e) { if (mounted) _snack(context, e.toString()); }
    }
    qty.dispose(); reason.dispose();
  }

  @override
  Widget build(BuildContext context) => Column(children: [
    Padding(padding: const EdgeInsets.fromLTRB(12, 12, 12, 4), child: Row(children: [
      Expanded(child: TextField(controller: _search, onChanged: _searchChanged,
        decoration: InputDecoration(prefixIcon: const Icon(Icons.search),
          hintText: S.t('Search product, lot, barcode or supplier', 'ابحث عن منتج أو دفعة أو باركود أو مورد'),
          border: const OutlineInputBorder(), isDense: true))),
      const SizedBox(width: 7),
      IconButton.filled(onPressed: _addStock, icon: const Icon(Icons.add_box),
          tooltip: S.t('Receive new stock', 'استلام مخزون جديد')),
    ])),
    SizedBox(height: 47, child: ListView(scrollDirection: Axis.horizontal, padding: const EdgeInsets.symmetric(horizontal: 8), children: [
      for (final item in [
        ('all', S.t('All', 'الكل')), ('low', S.t('Low stock', 'منخفض')), 
        ('expiring', S.t('Expiring soon', 'قريب الانتهاء')), ('expired', S.t('Expired', 'منتهي')),
      ]) Padding(padding: const EdgeInsets.symmetric(horizontal: 3), child: ChoiceChip(
        label: Text(item.$2), selected: _filter == item.$1,
        onSelected: (_) { setState(() => _filter = item.$1); _load(); },
      )),
    ])),
    Expanded(child: _loading ? const Center(child: CircularProgressIndicator())
      : _error.isNotEmpty ? _errorCard(_error, _load)
      : _rows.isEmpty ? _empty(S.t('No stock recorded yet. Add a product batch to start.', 'لا يوجد مخزون مسجّل. أضف دفعة دوائية للبدء.'), Icons.inventory_2_outlined)
      : RefreshIndicator(onRefresh: _load, child: ListView.builder(
        padding: const EdgeInsets.fromLTRB(10, 4, 10, 16), itemCount: _rows.length,
        itemBuilder: (_, i) => _BatchTile(batch: _rows[i], onTap: () => _adjust(_rows[i]))))),
  ]);
}

class _BatchTile extends StatelessWidget {
  final PharmacyBatch batch;
  final VoidCallback onTap;
  const _BatchTile({required this.batch, required this.onTap});
  @override
  Widget build(BuildContext context) {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final expiry = batch.expiry;
    final expired = expiry != null && expiry.isBefore(today);
    final soon = expiry != null && !expired && expiry.isBefore(today.add(const Duration(days: 31)));
    final low = batch.quantity <= batch.minimumStock;
    final color = expired ? Colors.redAccent : soon ? Colors.orangeAccent : low ? Colors.amber : _teal;
    final status = expired ? S.t('EXPIRED — DO NOT DISPENSE', 'منتهي — يُمنع صرفه')
        : soon ? S.t('Expiring soon', 'قريب الانتهاء')
        : low ? S.t('Low stock', 'مخزون منخفض') : S.t('In stock', 'متوفر');
    return Card(child: ListTile(
      onTap: onTap,
      leading: CircleAvatar(backgroundColor: color.withValues(alpha: .16),
          child: Text('${batch.quantity}', style: TextStyle(color: color, fontWeight: FontWeight.bold))),
      title: Text('${batch.brand} ${batch.strength}', maxLines: 1, overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontWeight: FontWeight.bold)),
      subtitle: Text('${batch.genericName} • ${batch.form}\n'
          '${S.t('Lot', 'الدفعة')}: ${batch.batchNumber}  •  ${S.t('Exp', 'الصلاحية')}: ${expiry == null ? '—' : _date(expiry)}\n'
          '${S.t('Sell', 'البيع')}: ${_money(batch.salePrice)}  •  ${S.t('Cost', 'التكلفة')}: ${_money(batch.purchasePrice)}',
          maxLines: 3, style: const TextStyle(fontSize: 10, height: 1.45)),
      isThreeLine: true,
      trailing: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
        Icon(expired ? Icons.block : low || soon ? Icons.warning_amber : Icons.check_circle_outline, color: color, size: 18),
        const SizedBox(height: 3),
        Text(status, textAlign: TextAlign.center, style: TextStyle(color: color, fontSize: 8, fontWeight: FontWeight.bold)),
      ]),
    ));
  }
}

class _AddStockSheet extends StatefulWidget {
  const _AddStockSheet();
  @override
  State<_AddStockSheet> createState() => _AddStockSheetState();
}

class _AddStockSheetState extends State<_AddStockSheet> {
  final _search = TextEditingController();
  final _form = GlobalKey<FormState>();
  final _lot = TextEditingController();
  final _barcode = TextEditingController();
  final _qty = TextEditingController(text: '1');
  final _min = TextEditingController(text: '5');
  final _cost = TextEditingController(text: '0');
  final _price = TextEditingController(text: '0');
  final _supplier = TextEditingController();
  final _location = TextEditingController();
  Timer? _debounce;
  List<PharmacyProduct> _products = [];
  PharmacyProduct? _selected;
  DateTime? _expiry;
  bool _loading = false;
  bool _saving = false;
  String _error = '';

  @override
  void initState() { super.initState(); _findProducts(''); }
  @override
  void dispose() {
    _debounce?.cancel(); _search.dispose(); _lot.dispose(); _barcode.dispose(); _qty.dispose();
    _min.dispose(); _cost.dispose(); _price.dispose(); _supplier.dispose(); _location.dispose(); super.dispose();
  }

  Future<void> _findProducts(String query) async {
    setState(() { _loading = true; _error = ''; });
    try {
      final rows = await PharmacyService.instance.searchProducts(query, limit: 60);
      if (mounted) setState(() { _products = rows.map(PharmacyProduct.fromMap).toList(); _loading = false; });
    } catch (e) { if (mounted) setState(() { _error = e.toString(); _loading = false; }); }
  }

  Future<void> _pickExpiry() async {
    final now = DateTime.now();
    final result = await showDatePicker(context: context,
      initialDate: _expiry ?? DateTime(now.year + 1, now.month, now.day),
      firstDate: DateTime(now.year, now.month, now.day),
      lastDate: DateTime(now.year + 20),
      helpText: S.t('Select printed expiry date', 'اختر تاريخ الصلاحية المطبوع'));
    if (result != null && mounted) setState(() => _expiry = result);
  }

  Future<void> _save() async {
    if (_selected == null) { setState(() => _error = S.t('Select a catalogue product first.', 'اختر منتجاً من القاعدة أولاً.')); return; }
    if (!_form.currentState!.validate()) return;
    if (_expiry == null) { setState(() => _error = S.t('Expiry date is required for traceability.', 'تاريخ الصلاحية مطلوب لتتبّع الدفعة.')); return; }
    setState(() { _saving = true; _error = ''; });
    try {
      await PharmacyService.instance.addStockBatch(
        productId: _selected!.id, batchNumber: _lot.text, barcode: _barcode.text,
        quantity: int.parse(_qty.text), minimumStock: int.parse(_min.text),
        purchasePrice: double.parse(_cost.text), salePrice: double.parse(_price.text),
        expiry: _expiry!, supplier: _supplier.text, location: _location.text);
      if (mounted) Navigator.pop(context, true);
    } catch (e) { if (mounted) setState(() { _saving = false; _error = e.toString(); }); }
  }

  String? _required(String? v) => v == null || v.trim().isEmpty ? S.t('Required', 'مطلوب') : null;
  String? _number(String? v, {bool integer = false, bool allowZero = false}) {
    if (_required(v) != null) return _required(v);
    final n = integer ? int.tryParse(v!) : double.tryParse(v!);
    if (n == null || !n.isFinite || n < 0) return S.t('Enter a valid non-negative number', 'أدخل رقماً صحيحاً غير سالب');
    if (integer && !allowZero && int.tryParse(v) == 0) return S.t('Must be greater than zero', 'يجب أن يكون أكبر من صفر');
    return null;
  }

  @override
  Widget build(BuildContext context) => Padding(
    padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
    child: SafeArea(child: SizedBox(height: (MediaQuery.sizeOf(context).height - MediaQuery.viewInsetsOf(context).bottom) * .88,
      child: Column(children: [
        Padding(padding: const EdgeInsets.all(14), child: Row(children: [
          Expanded(child: Text(S.t('Receive medicine stock', 'استلام مخزون دوائي'), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold))),
          IconButton(onPressed: () => Navigator.pop(context), icon: const Icon(Icons.close)),
        ])),
        if (_selected == null) ...[
          Padding(padding: const EdgeInsets.symmetric(horizontal: 12), child: TextField(
            controller: _search, onChanged: (v) { _debounce?.cancel(); _debounce = Timer(const Duration(milliseconds: 250), () => _findProducts(v)); },
            decoration: InputDecoration(prefixIcon: const Icon(Icons.search),
              hintText: S.t('Find brand, generic or barcode', 'ابحث بالاسم التجاري أو العلمي أو الباركود'), border: const OutlineInputBorder(), isDense: true))),
          if (_error.isNotEmpty) Padding(padding: const EdgeInsets.all(8), child: Text(_error, style: const TextStyle(color: Colors.orangeAccent))),
          Expanded(child: _loading ? const Center(child: CircularProgressIndicator()) : ListView.builder(
            itemCount: _products.length, itemBuilder: (_, i) {
              final p = _products[i];
              return ListTile(dense: true, title: Text(p.displayName),
                subtitle: Text('${p.genericName} • ${p.availableQuantity} ${S.t('in stock', 'بالمخزون')}'),
                trailing: const Icon(Icons.add_circle_outline, color: _teal),
                onTap: () => setState(() { _selected = p; if (p.suggestedPrice > 0) _price.text = p.suggestedPrice.toStringAsFixed(2); }));
            })),
        ] else Expanded(child: Form(key: _form, child: ListView(padding: const EdgeInsets.symmetric(horizontal: 14), children: [
          Card(child: ListTile(leading: const Icon(Icons.medication, color: _teal), title: Text(_selected!.displayName), subtitle: Text(_selected!.genericName), trailing: TextButton(onPressed: () => setState(() => _selected = null), child: Text(S.t('Change', 'تغيير'))))),
          const SizedBox(height: 8),
          TextFormField(controller: _lot, validator: _required, decoration: InputDecoration(labelText: S.t('Batch / lot number *', 'رقم التشغيلة *'))),
          TextFormField(controller: _barcode, keyboardType: TextInputType.number, decoration: InputDecoration(labelText: S.t('Barcode (optional)', 'الباركود (اختياري)'), helperText: S.t('A handheld scanner can type into this field.', 'يمكن لقارئ الباركود الكتابة في هذا الحقل.'))),
          Row(children: [
            Expanded(child: TextFormField(
              controller: _qty, validator: (v) => _number(v, integer: true),
              keyboardType: TextInputType.number,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              decoration: InputDecoration(labelText: S.t('Quantity *', 'الكمية *')),
            )),
            const SizedBox(width: 8),
            Expanded(child: TextFormField(
              controller: _min, validator: (v) => _number(v, integer: true, allowZero: true),
              keyboardType: TextInputType.number,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              decoration: InputDecoration(labelText: S.t('Reorder threshold', 'حد التنبيه')),
            )),
          ]),
          Row(children: [
            Expanded(child: TextFormField(controller: _cost, validator: _number,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: InputDecoration(labelText: S.t('Purchase cost / unit', 'تكلفة الشراء للوحدة')))),
            const SizedBox(width: 8),
            Expanded(child: TextFormField(controller: _price, validator: _number,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: InputDecoration(labelText: S.t('Retail price / unit', 'سعر البيع للوحدة')))),
          ]),
          const SizedBox(height: 8),
          OutlinedButton.icon(onPressed: _pickExpiry, icon: const Icon(Icons.event), label: Text(_expiry == null ? S.t('Set expiry date *', 'حدد تاريخ الصلاحية *') : '${S.t('Expiry', 'الصلاحية')}: ${_date(_expiry!)}')),
          TextFormField(controller: _supplier, decoration: InputDecoration(labelText: S.t('Supplier', 'المورد'))),
          TextFormField(controller: _location, decoration: InputDecoration(labelText: S.t('Shelf / location', 'الرف / الموقع'))),
          if (_error.isNotEmpty) Padding(padding: const EdgeInsets.symmetric(vertical: 8), child: Text(_error, style: const TextStyle(color: Colors.orangeAccent))),
          const SizedBox(height: 12),
          FilledButton.icon(onPressed: _saving ? null : _save, icon: _saving ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.save), label: Text(S.t('Save batch and stock movement', 'حفظ الدفعة وحركة المخزون'))),
          const SizedBox(height: 16),
        ]))),
      ]))),
  );
}

class _PointOfSaleTab extends StatefulWidget {
  const _PointOfSaleTab();
  @override
  State<_PointOfSaleTab> createState() => _PointOfSaleTabState();
}

class _PointOfSaleTabState extends State<_PointOfSaleTab> {
  final _search = TextEditingController();
  final _discount = TextEditingController(text: '0');
  final _paid = TextEditingController(text: '0');
  final _customer = TextEditingController();
  Timer? _debounce;
  List<PharmacyProduct> _products = [];
  final Map<int, _CartItem> _cart = {};
  String _payment = 'cash';
  bool _loading = true;
  bool _saving = false;
  String _error = '';
  bool _paidEdited = false;

  @override
  void initState() { super.initState(); _find(''); }
  @override
  void dispose() { _debounce?.cancel(); _search.dispose(); _discount.dispose(); _paid.dispose(); _customer.dispose(); super.dispose(); }

  Future<void> _find(String q) async {
    setState(() => _loading = true);
    try {
      final rows = await PharmacyService.instance.searchProducts(q, limit: 80);
      if (mounted) setState(() { _products = rows.map(PharmacyProduct.fromMap).toList(); _loading = false; });
    } catch (e) { if (mounted) setState(() { _loading = false; _error = e.toString(); }); }
  }

  double get _subtotal => _cart.values.fold(0, (sum, item) => sum + item.quantity * item.unitPrice);
  double get _discountValue => double.tryParse(_discount.text) ?? 0;
  double get _total => (_subtotal - _discountValue).clamp(0, double.infinity).toDouble();

  void _add(PharmacyProduct product) {
    if (product.availableQuantity <= 0) return;
    setState(() {
      final item = _cart[product.id];
      if (item == null) _cart[product.id] = _CartItem(product: product, quantity: 1, unitPrice: product.suggestedPrice);
      else if (item.quantity < product.availableQuantity) item.quantity++;
      _error = '';
      if (!_paidEdited) _paid.text = _total.toStringAsFixed(2);
    });
  }

  Future<void> _changePrice(_CartItem item) async {
    final c = TextEditingController(text: item.unitPrice.toStringAsFixed(2));
    final value = await showDialog<double>(context: context, builder: (context) => AlertDialog(
      title: Text(S.t('Set sale price', 'تحديد سعر البيع')),
      content: TextField(controller: c, autofocus: true, keyboardType: const TextInputType.numberWithOptions(decimal: true), decoration: InputDecoration(labelText: _currency)),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: Text(S.t('Cancel', 'إلغاء'))),
        FilledButton(onPressed: () {
          final n = double.tryParse(c.text);
          if (n != null && n >= 0) Navigator.pop(context, n);
        }, child: Text(S.t('Save', 'حفظ'))),
      ],
    ));
    c.dispose();
    if (!mounted) return;
    if (value != null) setState(() { item.unitPrice = value; if (!_paidEdited) _paid.text = _total.toStringAsFixed(2); });
  }

  Future<void> _checkout() async {
    if (_cart.isEmpty) return;
    final discount = double.tryParse(_discount.text);
    final paid = double.tryParse(_paid.text);
    if (discount == null || !discount.isFinite || discount < 0 ||
        paid == null || !paid.isFinite || paid < 0) {
      setState(() => _error = S.t('Enter valid discount and payment amounts.',
          'أدخل مبلغ خصم ومبلغ مدفوع صحيحين.'));
      return;
    }
    setState(() { _saving = true; _error = ''; });
    try {
      final result = await PharmacyService.instance.createSale(
        lines: _cart.values.map((item) => <String, Object?>{
          'productId': item.product.id, 'quantity': item.quantity, 'unitPrice': item.unitPrice,
        }).toList(),
        discount: _discountValue,
        paid: double.tryParse(_paid.text) ?? 0,
        paymentMethod: _payment,
        customer: _customer.text,
      );
      if (!mounted) return;
      setState(() { _cart.clear(); _discount.text = '0'; _paid.text = '0'; _paidEdited = false; _customer.clear(); _saving = false; });
      await _showReceipt(result);
      if (mounted) await _find(_search.text);
    } catch (e) { if (mounted) setState(() { _saving = false; _error = e.toString(); }); }
  }

  Future<void> _showReceipt(Map<String, Object?> sale) async {
    final items = (sale['items'] as List).cast<Map<String, Object?>>();
    final text = _receiptText(sale, items);
    await showDialog<void>(context: context, builder: (context) => AlertDialog(
      title: Text(S.t('Sale completed', 'اكتمل البيع')),
      content: SingleChildScrollView(child: SelectableText(text, textDirection: TextDirection.ltr)),
      actions: [
        TextButton.icon(onPressed: () async { await Clipboard.setData(ClipboardData(text: text)); if (context.mounted) Navigator.pop(context); }, icon: const Icon(Icons.copy), label: Text(S.t('Copy receipt', 'نسخ الفاتورة'))),
        FilledButton(onPressed: () => Navigator.pop(context), child: Text(S.t('Done', 'تم'))),
      ],
    ));
  }

  @override
  Widget build(BuildContext context) => Column(children: [
    Padding(padding: const EdgeInsets.fromLTRB(10, 10, 10, 5), child: TextField(
      controller: _search, onChanged: (v) { _debounce?.cancel(); _debounce = Timer(const Duration(milliseconds: 250), () => _find(v)); },
      decoration: InputDecoration(prefixIcon: const Icon(Icons.search), hintText: S.t('Product name, generic or barcode', 'اسم المنتج أو المادة أو الباركود'), border: const OutlineInputBorder(), isDense: true))),
    SizedBox(height: 150, child: _loading ? const Center(child: CircularProgressIndicator()) : ListView.builder(
      itemCount: _products.length, itemBuilder: (_, i) {
        final p = _products[i];
        return ListTile(dense: true, title: Text(p.displayName, maxLines: 1, overflow: TextOverflow.ellipsis),
          subtitle: Text('${p.genericName} • ${S.t('Available', 'المتاح')}: ${p.availableQuantity} • ${_money(p.suggestedPrice)}'),
          trailing: IconButton(onPressed: p.availableQuantity <= 0 ? null : () => _add(p), icon: const Icon(Icons.add_circle, color: _teal)),
          onTap: p.availableQuantity <= 0 ? null : () => _add(p));
      })),
    const Divider(height: 1),
    Expanded(child: _cart.isEmpty ? _empty(S.t('Search and add products to build the sale.', 'ابحث عن المنتجات وأضفها إلى الفاتورة.'), Icons.shopping_cart_outlined)
      : ListView(padding: const EdgeInsets.symmetric(horizontal: 8), children: [
        for (final item in _cart.values) Card(child: ListTile(
          dense: true, title: Text(item.product.displayName, maxLines: 1, overflow: TextOverflow.ellipsis),
          subtitle: InkWell(onTap: () => _changePrice(item), child: Text('${item.quantity} × ${_money(item.unitPrice)} = ${_money(item.quantity * item.unitPrice)}  ✎', style: const TextStyle(color: _teal))),
          trailing: SizedBox(width: 126, child: Row(mainAxisAlignment: MainAxisAlignment.end, children: [
            IconButton(visualDensity: VisualDensity.compact, onPressed: () => setState(() { if (item.quantity <= 1) _cart.remove(item.product.id); else item.quantity--; }), icon: const Icon(Icons.remove_circle_outline)),
            Text('${item.quantity}'),
            IconButton(visualDensity: VisualDensity.compact, onPressed: item.quantity >= item.product.availableQuantity ? null : () => setState(() => item.quantity++), icon: const Icon(Icons.add_circle_outline)),
          ])),
        )),
      ])),
    if (_error.isNotEmpty) Container(width: double.infinity, padding: const EdgeInsets.all(8), color: Colors.red.withValues(alpha: .12), child: Text(_error, style: const TextStyle(color: Colors.orangeAccent, fontSize: 11))),
    if (_cart.isNotEmpty) Container(color: const Color(0xFF0A2735), padding: const EdgeInsets.fromLTRB(12, 5, 12, 10), child: Column(children: [
      Row(children: [Expanded(child: Text(S.t('Subtotal', 'الإجمالي قبل الخصم'))), Text(_money(_subtotal))]),
      Row(children: [Expanded(child: TextField(controller: _discount, onChanged: (_) => setState(() { if (!_paidEdited) _paid.text = _total.toStringAsFixed(2); }), keyboardType: const TextInputType.numberWithOptions(decimal: true), decoration: InputDecoration(labelText: S.t('Discount', 'الخصم'), isDense: true))), const SizedBox(width: 12), Text(_money(_total), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: _teal))]),
      Row(children: [Expanded(child: TextField(controller: _customer, decoration: InputDecoration(labelText: S.t('Customer (optional)', 'العميل (اختياري)'), isDense: true))), const SizedBox(width: 8), DropdownButton<String>(value: _payment, items: [
        DropdownMenuItem(value: 'cash', child: Text(S.t('Cash', 'نقداً'))),
        DropdownMenuItem(value: 'card', child: Text(S.t('Card', 'بطاقة'))),
        DropdownMenuItem(value: 'mobile', child: Text(S.t('Mobile pay', 'دفع إلكتروني'))),
        DropdownMenuItem(value: 'credit', child: Text(S.t('Credit', 'آجل'))),
      ], onChanged: (v) { setState(() { _payment = v ?? 'cash'; if (_payment == 'credit') { _paid.text = '0'; _paidEdited = true; } else if (!_paidEdited) _paid.text = _total.toStringAsFixed(2); }); })]),
      Row(children: [Expanded(child: TextField(controller: _paid, onChanged: (_) => setState(() => _paidEdited = true), keyboardType: const TextInputType.numberWithOptions(decimal: true), decoration: InputDecoration(labelText: S.t('Amount received', 'المبلغ المقبوض'), isDense: true))), const SizedBox(width: 8), FilledButton.icon(onPressed: _saving ? null : _checkout, icon: _saving ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.check), label: Text(S.t('Complete sale', 'إتمام البيع')))]),
      Text(S.t('Due: ${_money((_total - (double.tryParse(_paid.text) ?? 0)).clamp(0, double.infinity))}  •  Change: ${_money(((double.tryParse(_paid.text) ?? 0) - _total).clamp(0, double.infinity))}', 'المتبقي: ${_money((_total - (double.tryParse(_paid.text) ?? 0)).clamp(0, double.infinity))}  •  الباقي: ${_money(((double.tryParse(_paid.text) ?? 0) - _total).clamp(0, double.infinity))}'), style: const TextStyle(fontSize: 10, color: Colors.white60)),
    ])),
  ]);
}

class _CartItem {
  final PharmacyProduct product;
  int quantity;
  double unitPrice;
  _CartItem({required this.product, required this.quantity, required this.unitPrice});
}

class _SalesTab extends StatefulWidget {
  const _SalesTab();
  @override
  State<_SalesTab> createState() => _SalesTabState();
}

class _SalesTabState extends State<_SalesTab> {
  late Future<List<PharmacySale>> _future;
  @override
  void initState() { super.initState(); _future = PharmacyService.instance.recentSales(); }
  Future<void> _reload() async => setState(() => _future = PharmacyService.instance.recentSales());

  Future<void> _open(PharmacySale sale) async {
    final data = await PharmacyService.instance.saleDetails(sale.id);
    final header = data['sale']! as Map<String, Object?>;
    final items = (data['items'] as List).cast<Map<String, Object?>>();
    final text = _receiptText(header, items);
    if (!mounted) return;
    await showDialog<void>(context: context, builder: (context) => AlertDialog(
      title: Text(sale.receiptNumber),
      content: SingleChildScrollView(child: SelectableText(text, textDirection: TextDirection.ltr)),
      actions: [TextButton.icon(onPressed: () async { await Clipboard.setData(ClipboardData(text: text)); if (context.mounted) Navigator.pop(context); }, icon: const Icon(Icons.copy), label: Text(S.t('Copy', 'نسخ'))), TextButton(onPressed: () => Navigator.pop(context), child: Text(S.t('Close', 'إغلاق')))],
    ));
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<List<PharmacySale>>(
    future: _future, builder: (context, snapshot) {
      if (snapshot.hasError) return _errorCard(snapshot.error.toString(), _reload);
      if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
      final sales = snapshot.data!;
      if (sales.isEmpty) return _empty(S.t('Completed sales will appear here.', 'ستظهر المبيعات المكتملة هنا.'), Icons.receipt_long);
      return RefreshIndicator(onRefresh: _reload, child: ListView.builder(padding: const EdgeInsets.all(10), itemCount: sales.length,
        itemBuilder: (_, i) {
          final sale = sales[i];
          final date = DateTime.fromMillisecondsSinceEpoch(sale.createdAt);
          return Card(child: ListTile(onTap: () => _open(sale), leading: const CircleAvatar(child: Icon(Icons.receipt)),
            title: Text(sale.receiptNumber, style: const TextStyle(fontWeight: FontWeight.bold)),
            subtitle: Text('${date.toLocal()} • ${sale.paymentMethod.toUpperCase()}${sale.due > 0 ? ' • ${S.t('Due', 'متبقي')}: ${_money(sale.due)}' : ''}', style: const TextStyle(fontSize: 10)),
            trailing: Text(_money(sale.total), style: const TextStyle(color: _teal, fontWeight: FontWeight.bold))));
        }));
    });
}

String _receiptText(Map<String, Object?> sale, List<Map<String, Object?>> items) {
  final b = StringBuffer()
    ..writeln('APH — AbdulmajeedPharma')
    ..writeln(kCopyright)
    ..writeln('Receipt: ${sale['receipt_number'] ?? ''}')
    ..writeln('Date: ${DateTime.fromMillisecondsSinceEpoch((sale['created_at'] as num? ?? 0).toInt()).toLocal()}')
    ..writeln('--------------------------------');
  for (final item in items) {
    final name = '${item['brand_name']} ${item['strength']} ${item['dosage_form']}';
    final quantity = (item['quantity'] as num? ?? 0).toInt();
    final unitPrice = (item['unit_price'] as num? ?? 0).toDouble();
    final lineTotal = (item['line_total'] as num? ?? 0).toDouble();
    final lot = item['batch_number'] ?? '';
    b.writeln(name);
    b.writeln('  $quantity × ${_money(unitPrice)} = ${_money(lineTotal)}');
    b.writeln('  Lot $lot');
  }
  final total = (sale['total'] as num? ?? 0).toDouble();
  final paid = (sale['paid'] as num? ?? 0).toDouble();
  final due = (total - paid).clamp(0, double.infinity).toDouble();
  final change = (paid - total).clamp(0, double.infinity).toDouble();
  b.writeln('--------------------------------')
    ..writeln('Subtotal: ${_money((sale['subtotal'] as num? ?? 0).toDouble())}')
    ..writeln('Discount: ${_money((sale['discount'] as num? ?? 0).toDouble())}')
    ..writeln('TOTAL: ${_money(total)}')
    ..writeln('Paid: ${_money(paid)}   Due: ${_money(due)}   Change: ${_money(change)}')
    ..writeln('Payment: ${sale['payment_method'] ?? ''}')
    ..writeln('Customer: ${sale['customer'] ?? '—'}')
    ..writeln('Thank you');
  return b.toString();
}

Widget _errorCard(String message, VoidCallback retry) => Center(child: Padding(
  padding: const EdgeInsets.all(20), child: Column(mainAxisSize: MainAxisSize.min, children: [
    const Icon(Icons.error_outline, color: Colors.orangeAccent, size: 36),
    const SizedBox(height: 8), SelectableText(message, textAlign: TextAlign.center),
    const SizedBox(height: 8), OutlinedButton.icon(onPressed: retry, icon: const Icon(Icons.refresh), label: Text(S.t('Retry', 'إعادة المحاولة'))),
  ]),
));

Widget _empty(String message, IconData icon) => Center(child: Padding(
  padding: const EdgeInsets.all(24), child: Column(mainAxisSize: MainAxisSize.min, children: [
    Icon(icon, color: Colors.white38, size: 48), const SizedBox(height: 12),
    Text(message, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white70, height: 1.6)),
  ]),
));

void _snack(BuildContext context, String message) => ScaffoldMessenger.of(context)
  ..hideCurrentSnackBar()
  ..showSnackBar(SnackBar(content: Text(message), duration: const Duration(seconds: 4)));

String _date(DateTime value) => '${value.year.toString().padLeft(4, '0')}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}';
