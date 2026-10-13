"""Taxonomy / catalog schemas."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class BodySystemOut(BaseModel):
    id: str
    slug: str
    name_en: str
    name_ar: str
    description_en: str = ""
    description_ar: str = ""
    icon: str = ""
    sort_order: int = 0
    is_active: bool = True

    model_config = {"from_attributes": True}


class TherapeuticGroupOut(BaseModel):
    id: str
    body_system_id: str
    slug: str
    name_en: str
    name_ar: str
    sort_order: int = 0

    model_config = {"from_attributes": True}


class PharmacologicalClassOut(BaseModel):
    id: str
    therapeutic_group_id: str
    slug: str
    name_en: str
    name_ar: str
    sort_order: int = 0

    model_config = {"from_attributes": True}


class TaxonomyCreate(BaseModel):
    name_en: str = Field(..., min_length=1)
    name_ar: str = ""
    slug: str = ""
    description_en: str = ""
    description_ar: str = ""
    body_system_id: Optional[str] = None
    therapeutic_group_id: Optional[str] = None
    sort_order: int = 0


class DosageFormOut(BaseModel):
    id: str
    slug: str
    name_en: str
    name_ar: str
    is_active: bool = True

    model_config = {"from_attributes": True}


class RouteOut(BaseModel):
    id: str
    slug: str
    name_en: str
    name_ar: str
    is_active: bool = True

    model_config = {"from_attributes": True}


class CountryOut(BaseModel):
    id: str
    iso_code: str
    name_en: str
    name_ar: str

    model_config = {"from_attributes": True}


class ManufacturerOut(BaseModel):
    id: str
    name_en: str
    name_ar: str = ""
    country_id: Optional[str] = None
    website: str = ""
    notes: str = ""

    model_config = {"from_attributes": True}


class ManufacturerCreate(BaseModel):
    name_en: str = Field(..., min_length=1)
    name_ar: str = ""
    country_id: Optional[str] = None
    website: str = ""
    notes: str = ""


class SourceOut(BaseModel):
    id: str
    name: str
    url: str = ""
    source_type: str
    description: str = ""
    publication_date: str = ""
    retrieved_date: str = ""
    license_info: str = ""
    verification_status: str
    is_demo: bool = True

    model_config = {"from_attributes": True}


class SourceCreate(BaseModel):
    name: str = Field(..., min_length=1)
    url: str = ""
    source_type: str = "other"
    description: str = ""
    publication_date: str = ""
    retrieved_date: str = ""
    license_info: str = ""
    is_demo: bool = True
