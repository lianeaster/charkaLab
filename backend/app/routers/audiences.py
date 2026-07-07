from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..audiences import AUDIENCES, get_audience
from ..database import get_db
from ..schemas import AudienceOut, SuggestProfileRequest, SuggestProfileResponse
from ..services import engine

router = APIRouter(prefix="/audiences", tags=["audiences"])


@router.get("", response_model=List[AudienceOut])
def list_audiences():
    return [
        AudienceOut(
            id=a["id"],
            name=a["name"],
            group=a["group"],
            alcohol_free=a["alcohol_free"],
            suggest=a["suggest"],
            forbidden_tags=a["forbidden_tags"],
            default_profile=a["default_profile"],
            disclaimer=a["disclaimer"],
        )
        for a in AUDIENCES
    ]


@router.post("/suggest-profile", response_model=SuggestProfileResponse)
def suggest_profile(req: SuggestProfileRequest, db: Session = Depends(get_db)):
    audience = get_audience(req.audience_id)
    if audience is None:
        raise HTTPException(status_code=404, detail="Невідома категорія аудиторії")
    if not audience["suggest"]:
        return SuggestProfileResponse()
    return engine.suggest_profile(
        db, audience, req.main_material_id, req.part, req.form, req.pit,
        season=req.season,
    )
