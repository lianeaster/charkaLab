from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import distinct, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import MaterialCompound, RawMaterial
from ..schemas import FormOption, MaterialFormsResponse, MaterialSuggestion

router = APIRouter(prefix="/materials", tags=["materials"])


@router.get("/suggest", response_model=List[MaterialSuggestion])
def suggest(
    q: str = Query("", description="Перші літери назви сировини"),
    limit: int = Query(10, ge=1, le=25),
    db: Session = Depends(get_db),
):
    stmt = select(RawMaterial)
    query = q.strip()
    if query:
        # збіг по початку слова, далі будь-яке входження
        stmt = stmt.where(RawMaterial.name.ilike(f"{query}%"))
    rows = db.scalars(stmt.order_by(RawMaterial.name).limit(limit)).all()
    if query and not rows:
        rows = db.scalars(
            select(RawMaterial)
            .where(RawMaterial.name.ilike(f"%{query}%"))
            .order_by(RawMaterial.name)
            .limit(limit)
        ).all()
    return [
        MaterialSuggestion(id=r.id, name=r.name, has_pit_variants=r.has_pit_variants)
        for r in rows
    ]


@router.get("/{material_id}/forms", response_model=MaterialFormsResponse)
def material_forms(material_id: int, db: Session = Depends(get_db)):
    mat = db.get(RawMaterial, material_id)
    if mat is None:
        raise HTTPException(status_code=404, detail="Сировину не знайдено")
    pairs = db.execute(
        select(distinct(MaterialCompound.form), MaterialCompound.pit).where(
            MaterialCompound.raw_material_id == material_id
        )
    ).all()
    seen = set()
    options: List[FormOption] = []
    for form, pit in pairs:
        key = (form, pit)
        if key in seen:
            continue
        seen.add(key)
        options.append(FormOption(form=form, pit=pit))
    options.sort(key=lambda o: (o.form, o.pit))
    return MaterialFormsResponse(
        id=mat.id,
        name=mat.name,
        has_pit_variants=mat.has_pit_variants,
        options=options,
    )
