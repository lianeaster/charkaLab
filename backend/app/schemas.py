from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class MaterialSuggestion(BaseModel):
    id: int
    name: str
    has_pit_variants: bool


class FormOption(BaseModel):
    part: str = "whole"
    form: str
    pit: str


class MaterialFormsResponse(BaseModel):
    id: int
    name: str
    has_pit_variants: bool
    options: List[FormOption]


class CharacteristicOut(BaseModel):
    id: int
    name: str


class BaseOut(BaseModel):
    id: int
    name: str


class MaterialSelection(BaseModel):
    material_id: int
    part: str = Field(default="whole")
    form: str = Field(default="fresh")
    pit: str = Field(default="na")


class GenerateRequest(BaseModel):
    main_material: MaterialSelection
    additional_materials: List[MaterialSelection] = Field(default_factory=list, max_length=10)
    base_id: Optional[int] = None
    desired_characteristics: List[int] = Field(default_factory=list)


class CompoundContribution(BaseModel):
    compound: str
    kind: str
    characteristics: List[str]


class MaterialInComposition(BaseModel):
    material_id: int
    name: str
    part: str = "whole"
    form: str
    pit: str
    role: str  # main | additional | suggested | balance | harmony | sweetener


class CharacteristicScore(BaseModel):
    name: str
    score: float
    covered: bool


class RecipeVariant(BaseModel):
    title: str
    match_score: float
    balance_score: float
    materials: List[MaterialInComposition]
    aroma_profile: List[CharacteristicScore]
    taste_profile: List[CharacteristicScore]
    covered: List[str]
    missing: List[str]
    compounds: List[CompoundContribution]
    balance_notes: List[str] = Field(default_factory=list)
    explanation: str


class GenerateResponse(BaseModel):
    base: Optional[str] = None
    desired: List[str]
    variants: List[RecipeVariant]
