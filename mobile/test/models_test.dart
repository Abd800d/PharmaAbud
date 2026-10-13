/// Model + offline schema tests (§74, §76).
import 'package:flutter_test/flutter_test.dart';
import 'package:aph_mobile/shared/models/models.dart';

void main() {
  group('SearchHitModel', () {
    test('parses API JSON including demo + verification flags', () {
      final hit = SearchHitModel.fromJson({
        'kind': 'drug',
        'id': 'abc',
        'name_en': 'Amoxicillin',
        'name_ar': 'أموكسيسيلين',
        'subtitle': 'Aminopenicillin',
        'match_type': 'exact_generic',
        'score': 100,
        'verification_status': 'imported_pending_review',
        'is_demo': true,
      });
      expect(hit.kind, 'drug');
      expect(hit.nameEn, 'Amoxicillin');
      expect(hit.nameAr, 'أموكسيسيلين');
      expect(hit.matchType, 'exact_generic');
      expect(hit.isDemo, isTrue);
      expect(hit.verificationStatus, isNot('verified'));
    });
  });

  group('DrugModel', () {
    test('parses full monograph with sections and sources', () {
      final drug = DrugModel.fromJson({
        'id': 'd1',
        'generic_name_en': 'Enalapril',
        'generic_name_ar': 'إينالابريل',
        'pharmacological_class_name': 'ACE Inhibitors',
        'atc_code': 'C09AA02',
        'verification_status': 'imported_pending_review',
        'is_demo': true,
        'dosages': [
          {'population': 'adult', 'text_en': 'Not available / Requires verified source', 'is_verified': false},
        ],
        'pregnancy': {'text_en': 'Not available / Requires verified source'},
        'sources': [
          {'name': 'APH Demo Seed (DEMO/DEVELOPMENT DATA — NOT VERIFIED)', 'section': 'record'},
        ],
      });
      expect(drug.genericNameEn, 'Enalapril');
      expect(drug.dosages.length, 1);
      // never presented as verified dose data
      expect(drug.dosages.first['is_verified'], isFalse);
      expect(drug.sources, isNotEmpty);
    });
  });

  group('ProductModel', () {
    test('separates commercial entity from generic drug', () {
      final product = ProductModel.fromJson({
        'id': 'p1',
        'drug_id': 'd1',
        'brand_name_en': 'DemoBrand Enalapril',
        'strength': '5 mg',
        'dosage_form': 'tablet',
        'ingredients': [
          {'ingredient_name_en': 'Enalapril', 'is_primary': true},
        ],
        'verification_status': 'imported_pending_review',
        'is_demo': true,
      });
      expect(product.drugId, 'd1');
      expect(product.brandNameEn, isNot(product.drugId));
      expect(product.ingredients.length, 1);
    });
  });

  group('BodySystemModel', () {
    test('bilingual name selection', () {
      final system = BodySystemModel.fromJson({
        'id': 's1',
        'slug': 'cardiovascular-system',
        'name_en': 'Cardiovascular System',
        'name_ar': 'الجهاز القلبي الوعائي',
        'drug_count': 2,
      });
      expect(system.nameFor('en'), 'Cardiovascular System');
      expect(system.nameFor('ar'), 'الجهاز القلبي الوعائي');
      expect(system.drugCount, 2);
    });
  });
}
