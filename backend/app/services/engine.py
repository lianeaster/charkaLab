"""Движок підбору збалансованих композицій аромосполук під бажаний профіль.

Баланс смаку (за теорією міксології): у напої жоден смак не повинен домінувати.
Солодке пом'якшує гіркоту/терпкість/пекучість, кислота дає свіжість і ріже
надмірну солодкість, гіркота додає глибини. Якщо у смаку "вилазить" щось, що
перебиває ароматичний профіль, додаємо протилежний смак для балансу.

Для гармонії кожна композиція містить щонайменше MIN_INGREDIENTS інгредієнтів.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    AromaCompound,
    Base_,
    Characteristic,
    CompoundCharacteristic,
    FORM_DRY,
    FORM_EXTRACT,
    FORM_FRESH,
    FORM_JUICE,
    FORM_OIL,
    KIND_AROMA,
    KIND_BOTH,
    KIND_TASTE,
    MaterialCompound,
    RawMaterial,
    VOL_BASE,
    VOL_HEART,
    VOL_TOP,
)
from ..audiences import get_audience
from .. import seasons
from .. import harmony
from ..schemas import (
    AudienceInfo,
    BaseInfluence,
    CharacteristicScore,
    CompoundContribution,
    GenerateRequest,
    GenerateResponse,
    MaterialInComposition,
    OutOfSeasonItem,
    PyramidLayer,
    ProfileFeasibility,
    RecipeVariant,
    SeasonInfo,
    SuggestProfileResponse,
)

MAX_VARIANTS = 4
MAX_SUGGESTED = 3
MIN_INGREDIENTS = 4
# Пошук РІЗНОМАНІТНИХ композицій: показуємо кілька рецептів із різними
# інгредієнтами, а не майже однакові. Після кожного прийнятого варіанта його
# додані інгредієнти «банимо», щоб наступний будувався з інших — або взагалі не
# знайшовся (тоді чесно показуємо менше варіантів).
DIVERSE_ATTEMPTS = 6       # скільки різних наборів додатків пробуємо
SCORE_DELTA = 0.1          # лишаємо варіанти в межах цього від найкращого збігу
MIN_VARIANT_DIFF = 2       # мін. різниця у наборі доданих інгредієнтів між варіантами
# Стеля кількості ароматичних складових (без підсолоджувача): дозволяє додавати
# більше інгредієнтів, щоб краще «вписатися» в профіль.
MAX_INGREDIENTS = 7
# Цільова виразність кожної бажаної характеристики; поки нота слабша — додаємо
# ще чистих підсилювачів.
TARGET_STRENGTH = 0.8
# Мінімальний внесок інгредієнта саме в цільову ноту, щоб вважати, що він її
# реально підсилює. Якщо жодна доступна сировина не дає стільки «чисто» —
# ноту вважаємо недосяжною й припиняємо марні додавання.
MIN_REINFORCE = 0.3
MAX_BALANCE_STEPS = 3

# Поріг, з якого бажана нота вважається реально присутньою (а не слідовою):
# нижче COVERED_MIN — нота «не покрита»; між COVERED_MIN і WEAK_CEIL — «слабка»
# (присутня, але ледь чутна — чесно позначаємо, не видаючи за повноцінну).
COVERED_MIN = 0.25
WEAK_CEIL = 0.5

# Базові смакові осі балансу
SWEET = "солодкий"
SOUR = "кислий"
BITTER = "гіркий"
ASTRINGENT = "терпкий"
PUNGENT = "пекучий"
# "Гострі" структурні смаки, які потребують пом'якшення солодким
HARSH_AXES = (BITTER, ASTRINGENT, PUNGENT)
# Поріг, з якого смак вважається помітним
BALANCE_TOL = 0.5


SUGAR_NAME = "цукор"
HONEY_NAME = "мед"
# профіль, за якого солодкість краще давати медом (він додає ці ноти доречно)
HONEY_AFFINITY = {"медовий", "квітковий"}
# скільки солодкості додати «понад» рівень гострих смаків, щоб напій не був різким
SUGAR_HEADROOM = 0.1

# ваги підсумкової оцінки відповідності профілю
W_COVERAGE = 0.45  # скільки бажаних характеристик присутні
W_STRENGTH = 0.20  # наскільки вони виражені
W_PRECISION = 0.35  # яка частка сигналу припадає саме на бажане (а не на «шум»)

# Штраф за «шум» (характеристики поза бажаним профілем) під час відбору сировини.
# Чим вищий — тим неохочіше алгоритм бере інгредієнти, що тягнуть сторонні ноти.
OFF_PENALTY = 0.8

# «Споріднені ноти»: коли користувач просить певну характеристику, деякі сусідні
# ноти сприймаються не як чистий шум, а як ЧАСТКОВЕ її втілення. Це дозволяє
# алгоритму брати сировину на кшталт м'яти під «свіжий» (її ментолово-охолоджуючі
# ноти — родичі свіжості), а не відкидати її як надто «шумну».
# Формат: бажана_нота -> {споріднена_нота: частка_спорідненості (0..1)}.
KIN: Dict[str, Dict[str, float]] = {
    "свіжий": {
        "зелений": 0.6,  # зелено-листяна свіжість (огірок, листковий спирт) — чиста
        "ментоловий": 0.6,
        "м'ятний": 0.6,
        "охолоджуючий": 0.6,
        "евкаліптовий": 0.5,
        "камфорний": 0.4,
    },
    # трав'яний невіддільний від зелено-сінних та смолисто-хвойних «родичів»:
    # мірцен (хміль) тягне хвойний/ялівцевий, азулен (ромашка) — бальзамічний.
    # Без цього будь-яка справжня трав'яна сировина відкидається як «шумна».
    "трав'яний": {
        "зелений": 0.7,
        "сінний": 0.6,
        "бальзамічний": 0.5,
        "ялівцевий": 0.5,
        "анісовий": 0.4,
        "камфорний": 0.4,
        "хвойний": 0.4,
        "евкаліптовий": 0.4,
        "деревинний": 0.3,
        "смолистий": 0.3,
    },
}


def _split_on_off(
    name: str, value: float, desired_set: Set[str]
) -> Tuple[float, float]:
    """Розкласти внесок ноти на «корисний» (on) і «шум» (off) з урахуванням
    спорідненості. Бажана нота — повністю on; солодкість — нейтральна; споріднена
    до якоїсь бажаної — частково on, частково off; решта — повністю off."""
    if name in desired_set:
        return value, 0.0
    if name == SWEET:
        return 0.0, 0.0
    best_kin = 0.0
    for d in desired_set:
        w = KIN.get(d, {}).get(name, 0.0)
        if w > best_kin:
            best_kin = w
    if best_kin > 0.0:
        return value * best_kin, value * (1.0 - best_kin)
    return 0.0, value

# Дозування інгредієнтів. Основна сировина йде в повному обсязі (MAIN_AMOUNT),
# а дозу решти алгоритм підбирає сам у межах [DOSE_MIN, DOSE_MAX] залежно від
# «чистоти» внеску: що влучніше інгредієнт б'є в бажаний профіль і що менше
# шумить, то більша його частка. Шумні інгредієнти стишуються до акценту.
MAIN_AMOUNT = 1.0
DOSE_MIN = 0.15
DOSE_MAX = 0.85
# доза ароматичних нот підсолоджувача (мед); сама солодкість дозується окремо
SWEETENER_AROMA = 0.6

# Стеля дози допоміжного інгредієнта за його ярусом летючості. Верхні (леткі)
# ноти беремо стримано — це короткий старт, а не тіло напою (саме так гамуємо
# «цитрус перебиває»); серединні — щедріше; базові — помірно, бо вони стійкі.
LAYER_DOSE_CAP = {VOL_TOP: 0.4, VOL_HEART: 0.85, VOL_BASE: 0.55}
# Поріг, нижче якого база вважається слабкою → додаємо ноту для післясмаку
BASE_MIN = 0.5

# Спеціальна назва для динамічної основи — дистилят з основної сировини.
# Реальний профіль будується у generate() з аромосполук головної сировини.
DISTILLATE_BASE_NAME = "ароматний дистилят (основна сировина)"

# Профілі основ: власний смаковий внесок, ABV-рекомендації, конфлікти, синергія.
# ABV визначає, що реально витягується: спирт (40-70%) — ліпофільні сполуки
# (терпени, ефірні олії, смоли); вино (11-14%) — переважно водорозчинні
# (антоціани, таніни, кислоти).
# profile_contrib: список (характеристика, інтенсивність, kind, ярус летючості) —
# власний внесок основи у профіль напою. Спирти 40-70% витягують ефірні олії;
# вина 11-14% несуть водорозчинні таніни/кислоти/антоціани (важка база).
BASE_PROFILES: Dict[str, Dict] = {
    "спирт пшеничний": {
        "abv": 70,
        "abv_hint": "40–70% — добре витягує ефірні олії, терпени, смоли",
        "profile_contrib": [],
        "conflicts": set(),
        "synergy": {"свіжий", "цитрусовий", "квітковий", "трав'яний", "хвойний"},
        "note": "Нейтральна основа — підкреслює аромат сировини, не вносить власних нот.",
    },
    "спирт цукровий": {
        "abv": 65,
        "abv_hint": "40–65% — добре витягує ефірні олії; злегка м'якший за пшеничний",
        "profile_contrib": [(SWEET, 0.15, KIND_TASTE, VOL_HEART)],
        "conflicts": set(),
        "synergy": {"фруктовий", "солодкий", "ягідний", "медовий"},
        "note": "Злегка солодкуватий, м'який — підсилює фруктово-ягідні та медові ноти.",
    },
    "вино червоне": {
        "abv": 13,
        "abv_hint": "11–14% — витягує антоціани, таніни, кислоти; ефірні олії — слабко",
        "profile_contrib": [
            (ASTRINGENT, 0.4, KIND_TASTE, VOL_BASE),
            ("ягідний", 0.3, KIND_AROMA, VOL_HEART),
            (SOUR, 0.25, KIND_TASTE, VOL_TOP),
        ],
        "conflicts": {"квітковий", "медовий", "лавандовий", "ванільний", "цитрусовий"},
        "synergy": {"ягідний", ASTRINGENT, "кісточковий", SOUR, "фруктовий"},
        "note": (
            "Танінний, ягідний, кислотний. Витягує переважно водорозчинні сполуки. "
            "Конфліктує з ніжними квітковими та ванільно-медовими нотами — танін їх перебиває."
        ),
    },
    "вино біле": {
        "abv": 12,
        "abv_hint": "11–13% — витягує антоціани, кислоти; ефірні олії — слабко",
        "profile_contrib": [
            ("свіжий", 0.25, KIND_AROMA, VOL_TOP),
            ("квітковий", 0.15, KIND_AROMA, VOL_HEART),
            (SOUR, 0.2, KIND_TASTE, VOL_TOP),
        ],
        "conflicts": {"смолистий", "деревинний", "землистий", "ялівцевий", "кедровий"},
        "synergy": {"цитрусовий", "квітковий", "свіжий", "медовий", "трав'яний"},
        "note": (
            "Свіже, квіткове, кислотне. Добре з цитрусово-квітковими профілями. "
            "Конфліктує з важкими смолистими та деревинними нотами."
        ),
    },
    # --- Безалкогольні основи (0% ABV) ---
    # Без спирту майже не екстрагуються ефірні олії/терпени — лише водорозчинні
    # цукри, кислоти, антоціани. Тому «ефір-залежні» ноти позначені як конфлікт:
    # алгоритм віддасть перевагу водорозчинній сировині (ягоди, фрукти, кислоти).
    "сік (фруктовий)": {
        "abv": 0,
        "abv_hint": "0% (безалкогольна) — витягує цукри/кислоти/антоціани; ефірні олії майже не екстрагує",
        "profile_contrib": [
            ("фруктовий", 0.4, KIND_AROMA, VOL_HEART),
            (SWEET, 0.3, KIND_TASTE, VOL_HEART),
            (SOUR, 0.15, KIND_TASTE, VOL_TOP),
        ],
        "conflicts": {"смолистий", "ялівцевий", "хвойний", "камфорний", "деревинний"},
        "synergy": {"фруктовий", "ягідний", "тропічний", "цитрусовий", "солодкий"},
        "note": (
            "Безалкогольна фруктова основа: солодко-фруктова, з легкою кислотою. "
            "Несе власний фруктовий характер; ефірно-олійні (смолисті, хвойні) "
            "ноти без спирту майже не витягуються."
        ),
    },
    "мінеральна вода газована": {
        "abv": 0,
        "abv_hint": "0% — нейтральний газований носій; екстракція слабка, додає лише свіжість бульбашок",
        "profile_contrib": [
            ("свіжий", 0.15, KIND_AROMA, VOL_TOP),
        ],
        "conflicts": {"смолистий", "ялівцевий", "хвойний", "камфорний", "деревинний"},
        "synergy": {"свіжий", "цитрусовий", "ягідний", "м'ятний"},
        "note": (
            "Нейтральний газований носій (spritz-стиль): майже не вносить смаку, "
            "лише освіжає грою бульбашок. Без спирту погано витягує ефірні олії — "
            "найкраще з ягідно-фруктовими та свіжими профілями."
        ),
    },
}


@dataclass
class ResolvedSelection:
    material_id: int
    name: str
    part: str
    form: str
    pit: str
    role: str  # main | additional | suggested | balance | harmony | sweetener | base_spirit
    sweet_add: float = 0.0  # пряма солодкість (цукор), без аромату
    amount: float = 1.0  # частка (доза) інгредієнта; основна сировина = 1.0
    # готовий внесок у профіль (для основи): список (char, value, kind, volatility).
    # Якщо заданий — береться напряму, без читання сировини з БД.
    inline_contrib: Optional[List[Tuple[str, float, str, str]]] = None


@dataclass
class Profile:
    aroma: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    taste: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    compounds: Dict[str, Tuple[str, Set[str]]] = field(default_factory=dict)
    # ольфакторна піраміда: top|heart|base → {характеристика: інтенсивність}
    layers: Dict[str, Dict[str, float]] = field(
        default_factory=lambda: {
            VOL_TOP: defaultdict(float),
            VOL_HEART: defaultdict(float),
            VOL_BASE: defaultdict(float),
        }
    )

    def total(self, char_name: str) -> float:
        return self.aroma.get(char_name, 0.0) + self.taste.get(char_name, 0.0)

    def layer_total(self, layer: str) -> float:
        return sum(self.layers.get(layer, {}).values())


def _compound_chars(compound: AromaCompound) -> Dict[str, float]:
    return {
        cc.characteristic.name: cc.weight
        for cc in compound.characteristics
        if cc.characteristic is not None
    }


def _add_selection_to_profile(
    db: Session, selection: ResolvedSelection, profile: Profile
) -> None:
    # Основа з готовим внеском (спирт/вино/дистилят) — додаємо напряму.
    if selection.inline_contrib is not None:
        for char_name, value, kind, layer in selection.inline_contrib:
            if value <= 0:
                continue
            if kind in (KIND_AROMA, KIND_BOTH):
                profile.aroma[char_name] += value
            if kind in (KIND_TASTE, KIND_BOTH):
                profile.taste[char_name] += value
            profile.layers[layer][char_name] += value
        return

    is_sweetener = selection.role == "sweetener" or selection.sweet_add > 0
    # Пряма (дозована) солодкість підсолоджувача — цукру чи меду
    if selection.sweet_add > 0:
        profile.taste[SWEET] += selection.sweet_add
        profile.layers[VOL_HEART][SWEET] += selection.sweet_add
        marker = selection.name or SUGAR_NAME
        if marker not in profile.compounds:
            profile.compounds[marker] = (KIND_TASTE, {SWEET})
        else:
            profile.compounds[marker][1].add(SWEET)
    # Чистий цукор не має сировини/аромату
    if selection.material_id <= 0:
        return
    amount = selection.amount
    # Серце напою — завжди основна сировина: її ноти кладемо в шар heart
    # незалежно від хімії. Решта — за летючістю самих сполук.
    force_heart = selection.role == "main"
    rows = db.scalars(
        select(MaterialCompound).where(
            MaterialCompound.raw_material_id == selection.material_id,
            MaterialCompound.part == selection.part,
            MaterialCompound.form == selection.form,
            MaterialCompound.pit == selection.pit,
        )
    ).all()
    for mc in rows:
        compound = db.get(AromaCompound, mc.compound_id)
        if compound is None:
            continue
        layer = VOL_HEART if force_heart else (compound.volatility or VOL_HEART)
        char_weights = _compound_chars(compound)
        recorded: Set[str] = set()
        for char_name, weight in char_weights.items():
            contribution = mc.intensity * weight * amount
            added_to_layer = False
            if compound.kind in (KIND_AROMA, KIND_BOTH):
                profile.aroma[char_name] += contribution
                profile.layers[layer][char_name] += contribution
                added_to_layer = True
                recorded.add(char_name)
            if compound.kind in (KIND_TASTE, KIND_BOTH):
                # для підсолоджувача (мед) дозу солодкості вже задано через
                # sweet_add — власні смакові ноти не додаємо, щоб не дублювати
                if not is_sweetener:
                    profile.taste[char_name] += contribution
                    if not added_to_layer:
                        profile.layers[layer][char_name] += contribution
                    recorded.add(char_name)
        if not recorded:
            continue
        if compound.name not in profile.compounds:
            profile.compounds[compound.name] = (compound.kind, recorded)
        else:
            profile.compounds[compound.name][1].update(recorded)


def _build_profile(db: Session, selections: List[ResolvedSelection]) -> Profile:
    profile = Profile()
    for sel in selections:
        _add_selection_to_profile(db, sel, profile)
    return profile


def _score(profile: Profile, desired_names: List[str]) -> float:
    """Оцінка відповідності бажаному профілю: покриття + сила + точність.

    Точність (precision) — яка частка всього ароматично-смакового сигналу
    припадає саме на бажані характеристики. Це штрафує композиції, де
    «вилазять» сторонні профілі (напр. цитрус/пекучість), навіть якщо
    бажані ноти формально присутні.
    """
    if not desired_names:
        return 0.0
    desired_set = set(desired_names)
    scores = [profile.total(name) for name in desired_names]
    covered = sum(1 for s in scores if s >= COVERED_MIN)
    coverage_ratio = covered / len(desired_names)
    capped = [min(s, 1.0) for s in scores]
    strength = sum(capped) / len(capped)

    # Точність рахуємо з урахуванням спорідненості: ноти-родичі бажаних (напр.
    # ментоловий/охолоджуючий для «свіжий») лише частково вважаються «шумом».
    on_signal = sum(scores)
    off_signal = 0.0
    for name, value in profile.aroma.items():
        if name not in desired_set:
            _on, off_part = _split_on_off(name, value, desired_set)
            on_signal += _on
            off_signal += off_part
    for name, value in profile.taste.items():
        if name not in desired_set:
            _on, off_part = _split_on_off(name, value, desired_set)
            on_signal += _on
            off_signal += off_part
    total_signal = on_signal + off_signal
    precision = on_signal / total_signal if total_signal > 0 else 0.0

    score = (
        W_COVERAGE * coverage_ratio
        + W_STRENGTH * strength
        + W_PRECISION * precision
    )
    return round(score, 3)


def _balance_score(profile: Profile) -> float:
    """Наскільки збалансований смак: жоден елемент не домінує."""
    sweet = profile.taste.get(SWEET, 0.0)
    sour = profile.taste.get(SOUR, 0.0)
    harsh = sum(profile.taste.get(a, 0.0) for a in HARSH_AXES)

    score = 1.0
    # гострі смаки не врівноважені солодким
    if harsh > 0.4:
        deficit = harsh - sweet
        if deficit > 0:
            score -= min(0.5, deficit * 0.4)
    # надмірна кислотність без солодкого
    if sour > BALANCE_TOL and sweet < sour * 0.5:
        score -= min(0.25, (sour - sweet) * 0.3)
    # нудотно-солодко та "пласко" — нема кислотного/гіркого контрасту
    if sweet > 1.2 and sour < 0.2 and harsh < 0.2:
        score -= 0.25
    # зовсім без структурного смаку — одновимірно
    if sweet + sour + harsh < 0.2:
        score -= 0.1
    return round(max(0.0, min(1.0, score)), 3)


def _resolve_name(db: Session, material_id: int) -> str:
    mat = db.get(RawMaterial, material_id)
    return mat.name if mat else f"#{material_id}"


def _honey_id(db: Session) -> Optional[int]:
    return db.scalar(select(RawMaterial.id).where(RawMaterial.name == HONEY_NAME))


def _forbidden_material_ids(db: Session, forbidden_tags: Set[str]) -> Set[int]:
    """ID сировини, що має хоч один заборонений тег (жорсткий фільтр ЦА)."""
    if not forbidden_tags:
        return set()
    out: Set[int] = set()
    rows = db.execute(select(RawMaterial.id, RawMaterial.tags)).all()
    for mid, tags in rows:
        mat_tags = {t for t in (tags or "").split(",") if t}
        if mat_tags & forbidden_tags:
            out.add(mid)
    return out


def _out_of_season_fresh_ids(db: Session, season: Optional[str]) -> Set[int]:
    """ID сировини, чия СВІЖА форма недоступна в заданий сезон.

    Сезонність стосується лише свіжої форми — інші форми (сушена/екстракт/сік)
    лишаються дозволеними. Тому ці id блокуються тільки для form == fresh.
    """
    if not seasons.is_valid(season):
        return set()
    out: Set[int] = set()
    rows = db.execute(select(RawMaterial.id, RawMaterial.name)).all()
    for mid, name in rows:
        if not seasons.fresh_in_season(name, season):
            out.add(mid)
    return out


# Підказка, якою формою замінити позасезонну свіжу сировину (за пріоритетом).
_PRESERVED_FORM_LABEL = {
    FORM_DRY: "сушена",
    FORM_EXTRACT: "екстракт",
    FORM_JUICE: "сік",
    FORM_OIL: "олія",
}
_PRESERVED_FORM_ORDER = (FORM_DRY, FORM_EXTRACT, FORM_JUICE, FORM_OIL)


def _preserved_form_suggestion(db: Session, material_id: int) -> Optional[str]:
    """Людська назва доступної несвіжої форми сировини (суха/екстракт/сік)."""
    forms = {form for (_part, form, _pit) in _option_breakdown(db, material_id)}
    for f in _PRESERVED_FORM_ORDER:
        if f in forms:
            return _PRESERVED_FORM_LABEL[f]
    return None


# Смакові осі — не використовуються як «ідентичність» основної сировини при
# доборі авто-профілю (вони покриваються базовими нотами/балансом).
_TASTE_AXES = {SWEET, SOUR, BITTER, ASTRINGENT, PUNGENT}
_MAX_PROFILE_NOTES = 5
_MATERIAL_PROFILE_PICKS = 2


def _note_reachable(
    db: Session, char: str, main_id: int, desired_set: Set[str]
) -> bool:
    """Чи реально дати ноту `char` на цій основній сировині: вона сама її несе,
    або є чистий підсилювач (не перебиває профіль), який дотягне до MIN_REINFORCE.

    Солодкість завжди досяжна — її додає підсолоджувач."""
    if char == SWEET:
        return True
    for chans in _option_breakdown(db, main_id).values():
        if chans.get(f"aroma::{char}", 0.0) + chans.get(f"taste::{char}", 0.0) > 0:
            return True
    cand = _best_for_char(db, char, {main_id}, desired_set)
    return cand is not None and cand[4] >= MIN_REINFORCE


def suggest_profile(
    db: Session,
    audience: Dict,
    main_material_id: Optional[int],
    part: Optional[str] = None,
    form: Optional[str] = None,
    pit: Optional[str] = None,
) -> SuggestProfileResponse:
    """Популярний профіль під ЦА + природні ноти основної сировини.

    Базові ноти категорії + топ-1–2 найвиразніші ароматичні ноти основної
    сировини; разом не більше _MAX_PROFILE_NOTES. Базові ноти, які обрана
    сировина не здатна дати (і нічим чистим не підсилити), не пропонуємо —
    щоб не обіцяти профіль, який провалиться.

    Якщо задано конкретний варіант (part/form/pit) — беремо ноти лише з нього,
    щоб не пропонувати, напр., мигдальний/кісточковий «з кісточкою», коли
    обрано «без кісточки».
    """
    base_notes: List[str] = list(audience.get("default_profile", []))
    picks: List[str] = []
    if main_material_id:
        breakdown = _option_breakdown(db, main_material_id)
        chosen_chans = breakdown.get((part, form, pit)) if part is not None else None
        agg: Dict[str, float] = defaultdict(float)
        sources = [chosen_chans] if chosen_chans else list(breakdown.values())
        for chans in sources:
            for key, val in chans.items():
                chan, name = key.split("::", 1)
                if chan == "aroma":
                    agg[name] += val
        ranked = sorted(agg.items(), key=lambda kv: kv[1], reverse=True)
        for name, _v in ranked:
            if name in _TASTE_AXES or name in base_notes:
                continue
            picks.append(name)
            if len(picks) >= _MATERIAL_PROFILE_PICKS:
                break

    if main_material_id:
        tentative = set(base_notes) | set(picks)
        base_notes = [
            n
            for n in base_notes
            if _note_reachable(db, n, main_material_id, tentative)
        ]
    names = (base_notes + picks)[:_MAX_PROFILE_NOTES]

    id_by_name = {
        c.name: c.id
        for c in db.scalars(
            select(Characteristic).where(Characteristic.name.in_(names))
        ).all()
    }
    ordered = [(n, id_by_name[n]) for n in names if n in id_by_name]
    return SuggestProfileResponse(
        characteristic_ids=[i for _n, i in ordered],
        characteristic_names=[n for n, _i in ordered],
    )


def _option_net(
    chans: Dict[str, float], desired_set: Set[str]
) -> Tuple[float, float, float]:
    """Для опції рахуємо корисний сигнал (бажане), «шум» (стороннє) і net.

    net = on - OFF_PENALTY * off — наскільки опція влучає у профіль, а не шумить.
    Солодкість не вважаємо шумом (її додаємо навмисно для балансу).
    """
    on = 0.0
    off = 0.0
    for key, value in chans.items():
        name = key.split("::", 1)[1]
        on_part, off_part = _split_on_off(name, value, desired_set)
        on += on_part
        off += off_part
    return on, off, on - OFF_PENALTY * off


def _overpowers(chans: Dict[str, float], desired_set: Set[str]) -> bool:
    """Чи «забиває» опція профіль: її найгучніша СТОРОННЯ нота (поза бажаним,
    крім солодкого) перевищує суму всіх корисних нот, які вона дає.

    Споріднені ноти (ментоловий тощо) тут рахуються повноцінно як сторонні —
    бо саме їхній фактичний рівень видно у профілі/піраміді/радарі. Тобто м'ята,
    що дає свіжість 1.3, але ментол 2.0, вважається такою, що перебиває.
    """
    merged: Dict[str, float] = defaultdict(float)
    for key, value in chans.items():
        merged[key.split("::", 1)[1]] += value
    on_desired = 0.0
    max_off = 0.0
    for name, value in merged.items():
        if name in desired_set:
            on_desired += value
        elif name != SWEET and value > max_off:
            max_off = value
    return max_off > on_desired


def _option_layer(db: Session, material_id: int, part: str, form: str, pit: str) -> str:
    """Домінантний ярус летючості опції (top|heart|base) за сумарним внеском."""
    rows = db.scalars(
        select(MaterialCompound).where(
            MaterialCompound.raw_material_id == material_id,
            MaterialCompound.part == part,
            MaterialCompound.form == form,
            MaterialCompound.pit == pit,
        )
    ).all()
    totals: Dict[str, float] = defaultdict(float)
    for mc in rows:
        compound = db.get(AromaCompound, mc.compound_id)
        if compound is None:
            continue
        weight_sum = sum(_compound_chars(compound).values())
        totals[compound.volatility or VOL_HEART] += mc.intensity * weight_sum
    if not totals:
        return VOL_HEART
    return max(totals.items(), key=lambda kv: kv[1])[0]


def _dose(
    db: Session,
    material_id: int,
    part: str,
    form: str,
    pit: str,
    desired_set: Set[str],
) -> float:
    """Підібрати дозу неосновного інгредієнта за «чистотою» внеску та ярусом.

    Чим вища частка корисного сигналу (бажане проти стороннього), тим більша
    доза. Зверху доза обмежена стелею ярусу: верхні (леткі) ноти беремо
    стримано, щоб вони не перебивали серце, базові — помірно (вони й так стійкі).
    """
    if material_id <= 0:
        return SWEETENER_AROMA
    chans = _option_breakdown(db, material_id).get((part, form, pit), {})
    on, off, _net = _option_net(chans, desired_set)
    if on + off <= 0:
        return DOSE_MIN
    cleanliness = on / (on + off)
    dose = DOSE_MIN + (DOSE_MAX - DOSE_MIN) * cleanliness
    layer = _option_layer(db, material_id, part, form, pit)
    cap = LAYER_DOSE_CAP.get(layer, DOSE_MAX)
    return round(min(dose, cap), 2)


def _find_candidates(
    db: Session,
    missing_names: Set[str],
    exclude_ids: Set[int],
    desired_set: Set[str],
    season_blocked_ids: Set[int] = frozenset(),
) -> List[Tuple[int, str, str, str, float, Set[str]]]:
    """Кандидати, що закривають прогалини профілю з мінімумом сторонніх нот.

    Повертає list of (material_id, part, form, pit, net, covered_chars), де net —
    «чистота» внеску (корисне мінус шум). Сортуємо: спершу скільки прогалин
    закриває, далі — вищий net (менше перебиває бажаний профіль).
    """
    if not missing_names:
        return []
    char_ids = db.scalars(
        select(Characteristic.id).where(Characteristic.name.in_(missing_names))
    ).all()
    if not char_ids:
        return []
    material_ids = db.scalars(
        select(MaterialCompound.raw_material_id)
        .join(
            CompoundCharacteristic,
            CompoundCharacteristic.compound_id == MaterialCompound.compound_id,
        )
        .where(
            CompoundCharacteristic.characteristic_id.in_(char_ids),
            MaterialCompound.raw_material_id.notin_(exclude_ids),
        )
        .distinct()
    ).all()

    candidates: List[Tuple[int, str, str, str, float, Set[str]]] = []
    for mid in material_ids:
        best: Optional[Tuple[Tuple[int, float], str, str, str, float, Set[str]]] = None
        for (part, form, pit), chans in _option_breakdown(db, mid).items():
            if form == FORM_FRESH and mid in season_blocked_ids:
                continue  # свіжа форма поза сезоном — не пропонуємо
            covered = {
                key.split("::", 1)[1]
                for key, value in chans.items()
                if value > 0 and key.split("::", 1)[1] in missing_names
            }
            if not covered:
                continue
            _on, _off, net = _option_net(chans, desired_set)
            sort_key = (len(covered), net)
            if best is None or sort_key > best[0]:
                best = (sort_key, part, form, pit, net, covered)
        if best is None:
            continue
        _key, part, form, pit, net, covered = best
        candidates.append((mid, part, form, pit, net, covered))
    candidates.sort(key=lambda c: (len(c[5]), c[4]), reverse=True)
    return candidates


# Кеш розкладок сировини на час життя процесу: дані сидяться один раз при старті
# і не змінюються, тож розкладку кожної сировини рахуємо лише раз. Це критично
# для швидкості пошуку різноманітних композицій (багато повторних звернень).
_BREAKDOWN_CACHE: Dict[int, Dict[Tuple[str, str, str], Dict[str, float]]] = {}


def _option_breakdown(
    db: Session, material_id: int
) -> Dict[Tuple[str, str, str], Dict[str, float]]:
    """Для кожної (part, form, pit) — внески за каналами: aroma_*, taste_*."""
    cached = _BREAKDOWN_CACHE.get(material_id)
    if cached is not None:
        return cached
    rows = db.scalars(
        select(MaterialCompound).where(
            MaterialCompound.raw_material_id == material_id
        )
    ).all()
    out: Dict[Tuple[str, str, str], Dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    for mc in rows:
        compound = db.get(AromaCompound, mc.compound_id)
        if compound is None:
            continue
        for char_name, weight in _compound_chars(compound).items():
            val = mc.intensity * weight
            key = (mc.part, mc.form, mc.pit)
            if compound.kind in (KIND_AROMA, KIND_BOTH):
                out[key][f"aroma::{char_name}"] += val
            if compound.kind in (KIND_TASTE, KIND_BOTH):
                out[key][f"taste::{char_name}"] += val
    _BREAKDOWN_CACHE[material_id] = out
    return out


def _find_taste_provider(
    db: Session,
    needed_char: str,
    exclude_ids: Set[int],
    avoid_chars: Set[str],
    season_blocked_ids: Set[int] = frozenset(),
) -> Optional[Tuple[int, str, str, str]]:
    """Сировина, що дає потрібний СМАК (needed_char) з мінімумом небажаних смаків.

    Повертає (material_id, part, form, pit).
    """
    char_id = db.scalar(
        select(Characteristic.id).where(Characteristic.name == needed_char)
    )
    if char_id is None:
        return None
    material_ids = db.scalars(
        select(MaterialCompound.raw_material_id)
        .join(
            CompoundCharacteristic,
            CompoundCharacteristic.compound_id == MaterialCompound.compound_id,
        )
        .where(
            CompoundCharacteristic.characteristic_id == char_id,
            MaterialCompound.raw_material_id.notin_(exclude_ids),
        )
        .distinct()
    ).all()

    best: Optional[Tuple[int, str, str, str, float]] = None
    for mid in material_ids:
        for (part, form, pit), chans in _option_breakdown(db, mid).items():
            if form == FORM_FRESH and mid in season_blocked_ids:
                continue
            need = chans.get(f"taste::{needed_char}", 0.0)
            if need <= 0:
                continue
            avoid = sum(chans.get(f"taste::{c}", 0.0) for c in avoid_chars)
            net = need - avoid
            if best is None or net > best[4]:
                best = (mid, part, form, pit, net)
    if best is None:
        return None
    return best[0], best[1], best[2], best[3]


def _best_for_char(
    db: Session,
    char: str,
    exclude_ids: Set[int],
    desired_set: Set[str],
    season_blocked_ids: Set[int] = frozenset(),
) -> Optional[Tuple[int, str, str, str, float]]:
    """Сировина, що дає НАЙБІЛЬШЕ саме характеристики `char` (аромат+смак),
    майже не шумлячи (net > 0). Повертає (mid, part, form, pit, char_value).

    На відміну від _find_candidates, ранжує за фактичним внеском у цільову ноту,
    а не за загальним net профілю — щоб не брати ягоду з мізерним «свіжим», але
    потужним «ягідним».
    """
    char_id = db.scalar(select(Characteristic.id).where(Characteristic.name == char))
    if char_id is None:
        return None
    material_ids = db.scalars(
        select(MaterialCompound.raw_material_id)
        .join(
            CompoundCharacteristic,
            CompoundCharacteristic.compound_id == MaterialCompound.compound_id,
        )
        .where(
            CompoundCharacteristic.characteristic_id == char_id,
            MaterialCompound.raw_material_id.notin_(exclude_ids),
        )
        .distinct()
    ).all()
    best: Optional[Tuple[int, str, str, str, float]] = None
    best_key: Optional[Tuple[float, float]] = None
    for mid in material_ids:
        for (part, form, pit), chans in _option_breakdown(db, mid).items():
            if form == FORM_FRESH and mid in season_blocked_ids:
                continue
            tval = chans.get(f"aroma::{char}", 0.0) + chans.get(f"taste::{char}", 0.0)
            if tval <= 0:
                continue
            _on, _off, net = _option_net(chans, desired_set)
            if net <= 0:
                continue  # шумна — додасть більше стороннього, ніж корисного
            if _overpowers(chans, desired_set):
                continue  # її стороння нота перебила б користь — не беремо
            key = (round(tval, 3), round(net, 3))
            if best_key is None or key > best_key:
                best_key = key
                best = (mid, part, form, pit, tval)
    return best


def _find_harmony(
    db: Session,
    desired_set: Set[str],
    exclude_ids: Set[int],
    season_blocked_ids: Set[int] = frozenset(),
) -> Optional[Tuple[int, str, str, str, bool]]:
    """Сировина для гармонії (мін. інгредієнтів): підсилює профіль, не додає гіркоти.

    Повертає (material_id, part, form, pit, reinforces_desired).
    """
    material_ids = db.scalars(
        select(RawMaterial.id).where(RawMaterial.id.notin_(exclude_ids))
    ).all()
    best: Optional[Tuple[int, str, str, str, bool, float]] = None
    for mid in material_ids:
        for (part, form, pit), chans in _option_breakdown(db, mid).items():
            if form == FORM_FRESH and mid in season_blocked_ids:
                continue
            harsh = sum(chans.get(f"taste::{a}", 0.0) for a in HARSH_AXES)
            if harsh > 0.4:
                continue  # не додаємо гострих смаків заради кількості
            on, _off, net = _option_net(chans, desired_set)
            # гармонізуючий інгредієнт мусить РЕАЛЬНО підсилювати бажаний профіль
            # і майже не шуміти; інакше краще менше інгредієнтів, ніж сторонні ноти
            if on <= 0 or net <= 0:
                continue
            if _overpowers(chans, desired_set):
                continue  # перебиває профіль — не додаємо заради кількості
            if best is None or net > best[5]:
                best = (mid, part, form, pit, True, net)
    if best is None:
        return None
    return best[0], best[1], best[2], best[3], best[4]


def _finalize(
    db: Session,
    selections: List[ResolvedSelection],
    desired_set: Set[str],
    *,
    max_ingredients: int = MAX_INGREDIENTS,
    sweetener: str = "auto",  # auto | honey | sugar
    base_conflict_chars: Set[str] = frozenset(),
    forbidden_ids: Set[int] = frozenset(),
    season_blocked_ids: Set[int] = frozenset(),
) -> Tuple[List[ResolvedSelection], List[str]]:
    """Дозування інгредієнтів + балансування смаку + мінімум інгредієнтів.

    max_ingredients — стеля ароматичних складових (для «лаконічної» композиції
    можна задати MIN_INGREDIENTS). sweetener — чим підсолоджувати: автоматично,
    примусово медом чи цукром (для варіанта з альтернативним підсолоджувачем).
    """
    notes: List[str] = []
    used: Set[int] = {s.material_id for s in selections}
    # Жорсткий фільтр ЦА: заборонену сировину взагалі не можна додавати —
    # позначаємо як «використану», щоб усі пошуки кандидатів її оминали.
    used |= set(forbidden_ids)
    # Мед не підказуємо як звичайну сировину — лише як підсолоджувач, щоб уникнути
    # подвійної згадки (мед-сировина + мед-солодкість).
    honey_id = _honey_id(db)
    honey_block = {honey_id} if honey_id else set()

    # Основна сировина — повна доза; решту дозуємо за «чистотою» внеску.
    for s in selections:
        if s.inline_contrib is not None:
            continue  # основа: внесок уже фінальний, дозування не застосовуємо
        if s.role == "main":
            s.amount = MAIN_AMOUNT
        else:
            s.amount = _dose(db, s.material_id, s.part, s.form, s.pit, desired_set)

    # Порядок важливий: спершу формуємо повний АРОМАТИЧНИЙ скелет (підсилення
    # профілю, мінімум інгредієнтів, базова нота), і лише ПОТІМ балансуємо смак.
    # Інакше гострі ноти доданих на підсиленні інгредієнтів лишаться без
    # солодкого протиставлення.

    # 1) Підсилення профілю: додаємо ще чисті складові, поки якась бажана нота
    #    слабка (або поки не набрали мінімум інгредієнтів), у межах стелі.
    def _aromatic_count() -> int:
        return sum(1 for s in selections if s.material_id > 0)

    # Ноти, які наявна сировина не здатна суттєво підсилити — більше не пробуємо
    # (щоб не додавати купу інгредієнтів, що нібито «підсилюють», але дають ~0).
    exhausted: Set[str] = set()

    def _weakest_desired() -> Optional[str]:
        prof = _build_profile(db, selections)
        weak = [(c, prof.total(c)) for c in desired_set if c not in exhausted]
        weak = [(c, v) for c, v in weak if v < TARGET_STRENGTH]
        if not weak:
            return None
        return min(weak, key=lambda cv: cv[1])[0]

    # Конфлікти з основою розширюють «шум»: інгредієнти, що підсилюють
    # конфліктні ноти, отримують нижчий net і не обираються.
    effective_desired = desired_set - base_conflict_chars

    guard = 0
    while guard < max_ingredients + 2 * MIN_INGREDIENTS:
        guard += 1
        count = _aromatic_count()
        if count >= max_ingredients:
            break
        target_char = _weakest_desired()
        need_min = count < MIN_INGREDIENTS
        if target_char is None and not need_min:
            break  # достатньо складових і профіль уже виразний

        mid = part = form = pit = None
        reinforced_char: Optional[str] = None
        block = used | honey_block
        # 1а) прицільно підсилюємо найслабшу бажану ноту — лише якщо знайдена
        #     сировина РЕАЛЬНО дає достатньо саме цієї ноти (а не мізер).
        if target_char is not None:
            cand = _best_for_char(
                db, target_char, block, effective_desired, season_blocked_ids
            )
            if cand is not None and cand[4] >= MIN_REINFORCE:
                mid, part, form, pit = cand[0], cand[1], cand[2], cand[3]
                reinforced_char = target_char
            else:
                # цю ноту годі підсилити наявною сировиною — позначаємо й далі
                exhausted.add(target_char)
                if not need_min:
                    continue  # мінімум набрано — не додаємо «порожній» інгредієнт
        # 1б) для добору мінімуму — будь-який чистий гармонійний інгредієнт
        if mid is None:
            harm = _find_harmony(db, effective_desired, block, season_blocked_ids)
            if harm is None:
                break
            mid, part, form, pit, _reinf = harm

        selections.append(
            ResolvedSelection(
                mid, _resolve_name(db, mid), part, form, pit, "harmony",
                amount=_dose(db, mid, part, form, pit, desired_set),
            )
        )
        used.add(mid)
        if reinforced_char is not None:
            notes.append(
                f"{_resolve_name(db, mid)}: підсилює «{reinforced_char}» у профілі"
            )
        else:
            notes.append(
                f"{_resolve_name(db, mid)}: додає складності для гармонії"
            )

    # 2) Глибокий післясмак: якщо база (стійкі ноти) слабка, додаємо одну чисту
    #    базову ноту, що підсилює бажаний профіль — вона тримається у фініші.
    if _aromatic_count() < max_ingredients:
        prof = _build_profile(db, selections)
        if prof.layer_total(VOL_BASE) < BASE_MIN:
            block = used | honey_block
            for c in _find_candidates(
                db, effective_desired, block, effective_desired, season_blocked_ids
            ):
                if c[4] <= 0:  # шумна — пропускаємо
                    continue
                if _option_layer(db, c[0], c[1], c[2], c[3]) != VOL_BASE:
                    continue
                cand_chans = _option_breakdown(db, c[0]).get((c[1], c[2], c[3]), {})
                if _overpowers(cand_chans, effective_desired):
                    continue  # перебиває профіль
                mid, part, form, pit = c[0], c[1], c[2], c[3]
                selections.append(
                    ResolvedSelection(
                        mid, _resolve_name(db, mid), part, form, pit, "base",
                        amount=_dose(db, mid, part, form, pit, desired_set),
                    )
                )
                used.add(mid)
                notes.append(
                    f"{_resolve_name(db, mid)}: базова нота для глибокого післясмаку"
                )
                break

    # 3) Баланс смаку — ОСТАННІМ кроком, коли всі ароматичні складові вже зібрані,
    #    щоб гострі ноти доданих інгредієнтів теж потрапили під пом'якшення.
    profile = _build_profile(db, selections)
    sweet = profile.taste.get(SWEET, 0.0)
    sour = profile.taste.get(SOUR, 0.0)
    harsh_vals = {a: profile.taste.get(a, 0.0) for a in HARSH_AXES}
    aroma_signal = max(profile.aroma.values(), default=0.0)

    # «Небажані» гострі смаки (ті, що не входять у бажаний профіль)
    harsh_off = {a: v for a, v in harsh_vals.items() if a not in desired_set and v > 0}
    harsh_off_total = sum(harsh_off.values())

    needed_sweet = 0.0
    reasons: List[str] = []

    if harsh_off:
        worst_axis = max(harsh_off, key=lambda a: harsh_off[a])
        worst_val = harsh_off[worst_axis]
        overpowers = worst_val >= 0.6 * aroma_signal
        unbalanced = harsh_off_total > sweet + 0.3
        if worst_val >= BALANCE_TOL and (overpowers or unbalanced):
            needed_sweet = max(needed_sweet, harsh_off_total + SUGAR_HEADROOM)
            tail = (
                ", що перебивав аромат"
                if overpowers
                else " для рівноваги смаку"
            )
            reasons.append(f"пом'якшити «{worst_axis}» присмак{tail}")

    # Надмірна кислотність (не бажана) теж згладжується солодким
    if sour >= BALANCE_TOL and SOUR not in desired_set and sweet < sour * 0.6:
        needed_sweet = max(needed_sweet, sour * 0.6)
        reasons.append("згладити надмірну кислотність")

    # Бажана солодкість: якщо «солодкий» прямо в профілі, але слабкий — доводимо
    # підсолоджувачем до цільової виразності (інакше нота лишається непокритою).
    if SWEET in desired_set and sweet < TARGET_STRENGTH:
        needed_sweet = max(needed_sweet, TARGET_STRENGTH)
        reasons.append("посилити бажану солодкість")

    # 3а) Додаємо підсолоджувач (мед або цукор), якщо потрібно
    dose = round(needed_sweet - sweet, 2)
    if dose > 0:
        honey_free = honey_id is not None and honey_id not in used
        if sweetener == "honey":
            use_honey = honey_free
        elif sweetener == "sugar":
            use_honey = False
        else:
            # авто: мед, якщо профіль «медовий/квітковий» і мед ще не в композиції
            use_honey = honey_free and bool(desired_set & HONEY_AFFINITY)
        if use_honey:
            # мед: солодкість + доречні медові/квіткові ноти
            selections.append(
                ResolvedSelection(
                    material_id=honey_id,
                    name=HONEY_NAME,
                    part="whole",
                    form="fresh",
                    pit="na",
                    role="sweetener",
                    sweet_add=dose,
                    amount=SWEETENER_AROMA,
                )
            )
            used.add(honey_id)
            notes.append(
                f"{HONEY_NAME} (~{dose}): солодкість і медові ноти, щоб "
                f"{', '.join(reasons)}"
            )
        else:
            selections.append(
                ResolvedSelection(
                    material_id=0,
                    name=SUGAR_NAME,
                    part="whole",
                    form="na",
                    pit="na",
                    role="sweetener",
                    sweet_add=dose,
                    amount=SWEETENER_AROMA,
                )
            )
            notes.append(
                f"{SUGAR_NAME} (~{dose}): солодкість, щоб {', '.join(reasons)}"
            )
        sweet += dose

    # 3б) Нудотно-солодко й «пласко» → додати кислинку для свіжості
    if (
        sweet >= 1.2
        and sour < 0.2
        and all(harsh_vals[a] < 0.2 for a in HARSH_AXES)
        and SWEET not in desired_set
    ):
        prov = _find_taste_provider(
            db, SOUR, used, set(HARSH_AXES), season_blocked_ids
        )
        if prov:
            mid, part, form, pit = prov
            selections.append(
                ResolvedSelection(
                    mid, _resolve_name(db, mid), part, form, pit, "balance",
                    amount=_dose(db, mid, part, form, pit, desired_set),
                )
            )
            used.add(mid)
            notes.append(
                f"{_resolve_name(db, mid)}: свіжа кислинка проти надмірної солодкості"
            )

    return selections, notes


def _profile_scores(
    profile: Profile, channel: Dict[str, float], desired: Set[str]
) -> List[CharacteristicScore]:
    out: List[CharacteristicScore] = []
    for name, value in sorted(channel.items(), key=lambda kv: kv[1], reverse=True):
        out.append(
            CharacteristicScore(
                name=name,
                score=round(value, 3),
                covered=name in desired,
            )
        )
    return out


def _build_pyramid(profile: Profile, desired_set: Set[str]) -> List[PyramidLayer]:
    """Ольфакторна піраміда напою: верхні / серце / база.

    Серце — ядро характеру (основна сировина). Верх — короткий яскравий старт,
    база — глибокий стійкий післясмак.
    """
    titles = {
        VOL_TOP: "Верхні ноти (старт)",
        VOL_HEART: "Серце (основна сировина)",
        VOL_BASE: "База (післясмак)",
    }
    out: List[PyramidLayer] = []
    for layer in (VOL_TOP, VOL_HEART, VOL_BASE):
        chars = profile.layers.get(layer, {})
        notes = [
            CharacteristicScore(
                name=name, score=round(value, 3), covered=name in desired_set
            )
            for name, value in sorted(
                chars.items(), key=lambda kv: kv[1], reverse=True
            )
            if value > 0
        ]
        out.append(
            PyramidLayer(
                layer=layer, title=titles[layer], notes=notes
            )
        )
    return out


def _make_variant(
    db: Session,
    title: str,
    selections: List[ResolvedSelection],
    desired_names: List[str],
    balance_notes: List[str],
) -> RecipeVariant:
    profile = _build_profile(db, selections)
    desired_set = set(desired_names)
    score = _score(profile, desired_names)
    balance = _balance_score(profile)
    # Гастрономічна гармонія: сумісність ароматичних родин (аромат+смак разом).
    merged_totals: Dict[str, float] = defaultdict(float)
    for name, value in profile.aroma.items():
        merged_totals[name] += value
    for name, value in profile.taste.items():
        merged_totals[name] += value
    harmony_res = harmony.score_harmony(merged_totals)
    covered = [n for n in desired_names if profile.total(n) >= COVERED_MIN]
    missing = [n for n in desired_names if profile.total(n) < COVERED_MIN]
    weak = [n for n in covered if profile.total(n) < WEAK_CEIL]

    compounds = [
        CompoundContribution(compound=name, kind=kind, characteristics=sorted(chars))
        for name, (kind, chars) in sorted(profile.compounds.items())
    ]
    materials = [
        MaterialInComposition(
            material_id=s.material_id,
            name=s.name,
            part=s.part,
            form=s.form,
            pit=s.pit,
            role=s.role,
            amount=round(s.amount, 2),
        )
        for s in selections
        if s.role != "base_spirit"  # основа показується окремо у банері
    ]
    suggested = [s.name for s in selections if s.role == "suggested"]

    pyramid = _build_pyramid(profile, desired_set)

    parts = [
        f"Покрито {len(covered)}/{len(desired_names)} бажаних характеристик."
    ]
    if suggested:
        parts.append(f"Для профілю додано: {', '.join(suggested)}.")
    if missing:
        parts.append(f"Не вистачає: {', '.join(missing)}.")
    if weak:
        parts.append(f"Слабко виражені: {', '.join(weak)}.")
    # «Баланс» — це лише про рівновагу смаку (солодке/кисле/гірке), а не про
    # відповідність профілю. Тому формулюємо явно, щоб не вводити в оману.
    if balance >= 0.85:
        parts.append("Смак (рівновага солодке/кисле/гірке) збалансований.")
    else:
        parts.append("Смак вимагав корекції балансу.")
    # Гармонія — про те, чи поєднання смачне, а не лише збалансоване.
    if harmony_res.score >= 0.85:
        parts.append("Ароматичні родини поєднуються гармонійно.")
    elif harmony_res.score >= 0.6:
        parts.append("Є легкий дисонанс між ароматичними родинами.")
    else:
        parts.append(
            "Увага: поєднання ароматичних родин дисонує — збалансовано за "
            "смаковими осями, але навряд чи буде смачним."
        )
    explanation = " ".join(parts)

    return RecipeVariant(
        title=title,
        match_score=score,
        balance_score=balance,
        harmony_score=harmony_res.score,
        harmony_notes=harmony_res.notes,
        materials=materials,
        aroma_profile=_profile_scores(profile, profile.aroma, desired_set),
        taste_profile=_profile_scores(profile, profile.taste, desired_set),
        covered=covered,
        missing=missing,
        weak=weak,
        compounds=compounds,
        balance_notes=balance_notes,
        explanation=explanation,
        pyramid=pyramid,
    )


def _overall(variant: RecipeVariant) -> float:
    # Гармонія враховується як окремий доданок (щоб дисонансні композиції не
    # спливали нагору лише через збіг/баланс) і додатково як множник —
    # відверто несмачне поєднання «садить» усю оцінку.
    base = (
        0.5 * variant.match_score
        + 0.2 * variant.balance_score
        + 0.3 * variant.harmony_score
    )
    return round(base * (0.4 + 0.6 * variant.harmony_score), 4)


def _feasibility(
    db: Session,
    chosen: List[ResolvedSelection],
    desired_names: List[str],
    variants: List[RecipeVariant],
    forbidden_ids: Set[int] = frozenset(),
) -> ProfileFeasibility:
    """Чи можна гарантувати бажаний профіль для обраної сировини.

    - «impossible»: якусь бажану ноту не дає жодна доступна сировина (навіть
      із додатками) — її неможливо створити.
    - «dominated»: ноти присутні, але обрана сировина дає сильніші сторонні
      ноти, що перебивають профіль — гарантувати його не можна.
    - «ok»: профіль досяжний.
    """
    if not desired_names:
        return ProfileFeasibility(status="ok", achievable=True, message="")

    desired_set = set(desired_names)
    chosen_profile = _build_profile(db, chosen)
    # Заборонену сировину виключаємо з пулу досяжності — інакше ноту вважатимемо
    # досяжною через інгредієнт, який фільтр ЦА не дозволяє.
    chosen_ids = {s.material_id for s in chosen} | set(forbidden_ids)

    # 1) Досяжність кожної бажаної характеристики (обрана сировина або будь-який кандидат)
    unreachable: List[str] = []
    for name in desired_names:
        if chosen_profile.total(name) > 0:
            continue
        if not _find_candidates(db, {name}, chosen_ids, desired_set):
            unreachable.append(name)

    # 2) Чи перебиває обрана сировина бажаний профіль (за найкращим варіантом)
    best = max(variants, key=lambda v: v.match_score) if variants else None
    dominating: List[str] = []
    if best is not None:
        scored = list(best.aroma_profile) + list(best.taste_profile)
        max_desired = max(
            (s.score for s in scored if s.name in desired_set), default=0.0
        )
        # «перебиває» = стороння нота помітно гучніша за найсильнішу бажану
        floor = max(max_desired * 1.6, 1.0)
        seen: Set[str] = set()
        for s in sorted(scored, key=lambda x: x.score, reverse=True):
            if s.name in desired_set or s.name == SWEET:
                continue
            if s.score > floor and s.name not in seen:
                seen.add(s.name)
                dominating.append(s.name)
            if len(dominating) >= 4:
                break

    if unreachable:
        return ProfileFeasibility(
            status="impossible",
            achievable=False,
            unreachable=unreachable,
            dominating=dominating,
            message=(
                "Цей профіль неможливо гарантувати: ноти "
                f"«{', '.join(unreachable)}» не дає жодна доступна сировина "
                "навіть із додатками. Додайте сировину з цими властивостями "
                "або приберіть ці характеристики."
            ),
        )

    if dominating:
        return ProfileFeasibility(
            status="dominated",
            achievable=False,
            dominating=dominating,
            message=(
                "Профіль присутній, але не домінує: обрана сировина дає сильніші "
                f"ноти ({', '.join(dominating)}), які його перебивають. "
                "Спробуйте м'якшу форму інгредієнтів (напр. сік чи суху замість "
                "свіжої цедри) або іншу основну сировину."
            ),
        )

    return ProfileFeasibility(
        status="ok",
        achievable=True,
        message="Профіль досяжний на обраній сировині.",
    )


def _distillate_contribution(
    db: Session, main_sel
) -> List[Tuple[str, float, str, str]]:
    """Внесок ароматного дистиляту: леткі (top/heart) аромосполуки основної
    сировини, на 50% інтенсивності. Таніни/антоціани/кислоти (taste) не переходять
    при дистиляції; важкі (base) аромосполуки переходять слабко (×0.25)."""
    rows = db.scalars(
        select(MaterialCompound).where(
            MaterialCompound.raw_material_id == main_sel.material_id,
            MaterialCompound.part == main_sel.part,
            MaterialCompound.form == main_sel.form,
            MaterialCompound.pit == main_sel.pit,
        )
    ).all()
    if not rows:  # fallback: та сама part/form (будь-яка кісточка)
        rows = db.scalars(
            select(MaterialCompound).where(
                MaterialCompound.raw_material_id == main_sel.material_id,
                MaterialCompound.part == main_sel.part,
                MaterialCompound.form == main_sel.form,
            )
        ).all()
    if not rows:  # останній fallback: будь-який варіант сировини
        rows = db.scalars(
            select(MaterialCompound).where(
                MaterialCompound.raw_material_id == main_sel.material_id
            )
        ).all()
    contrib: Dict[str, Tuple[float, str]] = {}
    for mc in rows:
        compound = db.get(AromaCompound, mc.compound_id)
        if compound is None or compound.kind == KIND_TASTE:
            continue  # лише аромат переходить у дистилят
        layer = compound.volatility or VOL_HEART
        # важкі (base) аромосполуки переходять слабше за леткі
        factor = 0.25 if layer == VOL_BASE else 0.5
        for char_name, weight in _compound_chars(compound).items():
            value = round(mc.intensity * weight * factor, 3)
            if value <= 0:
                continue
            prev = contrib.get(char_name)
            if prev is None or value > prev[0]:
                contrib[char_name] = (value, layer)
    return [(c, v, KIND_AROMA, lyr) for c, (v, lyr) in contrib.items()]


def _base_contribution(
    db: Session, base_name: Optional[str], main_sel
) -> List[Tuple[str, float, str, str]]:
    """Власний внесок основи у профіль напою."""
    if not base_name:
        return []
    if base_name == DISTILLATE_BASE_NAME:
        return _distillate_contribution(db, main_sel)
    bp = BASE_PROFILES.get(base_name)
    return list(bp["profile_contrib"]) if bp else []


def _base_influence(
    base_name: Optional[str],
    desired_set: Set[str],
    variants: List[RecipeVariant],
    *,
    dynamic_bp: Optional[Dict] = None,
) -> Optional[BaseInfluence]:
    """Аналіз впливу основи: власний профіль, конфлікти з бажаним профілем,
    синергія, ABV-рекомендація. dynamic_bp задається ззовні для дистиляту."""
    if not base_name:
        return None
    bp = dynamic_bp or BASE_PROFILES.get(base_name)
    if bp is None:
        return None

    conflicts = bp["conflicts"] & desired_set  # конфліктує з тим, що ми хочемо
    # Якщо бажаний профіль не перетинається з конфліктами — перевіримо найкращий варіант
    if not conflicts and variants:
        best = max(variants, key=lambda v: v.match_score)
        present = {s.name for s in best.aroma_profile + best.taste_profile if s.score > 0}
        conflicts = bp["conflicts"] & present  # конфліктує з тим, що реально є у варіанті
    synergy_all = bp["synergy"]
    synergy = synergy_all & desired_set  # з бажаного профілю — для повідомлення

    parts = []
    if conflicts:
        parts.append(
            f"Ноти «{', '.join(sorted(conflicts))}» конфліктують із цією основою — "
            "таніни або кислота можуть їх перебити."
        )
    if synergy:
        parts.append(
            f"Основа підсилює: «{', '.join(sorted(synergy))}»."
        )
    elif synergy_all and dynamic_bp:
        # Для дистиляту — показуємо ноти, які він несе, навіть якщо не в desired
        top_notes = sorted(synergy_all)[:6]
        parts.append(
            f"Дистилят несе аромат основної сировини: «{', '.join(top_notes)}»."
        )

    return BaseInfluence(
        name=base_name,
        abv_hint=bp["abv_hint"],
        note=bp["note"],
        conflicts=sorted(conflicts),
        synergy=sorted(synergy),
        message=" ".join(parts),
    )


def _greedy_seed(
    db: Session,
    chosen: List[ResolvedSelection],
    base_missing: Set[str],
    exclude: Set[int],
    desired_set: Set[str],
    max_suggested: int,
    season_blocked_ids: Set[int] = frozenset(),
) -> List[ResolvedSelection]:
    """Заготовка: обрана сировина + закриття прогалин профілю чистими кандидатами
    (поза `exclude`). `exclude` містить уже використане/заборонене/«забанене»."""
    seed = list(chosen)
    if not base_missing:
        return seed
    candidates = _find_candidates(db, base_missing, exclude, desired_set, season_blocked_ids)
    still = set(base_missing)
    used = set(exclude)
    added = 0
    for mid, part, form, pit, _val, covered in candidates:
        if not (covered & still):
            continue
        chans = _option_breakdown(db, mid).get((part, form, pit), {})
        if _overpowers(chans, desired_set):
            continue
        seed.append(
            ResolvedSelection(mid, _resolve_name(db, mid), part, form, pit, "suggested")
        )
        used.add(mid)
        still -= covered
        added += 1
        if not still or added >= max_suggested:
            break
    return seed


def _addition_ids(
    selections: List[ResolvedSelection], base_exclude: Set[int]
) -> Set[int]:
    """ID інгредієнтів, ДОДАНИХ алгоритмом (підбір/гармонія/база) — без обраної
    сировини, основи та підсолоджувача. Це «підпис» композиції для діверсифікації."""
    return {
        s.material_id
        for s in selections
        if s.material_id > 0
        and s.material_id not in base_exclude
        and s.role in ("suggested", "harmony", "base")
    }


def _variant_title(
    db: Session, added: Set[int], other_added: List[Set[int]]
) -> str:
    """Назва за відмітними інгредієнтами варіанта (унікальними щодо інших)."""
    if not added:
        return "Лаконічна композиція (основна сировина)"
    others = set().union(*other_added) if other_added else set()
    unique = added - others
    pick = sorted(unique) if unique else sorted(added)
    names = [_resolve_name(db, i) for i in pick[:2]]
    return "Композиція з: " + ", ".join(names)


def generate(db: Session, req: GenerateRequest) -> GenerateResponse:
    desired_rows = db.scalars(
        select(Characteristic).where(Characteristic.id.in_(req.desired_characteristics))
    ).all()
    desired_names = [c.name for c in desired_rows]
    desired_set = set(desired_names)

    # Цільова аудиторія: жорсткі фільтри сировини + обмеження на алкоголь.
    audience = get_audience(req.audience_id)
    forbidden_tags: Set[str] = (
        set(audience["forbidden_tags"]) if audience else set()
    )
    forbidden_ids = _forbidden_material_ids(db, forbidden_tags)

    # Сезонність: блокуємо лише СВІЖУ форму позасезонної сировини при авто-доборі.
    season = req.season if seasons.is_valid(req.season) else None
    season_blocked_ids = _out_of_season_fresh_ids(db, season)

    base_name: Optional[str] = None
    base_conflict_chars: Set[str] = set()
    distillate_bp: Optional[Dict] = None  # динамічний профіль для дистиляту (банер)
    base_contrib: List[Tuple[str, float, str, str]] = []
    if req.base_id is not None:
        base = db.get(Base_, req.base_id)
        base_name = base.name if base else None
        if base_name and base_name in BASE_PROFILES:
            base_conflict_chars = BASE_PROFILES[base_name]["conflicts"]
        # Власний внесок основи у профіль напою (реальний, не лише банер)
        base_contrib = _base_contribution(db, base_name, req.main_material)
        if base_name == DISTILLATE_BASE_NAME:
            synergy_chars = {c for c, _v, _k, _l in base_contrib}
            distillate_bp = {
                "abv": 75,
                "abv_hint": "70–85% — концентрує леткі ефірні олії та терпени основної сировини",
                "conflicts": set(),
                "synergy": synergy_chars,
                "note": (
                    "Ароматний дистилят із основної сировини — підсилює та закріплює "
                    "характер головного інгредієнта. Переносить леткі (top/heart) "
                    "аромосполуки; таніни та антоціани при дистиляції не переходять."
                ),
            }

    # Для безалкогольних ЦА відкидаємо алкогольну основу (спирт/вино/дистилят),
    # навіть якщо вона якось потрапила у запит — лишається лише 0% ABV.
    if audience and audience["alcohol_free"] and base_name:
        is_alcoholic = base_name == DISTILLATE_BASE_NAME or (
            BASE_PROFILES.get(base_name, {}).get("abv", 0) > 0
        )
        if is_alcoholic:
            base_name = None
            base_conflict_chars = set()
            base_contrib = []
            distillate_bp = None

    chosen: List[ResolvedSelection] = [
        ResolvedSelection(
            material_id=req.main_material.material_id,
            name=_resolve_name(db, req.main_material.material_id),
            part=req.main_material.part,
            form=req.main_material.form,
            pit=req.main_material.pit,
            role="main",
        )
    ]
    # Основа з власним внеском бере участь у профілі як окремий елемент,
    # але не показується серед інгредієнтів (вона у банері «Вплив основи»).
    if base_contrib:
        chosen.append(
            ResolvedSelection(
                material_id=-1,
                name=base_name or "основа",
                part="whole",
                form="na",
                pit="na",
                role="base_spirit",
                inline_contrib=base_contrib,
            )
        )
    for add in req.additional_materials:
        chosen.append(
            ResolvedSelection(
                material_id=add.material_id,
                name=_resolve_name(db, add.material_id),
                part=add.part,
                form=add.form,
                pit=add.pit,
                role="additional",
            )
        )

    base_profile = _build_profile(db, chosen)
    base_missing = {n for n in desired_names if base_profile.total(n) <= 0}
    exclude_ids = {s.material_id for s in chosen}
    # Мед не пропонуємо як звичайну сировину — він заходить лише як підсолоджувач
    # (медові ноти + солодкість) у кроці балансування, щоб не дублювався.
    honey_id = _honey_id(db)
    base_block = exclude_ids | ({honey_id} if honey_id else set()) | forbidden_ids

    # Збираємо ПУЛ кандидатних композицій. Кожна ітерація будує заготовку з
    # кандидатів, фіналізує її (підсилення/баланс), потім «банить» свої додані
    # інгредієнти — щоб наступна композиція складалася з інших. Так отримуємо
    # справді різні рецепти, а не майже однакові.
    pool: List[Tuple[List[ResolvedSelection], List[str], Set[int]]] = []
    banned: Set[int] = set()
    for _ in range(DIVERSE_ATTEMPTS):
        seed = _greedy_seed(
            db, chosen, base_missing, base_block | banned, desired_set, MAX_SUGGESTED,
            season_blocked_ids,
        )
        sel, notes = _finalize(
            db, seed, desired_set,
            max_ingredients=MAX_INGREDIENTS, sweetener="auto",
            base_conflict_chars=base_conflict_chars,
            forbidden_ids=forbidden_ids | banned,
            season_blocked_ids=season_blocked_ids,
        )
        added = _addition_ids(sel, exclude_ids)
        pool.append((sel, notes, added))
        if not added:
            break  # нічого не додано — інших комбінацій під цей профіль нема
        banned |= added

    # Лаконічна композиція (лише обрана сировина + мінімум) — окремий стиль.
    lean_sel, lean_notes = _finalize(
        db, list(chosen), desired_set,
        max_ingredients=MIN_INGREDIENTS, sweetener="auto",
        base_conflict_chars=base_conflict_chars,
        forbidden_ids=forbidden_ids,
        season_blocked_ids=season_blocked_ids,
    )
    pool.append((lean_sel, lean_notes, _addition_ids(lean_sel, exclude_ids)))

    # Оцінюємо весь пул і відбираємо найкращі ГЕНЕТИЧНО різні варіанти в межах
    # SCORE_DELTA від найкращого збігу.
    scored: List[Tuple[RecipeVariant, Set[int], Tuple]] = []
    for sel, notes, added in pool:
        v = _make_variant(db, "", sel, desired_names, notes)
        sig = tuple(sorted((m.material_id, m.part, m.form, m.pit) for m in v.materials))
        scored.append((v, added, sig))
    scored.sort(key=lambda t: _overall(t[0]), reverse=True)

    best_match = scored[0][0].match_score if scored else 0.0
    unique: List[RecipeVariant] = []
    kept_added: List[Set[int]] = []
    seen_sig: Set[Tuple] = set()
    for v, added, sig in scored:
        if sig in seen_sig:
            continue
        if v.match_score < best_match - SCORE_DELTA:
            continue
        # достатньо відрізняється від уже відібраних за набором додатків?
        if any(len(added ^ k) < MIN_VARIANT_DIFF for k in kept_added):
            continue
        v.title = _variant_title(db, added, kept_added)
        seen_sig.add(sig)
        kept_added.append(added)
        unique.append(v)
        if len(unique) >= MAX_VARIANTS:
            break

    # Підстраховка: якщо фільтр різноманітності лишив єдиний варіант, додамо
    # найкращий відмінний за складом (хай і поза SCORE_DELTA), щоб було з чого обирати.
    if len(unique) < 2:
        for v, added, sig in scored:
            if sig in seen_sig:
                continue
            if any(len(added ^ k) < MIN_VARIANT_DIFF for k in kept_added):
                continue
            v.title = _variant_title(db, added, kept_added)
            seen_sig.add(sig)
            kept_added.append(added)
            unique.append(v)
            if len(unique) >= 2:
                break

    feasibility = _feasibility(db, chosen, desired_names, unique, forbidden_ids)
    base_infl = _base_influence(
        base_name, desired_set, unique, dynamic_bp=distillate_bp
    )

    audience_info: Optional[AudienceInfo] = None
    if audience:
        examples: List[str] = []
        if forbidden_ids:
            example_ids = list(forbidden_ids)[:6]
            examples = [
                n
                for n in db.scalars(
                    select(RawMaterial.name).where(RawMaterial.id.in_(example_ids))
                ).all()
            ]
        audience_info = AudienceInfo(
            id=audience["id"],
            name=audience["name"],
            alcohol_free=audience["alcohol_free"],
            disclaimer=audience["disclaimer"],
            excluded_examples=sorted(examples),
            excluded_count=len(forbidden_ids),
        )

    # Сезонність: попередження про обрану користувачем свіжу сировину поза сезоном
    # (її не відкидаємо — лише радимо «зимову» форму).
    season_info: Optional[SeasonInfo] = None
    if season:
        out_items: List[OutOfSeasonItem] = []
        seen_oos: Set[int] = set()
        for s in chosen:
            if (
                s.role in ("main", "additional")
                and s.form == FORM_FRESH
                and s.material_id in season_blocked_ids
                and s.material_id not in seen_oos
            ):
                seen_oos.add(s.material_id)
                out_items.append(
                    OutOfSeasonItem(
                        name=s.name,
                        suggestion=_preserved_form_suggestion(db, s.material_id),
                    )
                )
        season_info = SeasonInfo(
            id=season,
            name=seasons.season_name(season),
            out_of_season=out_items,
        )

    return GenerateResponse(
        base=base_name,
        desired=desired_names,
        variants=unique,
        feasibility=feasibility,
        base_influence=base_infl,
        audience=audience_info,
        season=season_info,
    )
