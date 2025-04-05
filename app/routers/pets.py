import uuid
from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query, status, Response
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.models import Pet
from app.db import get_db
from app.auth import get_current_user  # Funkcja zależności zwracająca dane aktualnego użytkownika

router = APIRouter(prefix="/api/users")

class PetBase(BaseModel):
    name: str
    species: str
    breed: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    weight: Optional[float] = None
    description: Optional[str] = None

class PetCreate(PetBase):
    pass

class PetUpdate(PetBase):
    # Wszystkie pola opcjonalne, bo chcemy umożliwić częściową aktualizację
    name: Optional[str] = None
    species: Optional[str] = None

class PetOut(PetBase):
    id: str
    owner_id: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True




# Endpoint tworzenia pupila
@router.post("/pets/", response_model=PetOut, status_code=status.HTTP_201_CREATED)
async def create_pet(
    pet: PetCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    new_pet = Pet(
        id=str(uuid.uuid4()),
        name=pet.name,
        species=pet.species,
        breed=pet.breed,
        gender=pet.gender,
        date_of_birth=pet.date_of_birth,
        weight=pet.weight,
        description=pet.description,
        owner_id=current_user[0]["sub"]
    )
    db.add(new_pet)
    await db.commit()
    await db.refresh(new_pet)
    return new_pet

# Endpoint pobierania szczegółów konkretnego pupila (tylko dla właściciela)
@router.get("/pets/{pet_id}", response_model=PetOut)
async def get_pet(
    pet_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Pet).where(Pet.id == pet_id, Pet.owner_id == current_user[0]["sub"])
    )
    pet = result.scalars().first()
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")
    return pet

# Endpoint pobierania listy pupili dla aktualnie zalogowanego właściciela
@router.get("/pets/", response_model=List[PetOut])
async def list_pets(
    user_id=Query(None),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    q = select(Pet)
    if user_id:
        q = q.where(Pet.owner_id == user_id)
    else:
        q = q.where(Pet.owner_id == current_user[0]["sub"])

    result = await db.execute(q)
    pets = result.scalars().all()
    return pets

# Endpoint częściowej aktualizacji (PATCH) danych pupila
@router.patch("/pets/{pet_id}", response_model=PetOut)
async def update_pet(
    pet_id: str,
    pet_update: PetUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Pet).where(Pet.id == pet_id, Pet.owner_id == current_user[0]["sub"])
    )
    pet = result.scalars().first()
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")
    
    # Aktualizujemy tylko przesłane pola
    if pet_update.name is not None:
        pet.name = pet_update.name
    if pet_update.species is not None:
        pet.species = pet_update.species
    if pet_update.breed is not None:
        pet.breed = pet_update.breed
    if pet_update.gender is not None:
        pet.gender = pet_update.gender
    if pet_update.date_of_birth is not None:
        pet.date_of_birth = pet_update.date_of_birth
    if pet_update.weight is not None:
        pet.weight = pet_update.weight
    if pet_update.description is not None:
        pet.description = pet_update.description

    await db.commit()
    await db.refresh(pet)
    return pet

# Endpoint usuwania pupila
@router.delete("/pets/{pet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pet(
    pet_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Pet).where(Pet.id == pet_id, Pet.owner_id == current_user[0]["sub"])
    )
    pet = result.scalars().first()
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")
    
    await db.delete(pet)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)