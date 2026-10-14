import 'package:flutter/material.dart';
import '../app_settings.dart';
import '../db/db_helper.dart';
import '../models/drug_models.dart';

InputDecoration _dec(String label) => InputDecoration(
    labelText: label, border: const OutlineInputBorder(),
    contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10));

/// إضافة / تعديل دواء علمي يدوياً — يُحفظ دائماً في SQLite
class AddDrugScreen extends StatefulWidget {
  final GenericDrug? edit;
  const AddDrugScreen({super.key, this.edit});
  @override
  State<AddDrugScreen> createState() => _AddDrugScreenState();
}

class _AddDrugScreenState extends State<AddDrugScreen> {
  final _en = TextEditingController(), _ar = TextEditingController(),
      _sgE = TextEditingController(), _sgA = TextEditingController(),
      _atc = TextEditingController(), _intro = TextEditingController(),
      _mech = TextEditingController(), _ind = TextEditingController(),
      _dose = TextEditingController(), _inter = TextEditingController(),
      _warn = TextEditingController(), _preg = TextEditingController();
  String _systemId = 'misc';

  @override
  void initState() {
    super.initState();
    final e = widget.edit;
    if (e != null) {
      _en.text = e.nameEn; _ar.text = e.nameAr; _sgE.text = e.subgroupEn;
      _sgA.text = e.subgroupAr; _atc.text = e.atc; _intro.text = e.introduction;
      _mech.text = e.mechanism; _ind.text = e.indications; _dose.text = e.dosage;
      _inter.text = e.interactions; _warn.text = e.warnings; _preg.text = e.pregnancy;
      _systemId = e.systemId;
    }
  }

  Future<void> _save() async {
    if (_en.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Generic name (EN) is required *')));
      return;
    }
    final g = GenericDrug(
      id: widget.edit?.id, nameEn: _en.text.trim(), nameAr: _ar.text.trim(),
      systemId: _systemId,
      subgroupEn: _sgE.text.trim().isEmpty ? 'General' : _sgE.text.trim(),
      subgroupAr: _sgA.text.trim().isEmpty ? 'عام' : _sgA.text.trim(),
      atc: _atc.text.trim(), introduction: _intro.text.trim(),
      mechanism: _mech.text.trim(), indications: _ind.text.trim(),
      dosage: _dose.text.trim(), interactions: _inter.text.trim(),
      warnings: _warn.text.trim(), pregnancy: _preg.text.trim(),
      imagePath: widget.edit?.imagePath ?? '',
      source: widget.edit?.source ?? 'APH Admin (manual)',
    );
    if (widget.edit == null) {
      await DBHelper.instance.insertGeneric(g);
    } else {
      await DBHelper.instance.updateGeneric(g);
    }
    if (mounted) Navigator.pop(context, true);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.edit == null
          ? S.t('Add drug manually', 'إضافة دواء يدوياً')
          : S.t('Edit drug', 'تعديل الدواء'))),
      body: ListView(padding: const EdgeInsets.all(14), children: [
        TextField(controller: _en, decoration: _dec('Generic name (EN) *')),
        const SizedBox(height: 10),
        TextField(controller: _ar, decoration: _dec(S.t('Generic name (Arabic)', 'الاسم العلمي بالعربية'))),
        const SizedBox(height: 10),
        DropdownButtonFormField<String>(
          value: _systemId, decoration: _dec(S.t('Body system', 'الجهاز / التصنيف')),
          items: kSystems.map((s) => DropdownMenuItem(
              value: s.id, child: Text(S.ar ? s.ar : s.en))).toList(),
          onChanged: (v) => setState(() => _systemId = v ?? 'misc'),
        ),
        const SizedBox(height: 10),
        TextField(controller: _sgE, decoration: _dec('Pharmacological subgroup (EN)')),
        const SizedBox(height: 10),
        TextField(controller: _sgA, decoration: _dec(S.t('Subgroup (Arabic)', 'المجموعة الدوائية بالعربية'))),
        const SizedBox(height: 10),
        TextField(controller: _atc, decoration: _dec('ATC code')),
        const SizedBox(height: 10),
        TextField(controller: _intro, maxLines: 2, decoration: _dec(S.t('Introduction', 'مقدمة'))),
        const SizedBox(height: 10),
        TextField(controller: _mech, maxLines: 2, decoration: _dec(S.t('Mechanism of action', 'آلية العمل'))),
        const SizedBox(height: 10),
        TextField(controller: _ind, maxLines: 2, decoration: _dec(S.t('Indications', 'الاستخدامات'))),
        const SizedBox(height: 10),
        TextField(controller: _dose, maxLines: 2, decoration: _dec(S.t('Usual dose', 'الجرعة المعتادة'))),
        const SizedBox(height: 10),
        TextField(controller: _inter, maxLines: 2, decoration: _dec(S.t('Drug interactions', 'التداخلات الدوائية'))),
        const SizedBox(height: 10),
        TextField(controller: _warn, maxLines: 2, decoration: _dec(S.t('Warnings', 'تحذيرات'))),
        const SizedBox(height: 10),
        TextField(controller: _preg, maxLines: 2, decoration: _dec(S.t('Pregnancy & lactation', 'الحمل والرضاعة'))),
        const SizedBox(height: 16),
        FilledButton.icon(onPressed: _save, icon: const Icon(Icons.save),
            label: Text(S.t('Save permanently', 'حفظ دائم'))),
        if (widget.edit != null) ...[
          const SizedBox(height: 10),
          OutlinedButton.icon(
            icon: const Icon(Icons.delete, color: Colors.redAccent),
            label: Text(S.t('Delete this drug', 'حذف هذا الدواء'),
                style: const TextStyle(color: Colors.redAccent)),
            onPressed: () async {
              await DBHelper.instance.deleteGeneric(widget.edit!.id!);
              if (mounted) Navigator.pop(context, true);
            }),
        ],
      ]),
    );
  }
}

/// إضافة / تعديل منتج تجاري: الاسم + القوة + الشكل + الشركة + الدولة + وكيل اليمن
class AddProductScreen extends StatefulWidget {
  final GenericDrug generic;
  final TradeProduct? edit;
  const AddProductScreen({super.key, required this.generic, this.edit});
  @override
  State<AddProductScreen> createState() => _AddProductScreenState();
}

class _AddProductScreenState extends State<AddProductScreen> {
  final _brand = TextEditingController(), _strength = TextEditingController(),
      _form = TextEditingController(), _mfr = TextEditingController(),
      _country = TextEditingController(), _agent = TextEditingController();
  bool _verified = false;

  @override
  void initState() {
    super.initState();
    final e = widget.edit;
    if (e != null) {
      _brand.text = e.brandName; _strength.text = e.strength;
      _form.text = e.dosageForm; _mfr.text = e.manufacturer;
      _country.text = e.country; _agent.text = e.agentYemen;
      _verified = e.verified;
    }
  }

  Future<void> _save() async {
    if (_brand.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Brand name is required *')));
      return;
    }
    final p = TradeProduct(
      id: widget.edit?.id, genericId: widget.generic.id!,
      brandName: _brand.text.trim(), strength: _strength.text.trim(),
      dosageForm: _form.text.trim(), manufacturer: _mfr.text.trim(),
      country: _country.text.trim(), agentYemen: _agent.text.trim(),
      imagePath: widget.edit?.imagePath ?? '',
      source: 'APH Admin (manual)', verified: _verified,
    );
    if (widget.edit == null) {
      await DBHelper.instance.insertTrade(p);
    } else {
      await DBHelper.instance.updateTrade(p);
    }
    if (mounted) Navigator.pop(context, true);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(
          '${widget.edit == null ? S.t('Add', 'إضافة') : S.t('Edit', 'تعديل')} — ${widget.generic.nameEn}')),
      body: ListView(padding: const EdgeInsets.all(14), children: [
        TextField(controller: _brand, decoration: _dec('Brand name *')),
        const SizedBox(height: 10),
        TextField(controller: _strength, decoration: _dec(S.t('Strength (e.g. 500 mg)', 'القوة / التركيز'))),
        const SizedBox(height: 10),
        TextField(controller: _form, decoration: _dec(S.t('Dosage form (Tablet/Capsule/Syrup…)', 'الشكل الصيدلاني'))),
        const SizedBox(height: 10),
        TextField(controller: _mfr, decoration: _dec(S.t('Manufacturer company', 'الشركة المصنعة'))),
        const SizedBox(height: 10),
        TextField(controller: _country, decoration: _dec(S.t('Country of origin', 'بلد الصنع'))),
        const SizedBox(height: 10),
        TextField(controller: _agent, decoration: _dec(S.t('Agent / supplier in Yemen', 'الوكيل / المورد في اليمن'))),
        SwitchListTile(
          value: _verified, onChanged: (v) => setState(() => _verified = v),
          title: Text(S.t('Yemen agent verified', 'وكيل اليمن موثّق')),
        ),
        const SizedBox(height: 10),
        FilledButton.icon(onPressed: _save, icon: const Icon(Icons.save),
            label: Text(S.t('Save permanently', 'حفظ دائم'))),
      ]),
    );
  }
}
