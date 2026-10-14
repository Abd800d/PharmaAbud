"""SQLAlchemy models package.

Importing this module registers every model on the declarative Base so
`Base.metadata.create_all()` and Alembic see the complete schema.
"""
from app.db.base import Base
from app.models.ai import AiCitation, AiConversation, AiMessage
from app.models.common import (
    Bilingual,
    DuplicateKind,
    DrugRequestStatus,
    ImageKind,
    ImportRowStatus,
    ImportStatus,
    RecordStatus,
    SourceType,
    SyncOperation,
    SyncStatus,
    Timestamped,
    TranslationStatus,
    UUIDPk,
    VerificationStatus,
    Versioned,
    new_uuid,
    utcnow,
)
from app.models.drug import (
    Drug,
    DrugAdministration,
    DrugAlternative,
    DrugContraindication,
    DrugDosage,
    DrugFoodInteraction,
    DrugIndication,
    DrugInteraction,
    DrugLactation,
    DrugMonitoring,
    DrugOverdose,
    DrugPregnancy,
    DrugPrecaution,
    DrugSideEffect,
    DrugSynonym,
    DrugWarning,
)
from app.models.identity import Permission, RefreshToken, Role, RolePermission, User, UserRole
from app.models.operations import (
    AuditLog,
    DeviceSyncState,
    DrugRequest,
    Favorite,
    RecordLink,
    ImportErrorRecord,
    Import,
    ImportRow,
    RecentSearch,
    SearchTermStat,
    SyncQueueItem,
    VerificationRecord,
)
from app.models.product import Product, ProductImage, ProductIngredient, ProductPackage
from app.models.reference import ContentSource, DrugSource, ProductSource, Source, Translation
from app.models.taxonomy import (
    BodySystem,
    Country,
    DosageForm,
    DrugClassification,
    Manufacturer,
    PharmacologicalClass,
    Route,
    TherapeuticGroup,
)

__all__ = [
    "Base",
    "AiCitation", "AiConversation", "AiMessage",
    "Bilingual", "DuplicateKind", "DrugRequestStatus", "ImageKind",
    "ImportRowStatus", "ImportStatus", "RecordStatus", "SourceType",
    "SyncOperation", "SyncStatus", "Timestamped", "TranslationStatus",
    "UUIDPk", "VerificationStatus", "Versioned", "new_uuid", "utcnow",
    "Drug", "DrugAdministration", "DrugAlternative", "DrugContraindication",
    "DrugDosage", "DrugFoodInteraction", "DrugIndication", "DrugInteraction",
    "DrugLactation", "DrugMonitoring", "DrugOverdose", "DrugPregnancy",
    "DrugPrecaution", "DrugSideEffect", "DrugSynonym", "DrugWarning",
    "Permission", "RefreshToken", "Role", "RolePermission", "User", "UserRole",
    "AuditLog", "DeviceSyncState", "DrugRequest", "Favorite",
    "ImportErrorRecord", "Import", "ImportRow", "RecentSearch", "RecordLink",
    "SearchTermStat", "SyncQueueItem", "VerificationRecord",
    "Product", "ProductImage", "ProductIngredient", "ProductPackage",
    "ContentSource", "DrugSource", "ProductSource", "Source", "Translation",
    "BodySystem", "Country", "DosageForm", "DrugClassification",
    "Manufacturer", "PharmacologicalClass", "Route", "TherapeuticGroup",
]
