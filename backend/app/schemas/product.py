"""Product schemas (commercial entity)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class IngredientIn(BaseModel):
    ingredient_name_en: str
    ingredient_name_ar: str = ""
    drug_id: Optional[str] = None
    strength: str = ""
    strength_value: str = ""
    strength_unit: str = ""
    is_primary: bool = True


class ProductCreate(BaseModel):
    drug_id: Optional[str] = None
    brand_name_en: str = Field(..., min_length=1, max_length=255)
    brand_name_ar: str = ""
    strength: str = ""
    strength_value: str = ""
    strength_unit: str = ""
    dosage_form: str = ""
    route: str = ""
    manufacturer_id: Optional[str] = None
    manufacturer_name: Optional[str] = None
    manufacturer_country_id: Optional[str] = None
    marketing_country_id: Optional[str] = None
    barcode: str = ""
    gtin: str = ""
    registration_number: str = ""
    status: str = "active"
    is_demo: bool = True
    ingredients: List[IngredientIn] = []


class ProductUpdate(BaseModel):
    drug_id: Optional[str] = None
    brand_name_en: Optional[str] = None
    brand_name_ar: Optional[str] = None
    strength: Optional[str] = None
    dosage_form: Optional[str] = None
    route: Optional[str] = None
    manufacturer_id: Optional[str] = None
    manufacturer_country_id: Optional[str] = None
    marketing_country_id: Optional[str] = None
    barcode: Optional[str] = None
    registration_number: Optional[str] = None
    status: Optional[str] = None


class ProductOut(BaseModel):
    id: str
    drug_id: Optional[str] = None
    brand_name_en: str
    brand_name_ar: str = ""
    strength: str = ""
    dosage_form: str = ""
    route: str = ""
    barcode: str = ""
    registration_number: str = ""
    status: str = "active"
    is_demo: bool = True
    verification_status: str
    record_version: int = 1
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductDetailOut(ProductOut):
    strength_value: str = ""
    strength_unit: str = ""
    gtin: str = ""
    manufacturer_id: Optional[str] = None
    manufacturer_name: Optional[str] = None
    manufacturer_country_id: Optional[str] = None
    marketing_country_id: Optional[str] = None
    ingredients: List[dict] = []
    packages: List[dict] = []
    images: List[dict] = []
    sources: List[dict] = []
    drug: Optional[DrugOutBrief] = None  # noqa: F821 — resolved below


class DrugOutBrief(BaseModel):
    id: str
    generic_name_en: str
    generic_name_ar: str = ""
    verification_status: str

    model_config = {"from_attributes": True}


# resolve forward reference
ProductDetailOut.model_rebuild()
