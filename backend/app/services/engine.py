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
    KIND_AROMA,
    KIND_BOTH,
    KIND_TASTE,
    MaterialCompound,
    RawMaterial,
    VOL_BASE,
    VOL_HEART,
    VOL_TOP,
)
from ..schemas import (
    BaseInfluence,
    CharacteristicScore,
    CompoundContribution,
    GenerateRequest,
    GenerateResponse,
    MaterialInComposition,
    PyramidLayer,
    ProfileFeasibility,
    RecipeVariant,
)

MAX_VARIANTS = 4
MAX_SUGGESTED = 3
MIN_INGREDIENTS = 4
# Стеля кількості ароматичних складових (без підсолоджувача): дозволяє додавати
# більше інгредієнтів, щоб краще «вписатися» в профіль.
MAX_INGREDIENTS = 7
# Цільова виразність кожної бажаної характеристики; поки нота слабша — додаємо
# ще чистих підсилювачів.
TARGET_STRENGTH = 0.8
MAX_BALANCE_STEPS = 3

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
BASE_PROFILES: Dict[str, Dict] = {
    "спирт пшеничний": {
        "abv": 70,
        "abv_hint": "40–70% — добре витягує ефірні олії, терпени, смоли",
        "profile": {},
        "conflicts": set(),
        "synergy": {"свіжий", "цитрусовий", "квітковий", "трав'яний", "хвойний"},
        "note": "Нейтральна основа — підкреслює аромат сировини, не вносить власних нот.",
    },
    "спирт цукровий": {
        "abv": 65,
        "abv_hint": "40–65% — добре витягує ефірні олії; злегка м'якший за пшеничний",
        "profile": {SWEET: 0.15},
        "conflicts": set(),
        "synergy": {"фруктовий", "солодкий", "ягідний", "медовий"},
        "note": "Злегка солодкуватий, м'який — підсилює фруктово-ягідні та медові ноти.",
    },
    "вино червоне": {
        "abv": 13,
        "abv_hint": "11–14% — витягує антоціани, таніни, кислоти; ефірні олії — слабко",
        "profile": {ASTRINGENT: 0.4, "ягідний": 0.3, SOUR: 0.25},
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
        "profile": {"свіжий": 0.25, "квітковий": 0.15, SOUR: 0.2},
        "conflicts": {"смолистий", "деревинний", "землистий", "ялівцевий", "кедровий"},
        "synergy": {"цитрусовий", "квітковий", "свіжий", "медовий", "трав'яний"},
        "note": (
            "Свіже, квіткове, кислотне. Добре з цитрусово-квітковими профілями. "
            "Конфліктує з важкими смолистими та деревинними нотами."
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
    role: str  # main | additional | suggested | balance | harmony | sweetener
    sweet_add: float = 0.0  # пряма солодкість (цукор), без аромату
    amount: float = 1.0  # частка (доза) інгредієнта; основна сировина = 1.0


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
    covered = sum(1 for s in scores if s > 0)
    coverage_ratio = covered / len(desired_names)
    capped = [min(s, 1.0) for s in scores]
    strength = sum(capped) / len(capped)

    on_signal = sum(scores)
    off_signal = 0.0
    for name, value in profile.aroma.items():
        if name not in desired_set:
            off_signal += value
    for name, value in profile.taste.items():
        # солодкість зазвичай додаємо навмисно (баланс) — не вважаємо «шумом»
        if name not in desired_set and name != SWEET:
            off_signal += value
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
        if name in desired_set:
            on += value
        elif name != SWEET:
            off += value
    return on, off, on - OFF_PENALTY * off


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
    db: Session, missing_names: Set[str], exclude_ids: Set[int], desired_set: Set[str]
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


def _option_breakdown(
    db: Session, material_id: int
) -> Dict[Tuple[str, str, str], Dict[str, float]]:
    """Для кожної (part, form, pit) — внески за каналами: aroma_*, taste_*."""
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
    return out


def _find_taste_provider(
    db: Session, needed_char: str, exclude_ids: Set[int], avoid_chars: Set[str]
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


def _find_harmony(
    db: Session, desired_set: Set[str], exclude_ids: Set[int]
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
            harsh = sum(chans.get(f"taste::{a}", 0.0) for a in HARSH_AXES)
            if harsh > 0.4:
                continue  # не додаємо гострих смаків заради кількості
            on, _off, net = _option_net(chans, desired_set)
            # гармонізуючий інгредієнт мусить РЕАЛЬНО підсилювати бажаний профіль
            # і майже не шуміти; інакше краще менше інгредієнтів, ніж сторонні ноти
            if on <= 0 or net <= 0:
                continue
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
) -> Tuple[List[ResolvedSelection], List[str]]:
    """Дозування інгредієнтів + балансування смаку + мінімум інгредієнтів.

    max_ingredients — стеля ароматичних складових (для «лаконічної» композиції
    можна задати MIN_INGREDIENTS). sweetener — чим підсолоджувати: автоматично,
    примусово медом чи цукром (для варіанта з альтернативним підсолоджувачем).
    """
    notes: List[str] = []
    used: Set[int] = {s.material_id for s in selections}
    # Мед не підказуємо як звичайну сировину — лише як підсолоджувач, щоб уникнути
    # подвійної згадки (мед-сировина + мед-солодкість).
    honey_id = _honey_id(db)
    honey_block = {honey_id} if honey_id else set()

    # Основна сировина — повна доза; решту дозуємо за «чистотою» внеску.
    for s in selections:
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

    def _weakest_desired() -> Optional[str]:
        prof = _build_profile(db, selections)
        weak = [(c, prof.total(c)) for c in desired_set]
        weak = [(c, v) for c, v in weak if v < TARGET_STRENGTH]
        if not weak:
            return None
        return min(weak, key=lambda cv: cv[1])[0]

    guard = 0
    while guard < max_ingredients + MIN_INGREDIENTS:
        guard += 1
        count = _aromatic_count()
        if count >= max_ingredients:
            break
        target_char = _weakest_desired()
        need_min = count < MIN_INGREDIENTS
        if target_char is None and not need_min:
            break  # достатньо складових і профіль уже виразний

        mid = part = form = pit = None
        block = used | honey_block
        # Конфлікти з основою розширюють «шум» при оцінці кандидатів: інгредієнти,
        # що підсилюють конфліктні ноти, отримують нижчий net і не обираються.
        effective_desired = desired_set - base_conflict_chars
        # 1а) прицільно підсилюємо найслабшу бажану ноту чистою сировиною
        if target_char is not None:
            for c in _find_candidates(db, {target_char}, block, effective_desired):
                if c[4] > 0:  # net > 0 — підсилює, майже не шумить
                    mid, part, form, pit = c[0], c[1], c[2], c[3]
                    break
        # 1б) інакше (для добору мінімуму) — будь-який чистий гармонійний інгредієнт
        if mid is None:
            harm = _find_harmony(db, effective_desired, block)
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
        if target_char is not None:
            notes.append(
                f"{_resolve_name(db, mid)}: підсилює «{target_char}» у профілі"
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
            for c in _find_candidates(db, effective_desired, block, effective_desired):
                if c[4] <= 0:  # шумна — пропускаємо
                    continue
                if _option_layer(db, c[0], c[1], c[2], c[3]) != VOL_BASE:
                    continue
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
        prov = _find_taste_provider(db, SOUR, used, set(HARSH_AXES))
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
    covered = [n for n in desired_names if profile.total(n) > 0]
    missing = [n for n in desired_names if profile.total(n) <= 0]

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
    if balance >= 0.85:
        parts.append("Смак збалансований.")
    else:
        parts.append("Смак вимагав корекції балансу.")
    explanation = " ".join(parts)

    return RecipeVariant(
        title=title,
        match_score=score,
        balance_score=balance,
        materials=materials,
        aroma_profile=_profile_scores(profile, profile.aroma, desired_set),
        taste_profile=_profile_scores(profile, profile.taste, desired_set),
        covered=covered,
        missing=missing,
        compounds=compounds,
        balance_notes=balance_notes,
        explanation=explanation,
        pyramid=pyramid,
    )


def _overall(variant: RecipeVariant) -> float:
    return 0.6 * variant.match_score + 0.4 * variant.balance_score


def _feasibility(
    db: Session,
    chosen: List[ResolvedSelection],
    desired_names: List[str],
    variants: List[RecipeVariant],
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
    chosen_ids = {s.material_id for s in chosen}

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


def generate(db: Session, req: GenerateRequest) -> GenerateResponse:
    desired_rows = db.scalars(
        select(Characteristic).where(Characteristic.id.in_(req.desired_characteristics))
    ).all()
    desired_names = [c.name for c in desired_rows]
    desired_set = set(desired_names)

    base_name: Optional[str] = None
    base_conflict_chars: Set[str] = set()
    distillate_bp: Optional[Dict] = None  # динамічний профіль для дистиляту
    if req.base_id is not None:
        base = db.get(Base_, req.base_id)
        base_name = base.name if base else None
        if base_name and base_name in BASE_PROFILES:
            base_conflict_chars = BASE_PROFILES[base_name]["conflicts"]
        elif base_name == DISTILLATE_BASE_NAME:
            # Будуємо профіль дистиляту з аромосполук основної сировини.
            # Дистиляція переносить леткі ноти (top/heart), але не таніни/кислоти.
            # Ефект: ABV ~75%, синергія = весь аромат основної сировини, нульовий конфлікт.
            main_sel = req.main_material
            breakdown = _option_breakdown(db, main_sel.material_id)
            # Пробуємо точний збіг, потім — будь-який варіант тієї ж part/form
            option_chans = breakdown.get((main_sel.part, main_sel.form, main_sel.pit), {})
            if not option_chans:
                for (p, f, _pit), chans in breakdown.items():
                    if p == main_sel.part and f == main_sel.form and chans:
                        option_chans = chans
                        break
            if not option_chans and breakdown:
                option_chans = next(iter(breakdown.values()))
            dist_profile: Dict[str, float] = {}
            for key, val in option_chans.items():
                if not key.startswith("aroma::"):
                    continue
                char_name = key[len("aroma::"):]
                # Перевіряємо летючість сполук — дистилят переважно несе top/heart
                dist_profile[char_name] = round(val * 0.5, 3)  # 50% від свіжого
            synergy_chars = set(dist_profile.keys())
            distillate_bp = {
                "abv": 75,
                "abv_hint": "70–85% — концентрує леткі ефірні олії та терпени основної сировини",
                "profile": dist_profile,
                "conflicts": set(),
                "synergy": synergy_chars,
                "note": (
                    f"Ароматний дистилят із основної сировини — підсилює та закріплює "
                    f"характер головного інгредієнта. Переносить леткі (top/heart) "
                    f"аромосполуки; таніни та антоціани при дистиляції не переходять."
                ),
            }

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
    auto_exclude = exclude_ids | ({honey_id} if honey_id else set())
    candidates = (
        _find_candidates(db, base_missing, auto_exclude, desired_set)
        if base_missing
        else []
    )

    # Жадібна заготовка: обрана сировина + закриття прогалин профілю кандидатами.
    greedy = list(chosen)
    still_missing = set(base_missing)
    used: Set[int] = set(exclude_ids)
    for mid, part, form, pit, _val, covered in candidates:
        if not (covered & still_missing):
            continue
        greedy.append(
            ResolvedSelection(mid, _resolve_name(db, mid), part, form, pit, "suggested")
        )
        used.add(mid)
        still_missing -= covered
        if not still_missing or len(used) - len(exclude_ids) >= MAX_SUGGESTED:
            break

    # Три ГЕНЕТИЧНО різні стратегії композиції замість збіжних «альтернатив»:
    variants: List[RecipeVariant] = []

    # A) Повна композиція під профіль — багата, до MAX_INGREDIENTS, авто-баланс.
    full_sel, full_notes = _finalize(
        db, list(greedy), desired_set,
        max_ingredients=MAX_INGREDIENTS, sweetener="auto",
        base_conflict_chars=base_conflict_chars,
    )
    variants.append(
        _make_variant(db, "Повна композиція під профіль", full_sel, desired_names, full_notes)
    )

    # Який підсолоджувач узяла повна композиція — для альтернативи беремо інший.
    full_sweet = next((s.name for s in full_sel if s.role == "sweetener"), None)

    # B) Лаконічна композиція — лише обрана сировина + мінімум для покриття/балансу.
    lean_sel, lean_notes = _finalize(
        db, list(chosen), desired_set,
        max_ingredients=MIN_INGREDIENTS, sweetener="auto",
        base_conflict_chars=base_conflict_chars,
    )
    variants.append(
        _make_variant(
            db, "Лаконічна композиція (мінімум складових)", lean_sel, desired_names, lean_notes
        )
    )

    # C) З альтернативним підсолоджувачем — та сама база, але мед↔цукор.
    if full_sweet is not None:
        alt = "sugar" if full_sweet == HONEY_NAME else "honey"
        alt_label = SUGAR_NAME if alt == "sugar" else HONEY_NAME
        alt_sel, alt_notes = _finalize(
            db, list(greedy), desired_set,
            max_ingredients=MAX_INGREDIENTS, sweetener=alt,
            base_conflict_chars=base_conflict_chars,
        )
        variants.append(
            _make_variant(
                db, f"Варіант із підсолоджувачем: {alt_label}", alt_sel, desired_names, alt_notes
            )
        )

    # дедуплікація за набором матеріалів + сортування за загальною оцінкою
    seen: Set[Tuple] = set()
    unique: List[RecipeVariant] = []
    for v in sorted(variants, key=_overall, reverse=True):
        key = tuple(sorted((m.material_id, m.part, m.form, m.pit) for m in v.materials))
        if key in seen:
            continue
        seen.add(key)
        unique.append(v)
        if len(unique) >= MAX_VARIANTS:
            break

    feasibility = _feasibility(db, chosen, desired_names, unique)
    base_infl = _base_influence(
        base_name, desired_set, unique, dynamic_bp=distillate_bp
    )

    return GenerateResponse(
        base=base_name,
        desired=desired_names,
        variants=unique,
        feasibility=feasibility,
        base_influence=base_infl,
    )
