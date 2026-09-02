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
    # сезон (spring|summer|autumn|winter); None — не враховувати сезонність
    season: Optional[str] = None


class EditedMaterial(MaterialSelection):
    # роль зберігаємо, щоб не втратити підпис («підібрана»/«для гармонії» тощо);
    # користувацькі додавання приходять як "additional"
    role: str = "additional"


class RecomputeRequest(BaseModel):
    """Перерахунок одного варіанта з відредагованим складом.

    materials — усі НЕосновні й НЕпідсолоджувальні інгредієнти, які користувач
    залишив/додав. Основна сировина фіксована; підсолоджувач (цукор/мед) та
    баланс перераховуються автоматично. Нові ароматичні інгредієнти алгоритм
    сам НЕ додає — склад лишається саме таким, як його зібрав користувач.
    """

    main_material: MaterialSelection
    materials: List[EditedMaterial] = Field(default_factory=list, max_length=20)
    base_id: Optional[int] = None
    desired_characteristics: List[int] = Field(default_factory=list)
    audience_id: Optional[str] = None
    season: Optional[str] = None
    title: str = ""


class SurpriseRequest(BaseModel):
    """«Здивуй мене»: система сама добирає профілі під основну сировину.

    desired не задається — його генерує двигун (по 3 характеристики на рецепт,
    можуть різнитися між рецептами), максимізуючи збіг+баланс+гармонію.
    """

    main_material: MaterialSelection
    additional_materials: List[MaterialSelection] = Field(
        default_factory=list, max_length=10
    )
    base_id: Optional[int] = None
    audience_id: Optional[str] = None
    season: Optional[str] = None


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
    # сезон — щоб не пропонувати ноти, досяжні лише позасезонною свіжою сировиною
    season: Optional[str] = None


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


class OutOfSeasonItem(BaseModel):
    name: str
    # людська підказка, чим замінити позасезонну свіжу форму (суха/екстракт/сік),
    # або None — якщо консервованої форми немає
    suggestion: Optional[str] = None


class SeasonInfo(BaseModel):
    id: str
    name: str
    # обрана користувачем свіжа сировина, що поза сезоном (попередження)
    out_of_season: List[OutOfSeasonItem] = Field(default_factory=list)


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


class RecipeSimilarity(BaseModel):
    """Схожість композиції з відомою рецептурою (див. services/similarity.py).
    Присутня лише коли схожість перевищує поріг — щоб не засмічувати відповідь
    випадковими збігами."""

    percent: int
    # назва впізнаного напою («Джин (London Dry)»)
    drink: str = ""
    # сировина композиції, що входить і до характерного складу цього напою
    matched: List[str] = Field(default_factory=list)
    note: str = ""


class RecipeVariant(BaseModel):
    title: str
    # бажаний профіль саме цього варіанта (для «Здивуй мене» — свій на кожен
    # рецепт; для звичайної генерації збігається із загальним).
    desired: List[str] = Field(default_factory=list)
    match_score: float
    balance_score: float
    # гастрономічна гармонія: наскільки поєднання ароматичних родин їстівне
    # (1.0 — жодних дисонансів). На відміну від balance_score (рівновага осей),
    # ловить конфлікти на кшталт «часник + полуниця».
    harmony_score: float = 1.0
    harmony_notes: List[str] = Field(default_factory=list)
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
    # попередження (напр. позасезонна свіжа сировина при перерахунку складу)
    warnings: List[str] = Field(default_factory=list)
    # схожі відомі рецептури (від найближчої); порожньо — нічого не впізнано.
    # Композиція може нагадувати кілька напоїв, тож це список, а не один збіг.
    similarities: List[RecipeSimilarity] = Field(default_factory=list)


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
    season: Optional[SeasonInfo] = None
