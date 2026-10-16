/// AbdulmajeedPharma (APH) — Data models
/// © Dr. Abdulmajeed Abdullah Almakhedhi

class BodySystem {
  final String id, en, ar;
  const BodySystem(this.id, this.en, this.ar);
}

const List<BodySystem> kSystems = [
  BodySystem('nervous', 'Nervous System', 'الجهاز العصبي'),
  BodySystem('cardiovascular', 'Cardiovascular System', 'القلب والأوعية الدموية'),
  BodySystem('blood', 'Blood and Hematopoietic System', 'الدم ومكوّنات الدم'),
  BodySystem('respiratory', 'Respiratory System', 'الجهاز التنفسي'),
  BodySystem('gi', 'Gastrointestinal System', 'الجهاز الهضمي'),
  BodySystem('hepatobiliary', 'Hepatobiliary System', 'الكبد والقنوات الصفراوية'),
  BodySystem('endocrine', 'Endocrine System', 'الغدد الصماء والسكري'),
  BodySystem('renal', 'Renal and Urinary System', 'الكلى والمسالك البولية'),
  BodySystem('reproductive', 'Reproductive System', 'الجهاز التناسلي'),
  BodySystem('musculoskeletal', 'Musculoskeletal System', 'العضلات والعظام'),
  BodySystem('skin', 'Skin System', 'الجلد'),
  BodySystem('eye', 'Eye', 'العين'),
  BodySystem('ent', 'Ear, Nose, and Throat', 'الأذن والأنف والحنجرة'),
  BodySystem('immune', 'Immune System', 'جهاز المناعة والحساسية'),
  BodySystem('antiinfective', 'Anti-infective System', 'مضادات العدوى'),
  BodySystem('oncology', 'Oncology', 'الأورام'),
  BodySystem('emergency', 'Emergency and Toxicology', 'الطوارئ والتسمم'),
  BodySystem('misc', 'Diagnostic and Miscellaneous', 'التشخيص وأدوية متنوعة'),
];

BodySystem systemById(String id) =>
    kSystems.firstWhere((s) => s.id == id, orElse: () => kSystems.last);

/// الاسم العلمي (المادة الفعالة)
class GenericDrug {
  final int? id;
  final String nameEn, nameAr, systemId, subgroupEn, subgroupAr, atc;
  final String introduction, mechanism, indications, dosage;
  final String interactions, warnings, pregnancy, imagePath, source;

  const GenericDrug({
    this.id,
    required this.nameEn,
    this.nameAr = '',
    this.systemId = 'misc',
    this.subgroupEn = 'General',
    this.subgroupAr = 'عام',
    this.atc = '',
    this.introduction = '',
    this.mechanism = '',
    this.indications = '',
    this.dosage = '',
    this.interactions = '',
    this.warnings = '',
    this.pregnancy = '',
    this.imagePath = '',
    this.source = 'APH',
  });

  GenericDrug copyWith({String? imagePath}) => GenericDrug(
        id: id, nameEn: nameEn, nameAr: nameAr, systemId: systemId,
        subgroupEn: subgroupEn, subgroupAr: subgroupAr, atc: atc,
        introduction: introduction, mechanism: mechanism,
        indications: indications, dosage: dosage, interactions: interactions,
        warnings: warnings, pregnancy: pregnancy,
        imagePath: imagePath ?? this.imagePath, source: source,
      );

  Map<String, dynamic> toMap() => {
        'id': id, 'name_en': nameEn, 'name_ar': nameAr, 'system_id': systemId,
        'subgroup_en': subgroupEn, 'subgroup_ar': subgroupAr, 'atc_code': atc,
        'introduction': introduction, 'mechanism': mechanism,
        'indications': indications, 'dosage': dosage,
        'interactions': interactions, 'warnings': warnings,
        'pregnancy': pregnancy, 'image_path': imagePath, 'source': source,
      };

  factory GenericDrug.fromMap(Map<String, dynamic> m) => GenericDrug(
        id: m['id'] as int?,
        nameEn: (m['name_en'] ?? m['genericEn'] ?? '') as String,
        nameAr: (m['name_ar'] ?? m['genericAr'] ?? '') as String,
        systemId: (m['system_id'] ?? m['systemId'] ?? 'misc') as String,
        subgroupEn: (m['subgroup_en'] ?? m['subgroupEn'] ?? 'General') as String,
        subgroupAr: (m['subgroup_ar'] ?? m['subgroupAr'] ?? 'عام') as String,
        atc: (m['atc_code'] ?? m['atc'] ?? '') as String,
        introduction: (m['introduction'] ?? '') as String,
        mechanism: (m['mechanism'] ?? m['mechanismOfAction'] ?? '') as String,
        indications: (m['indications'] ?? '') as String,
        dosage: (m['dosage'] ?? '') as String,
        interactions: (m['interactions'] ?? m['drugInteractions'] ?? '') as String,
        warnings: (m['warnings'] ?? '') as String,
        pregnancy: (m['pregnancy'] ?? '') as String,
        imagePath: (m['image_path'] ?? m['image'] ?? '') as String,
        source: (m['source'] ?? 'APH') as String,
      );
}

/// منتج تجاري مرتبط باسم علمي (1 -> N)
class TradeProduct {
  final int? id;
  final int genericId;
  final String brandName, manufacturer, country, strength, dosageForm;
  final String agentYemen, imagePath, source;
  final bool verified;

  const TradeProduct({
    this.id,
    required this.genericId,
    required this.brandName,
    this.manufacturer = '',
    this.country = '',
    this.strength = '',
    this.dosageForm = '',
    this.agentYemen = '',
    this.imagePath = '',
    this.source = '',
    this.verified = false,
  });

  Map<String, dynamic> toMap() => {
        'id': id, 'generic_id': genericId, 'brand_name': brandName,
        'manufacturer': manufacturer, 'country': country,
        'strength': strength, 'dosage_form': dosageForm,
        'agent_yemen': agentYemen, 'image_path': imagePath,
        'source': source, 'verified': verified ? 1 : 0,
      };

  factory TradeProduct.fromMap(Map<String, dynamic> m) => TradeProduct(
        id: m['id'] as int?,
        genericId: (m['generic_id'] ?? m['genericId'] ?? 0) as int,
        brandName: (m['brand_name'] ?? m['brand'] ?? '') as String,
        manufacturer: (m['manufacturer'] ?? '') as String,
        country: (m['country'] ?? '') as String,
        strength: (m['strength'] ?? '') as String,
        dosageForm: (m['dosage_form'] ?? m['form'] ?? '') as String,
        agentYemen: (m['agent_yemen'] ?? m['agentYemen'] ?? '') as String,
        imagePath: (m['image_path'] ?? m['image'] ?? '') as String,
        source: (m['source'] ?? '') as String,
        verified: (m['verified'] ?? false) == true || (m['verified'] ?? 0) == 1,
      );
}

class ChatMessage {
  final int? id;
  final String author, body;
  final bool isAdmin;
  final int createdAt;

  /// معرّف الرسالة القادمة من لوحة التحكم على الويب (لمنع التكرار عند المزامنة)
  final String sourceId;
  const ChatMessage({this.id, required this.author, required this.body,
      this.isAdmin = false, required this.createdAt, this.sourceId = ''});
  Map<String, dynamic> toMap() => {'id': id, 'author': author, 'body': body,
      'is_admin': isAdmin ? 1 : 0, 'created_at': createdAt,
      'source_id': sourceId};
  factory ChatMessage.fromMap(Map<String, dynamic> m) => ChatMessage(
        id: m['id'] as int?, author: (m['author'] ?? '') as String,
        body: (m['body'] ?? '') as String, isAdmin: (m['is_admin'] ?? 0) == 1,
        createdAt: (m['created_at'] ?? 0) as int,
        sourceId: (m['source_id'] ?? '') as String);
}
