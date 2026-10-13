"""Commercial product tables: product, ingredients, packages, images.

Products are strictly separated from the scientific drug entity (§5).
Combination products carry multiple product_ingredients rows.
"""
from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import ImageKind, Timestamped, UUIDPk, VerificationStatus, Versioned


class Product(Base, UUIDPk, Timestamped, Versioned):
    __tablename__ = "drug_products"

    drug_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("drugs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    brand_name_en: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    brand_name_ar: Mapped[str] = mapped_column(String(255), default="", nullable=False, index=True)
    strength: Mapped[str] = mapped_column(String(128), default="", nullable=False, index=True)
    strength_value: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    strength_unit: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    dosage_form: Mapped[str] = mapped_column(String(64), default="", nullable=False, index=True)
    route: Mapped[str] = mapped_column(String(64), default="", nullable=False, index=True)
    manufacturer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("manufacturers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    manufacturer_country_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("countries.id", ondelete="SET NULL"), nullable=True, index=True
    )
    marketing_country_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("countries.id", ondelete="SET NULL"), nullable=True, index=True
    )
    barcode: Mapped[str] = mapped_column(String(64), default="", nullable=False, index=True)
    gtin: Mapped[str] = mapped_column(String(64), default="", nullable=False, index=True)
    registration_number: Mapped[str] = mapped_column(String(128), default="", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)  # active | discontinued | unknown
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    verification_status: Mapped[str] = mapped_column(
        String(48), default=VerificationStatus.DRAFT.value, nullable=False, index=True
    )
    search_text: Mapped[str] = mapped_column(Text, default="", nullable=False)

    drug = relationship("Drug", back_populates="products", lazy="selectin")
    ingredients: Mapped[list["ProductIngredient"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", lazy="selectin"
    )
    packages: Mapped[list["ProductPackage"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", lazy="selectin"
    )
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", lazy="selectin"
    )
    manufacturer = relationship("Manufacturer", lazy="selectin")


class ProductIngredient(Base, UUIDPk):
    """One row per active ingredient (combination products have 2+)."""

    __tablename__ = "product_ingredients"
    __table_args__ = (UniqueConstraint("product_id", "ingredient_name_en", name="uq_product_ingredient"),)

    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("drug_products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ingredient_name_en: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    ingredient_name_ar: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    drug_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("drugs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    strength: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    strength_value: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    strength_unit: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    product: Mapped[Product] = relationship(back_populates="ingredients", lazy="selectin")


class ProductPackage(Base, UUIDPk, Timestamped):
    __tablename__ = "product_packages"

    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("drug_products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    package_size: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    package_description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    package_description_ar: Mapped[str] = mapped_column(Text, default="", nullable=False)
    barcode: Mapped[str] = mapped_column(String(64), default="", nullable=False, index=True)
    gtin: Mapped[str] = mapped_column(String(64), default="", nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    product: Mapped[Product] = relationship(back_populates="packages", lazy="selectin")


class ProductImage(Base, UUIDPk, Timestamped):
    """Permanent object-storage record for a product image (§16)."""

    __tablename__ = "product_images"

    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("drug_products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), default=ImageKind.FRONT_PACKAGE.value, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(32), default="local", nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), default="image/jpeg", nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    width: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    height: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    thumbnail_path: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    source: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    copyright_info: Mapped[str] = mapped_column(Text, default="", nullable=False)
    uploaded_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verification_status: Mapped[str] = mapped_column(
        String(48), default=VerificationStatus.PENDING_VERIFICATION.value, nullable=False, index=True
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    product: Mapped[Product] = relationship(back_populates="images", lazy="selectin")
