from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Base_, Characteristic
from ..schemas import BaseOut, CharacteristicOut

router = APIRouter(tags=["meta"])


@router.get("/characteristics", response_model=List[CharacteristicOut])
def list_characteristics(db: Session = Depends(get_db)):
    rows = db.scalars(select(Characteristic).order_by(Characteristic.name)).all()
    return [CharacteristicOut(id=r.id, name=r.name) for r in rows]


@router.get("/bases", response_model=List[BaseOut])
def list_bases(db: Session = Depends(get_db)):
    rows = db.scalars(select(Base_).order_by(Base_.id)).all()
    return [BaseOut(id=r.id, name=r.name) for r in rows]
