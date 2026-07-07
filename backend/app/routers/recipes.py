from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import RawMaterial
from ..schemas import (
    GenerateRequest,
    GenerateResponse,
    MaterialSelection,
    RecipeVariant,
    RecomputeRequest,
    SurpriseRequest,
)
from ..services import engine

router = APIRouter(prefix="/recipes", tags=["recipes"])


def _validate_user_materials(
    db: Session,
    audience_id: Optional[str],
    selections: List[MaterialSelection],
) -> None:
    """Спільна валідація обраної користувачем сировини.

    1. Сировина має існувати, а її варіант (частина/форма/кісточка) — бути
       реальним препаратом (інакше внесок у профіль тихо стане нульовим).
    2. Жорсткий фільтр ЦА діє й на користувацький вибір: заборонену для
       аудиторії сировину не приймаємо — інакше «безпечний» рецепт міститиме
       протипоказаний інгредієнт.
    """
    for m in selections:
        if m.material_id <= 0:
            continue
        mat = db.get(RawMaterial, m.material_id)
        if mat is None:
            raise HTTPException(
                status_code=404, detail=f"Сировину #{m.material_id} не знайдено"
            )
        if not engine.variant_exists(db, m.material_id, m.part, m.form, m.pit):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"У сировини «{mat.name}» немає варіанта "
                    f"({m.part} / {m.form} / {m.pit})"
                ),
            )
    violations = engine.forbidden_user_materials(
        db, audience_id, [m.material_id for m in selections if m.material_id > 0]
    )
    if violations:
        raise HTTPException(
            status_code=422,
            detail=(
                "Сировина протипоказана обраній аудиторії: "
                f"{', '.join(violations)}. Приберіть її або змініть аудиторію."
            ),
        )


@router.post("/generate", response_model=GenerateResponse)
def generate_recipe(req: GenerateRequest, db: Session = Depends(get_db)):
    _validate_user_materials(
        db, req.audience_id, [req.main_material, *req.additional_materials]
    )
    return engine.generate(db, req)


@router.post("/surprise", response_model=GenerateResponse)
def surprise_recipe(req: SurpriseRequest, db: Session = Depends(get_db)):
    """«Здивуй мене»: система сама добирає профілі під основну сировину."""
    _validate_user_materials(
        db, req.audience_id, [req.main_material, *req.additional_materials]
    )
    return engine.surprise(db, req)


@router.post("/recompute", response_model=RecipeVariant)
def recompute_recipe(req: RecomputeRequest, db: Session = Depends(get_db)):
    """Перерахунок одного варіанта з відредагованим складом (без основної)."""
    _validate_user_materials(
        db, req.audience_id, [req.main_material, *req.materials]
    )
    return engine.recompute(db, req)
