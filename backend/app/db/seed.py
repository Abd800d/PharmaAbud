"""Database seeding: RBAC baseline + the 18 medical systems + DEMO dataset.

IMPORTANT (§85–§87):
  * All seeded pharmaceutical records are marked `is_demo = True` and carry
    verification status `imported_pending_review` or `draft` — they are
    DEMO / DEVELOPMENT DATA and are NOT presented as verified production data.
  * Doses read "Not available / Requires verified source" unless a verified
    source exists. Nothing is invented.
  * The demo source explicitly labels itself as demo data.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import (
    BodySystem,
    Country,
    DosageForm,
    Drug,
    DrugAlternative,
    DrugClassification,
    DrugContraindication,
    DrugDosage,
    DrugIndication,
    DrugInteraction,
    DrugLactation,
    DrugPregnancy,
    DrugSideEffect,
    DrugWarning,
    Manufacturer,
    Permission,
    PharmacologicalClass,
    Product,
    ProductIngredient,
    Role,
    Route,
    Source,
    TherapeuticGroup,
    User,
    VerificationStatus,
)
from app.core.security import hash_password
from app.services.normalization import normalize_arabic, normalize_text
from app.services.search import build_drug_search_fields, build_product_search_fields

_log = get_logger("app")

NOT_AVAILABLE = "Not available / Requires verified source"

# ------------------------------------------------------------------ RBAC (§28)
PERMISSIONS: List[Tuple[str, str, str, str]] = [
    ("drug.read", "Read drugs", "قراءة الأدوية", "drug"),
    ("drug.create", "Create drugs", "إنشاء أدوية", "drug"),
    ("drug.edit", "Edit drugs", "تعديل الأدوية", "drug"),
    ("drug.delete", "Delete/archive drugs", "حذف/أرشفة الأدوية", "drug"),
    ("drug.verify", "Verify drugs", "اعتماد الأدوية", "drug"),
    ("product.create", "Create products", "إنشاء المنتجات", "product"),
    ("product.edit", "Edit products", "تعديل المنتجات", "product"),
    ("product.verify", "Verify products", "اعتماد المنتجات", "product"),
    ("image.upload", "Upload images", "رفع الصور", "image"),
    ("image.approve", "Approve images", "اعتماد الصور", "image"),
    ("import.create", "Create imports", "إنشاء الاستيراد", "import"),
    ("import.approve", "Approve/execute imports", "تنفيذ الاستيراد", "import"),
    ("source.manage", "Manage sources", "إدارة المصادر", "source"),
    ("user.manage", "Manage users", "إدارة المستخدمين", "user"),
    ("audit.read", "Read audit logs", "قراءة سجلات التدقيق", "audit"),
    ("settings.manage", "Manage settings", "إدارة الإعدادات", "settings"),
    ("data.export", "Export data", "تصدير البيانات", "data"),
]

ROLES: Dict[str, Dict] = {
    "public_user": {
        "name_en": "Public User", "name_ar": "مستخدم عام",
        "perms": ["drug.read"],
    },
    "pharmacist_reviewer": {
        "name_en": "Pharmacist Reviewer", "name_ar": "مدقق صيدلي",
        "perms": ["drug.read", "drug.verify", "product.verify", "image.approve", "audit.read"],
    },
    "data_manager": {
        "name_en": "Data Manager", "name_ar": "مدير بيانات",
        "perms": ["drug.read", "drug.create", "drug.edit", "product.create", "product.edit",
                  "import.create", "import.approve", "source.manage", "image.upload", "data.export"],
    },
    "image_reviewer": {
        "name_en": "Image Reviewer", "name_ar": "مدقق صور",
        "perms": ["drug.read", "image.upload", "image.approve"],
    },
    "translator": {
        "name_en": "Translator", "name_ar": "مترجم",
        "perms": ["drug.read", "drug.edit"],
    },
    "administrator": {
        "name_en": "Administrator", "name_ar": "مدير النظام",
        "perms": [p[0] for p in PERMISSIONS],
    },
    "super_administrator": {
        "name_en": "Super Administrator", "name_ar": "المدير العام",
        "perms": [p[0] for p in PERMISSIONS],
    },
}

# ------------------------------------------------------------------ 18 systems (§4)
SYSTEMS: List[Tuple[str, str, str]] = [
    ("nervous-system", "Nervous System", "الجهاز العصبي"),
    ("cardiovascular-system", "Cardiovascular System", "الجهاز القلبي الوعائي"),
    ("blood-hematopoietic", "Blood and Hematopoietic System", "الجهاز الدموي والدموي"),
    ("respiratory-system", "Respiratory System", "الجهاز التنفسي"),
    ("gastrointestinal-system", "Gastrointestinal System", "الجهاز الهضمي"),
    ("hepatobiliary-system", "Hepatobiliary System", "الجهاز الكبدي الصفراوي"),
    ("endocrine-system", "Endocrine System", "الجهاز الصماوي"),
    ("renal-urinary", "Renal and Urinary System", "الجهاز الكلوي والبولي"),
    ("reproductive-system", "Reproductive System", "الجهاز التناسلي"),
    ("musculoskeletal-system", "Musculoskeletal System", "الجهاز العضلي الهيكلي"),
    ("skin-system", "Skin System", "الجلد"),
    ("eye", "Eye", "العين"),
    ("ent", "Ear, Nose, and Throat", "الأنف والأذن والحنجرة"),
    ("immune-system", "Immune System", "الجهاز المناعي"),
    ("anti-infective", "Anti-infective System", "المضادات العدوى"),
    ("oncology", "Oncology", "الأورام"),
    ("emergency-toxicology", "Emergency and Toxicology", "الطوارئ والتسمم"),
    ("diagnostic-misc", "Diagnostic and Miscellaneous", "التشخيصية والمتنوعة"),
]

DOSAGE_FORMS = [
    ("tablet", "Tablet", "قرص"), ("capsule", "Capsule", "كبسولة"), ("softgel", "Softgel", "كبسولة هلامية"),
    ("oral_solution", "Oral Solution", "حلال فموي"), ("oral_suspension", "Oral Suspension", "معلق فموي"),
    ("syrup", "Syrup", "شراب"), ("powder", "Powder", "مسحوق"), ("granules", "Granules", "حبيبات"),
    ("injection", "Injection", "حقن"), ("infusion", "Infusion", "تسريب وريدي"),
    ("cream", "Cream", "كريم"), ("ointment", "Ointment", "مرهم"), ("gel", "Gel", "جل"),
    ("lotion", "Lotion", "لوشن"), ("foam", "Foam", "رغوة"), ("patch", "Patch", "لاصقة"),
    ("suppository", "Suppository", "تحاميل"), ("vaginal_tablet", "Vaginal Tablet", "قرص مهبلي"),
    ("vaginal_cream", "Vaginal Cream", "كريم مهبلي"), ("eye_drops", "Eye Drops", "قطرات عين"),
    ("eye_ointment", "Eye Ointment", "مرهم عيني"), ("ear_drops", "Ear Drops", "قطرات أذن"),
    ("nasal_spray", "Nasal Spray", "بخاخ أنفي"), ("inhaler", "Inhaler", "بخاخ استنشاقي"),
    ("nebulizer_solution", "Nebulizer Solution", "حلال البخار"), ("mouthwash", "Mouthwash", "غسول فموي"),
    ("sublingual_tablet", "Sublingual Tablet", "قرص تحت اللسان"), ("buccal_tablet", "Buccal Tablet", "قرص خدّي"),
    ("transdermal_system", "Transdermal System", "نظام عبر الجلد"), ("implant", "Implant", "زرع"),
    ("other", "Other", "أخرى"),
]

ROUTES = [
    ("oral", "Oral", "فموي"), ("intravenous", "Intravenous", "وريدي"),
    ("intramuscular", "Intramuscular", "عضلي"), ("subcutaneous", "Subcutaneous", "تحت الجلد"),
    ("topical", "Topical", "موضعي"), ("inhalation", "Inhalation", "استنشاقي"),
    ("ophthalmic", "Ophthalmic", "عن طريق العين"), ("otic", "Otic", "عن طريق الأذن"),
    ("nasal", "Nasal", "أنفي"), ("rectal", "Rectal", "شرجي"),
    ("vaginal", "Vaginal", "مهبلي"), ("transdermal", "Transdermal", "عبر الجلد"),
    ("sublingual", "Sublingual", "تحت اللسان"), ("buccal", "Buccal", "خدّي"),
    ("intrathecal", "Intrathecal", "عن طريق الأم الجافية"), ("other", "Other", "أخرى"),
]

COUNTRIES = [
    ("SA", "Saudi Arabia", "المملكة العربية السعودية"), ("AE", "United Arab Emirates", "الإمارات العربية المتحدة"),
    ("EG", "Egypt", "مصر"), ("JO", "Jordan", "الأردن"), ("KW", "Kuwait", "الكويت"),
    ("QA", "Qatar", "قطر"), ("BH", "Bahrain", "البحرين"), ("OM", "Oman", "عُمان"),
    ("US", "United States", "الولايات المتحدة"), ("GB", "United Kingdom", "المملكة المتحدة"),
    ("DE", "Germany", "ألمانيا"), ("FR", "France", "فرنسا"), ("IN", "India", "الهند"),
    ("CH", "Switzerland", "سويسرا"), ("TR", "Türkiye", "تركيا"), ("JP", "Japan", "اليابان"),
]

# ------------------------------------------------------------------ demo drugs (§87)
# Each tuple: (system_slug, group_en, group_ar, class_en, class_ar, drug_en, drug_ar,
#              class_line, overview, mechanism)
# All content is DEMO seed text (well-established class-level statements),
# marked is_demo and pending review. Doses are NEVER invented.
DEMO_DRUGS: List[Tuple] = [
    ("nervous-system", "Antidepressants", "مضادات الاكتئاب", "Tricyclic Antidepressants", "مضادات الاكتئاب ثلاثية الحلقات",
     "Amitriptyline", "أميتربتيلين", "Tricyclic antidepressant",
     "DEMO DATA — tricyclic antidepressant class entry for development purposes.",
     "DEMO DATA — class-level statement: tricyclic antidepressants inhibit reuptake of serotonin and norepinephrine."),
    ("nervous-system", "Anticonvulsants", "مضادات الصرع", "Gabapentinoids", "الجابابنتينويدات",
     "Gabapentin", "غابابنتين", "Gabapentinoid",
     "DEMO DATA — gabapentinoid class entry for development purposes.",
     "DEMO DATA — class-level statement: gabapentinoids bind the α2δ subunit of voltage-gated calcium channels."),
    ("cardiovascular-system", "Antihypertensives", "خافضات الضغط", "ACE Inhibitors", "مثبطات إنزيم محول أنجيوتنسين",
     "Enalapril", "إينالابريل", "ACE inhibitor",
     "DEMO DATA — ACE inhibitor class entry for development purposes.",
     "DEMO DATA — class-level statement: ACE inhibitors block conversion of angiotensin I to angiotensin II."),
    ("cardiovascular-system", "Antihypertensives", "خافضات الضغط", "Calcium Channel Blockers", "محصرات قنوات الكالسيوم",
     "Amlodipine", "أملوديبين", "Dihydropyridine calcium channel blocker",
     "DEMO DATA — calcium channel blocker class entry for development purposes.",
     "DEMO DATA — class-level statement: dihydropyridine calcium channel blockers relax vascular smooth muscle."),
    ("blood-hematopoietic", "Antianemics", "مضادات فقر الدم", "Iron Supplements", "مكملات الحديد",
     "Ferrous Sulfate", "كبريتات الحديدوز", "Iron salt",
     "DEMO DATA — iron supplement class entry for development purposes.",
     "DEMO DATA — class-level statement: oral iron salts replenish body iron stores."),
    ("blood-hematopoietic", "Anticoagulants", "مضادات التخثر", "Vitamin K Antagonists", "مضادات فيتامين ك",
     "Warfarin", "وارفارين", "Vitamin K antagonist",
     "DEMO DATA — anticoagulant class entry for development purposes.",
     "DEMO DATA — class-level statement: vitamin K antagonists inhibit synthesis of vitamin K–dependent clotting factors."),
    ("respiratory-system", "Bronchodilators", "موسعة الشعب", "Short-acting Beta-2 Agonists", "محفزات بيتا-2 قصيرة المفعول",
     "Salbutamol", "سالبوتامول", "Short-acting beta-2 agonist",
     "DEMO DATA — bronchodilator class entry for development purposes.",
     "DEMO DATA — class-level statement: beta-2 agonists relax bronchial smooth muscle."),
    ("respiratory-system", "Leukotriene Modifiers", "معدلات اللوكوترين", "Leukotriene Receptor Antagonists", "محصرات مستقبلات اللوكوترين",
     "Montelukast", "مونتيلوكاست", "Leukotriene receptor antagonist",
     "DEMO DATA — leukotriene modifier class entry for development purposes.",
     "DEMO DATA — class-level statement: leukotriene receptor antagonists block cysteinyl leukotriene receptors."),
    ("gastrointestinal-system", "Antisecretories", "مضادات الإفراز", "Proton Pump Inhibitors", "مثبطات مضخة البروتون",
     "Omeprazole", "أوميبرازول", "Proton pump inhibitor",
     "DEMO DATA — PPI class entry for development purposes.",
     "DEMO DATA — class-level statement: PPIs irreversibly inhibit the gastric H+/K+ ATPase proton pump."),
    ("gastrointestinal-system", "Antiemetics", "مضادات القيء", "5-HT3 Antagonists", "محاصرات 5-HT3",
     "Ondansetron", "أوندانسيترون", "5-HT3 receptor antagonist",
     "DEMO DATA — antiemetic class entry for development purposes.",
     "DEMO DATA — class-level statement: 5-HT3 antagonists block serotonin receptors in the chemoreceptor trigger zone."),
    ("hepatobiliary-system", "Gallstone Solvents", "مذيبات الحصوات الصفراوية", "Bile Acids", "الأحماض الصفراوية",
     "Ursodeoxycholic Acid", "حمض الأورسوديوكسوكوليك", "Bile acid",
     "DEMO DATA — hepatobiliary class entry for development purposes.",
     "DEMO DATA — class-level statement: ursodeoxycholic acid reduces cholesterol saturation of bile."),
    ("endocrine-system", "Antidiabetics", "مضادات السكري", "Biguanides", "البيجوانيدات",
     "Metformin", "ميتفورمين", "Biguanide",
     "DEMO DATA — antidiabetic class entry for development purposes.",
     "DEMO DATA — class-level statement: biguanides decrease hepatic glucose production and improve insulin sensitivity."),
    ("endocrine-system", "Thyroid Hormones", "هرمونات الغدة الدرقية", "Thyroid Hormones", "هرمونات الغدة الدرقية",
     "Levothyroxine", "ليفوثيروكسين", "Synthetic thyroid hormone",
     "DEMO DATA — thyroid hormone class entry for development purposes.",
     "DEMO DATA — class-level statement: levothyroxine is synthetic T4, converted peripherally to T3."),
    ("renal-urinary", "Diuretics", "مدرات البول", "Loop Diuretics", "مدرات البول الحلقية",
     "Furosemide", "فوروسيميد", "Loop diuretic",
     "DEMO DATA — diuretic class entry for development purposes.",
     "DEMO DATA — class-level statement: loop diuretics inhibit the Na-K-2Cl cotransporter in the loop of Henle."),
    ("renal-urinary", "Urologicals", "المسالك البولية", "Alpha-1 Blockers", "محصرات ألفا-1",
     "Tamsulosin", "تامسولوسين", "Alpha-1 adrenergic blocker",
     "DEMO DATA — urological class entry for development purposes.",
     "DEMO DATA — class-level statement: alpha-1 blockers relax smooth muscle in the prostate and bladder neck."),
    ("reproductive-system", "Emergency Contraception", "الطارئ للتحاليل", "Progestins", "البروجستينات",
     "Levonorgestrel", "ليفونورجيستريل", "Progestin",
     "DEMO DATA — reproductive class entry for development purposes.",
     "DEMO DATA — class-level statement: levonorgestrel is a synthetic progestogen used in emergency contraception."),
    ("musculoskeletal-system", "NSAIDs", "مضادات الالتهاب غير الستيرويدية", "Propionic Acid Derivatives", "مشتقات حمض البروبيونيك",
     "Ibuprofen", "إيبوبروفين", "NSAID",
     "DEMO DATA — NSAID class entry for development purposes.",
     "DEMO DATA — class-level statement: NSAIDs inhibit cyclooxygenase enzymes and prostaglandin synthesis."),
    ("musculoskeletal-system", "Osteoporosis Agents", "علاج هشاشة العظام", "Bisphosphonates", "البيسفوسفونات",
     "Alendronate", "ألندرونات", "Bisphosphonate",
     "DEMO DATA — bisphosphonate class entry for development purposes.",
     "DEMO DATA — class-level statement: bisphosphonates inhibit osteoclast-mediated bone resorption."),
    ("skin-system", "Topical Corticosteroids", "الكورتيكوستيرويدات الموضعية", "Corticosteroids", "الكورتيكوستيرويدات",
     "Hydrocortisone", "هيدروكورتيزون", "Topical corticosteroid",
     "DEMO DATA — topical corticosteroid class entry for development purposes.",
     "DEMO DATA — class-level statement: topical corticosteroids have anti-inflammatory and antipruritic effects."),
    ("skin-system", "Antifungals", "مضادات الفطريات", "Azole Antifungals", "مضادات الفطريات الآزولية",
     "Clotrimazole", "كلوتريمازول", "Imidazole antifungal",
     "DEMO DATA — antifungal class entry for development purposes.",
     "DEMO DATA — class-level statement: imidazole antifungals disrupt ergosterol synthesis in fungal cell membranes."),
    ("eye", "Antiglaucoma", "مضادات الجلوكوما", "Beta Blockers (Ophthalmic)", "حاصرات بيتا (عن طريق العين)",
     "Timolol", "تيمولول", "Ophthalmic beta blocker",
     "DEMO DATA — ophthalmic class entry for development purposes.",
     "DEMO DATA — class-level statement: ophthalmic beta blockers reduce aqueous humor production."),
    ("ent", "Nasal Decongestants", "موصلة الأنف", "Imidazoline Derivatives", "مشتقات الإميدازولين",
     "Oxymetazoline", "أوكسي ميتازولين", "Nasal decongestant",
     "DEMO DATA — ENT class entry for development purposes.",
     "DEMO DATA — class-level statement: topical nasal decongestants act on alpha-adrenergic receptors reducing mucosal congestion."),
    ("immune-system", "Immunosuppressants", "مثبطات المناعة", "Calcineurin Inhibitors", "مثبطات الكالسينيورين",
     "Cyclosporine", "سيكلوسبورين", "Calcineurin inhibitor",
     "DEMO DATA — immunosuppressant class entry for development purposes.",
     "DEMO DATA — class-level statement: calcineurin inhibitors suppress T-cell activation."),
    ("anti-infective", "Antibiotics", "المضادات الحيوية", "Aminopenicillins", "الأمينوبينيسيلينات",
     "Amoxicillin", "أموكسيسيلين", "Aminopenicillin (beta-lactam antibiotic)",
     "DEMO DATA — aminopenicillin class entry for development purposes.",
     "DEMO DATA — class-level statement: penicillins inhibit bacterial cell-wall synthesis by binding penicillin-binding proteins."),
    ("anti-infective", "Antibiotics", "المضادات الحيوية", "Beta-lactam / Beta-lactamase Inhibitor Combinations", "مجموعات البيتالاكتام مع مثبطات البيتالاكتاماز",
     "Amoxicillin and Clavulanate", "أموكسيسيلين وكلافولانات", "Combination antibiotic",
     "DEMO DATA — combination antibiotic entry for development purposes.",
     "DEMO DATA — class-level statement: clavulanate inhibits beta-lactamase enzymes, extending amoxicillin's spectrum."),
    ("anti-infective", "Macrolides", "المكرويدات", "Macrolide Antibiotics", "مضادات حيوية مكرويدية",
     "Azithromycin", "أزيثرومايسين", "Macrolide antibiotic",
     "DEMO DATA — macrolide class entry for development purposes.",
     "DEMO DATA — class-level statement: macrolides inhibit bacterial protein synthesis by binding the 50S ribosomal subunit."),
    ("oncology", "Antimetabolites", "مضادات الأيض", "Folate Antagonists", "مضادات الفولات",
     "Methotrexate", "ميثوتريكسات", "Folate antagonist",
     "DEMO DATA — antimetabolite class entry for development purposes.",
     "DEMO DATA — class-level statement: methotrexate inhibits dihydrofolate reductase."),
    ("oncology", "Alkylating Agents", "العوامل المألكة", "Nitrogen Mustards", "مشتقات النيتروجين MUSTARD",
     "Cyclophosphamide", "سيكلوفوسفاميد", "Alkylating agent",
     "DEMO DATA — alkylating agent class entry for development purposes.",
     "DEMO DATA — class-level statement: alkylating agents form cross-links in DNA."),
    ("emergency-toxicology", "Antidotes", "المضادات", "Opioid Antagonists", "مضادات الأفيونات",
     "Naloxone", "نالوكسون", "Opioid antagonist",
     "DEMO DATA — antidote class entry for development purposes.",
     "DEMO DATA — class-level statement: naloxone competitively blocks opioid receptors."),
    ("emergency-toxicology", "Antidotes", "المضادات", "Benzodiazepine Antagonists", "مضادات البنزوديازيبين",
     "Flumazenil", "فلومازينيل", "Benzodiazepine antagonist",
     "DEMO DATA — antidote class entry for development purposes.",
     "DEMO DATA — class-level statement: flumazenil competitively inhibits benzodiazepine binding at GABA-A receptors."),
    ("diagnostic-misc", "Contrast Media", "الصبغات التشخيصية", "Iodinated Contrast Media", "الصبغات المحتوية على اليود",
     "Iohexol", "أيوهيكسول", "Non-ionic iodinated contrast medium",
     "DEMO DATA — diagnostic agent class entry for development purposes.",
     "DEMO DATA — class-level statement: non-ionic iodinated contrast media provide radiographic opacification."),
]


def seed_database(db: Session, *, with_demo: bool = True, create_admin: bool = True) -> Dict[str, int]:
    """Idempotent seed: permissions → roles → taxonomy → demo records."""
    counts = {"permissions": 0, "roles": 0, "systems": 0, "drugs": 0, "products": 0}

    # ---- permissions ----
    perm_by_code: Dict[str, Permission] = {p.code: p for p in db.scalars(select(Permission)).all()}
    for code, name_en, name_ar, group in PERMISSIONS:
        if code not in perm_by_code:
            perm = Permission(code=code, name_en=name_en, name_ar=name_ar, group=group)
            db.add(perm)
            perm_by_code[code] = perm
            counts["permissions"] += 1
    db.flush()

    # ---- roles ----
    role_by_code: Dict[str, Role] = {r.code: r for r in db.scalars(select(Role)).all()}
    for code, meta in ROLES.items():
        role = role_by_code.get(code)
        if role is None:
            role = Role(code=code, name_en=meta["name_en"], name_ar=meta["name_ar"],
                        description="", is_system=True)
            db.add(role)
            role_by_code[code] = role
            counts["roles"] += 1
        role.permissions = [perm_by_code[c] for c in meta["perms"] if c in perm_by_code]
    db.flush()

    # ---- admin account (development only; password must be overridden in prod) ----
    if create_admin:
        admin = db.scalar(select(User).where(User.email == "admin@aphdemo.com"))
        if admin is None:
            admin = User(
                email="admin@aphdemo.com",
                full_name="APH Administrator",
                password_hash=hash_password("ChangeMe!123"),
                is_active=True,
                is_verified=True,
            )
            admin.roles.append(role_by_code["administrator"])
            db.add(admin)

    # ---- dosage forms / routes / countries ----
    for slug, en, ar in DOSAGE_FORMS:
        if db.scalar(select(DosageForm).where(DosageForm.slug == slug)) is None:
            db.add(DosageForm(slug=slug, name_en=en, name_ar=ar))
    for slug, en, ar in ROUTES:
        if db.scalar(select(Route).where(Route.slug == slug)) is None:
            db.add(Route(slug=slug, name_en=en, name_ar=ar))
    for iso, en, ar in COUNTRIES:
        if db.scalar(select(Country).where(Country.iso_code == iso)) is None:
            db.add(Country(iso_code=iso, name_en=en, name_ar=ar))
    db.flush()

    if not with_demo:
        db.flush()
        return counts

    # ---- demo source (explicitly labelled) ----
    demo_source = db.scalar(select(Source).where(Source.name == "APH Demo Seed (DEMO/DEVELOPMENT DATA — NOT VERIFIED)"))
    if demo_source is None:
        demo_source = Source(
            name="APH Demo Seed (DEMO/DEVELOPMENT DATA — NOT VERIFIED)",
            url="",
            source_type="demo",
            description="Development seed data created to exercise the APH platform. "
                        "NOT verified pharmaceutical information. Do not cite in clinical contexts.",
            license_info="Owned by APH (© Dr. Abdulmajeed Abdullah Almakhedhi) — demo content.",
            verification_status=VerificationStatus.IMPORTED_PENDING_REVIEW.value,
            is_demo=True,
        )
        db.add(demo_source)
        db.flush()

    # ---- systems + groups + classes ----
    system_by_slug: Dict[str, BodySystem] = {}
    for idx, (slug, en, ar) in enumerate(SYSTEMS):
        system = db.scalar(select(BodySystem).where(BodySystem.slug == slug))
        if system is None:
            system = BodySystem(slug=slug, name_en=en, name_ar=ar, sort_order=idx + 1,
                                description_en="DEMO taxonomy entry.", description_ar="إدخال تجريبي.")
            db.add(system)
            counts["systems"] += 1
        system_by_slug[slug] = system
    db.flush()

    groups_cache: Dict[str, TherapeuticGroup] = {}
    classes_cache: Dict[str, PharmacologicalClass] = {}

    def get_group(system: BodySystem, slug: str, en: str, ar: str) -> TherapeuticGroup:
        key = f"{system.slug}:{slug}"
        if key not in groups_cache:
            g = db.scalar(select(TherapeuticGroup).where(
                TherapeuticGroup.body_system_id == system.id, TherapeuticGroup.slug == slug))
            if g is None:
                g = TherapeuticGroup(body_system_id=system.id, slug=slug, name_en=en, name_ar=ar)
                db.add(g)
                db.flush()  # populate g.id before it is referenced
            groups_cache[key] = g
        return groups_cache[key]

    def get_class(group: TherapeuticGroup, slug: str, en: str, ar: str) -> PharmacologicalClass:
        key = f"{group.slug}:{slug}"
        if key not in classes_cache:
            c = db.scalar(select(PharmacologicalClass).where(
                PharmacologicalClass.therapeutic_group_id == group.id, PharmacologicalClass.slug == slug))
            if c is None:
                c = PharmacologicalClass(therapeutic_group_id=group.id, slug=slug, name_en=en, name_ar=ar)
                db.add(c)
                db.flush()  # populate c.id before it is referenced
            classes_cache[key] = c
        return classes_cache[key]

    db.flush()

    # ---- demo drugs + products ----
    demo_manufacturer = db.scalar(select(Manufacturer).where(Manufacturer.name_en == "Demo Pharma (DEMO DATA)"))
    if demo_manufacturer is None:
        demo_manufacturer = Manufacturer(name_en="Demo Pharma (DEMO DATA)", name_ar="ديمو فارما (بيانات تجريبية)")
        db.add(demo_manufacturer)
        db.flush()

    for (sys_slug, group_en, group_ar, class_en, class_ar,
         drug_en, drug_ar, class_line, overview, mechanism) in DEMO_DRUGS:
        system = system_by_slug[sys_slug]
        slugify = lambda s: normalize_text(s).replace(" ", "-")[:80]
        group = get_group(system, slugify(group_en), group_en, group_ar)
        pharm_class = get_class(group, slugify(class_en), class_en, class_ar)
        db.flush()

        drug = db.scalar(select(Drug).where(Drug.generic_name_en == drug_en))
        if drug is None:
            drug = Drug(
                generic_name_en=drug_en,
                generic_name_ar=drug_ar,
                drug_class=class_line,
                pharmacological_class_name=class_en,
                therapeutic_class_name=group_en,
                overview_en=overview,
                overview_ar="بيانات تجريبية للتطوير فقط — غير موثقة.",
                mechanism_en=mechanism,
                mechanism_ar="بيانات تجريبية (مستوى الصنف) — غير موثقة.",
                is_demo=True,
                verification_status=VerificationStatus.IMPORTED_PENDING_REVIEW.value,
            )
            db.add(drug)
            db.flush()
            counts["drugs"] += 1

            db.add(DrugClassification(
                drug_id=drug.id,
                pharmacological_class_id=pharm_class.id,
                body_system_id=system.id,
                therapeutic_group_id=group.id,
                is_primary=True,
            ))
            db.add(DrugIndication(drug_id=drug.id,
                                  text_en="DEMO DATA — indication placeholder requiring verified source.",
                                  text_ar="بيانات تجريبية — يتطلب مصدراً موثوقاً."))
            db.add(DrugDosage(
                drug_id=drug.id, population="adult", text_en=NOT_AVAILABLE,
                text_ar="غير متاح / يتطلب مصدراً موثوقاً", is_verified=False,
            ))
            db.add(DrugDosage(
                drug_id=drug.id, population="pediatric", text_en=NOT_AVAILABLE,
                text_ar="غير متاح / يتطلب مصدراً موثوقاً", is_verified=False,
            ))
            db.add(DrugPregnancy(
                drug_id=drug.id, text_en=NOT_AVAILABLE,
                text_ar="غير متاح / يتطلب مصدراً موثوقاً",
                risk_label="", risk_system="",
            ))
            db.add(DrugLactation(
                drug_id=drug.id, text_en=NOT_AVAILABLE,
                text_ar="غير متاح / يتطلب مصدراً موثوقاً",
            ))
            db.add(DrugWarning(
                drug_id=drug.id,
                text_en="DEMO DATA — always verify against official product information before clinical use.",
                text_ar="بيانات تجريبية — تحقق دائماً من معلومات المنتج الرسمية قبل الاستخدام السريري.",
            ))
            db.add(DrugSideEffect(
                drug_id=drug.id,
                text_en="DEMO DATA — side effect profile requires verified source.",
                text_ar="بيانات تجريبية — يتطلب مصدراً موثوقاً.",
            ))
            db.add(DrugContraindication(
                drug_id=drug.id,
                text_en="DEMO DATA — contraindications require verified source.",
                text_ar="بيانات تجريبية — الموانع تتطلب مصدراً موثوقاً.",
            ))
            db.add(DrugInteraction(
                drug_id=drug.id, interacting_agent="",
                text_en="DEMO DATA — interaction data requires verified source.",
                text_ar="بيانات تجريبية — التداخلات تتطلب مصدراً موثوقاً.",
            ))
            build_drug_search_fields(db, drug)

            # one demo product per drug
            product = Product(
                drug_id=drug.id,
                brand_name_en=f"DemoBrand {drug_en.split()[0]}",
                brand_name_ar=f"ديمو {drug_ar.split()[0] if drug_ar else ''}".strip(),
                strength="500 mg",
                strength_value="500",
                strength_unit="mg",
                dosage_form="tablet",
                route="oral",
                manufacturer_id=demo_manufacturer.id,
                barcode=f"DEMO{abs(hash(drug_en)) % 100000000:08d}",
                registration_number=f"DEMO-REG-{abs(hash(drug_en)) % 10000:04d}",
                is_demo=True,
                verification_status=VerificationStatus.IMPORTED_PENDING_REVIEW.value,
            )
            db.add(product)
            db.flush()
            db.add(ProductIngredient(
                product_id=product.id,
                ingredient_name_en=drug_en,
                ingredient_name_ar=drug_ar,
                drug_id=drug.id,
                strength="500 mg",
                is_primary=True,
            ))
            build_product_search_fields(product)
            counts["products"] += 1

    # ---- demo therapeutic alternatives (different ingredients, similar purpose) ----
    alt_pairs = [
        ("Enalapril", "Amlodipine"),
        ("Amoxicillin", "Azithromycin"),
        ("Omeprazole", "Ondansetron"),
        ("Salbutamol", "Montelukast"),
    ]
    for a, b in alt_pairs:
        da = db.scalar(select(Drug).where(Drug.generic_name_en == a))
        db_b = db.scalar(select(Drug).where(Drug.generic_name_en == b))
        if da and db_b:
            exists = db.scalar(select(DrugAlternative).where(
                DrugAlternative.drug_id == da.id, DrugAlternative.alternative_drug_id == db_b.id))
            if exists is None:
                db.add(DrugAlternative(
                    drug_id=da.id, alternative_drug_id=db_b.id,
                    rationale_en="DEMO DATA — therapeutic alternative example; not a substitution recommendation.",
                    rationale_ar="بيانات تجريبية — مثال على البدائل العلاجية؛ ليست توصية بالتبديل.",
                    evidence_level="demo",
                ))

    db.flush()
    _log.info("Seed complete: %s", counts)
    return counts
