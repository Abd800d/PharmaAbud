"""Drug monograph schemas."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class DrugBase(BaseModel):
    generic_name_en: str = Field(..., min_length=1, max_length=255)
    generic_name_ar: str = Field(default="", max_length=255)
    scientific_name: str = ""
    pronunciation: str = ""
    drug_class: str = ""
    pharmacological_class_name: str = ""
    therapeutic_class_name: str = ""
    drug_category: str = ""
    atc_code: str = ""
    cas_number: str = ""
    molecular_formula: str = ""
    molecular_weight: str = ""
    overview_en: str = ""
    overview_ar: str = ""
    mechanism_en: str = ""
    mechanism_ar: str = ""
    pharmacodynamics_en: str = ""
    pharmacodynamics_ar: str = ""
    pharmacokinetics_en: str = ""
    pharmacokinetics_ar: str = ""
    absorption_en: str = ""
    absorption_ar: str = ""
    distribution_en: str = ""
    distribution_ar: str = ""
    metabolism_en: str = ""
    metabolism_ar: str = ""
    elimination_en: str = ""
    elimination_ar: str = ""
    half_life: str = ""
    is_combination: bool = False
    is_demo: bool = True


class DrugCreate(DrugBase):
    pass


class DrugUpdate(BaseModel):
    generic_name_en: Optional[str] = None
    generic_name_ar: Optional[str] = None
    scientific_name: Optional[str] = None
    pronunciation: Optional[str] = None
    drug_class: Optional[str] = None
    pharmacological_class_name: Optional[str] = None
    therapeutic_class_name: Optional[str] = None
    drug_category: Optional[str] = None
    atc_code: Optional[str] = None
    cas_number: Optional[str] = None
    molecular_formula: Optional[str] = None
    molecular_weight: Optional[str] = None
    overview_en: Optional[str] = None
    overview_ar: Optional[str] = None
    mechanism_en: Optional[str] = None
    mechanism_ar: Optional[str] = None
    pharmacodynamics_en: Optional[str] = None
    pharmacodynamics_ar: Optional[str] = None
    pharmacokinetics_en: Optional[str] = None
    pharmacokinetics_ar: Optional[str] = None
    absorption_en: Optional[str] = None
    absorption_ar: Optional[str] = None
    distribution_en: Optional[str] = None
    distribution_ar: Optional[str] = None
    metabolism_en: Optional[str] = None
    metabolism_ar: Optional[str] = None
    elimination_en: Optional[str] = None
    elimination_ar: Optional[str] = None
    half_life: Optional[str] = None
    is_combination: Optional[bool] = None
    is_demo: Optional[bool] = None


class DrugSynonymIn(BaseModel):
    term: str
    language: str = "en"


class DrugClassificationIn(BaseModel):
    pharmacological_class_id: str
    is_primary: bool = False


class DrugOut(BaseModel):
    id: str
    generic_name_en: str
    generic_name_ar: str
    scientific_name: str = ""
    drug_class: str = ""
    pharmacological_class_name: str = ""
    therapeutic_class_name: str = ""
    atc_code: str = ""
    is_combination: bool = False
    is_demo: bool = True
    verification_status: str
    record_version: int = 1
    created_at: datetime
    updated_at: datetime
    verified_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SectionText(BaseModel):
    text_en: str = ""
    text_ar: str = ""


class DosageIn(BaseModel):
    population: str = "adult"
    indication: str = ""
    route: str = ""
    text_en: str = Field(..., description='e.g. dose text, or "Not available / Requires verified source"')
    text_ar: str = ""
    dose_value: str = ""
    dose_unit: str = ""
    frequency: str = ""
    max_dose: str = ""
    duration: str = ""
    is_verified: bool = False


class DrugDetailOut(DrugOut):
    overview_en: str = ""
    overview_ar: str = ""
    mechanism_en: str = ""
    mechanism_ar: str = ""
    pharmacodynamics_en: str = ""
    pharmacodynamics_ar: str = ""
    pharmacokinetics_en: str = ""
    pharmacokinetics_ar: str = ""
    half_life: str = ""
    synonyms: List[DrugSynonymIn] = []
    indications: List[dict] = []
    contraindications: List[dict] = []
    warnings: List[dict] = []
    precautions: List[dict] = []
    side_effects: List[dict] = []
    interactions: List[dict] = []
    food_interactions: List[dict] = []
    dosages: List[dict] = []
    pregnancy: Optional[dict] = None
    lactation: Optional[dict] = None
    monitoring: List[dict] = []
    administration: List[dict] = []
    overdose: Optional[dict] = None
    classifications: List[dict] = []
    sources: List[dict] = []
