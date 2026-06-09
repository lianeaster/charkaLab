from __future__ import annotations

from typing import List, Optional

from sqlalchemy import Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# form values (спосіб приготування) for MaterialCompound
FORM_FRESH = "fresh"
FORM_DRY = "dry"
FORM_EXTRACT = "extract"
FORM_OIL = "oil"
FORM_JUICE = "juice"
FORMS = (FORM_FRESH, FORM_DRY, FORM_EXTRACT, FORM_OIL, FORM_JUICE)

# part values (частина сировини / препарат) — у однієї сировини частини
# (квіти, цедра, плід, ягоди...) мають різний аромат і смак
PART_WHOLE = "whole"
PART_FLOWER = "flower"
PART_ZEST = "zest"
PART_FRUIT = "fruit"
PART_BERRY = "berry"
PART_LEAF = "leaf"
PART_ROOT = "root"
PART_BARK = "bark"
PART_SEED = "seed"
PART_HERB = "herb"
PART_NEEDLE = "needle"
PART_RHIZOME = "rhizome"
PART_RESIN = "resin"
PARTS = (
    PART_WHOLE, PART_FLOWER, PART_ZEST, PART_FRUIT, PART_BERRY, PART_LEAF,
    PART_ROOT, PART_BARK, PART_SEED, PART_HERB, PART_NEEDLE, PART_RHIZOME,
    PART_RESIN,
)

# pit values
PIT_WITH = "with"
PIT_WITHOUT = "without"
PIT_NA = "na"
PITS = (PIT_WITH, PIT_WITHOUT, PIT_NA)

# compound kinds
KIND_AROMA = "aroma"
KIND_TASTE = "taste"
KIND_BOTH = "both"
KINDS = (KIND_AROMA, KIND_TASTE, KIND_BOTH)


class RawMaterial(Base):
    __tablename__ = "raw_materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    # чи має сировина варіанти "з кісточкою / без кісточки"
    has_pit_variants: Mapped[bool] = mapped_column(default=False)

    compounds: Mapped[List["MaterialCompound"]] = relationship(
        back_populates="raw_material", cascade="all, delete-orphan"
    )


class AromaCompound(Base):
    __tablename__ = "aroma_compounds"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    # aroma | taste | both
    kind: Mapped[str] = mapped_column(String(10), default=KIND_BOTH)

    materials: Mapped[List["MaterialCompound"]] = relationship(
        back_populates="compound", cascade="all, delete-orphan"
    )
    characteristics: Mapped[List["CompoundCharacteristic"]] = relationship(
        back_populates="compound", cascade="all, delete-orphan"
    )


class Characteristic(Base):
    __tablename__ = "characteristics"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True, index=True)

    compounds: Mapped[List["CompoundCharacteristic"]] = relationship(
        back_populates="characteristic", cascade="all, delete-orphan"
    )


class MaterialCompound(Base):
    """Концентрація аромосполуки в сировині залежно від форми та наявності кісточки."""

    __tablename__ = "material_compounds"
    __table_args__ = (
        UniqueConstraint(
            "raw_material_id", "compound_id", "part", "form", "pit",
            name="uq_material_compound_part_form_pit",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_material_id: Mapped[int] = mapped_column(
        ForeignKey("raw_materials.id", ondelete="CASCADE"), index=True
    )
    compound_id: Mapped[int] = mapped_column(
        ForeignKey("aroma_compounds.id", ondelete="CASCADE"), index=True
    )
    part: Mapped[str] = mapped_column(String(12), default=PART_WHOLE)
    form: Mapped[str] = mapped_column(String(10), default=FORM_FRESH)
    pit: Mapped[str] = mapped_column(String(10), default=PIT_NA)
    intensity: Mapped[float] = mapped_column(Float, default=1.0)

    raw_material: Mapped["RawMaterial"] = relationship(back_populates="compounds")
    compound: Mapped["AromaCompound"] = relationship(back_populates="materials")


class CompoundCharacteristic(Base):
    __tablename__ = "compound_characteristics"
    __table_args__ = (
        UniqueConstraint(
            "compound_id", "characteristic_id",
            name="uq_compound_characteristic",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    compound_id: Mapped[int] = mapped_column(
        ForeignKey("aroma_compounds.id", ondelete="CASCADE"), index=True
    )
    characteristic_id: Mapped[int] = mapped_column(
        ForeignKey("characteristics.id", ondelete="CASCADE"), index=True
    )
    weight: Mapped[float] = mapped_column(Float, default=1.0)

    compound: Mapped["AromaCompound"] = relationship(back_populates="characteristics")
    characteristic: Mapped["Characteristic"] = relationship(back_populates="compounds")


class Base_(Base):
    """Основа напою: спирт пшеничний/цукровий, вино червоне/біле."""

    __tablename__ = "bases"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
