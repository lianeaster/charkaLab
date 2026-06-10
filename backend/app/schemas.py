from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class MaterialSuggestion(BaseModel):
    id: int
    name: str
    has_pit_variants: bool
    aliases: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


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
    audience_id: Optional[str] = None


class AudienceOut(BaseModel):
    id: str
    name: str
    group: str  # adults | special
    alcohol_free: bool
    suggest: bool
    forbidden_tags: List[str] = Field(default_factory=list)
    default_profile: List[str] = Field(default_factory=list)
    disclaimer: str = ""


class SuggestProfileRequest(BaseModel):
    audience_id: str
    main_material_id: Optional[int] = None
    # обраний варіант основної сировини — щоб не пропонувати ноти з іншого
    # препарату (напр. мигдальний/кісточковий «з кісточкою», коли обрано «без»)
    part: Optional[str] = None
    form: Optional[str] = None
    pit: Optional[str] = None


class SuggestProfileResponse(BaseModel):
    characteristic_ids: List[int] = Field(default_factory=list)
    characteristic_names: List[str] = Field(default_factory=list)


class AudienceInfo(BaseModel):
    id: str
    name: str
    alcohol_free: bool = False
    disclaimer: str = ""
    # приклади виключеної сировини (для прозорості банера)
    excluded_examples: List[str] = Field(default_factory=list)
    excluded_count: int = 0


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
    amount: float = 1.0  # відносна доза (основна сировина = 1.0)


class CharacteristicScore(BaseModel):
    name: str
    score: float
    covered: bool


class PyramidLayer(BaseModel):
    layer: str  # top | heart | base
    title: str
    notes: List[CharacteristicScore] = Field(default_factory=list)


class RecipeVariant(BaseModel):
    title: str
    match_score: float
    balance_score: float
    materials: List[MaterialInComposition]
    aroma_profile: List[CharacteristicScore]
    taste_profile: List[CharacteristicScore]
    covered: List[str]
    missing: List[str]
    weak: List[str] = Field(default_factory=list)
    compounds: List[CompoundContribution]
    balance_notes: List[str] = Field(default_factory=list)
    explanation: str
    pyramid: List[PyramidLayer] = Field(default_factory=list)


class BaseInfluence(BaseModel):
    name: str
    abv_hint: str = ""
    note: str = ""
    # характеристики бажаного профілю, що конфліктують з основою
    conflicts: List[str] = Field(default_factory=list)
    # характеристики бажаного профілю, що синергують з основою
    synergy: List[str] = Field(default_factory=list)
    message: str = ""


class ProfileFeasibility(BaseModel):
    # ok | dominated | impossible
    status: str = "ok"
    achievable: bool = True
    # бажані характеристики, яких не може дати жодна доступна сировина
    unreachable: List[str] = Field(default_factory=list)
    # сторонні ноти обраної сировини, що перебивають бажаний профіль
    dominating: List[str] = Field(default_factory=list)
    message: str = ""


class GenerateResponse(BaseModel):
    base: Optional[str] = None
    desired: List[str]
    variants: List[RecipeVariant]
    feasibility: ProfileFeasibility = Field(default_factory=ProfileFeasibility)
    base_influence: Optional[BaseInfluence] = None
    audience: Optional[AudienceInfo] = None
