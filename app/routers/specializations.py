from typing import List
import uuid
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from app.db import get_db
from app.models import Specialization

router = APIRouter()


class SpecializationCreate(BaseModel):
    title: str
    short_description: str | None = None


class SpecializationUpdate(BaseModel):
    title: str | None = None
    short_description: str | None = None


class SpecializationResponse(BaseModel):
    id: str
    title: str
    short_description: str | None = None

    class Config:
        orm_mode = True


@router.get("/api/users/specializations", response_model=List[SpecializationResponse])
async def get_specializations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Specialization))
    specializations = result.scalars().all()
    return specializations


@router.post("/api/users/specializations", response_model=SpecializationResponse)
async def create_specialization(
    specialization_in: SpecializationCreate, db: AsyncSession = Depends(get_db)
):
    new_spec = Specialization(
        id=str(uuid.uuid4()),
        title=specialization_in.title,
        short_description=specialization_in.short_description,
    )
    db.add(new_spec)
    await db.commit()
    await db.refresh(new_spec)
    return new_spec


@router.put(
    "/api/users/specializations/{spec_id}", response_model=SpecializationResponse
)
async def update_specialization(
    spec_id: str,
    specialization_in: SpecializationUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Specialization).where(Specialization.id == spec_id)
    )
    spec = result.scalar_one_or_none()
    if spec is None:
        raise HTTPException(status_code=404, detail="Specjalizacja nie znaleziona")
    if specialization_in.title is not None:
        spec.title = specialization_in.title
    if specialization_in.short_description is not None:
        spec.short_description = specialization_in.short_description
    await db.commit()
    await db.refresh(spec)
    return spec


@router.delete("/api/users/specializations/{spec_id}")
async def delete_specialization(spec_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Specialization).where(Specialization.id == spec_id)
    )
    spec = result.scalar_one_or_none()
    if spec is None:
        raise HTTPException(status_code=404, detail="Specjalizacja nie znaleziona")
    await db.delete(spec)
    await db.commit()
    return {"detail": "Specjalizacja usunięta pomyślnie"}
