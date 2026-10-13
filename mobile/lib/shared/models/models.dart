/// Domain models shared across features (Clean Architecture — domain layer).
library aph.models;

class BodySystemModel {
  const BodySystemModel({
    required this.id,
    required this.slug,
    required this.nameEn,
    required this.nameAr,
    this.drugCount = 0,
  });

  final String id;
  final String slug;
  final String nameEn;
  final String nameAr;
  final int drugCount;

  factory BodySystemModel.fromJson(Map<String, dynamic> j) => BodySystemModel(
        id: j['id'] as String? ?? '',
        slug: j['slug'] as String? ?? '',
        nameEn: j['name_en'] as String? ?? '',
        nameAr: j['name_ar'] as String? ?? '',
        drugCount: (j['drug_count'] as num?)?.toInt() ?? 0,
      );

  String nameFor(String languageCode) => languageCode == 'ar' ? (nameAr.isNotEmpty ? nameAr : nameEn) : nameEn;
}

class SearchHitModel {
  const SearchHitModel({
    required this.kind,
    required this.id,
    required this.nameEn,
    required this.nameAr,
    required this.subtitle,
    required this.matchType,
    required this.score,
    required this.verificationStatus,
    this.isDemo = false,
  });

  final String kind; // drug | product
  final String id;
  final String nameEn;
  final String nameAr;
  final String subtitle;
  final String matchType;
  final double score;
  final String verificationStatus;
  final bool isDemo;

  factory SearchHitModel.fromJson(Map<String, dynamic> j) => SearchHitModel(
        kind: j['kind'] as String? ?? 'drug',
        id: j['id'] as String? ?? '',
        nameEn: j['name_en'] as String? ?? '',
        nameAr: j['name_ar'] as String? ?? '',
        subtitle: j['subtitle'] as String? ?? '',
        matchType: j['match_type'] as String? ?? '',
        score: (j['score'] as num?)?.toDouble() ?? 0,
        verificationStatus: j['verification_status'] as String? ?? 'draft',
        isDemo: j['is_demo'] as bool? ?? false,
      );
}

class DrugModel {
  const DrugModel({
    required this.id,
    required this.genericNameEn,
    required this.genericNameAr,
    this.scientificName = '',
    this.drugClass = '',
    this.pharmacologicalClassName = '',
    this.therapeuticClassName = '',
    this.atcCode = '',
    this.overviewEn = '',
    this.overviewAr = '',
    this.mechanismEn = '',
    this.mechanismAr = '',
    this.pharmacokineticsEn = '',
    this.halfLife = '',
    this.verificationStatus = 'draft',
    this.isDemo = true,
    this.recordVersion = 1,
    this.synonyms = const [],
    this.indications = const [],
    this.contraindications = const [],
    this.warnings = const [],
    this.precautions = const [],
    this.sideEffects = const [],
    this.interactions = const [],
    this.foodInteractions = const [],
    this.dosages = const [],
    this.pregnancy,
    this.lactation,
    this.monitoring = const [],
    this.administration = const [],
    this.overdose,
    this.classifications = const [],
    this.sources = const [],
  });

  final String id;
  final String genericNameEn;
  final String genericNameAr;
  final String scientificName;
  final String drugClass;
  final String pharmacologicalClassName;
  final String therapeuticClassName;
  final String atcCode;
  final String overviewEn;
  final String overviewAr;
  final String mechanismEn;
  final String mechanismAr;
  final String pharmacokineticsEn;
  final String halfLife;
  final String verificationStatus;
  final bool isDemo;
  final int recordVersion;
  final List<Map<String, dynamic>> synonyms;
  final List<Map<String, dynamic>> indications;
  final List<Map<String, dynamic>> contraindications;
  final List<Map<String, dynamic>> warnings;
  final List<Map<String, dynamic>> precautions;
  final List<Map<String, dynamic>> sideEffects;
  final List<Map<String, dynamic>> interactions;
  final List<Map<String, dynamic>> foodInteractions;
  final List<Map<String, dynamic>> dosages;
  final Map<String, dynamic>? pregnancy;
  final Map<String, dynamic>? lactation;
  final List<Map<String, dynamic>> monitoring;
  final List<Map<String, dynamic>> administration;
  final Map<String, dynamic>? overdose;
  final List<Map<String, dynamic>> classifications;
  final List<Map<String, dynamic>> sources;

  factory DrugModel.fromJson(Map<String, dynamic> j) => DrugModel(
        id: j['id'] as String? ?? '',
        genericNameEn: j['generic_name_en'] as String? ?? '',
        genericNameAr: j['generic_name_ar'] as String? ?? '',
        scientificName: j['scientific_name'] as String? ?? '',
        drugClass: j['drug_class'] as String? ?? '',
        pharmacologicalClassName: j['pharmacological_class_name'] as String? ?? '',
        therapeuticClassName: j['therapeutic_class_name'] as String? ?? '',
        atcCode: j['atc_code'] as String? ?? '',
        overviewEn: j['overview_en'] as String? ?? '',
        overviewAr: j['overview_ar'] as String? ?? '',
        mechanismEn: j['mechanism_en'] as String? ?? '',
        mechanismAr: j['mechanism_ar'] as String? ?? '',
        pharmacokineticsEn: j['pharmacokinetics_en'] as String? ?? '',
        halfLife: j['half_life'] as String? ?? '',
        verificationStatus: j['verification_status'] as String? ?? 'draft',
        isDemo: j['is_demo'] as bool? ?? true,
        recordVersion: (j['record_version'] as num?)?.toInt() ?? 1,
        synonyms: _list(j['synonyms']),
        indications: _list(j['indications']),
        contraindications: _list(j['contraindications']),
        warnings: _list(j['warnings']),
        precautions: _list(j['precautions']),
        sideEffects: _list(j['side_effects']),
        interactions: _list(j['interactions']),
        foodInteractions: _list(j['food_interactions']),
        dosages: _list(j['dosages']),
        pregnancy: j['pregnancy'] is Map ? Map<String, dynamic>.from(j['pregnancy']) : null,
        lactation: j['lactation'] is Map ? Map<String, dynamic>.from(j['lactation']) : null,
        monitoring: _list(j['monitoring']),
        administration: _list(j['administration']),
        overdose: j['overdose'] is Map ? Map<String, dynamic>.from(j['overdose']) : null,
        classifications: _list(j['classifications']),
        sources: _list(j['sources']),
      );

  static List<Map<String, dynamic>> _list(dynamic v) =>
      v is List ? v.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList() : const [];
}

class ProductModel {
  const ProductModel({
    required this.id,
    this.drugId,
    required this.brandNameEn,
    this.brandNameAr = '',
    this.strength = '',
    this.strengthValue = '',
    this.strengthUnit = '',
    this.dosageForm = '',
    this.route = '',
    this.manufacturerName,
    this.manufacturerCountryId,
    this.marketingCountryId,
    this.barcode = '',
    this.gtin = '',
    this.registrationNumber = '',
    this.status = 'active',
    this.verificationStatus = 'draft',
    this.isDemo = true,
    this.ingredients = const [],
    this.packages = const [],
    this.images = const [],
    this.sources = const [],
    this.drug,
  });

  final String id;
  final String? drugId;
  final String brandNameEn;
  final String brandNameAr;
  final String strength;
  final String strengthValue;
  final String strengthUnit;
  final String dosageForm;
  final String route;
  final String? manufacturerName;
  final String? manufacturerCountryId;
  final String? marketingCountryId;
  final String barcode;
  final String gtin;
  final String registrationNumber;
  final String status;
  final String verificationStatus;
  final bool isDemo;
  final List<Map<String, dynamic>> ingredients;
  final List<Map<String, dynamic>> packages;
  final List<Map<String, dynamic>> images;
  final List<Map<String, dynamic>> sources;
  final Map<String, dynamic>? drug;

  factory ProductModel.fromJson(Map<String, dynamic> j) => ProductModel(
        id: j['id'] as String? ?? '',
        drugId: j['drug_id'] as String?,
        brandNameEn: j['brand_name_en'] as String? ?? '',
        brandNameAr: j['brand_name_ar'] as String? ?? '',
        strength: j['strength'] as String? ?? '',
        strengthValue: j['strength_value'] as String? ?? '',
        strengthUnit: j['strength_unit'] as String? ?? '',
        dosageForm: j['dosage_form'] as String? ?? '',
        route: j['route'] as String? ?? '',
        manufacturerName: j['manufacturer_name'] as String?,
        manufacturerCountryId: j['manufacturer_country_id'] as String?,
        marketingCountryId: j['marketing_country_id'] as String?,
        barcode: j['barcode'] as String? ?? '',
        gtin: j['gtin'] as String? ?? '',
        registrationNumber: j['registration_number'] as String? ?? '',
        status: j['status'] as String? ?? 'active',
        verificationStatus: j['verification_status'] as String? ?? 'draft',
        isDemo: j['is_demo'] as bool? ?? true,
        ingredients: DrugModel._list(j['ingredients']),
        packages: DrugModel._list(j['packages']),
        images: DrugModel._list(j['images']),
        sources: DrugModel._list(j['sources']),
        drug: j['drug'] is Map ? Map<String, dynamic>.from(j['drug']) : null,
      );
}
