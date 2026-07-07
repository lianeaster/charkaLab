"""Гастрономічна гармонія композиції.

Балансу смакових осей (солодке/кисле/гірке/терпке/пекуче) недостатньо, щоб напій
був СМАЧНИМ. Технічно врівноважена композиція може поєднувати смаки з різних
«гастрономічних світів» — напр. часниково-сірчану базу з десертно-ягідними
нотами. Осі при цьому рівні (пекучість часнику гаситься цукром), але поєднання
неїстівне.

Цей модуль оцінює саме сумісність АРОМАТИЧНИХ РОДИН між собою. Ноти згруповано у
родини (цитрусові, ягідні, солодко-десертні, часниково-сірчані…), а між родинами
задано конфлікти — пари, що гастрономічно не в'яжуться. Що сильніше у профілі
одночасно присутні дві конфліктні родини, то нижча гармонія.

Модель навмисно консервативна: більшість поєднань нейтральні (штрафу нема),
штрафуються лише явні дисонанси. Її легко розширювати новими родинами/правилами.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Tuple

# --- Ароматичні родини: характеристика -> родина ---------------------------
# Смакові осі (кислий/гіркий/терпкий) сюди НЕ входять — вони структурні й
# покриваються балансом; для гармонії важать саме ароматичні «світи» смаку.

CITRUS = "citrus"
FRESH = "fresh"
FLORAL = "floral"
FRUITY = "fruity"
BERRY = "berry"
SWEET = "sweet"
HERBAL = "herbal"
SPICY = "spicy"
WOODY = "woody"
NUTTY = "nutty"
ROASTED = "roasted"
SAVORY = "savory"

# Людські назви родин для пояснень користувачу
FAMILY_LABEL: Dict[str, str] = {
    CITRUS: "цитрусовий",
    FRESH: "свіжий/охолоджуючий",
    FLORAL: "квітковий",
    FRUITY: "фруктовий",
    BERRY: "ягідний",
    SWEET: "солодко-десертний",
    HERBAL: "трав'яний",
    SPICY: "пряний",
    WOODY: "деревинно-смолистий",
    NUTTY: "горіховий",
    ROASTED: "смажено-кавовий",
    SAVORY: "часниково-сірчаний (стравний)",
}

FAMILY_OF: Dict[str, str] = {
    # --- цитрусові ---
    "цитрусовий": CITRUS,
    "лимонний": CITRUS,
    "лаймовий": CITRUS,
    "апельсиновий": CITRUS,
    "грейпфрутовий": CITRUS,
    "бергамотовий": CITRUS,
    # --- свіжі / охолоджуючі / зелені ---
    "свіжий": FRESH,
    "зелений": FRESH,
    "ментоловий": FRESH,
    "м'ятний": FRESH,
    "охолоджуючий": FRESH,
    "евкаліптовий": FRESH,
    "камфорний": FRESH,
    # --- квіткові ---
    "квітковий": FLORAL,
    "трояндовий": FLORAL,
    "фіалковий": FLORAL,
    "лавандовий": FLORAL,
    # --- фруктові (зокрема тропічні та кісточкові) ---
    "фруктовий": FRUITY,
    "тропічний": FRUITY,
    "кісточковий": FRUITY,
    # --- ягідні ---
    "ягідний": BERRY,
    # --- солодко-десертні ---
    "солодкий": SWEET,
    "ванільний": SWEET,
    "карамельний": SWEET,
    "медовий": SWEET,
    # --- трав'яні / чайні / анісово-лакричні / сінні ---
    "трав'яний": HERBAL,
    "сінний": HERBAL,
    "чайний": HERBAL,
    "анісовий": HERBAL,
    "лакричний": HERBAL,
    # --- пряні / зігріваючі ---
    "пряний": SPICY,
    "коричний": SPICY,
    "гвоздичний": SPICY,
    "мускатний": SPICY,
    "імбирний": SPICY,
    "перцевий": SPICY,
    "зігріваючий": SPICY,
    "пекучий": SPICY,
    "поколюючий": SPICY,
    # --- деревинно-смолисті / землисті ---
    "деревинний": WOODY,
    "смолистий": WOODY,
    "хвойний": WOODY,
    "ялівцевий": WOODY,
    "кедровий": WOODY,
    "землистий": WOODY,
    "бальзамічний": WOODY,
    # --- горіхові ---
    "горіховий": NUTTY,
    "мигдальний": NUTTY,
    # --- смажено-кавові / димні ---
    "кавовий": ROASTED,
    "шоколадний": ROASTED,
    "димний": ROASTED,
    "смажений": ROASTED,
    # --- часниково-сірчані / бульйонні (стравні) ---
    "часниковий": SAVORY,
    "сірчаний": SAVORY,
    "бульйонний": SAVORY,
}

# --- Матриця конфліктів родин ----------------------------------------------
# Ключ — невпорядкована пара родин; значення — тяжкість дисонансу (0..1).
# Задаємо ЛИШЕ конфлікти; усі інші пари вважаються сумісними (штрафу нема).
# Головний офендер — SAVORY (часник/сірка/бульйон) у солодко-ягідно-фруктово-
# квіткових напоях. Смажено-кавові ноти конфліктують із делікатними свіжими та
# квітковими.
_CLASH_RAW: Dict[Tuple[str, str], float] = {
    (SAVORY, SWEET): 1.0,
    (SAVORY, BERRY): 0.9,
    (SAVORY, FRUITY): 0.9,
    (SAVORY, FLORAL): 0.85,
    (SAVORY, FRESH): 0.5,
    (SAVORY, CITRUS): 0.45,
    (ROASTED, FRESH): 0.4,
    (ROASTED, FLORAL): 0.3,
}
CLASH: Dict[frozenset, float] = {
    frozenset(pair): sev for pair, sev in _CLASH_RAW.items()
}

# Родина мусить складати щонайменше цю частку ароматичного сигналу, щоб її
# врахувати (сліди не створюють дисонансу).
PRESENCE_MIN = 0.07
# Множник тяжкості: наскільки різко конфлікт «садить» гармонію. Підібрано так, що
# один помірний конфлікт дає помітний, але не катастрофічний спад, а кілька
# сильних (часник у десертно-ягідному напої) — обвал до ~0.
CLASH_K = 2.6
# Поріг штрафу окремої пари, з якого додаємо пояснення користувачу.
NOTE_MIN = 0.05


@dataclass
class HarmonyResult:
    score: float
    notes: List[str] = field(default_factory=list)
    # присутні родини (частка сигналу) — для діагностики/UI за потреби
    families: Dict[str, float] = field(default_factory=dict)


def _family_presence(totals: Mapping[str, float]) -> Dict[str, float]:
    """Сумарний внесок кожної родини за характеристиками профілю (частки)."""
    raw: Dict[str, float] = defaultdict(float)
    for name, value in totals.items():
        if value <= 0:
            continue
        fam = FAMILY_OF.get(name)
        if fam is not None:
            raw[fam] += value
    total = sum(raw.values())
    if total <= 0:
        return {}
    return {fam: val / total for fam, val in raw.items()}


def score_harmony(totals: Mapping[str, float]) -> HarmonyResult:
    """Оцінка гастрономічної гармонії за сумарним профілем (аромат+смак).

    totals — характеристика -> сумарна інтенсивність у напої. Повертає оцінку
    [0..1] (1 — жодних дисонансів) і людські пояснення до кожного помітного
    конфлікту родин.
    """
    families = _family_presence(totals)
    if not families:
        return HarmonyResult(score=1.0, notes=[], families={})

    present = {f: frac for f, frac in families.items() if frac >= PRESENCE_MIN}

    penalty_total = 0.0
    clashes: List[Tuple[float, str, str]] = []
    fams = sorted(present)
    for i, a in enumerate(fams):
        for b in fams[i + 1:]:
            sev = CLASH.get(frozenset((a, b)))
            if sev is None:
                continue
            overlap = min(present[a], present[b])
            penalty = sev * CLASH_K * overlap
            if penalty <= 0:
                continue
            penalty_total += penalty
            clashes.append((penalty, a, b))

    score = max(0.0, min(1.0, 1.0 - penalty_total))

    clashes.sort(reverse=True)
    notes: List[str] = []
    for penalty, a, b in clashes:
        if penalty < NOTE_MIN:
            continue
        notes.append(
            f"«{FAMILY_LABEL[a]}» і «{FAMILY_LABEL[b]}» — смаки з різних "
            "гастрономічних світів, разом дисонують"
        )

    return HarmonyResult(
        score=round(score, 3), notes=notes, families=families
    )


def dominant_clash(totals: Mapping[str, float]) -> Optional[Tuple[str, str]]:
    """Найсильніша конфліктна пара родин (людські назви) або None."""
    res = score_harmony(totals)
    families = {f: v for f, v in res.families.items() if v >= PRESENCE_MIN}
    worst: Optional[Tuple[float, str, str]] = None
    fams = sorted(families)
    for i, a in enumerate(fams):
        for b in fams[i + 1:]:
            sev = CLASH.get(frozenset((a, b)))
            if sev is None:
                continue
            penalty = sev * min(families[a], families[b])
            if worst is None or penalty > worst[0]:
                worst = (penalty, a, b)
    if worst is None:
        return None
    return FAMILY_LABEL[worst[1]], FAMILY_LABEL[worst[2]]
