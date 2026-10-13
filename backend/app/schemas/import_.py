"""Import engine schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ImportOut(BaseModel):
    id: str
    filename: str
    file_format: str
    status: str
    entity_type: str
    total_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0
    duplicate_rows: int = 0
    imported_rows: int = 0
    error_message: str = ""
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ColumnMapping(BaseModel):
    mapping: Dict[str, str] = Field(default_factory=dict, description="source column -> canonical field")


class ImportExecuteRequest(BaseModel):
    mapping: Dict[str, str] = Field(default_factory=dict)
    entity_type: str = Field(default="product", pattern="^(drug|product)$")
    source_id: Optional[str] = None
    commit: bool = False


class ImportErrorOut(BaseModel):
    id: str
    row_number: int
    field: str
    value: str
    error: str
    suggested_correction: str = ""
    status: str = "open"

    model_config = {"from_attributes": True}


class ImportPreviewOut(BaseModel):
    total_rows: int
    valid_rows: int
    invalid_rows: int
    duplicate_rows: int
    columns_detected: List[str]
    suggested_mapping: Dict[str, str]
    sample_rows: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]
