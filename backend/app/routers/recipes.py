from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import RawMaterial
from ..schemas import GenerateRequest, GenerateResponse
from ..services import engine

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.post("/generate", response_model=GenerateResponse)
def generate_recipe(req: GenerateRequest, db: Session = Depends(get_db)):
    if db.get(RawMaterial, req.main_material.material_id) is None:
        raise HTTPException(status_code=404, detail="Основну сировину не знайдено")
    if len(req.additional_materials) > 10:
        raise HTTPException(status_code=422, detail="Максимум 10 додаткових сировин")
    return engine.generate(db, req)
