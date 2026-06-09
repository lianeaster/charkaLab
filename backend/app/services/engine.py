"""Движок підбору композицій аромосполук під бажаний профіль напою."""

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
    MaterialSelection,
    RecipeVariant,
)

MAX_VARIANTS = 4
MAX_SUGGESTED = 3


@dataclass
class ResolvedSelection:
    material_id: int
    name: str
    form: str
    pit: str
    role: str


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
    rows = db.scalars(
        select(MaterialCompound).where(
            MaterialCompound.raw_material_id == selection.material_id,
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
    if not desired_names:
        return 0.0
    scores = [profile.total(name) for name in desired_names]
    covered = sum(1 for s in scores if s > 0)
    coverage_ratio = covered / len(desired_names)
    capped = [min(s, 1.0) for s in scores]
    strength = sum(capped) / len(capped)
    return round(0.65 * coverage_ratio + 0.35 * strength, 3)


def _resolve_name(db: Session, material_id: int) -> str:
    mat = db.get(RawMaterial, material_id)
    return mat.name if mat else f"#{material_id}"


def _best_option_for_chars(
    db: Session, material_id: int, target_chars: Set[str]
) -> Optional[Tuple[str, str, float]]:
    """Знайти (form, pit), що максимально покриває потрібні характеристики."""
    rows = db.scalars(
        select(MaterialCompound).where(
            MaterialCompound.raw_material_id == material_id
        )
    ).all()
    by_option: Dict[Tuple[str, str], float] = defaultdict(float)
    for mc in rows:
        compound = db.get(AromaCompound, mc.compound_id)
        if compound is None:
            continue
        for char_name, weight in _compound_chars(compound).items():
            if char_name in target_chars:
                by_option[(mc.form, mc.pit)] += mc.intensity * weight
    if not by_option:
        return None
    (form, pit), val = max(by_option.items(), key=lambda kv: kv[1])
    return form, pit, val


def _find_candidates(
    db: Session, missing_names: Set[str], exclude_ids: Set[int]
) -> List[Tuple[int, str, str, float, Set[str]]]:
    """Кандидати-сировина, що дають потрібні характеристики.

    Повертає list of (material_id, form, pit, value, covered_chars).
    """
    if not missing_names:
        return []
    char_ids = db.scalars(
        select(Characteristic.id).where(Characteristic.name.in_(missing_names))
    ).all()
    if not char_ids:
        return []
    # сировина, що містить сполуки з потрібними характеристиками
    material_ids = db.scalars(
        select(MaterialCompound.raw_material_id)
        .join(CompoundCharacteristic, CompoundCharacteristic.compound_id == MaterialCompound.compound_id)
        .where(
            CompoundCharacteristic.characteristic_id.in_(char_ids),
            MaterialCompound.raw_material_id.notin_(exclude_ids),
        )
        .distinct()
    ).all()

    candidates: List[Tuple[int, str, str, float, Set[str]]] = []
    for mid in material_ids:
        best = _best_option_for_chars(db, mid, missing_names)
        if best is None:
            continue
        form, pit, val = best
        if val <= 0:
            continue
        covered = _covered_chars(db, mid, form, pit, missing_names)
        if not covered:
            continue
        candidates.append((mid, form, pit, val, covered))
    candidates.sort(key=lambda c: (len(c[4]), c[3]), reverse=True)
    return candidates


def _covered_chars(
    db: Session, material_id: int, form: str, pit: str, target: Set[str]
) -> Set[str]:
    rows = db.scalars(
        select(MaterialCompound).where(
            MaterialCompound.raw_material_id == material_id,
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
) -> RecipeVariant:
    profile = _build_profile(db, selections)
    desired_set = set(desired_names)
    score = _score(profile, desired_names)
    covered = [n for n in desired_names if profile.total(n) > 0]
    missing = [n for n in desired_names if profile.total(n) <= 0]

    compounds = [
        CompoundContribution(
            compound=name,
            kind=kind,
            characteristics=sorted(chars),
        )
        for name, (kind, chars) in sorted(profile.compounds.items())
    ]
    materials = [
        MaterialInComposition(
            material_id=s.material_id,
            name=s.name,
            form=s.form,
            pit=s.pit,
            role=s.role,
        )
        for s in selections
    ]
    suggested = [s.name for s in selections if s.role == "suggested"]
    if suggested:
        explanation = (
            f"Покрито {len(covered)}/{len(desired_names)} бажаних характеристик. "
            f"Додано сировину для підсилення: {', '.join(suggested)}."
        )
    else:
        explanation = (
            f"Композиція з обраної сировини. "
            f"Покрито {len(covered)}/{len(desired_names)} бажаних характеристик."
        )
    if missing:
        explanation += f" Не вистачає: {', '.join(missing)}."

    return RecipeVariant(
        title=title,
        match_score=score,
        materials=materials,
        aroma_profile=_profile_scores(profile, profile.aroma, desired_set),
        taste_profile=_profile_scores(profile, profile.taste, desired_set),
        covered=covered,
        missing=missing,
        compounds=compounds,
        explanation=explanation,
    )


def generate(db: Session, req: GenerateRequest) -> GenerateResponse:
    desired_rows = db.scalars(
        select(Characteristic).where(Characteristic.id.in_(req.desired_characteristics))
    ).all()
    desired_names = [c.name for c in desired_rows]

    base_name: Optional[str] = None
    if req.base_id is not None:
        base = db.get(Base_, req.base_id)
        base_name = base.name if base else None

    chosen: List[ResolvedSelection] = []
    chosen.append(
        ResolvedSelection(
            material_id=req.main_material.material_id,
            name=_resolve_name(db, req.main_material.material_id),
            form=req.main_material.form,
            pit=req.main_material.pit,
            role="main",
        )
    )
    for add in req.additional_materials:
        chosen.append(
            ResolvedSelection(
                material_id=add.material_id,
                name=_resolve_name(db, add.material_id),
                form=add.form,
                pit=add.pit,
                role="additional",
            )
        )

    variants: List[RecipeVariant] = []
    base_variant = _make_variant(db, "Композиція з обраної сировини", chosen, desired_names)
    variants.append(base_variant)

    missing = set(base_variant.missing)
    exclude_ids = {s.material_id for s in chosen}

    if missing and desired_names:
        candidates = _find_candidates(db, missing, exclude_ids)

        # Варіант 2: додаємо кілька кандидатів, що жадібно закривають прогалини
        greedy: List[ResolvedSelection] = list(chosen)
        still_missing = set(missing)
        used: Set[int] = set()
        for mid, form, pit, _val, covered in candidates:
            if not (covered & still_missing):
                continue
            greedy.append(
                ResolvedSelection(
                    material_id=mid,
                    name=_resolve_name(db, mid),
                    form=form,
                    pit=pit,
                    role="suggested",
                )
            )
            used.add(mid)
            still_missing -= covered
            if not still_missing or len(used) >= MAX_SUGGESTED:
                break
        if used:
            variants.append(
                _make_variant(
                    db,
                    "Композиція з підібраною додатковою сировиною",
                    greedy,
                    desired_names,
                )
            )

        # Окремі варіанти: базова + один кандидат (альтернативи на вибір)
        for mid, form, pit, _val, _covered in candidates[:MAX_VARIANTS]:
            if mid in used:
                continue
            single = list(chosen)
            single.append(
                ResolvedSelection(
                    material_id=mid,
                    name=_resolve_name(db, mid),
                    form=form,
                    pit=pit,
                    role="suggested",
                )
            )
            variants.append(
                _make_variant(
                    db,
                    f"Альтернатива: + {_resolve_name(db, mid)}",
                    single,
                    desired_names,
                )
            )

    # унікалізація за набором матеріалів та сортування за оцінкою
    seen: Set[Tuple] = set()
    unique: List[RecipeVariant] = []
    for v in sorted(variants, key=lambda x: x.match_score, reverse=True):
        key = tuple(sorted((m.material_id, m.form, m.pit) for m in v.materials))
        if key in seen:
            continue
        seen.add(key)
        unique.append(v)
        if len(unique) >= MAX_VARIANTS:
            break

    return GenerateResponse(base=base_name, desired=desired_names, variants=unique)
