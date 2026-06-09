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
)
from ..schemas import (
    CharacteristicScore,
    CompoundContribution,
    GenerateRequest,
    GenerateResponse,
    MaterialInComposition,
    RecipeVariant,
)

MAX_VARIANTS = 4
MAX_SUGGESTED = 3
MIN_INGREDIENTS = 4
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
# скільки солодкості додати «понад» рівень гострих смаків, щоб напій не був різким
SUGAR_HEADROOM = 0.1


@dataclass
class ResolvedSelection:
    material_id: int
    name: str
    part: str
    form: str
    pit: str
    role: str  # main | additional | suggested | balance | harmony | sweetener
    sweet_add: float = 0.0  # пряма солодкість (цукор), без аромату


@dataclass
class Profile:
    aroma: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    taste: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    compounds: Dict[str, Tuple[str, Set[str]]] = field(default_factory=dict)

    def total(self, char_name: str) -> float:
        return self.aroma.get(char_name, 0.0) + self.taste.get(char_name, 0.0)


def _compound_chars(compound: AromaCompound) -> Dict[str, float]:
    return {
        cc.characteristic.name: cc.weight
        for cc in compound.characteristics
        if cc.characteristic is not None
    }


def _add_selection_to_profile(
    db: Session, selection: ResolvedSelection, profile: Profile
) -> None:
    # Цукор — чиста солодкість, без сировинного аромату
    if selection.role == "sweetener" or selection.sweet_add > 0:
        profile.taste[SWEET] += selection.sweet_add
        if SUGAR_NAME not in profile.compounds:
            profile.compounds[SUGAR_NAME] = (KIND_TASTE, {SWEET})
        else:
            profile.compounds[SUGAR_NAME][1].add(SWEET)
        return
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
        char_weights = _compound_chars(compound)
        char_names: Set[str] = set(char_weights.keys())
        for char_name, weight in char_weights.items():
            contribution = mc.intensity * weight
            if compound.kind in (KIND_AROMA, KIND_BOTH):
                profile.aroma[char_name] += contribution
            if compound.kind in (KIND_TASTE, KIND_BOTH):
                profile.taste[char_name] += contribution
        if compound.name not in profile.compounds:
            profile.compounds[compound.name] = (compound.kind, char_names)
        else:
            profile.compounds[compound.name][1].update(char_names)


def _build_profile(db: Session, selections: List[ResolvedSelection]) -> Profile:
    profile = Profile()
    for sel in selections:
        _add_selection_to_profile(db, sel, profile)
    return profile


def _score(profile: Profile, desired_names: List[str]) -> float:
    """Оцінка відповідності бажаному ароматичному профілю."""
    if not desired_names:
        return 0.0
    scores = [profile.total(name) for name in desired_names]
    covered = sum(1 for s in scores if s > 0)
    coverage_ratio = covered / len(desired_names)
    capped = [min(s, 1.0) for s in scores]
    strength = sum(capped) / len(capped)
    return round(0.65 * coverage_ratio + 0.35 * strength, 3)


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


def _best_option_for_chars(
    db: Session, material_id: int, target_chars: Set[str]
) -> Optional[Tuple[str, str, str, float]]:
    """Знайти (part, form, pit), що максимально покриває потрібні характеристики."""
    rows = db.scalars(
        select(MaterialCompound).where(
            MaterialCompound.raw_material_id == material_id
        )
    ).all()
    by_option: Dict[Tuple[str, str, str], float] = defaultdict(float)
    for mc in rows:
        compound = db.get(AromaCompound, mc.compound_id)
        if compound is None:
            continue
        for char_name, weight in _compound_chars(compound).items():
            if char_name in target_chars:
                by_option[(mc.part, mc.form, mc.pit)] += mc.intensity * weight
    if not by_option:
        return None
    (part, form, pit), val = max(by_option.items(), key=lambda kv: kv[1])
    return part, form, pit, val


def _find_candidates(
    db: Session, missing_names: Set[str], exclude_ids: Set[int]
) -> List[Tuple[int, str, str, str, float, Set[str]]]:
    """Кандидати-сировина, що дають потрібні характеристики.

    Повертає list of (material_id, part, form, pit, value, covered_chars).
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
        best = _best_option_for_chars(db, mid, missing_names)
        if best is None:
            continue
        part, form, pit, val = best
        if val <= 0:
            continue
        covered = _covered_chars(db, mid, part, form, pit, missing_names)
        if not covered:
            continue
        candidates.append((mid, part, form, pit, val, covered))
    candidates.sort(key=lambda c: (len(c[5]), c[4]), reverse=True)
    return candidates


def _covered_chars(
    db: Session, material_id: int, part: str, form: str, pit: str, target: Set[str]
) -> Set[str]:
    rows = db.scalars(
        select(MaterialCompound).where(
            MaterialCompound.raw_material_id == material_id,
            MaterialCompound.part == part,
            MaterialCompound.form == form,
            MaterialCompound.pit == pit,
        )
    ).all()
    covered: Set[str] = set()
    for mc in rows:
        compound = db.get(AromaCompound, mc.compound_id)
        if compound is None:
            continue
        for char_name in _compound_chars(compound):
            if char_name in target:
                covered.add(char_name)
    return covered


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
            if harsh > 0.6:
                continue  # не додаємо гіркоти заради кількості
            aroma_val = sum(v for k, v in chans.items() if k.startswith("aroma::"))
            if aroma_val <= 0:
                continue
            desired_hits = sum(
                v
                for k, v in chans.items()
                if k.startswith("aroma::") and k.split("::", 1)[1] in desired_set
            )
            quality = desired_hits * 2.0 + aroma_val - harsh
            if best is None or quality > best[5]:
                best = (mid, part, form, pit, desired_hits > 0, quality)
    if best is None:
        return None
    return best[0], best[1], best[2], best[3], best[4]


def _finalize(
    db: Session, selections: List[ResolvedSelection], desired_set: Set[str]
) -> Tuple[List[ResolvedSelection], List[str]]:
    """Балансування смаку (цукром/кислотою) + мінімум інгредієнтів."""
    notes: List[str] = []
    used: Set[int] = {s.material_id for s in selections}

    profile = _build_profile(db, selections)
    sweet = profile.taste.get(SWEET, 0.0)
    sour = profile.taste.get(SOUR, 0.0)
    harsh_vals = {a: profile.taste.get(a, 0.0) for a in HARSH_AXES}
    aroma_signal = max(profile.aroma.values(), default=0.0)

    # «Небажані» гострі смаки (ті, що не входять у бажаний профіль)
    harsh_off = {a: v for a, v in harsh_vals.items() if a not in desired_set and v > 0}
    harsh_off_total = sum(harsh_off.values())

    # Скільки солодкості (цукру) треба додати для балансу.
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

    # 1) Додаємо цукор, якщо потрібно
    dose = round(needed_sweet - sweet, 2)
    if dose > 0:
        selections.append(
            ResolvedSelection(
                material_id=0,
                name=SUGAR_NAME,
                part="whole",
                form="na",
                pit="na",
                role="sweetener",
                sweet_add=dose,
            )
        )
        sweet += dose
        notes.append(
            f"{SUGAR_NAME} (~{dose}): солодкість, щоб {', '.join(reasons)}"
        )

    # 2) Нудотно-солодко й «пласко» → додати кислинку для свіжості
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
                ResolvedSelection(mid, _resolve_name(db, mid), part, form, pit, "balance")
            )
            used.add(mid)
            notes.append(
                f"{_resolve_name(db, mid)}: свіжа кислинка проти надмірної солодкості"
            )

    # 3) Мінімум ароматичних інгредієнтів для гармонії (цукор не рахуємо)
    def _aromatic_count() -> int:
        return sum(1 for s in selections if s.material_id > 0)

    guard = 0
    while _aromatic_count() < MIN_INGREDIENTS and guard < 6:
        guard += 1
        harm = _find_harmony(db, desired_set, used)
        if harm is None:
            break
        mid, part, form, pit, reinforces = harm
        selections.append(
            ResolvedSelection(mid, _resolve_name(db, mid), part, form, pit, "harmony")
        )
        used.add(mid)
        reason = (
            "підсилює бажаний профіль"
            if reinforces
            else "додає ароматичної складності для гармонії"
        )
        notes.append(f"{_resolve_name(db, mid)}: {reason}")

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
        )
        for s in selections
    ]
    suggested = [s.name for s in selections if s.role == "suggested"]

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
    )


def _overall(variant: RecipeVariant) -> float:
    return 0.6 * variant.match_score + 0.4 * variant.balance_score


def generate(db: Session, req: GenerateRequest) -> GenerateResponse:
    desired_rows = db.scalars(
        select(Characteristic).where(Characteristic.id.in_(req.desired_characteristics))
    ).all()
    desired_names = [c.name for c in desired_rows]
    desired_set = set(desired_names)

    base_name: Optional[str] = None
    if req.base_id is not None:
        base = db.get(Base_, req.base_id)
        base_name = base.name if base else None

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
    candidates = _find_candidates(db, base_missing, exclude_ids) if base_missing else []

    # Набори-заготовки композицій (до балансування)
    seeds: List[Tuple[str, List[ResolvedSelection]]] = []

    # 1) Основна: обрана сировина + жадібне закриття прогалин профілю
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
    seeds.append(("Збалансована композиція під профіль", greedy))

    # 2) Лише обрана сировина (збалансована)
    seeds.append(("Збалансована композиція з обраної сировини", list(chosen)))

    # 3) Альтернативи: обрана + один кандидат
    for mid, part, form, pit, _val, _covered in candidates[:MAX_VARIANTS]:
        single = list(chosen)
        single.append(
            ResolvedSelection(mid, _resolve_name(db, mid), part, form, pit, "suggested")
        )
        seeds.append((f"Альтернатива: + {_resolve_name(db, mid)}", single))

    variants: List[RecipeVariant] = []
    for title, sel in seeds:
        finalized, notes = _finalize(db, list(sel), desired_set)
        variants.append(_make_variant(db, title, finalized, desired_names, notes))

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

    return GenerateResponse(base=base_name, desired=desired_names, variants=unique)
