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
    query = q.strip()
    if not query:
        rows = db.scalars(
            select(RawMaterial).order_by(RawMaterial.name).limit(limit)
        ).all()
    else:
        # 1) збіг по початку назви; 2) входження в назву або синоніми
        rows = db.scalars(
            select(RawMaterial)
            .where(RawMaterial.name.ilike(f"{query}%"))
            .order_by(RawMaterial.name)
            .limit(limit)
        ).all()
        if not rows:
            rows = db.scalars(
                select(RawMaterial)
                .where(
                    RawMaterial.name.ilike(f"%{query}%")
                    | RawMaterial.aliases.ilike(f"%{query}%")
                )
                .order_by(RawMaterial.name)
                .limit(limit)
            ).all()
    return [
        MaterialSuggestion(
            id=r.id,
            name=r.name,
            has_pit_variants=r.has_pit_variants,
            aliases=[a for a in (r.aliases or "").split(",") if a],
        )
        for r in rows
    ]


@router.get("/{material_id}/forms", response_model=MaterialFormsResponse)
def material_forms(material_id: int, db: Session = Depends(get_db)):
    mat = db.get(RawMaterial, material_id)
    if mat is None:
        raise HTTPException(status_code=404, detail="Сировину не знайдено")
    rows = db.execute(
        select(
            distinct(MaterialCompound.part),
            MaterialCompound.form,
            MaterialCompound.pit,
        ).where(MaterialCompound.raw_material_id == material_id)
    ).all()
    seen = set()
    options: List[FormOption] = []
    for part, form, pit in rows:
        key = (part, form, pit)
        if key in seen:
            continue
        seen.add(key)
        options.append(FormOption(part=part, form=form, pit=pit))
    options.sort(key=lambda o: (o.part, o.form, o.pit))
    return MaterialFormsResponse(
        id=mat.id,
        name=mat.name,
        has_pit_variants=mat.has_pit_variants,
        options=options,
    )
