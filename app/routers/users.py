import os
import uuid
from typing import List, Optional

from app.es.index import index_user
from app.keycloak_api import keycloak_admin
from sqlalchemy.orm import selectinload
from app.auth import get_current_user
from app.db import get_db
from app.metrics import REQUEST_COUNT
from app.minio import MINIO_BUCKET, get_minio_client
from app.models import Profile, Specialization
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.es.instance import get_es_instance
from io import BytesIO
from minio.error import S3Error


router = APIRouter()


class SocialLinkOut(BaseModel):
    id: int
    platform: str
    url: str

    class Config:
        orm_mode = True


class ProfileData(BaseModel):
    # keycloak data
    id: str | None = None
    name: str | None = None
    email: str | None = None
    firstName: str | None = None
    lastName: str | None = None
    username: str | None = None

    # profile data
    picture: str | None = None
    location: str | None = None
    description: str | None = None
    about_me: str | None = None
    specializations: list[str] = []
    social_links: list[SocialLinkOut] = []


class SearchHit(BaseModel):
    id: str
    name: str
    description: str
    type: str
    location: str

class ProfilePatch(BaseModel):
    email: Optional[str] = None
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    about_me: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    username: Optional[str] = None
    specializations: Optional[List[str]] = None


@router.get("/api/users/users/current", response_model=ProfileData)
async def get_current_user_data(
    user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    user, profile = user
    result = await db.execute(
        select(Profile)
        .options(
            selectinload(Profile.specializations), selectinload(Profile.social_links)
        )
        .where(Profile.id == user["sub"])
    )
    user_profile = result.scalar()

    response = keycloak_admin.get_user(
        user["sub"],
    )

    user = response

    if not user_profile:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": user["id"],
        "email": user["email"],
        "firstName": user["firstName"],
        "lastName": user["lastName"],
        "username": user["username"],
        "picture": user_profile.picture,
        "description": user_profile.description,
        "about_me": user_profile.about_me,
        "location": user_profile.location,
        "specializations": [spec.id for spec in user_profile.specializations],
        "social_links": [
            {"id": link.id, "platform": link.platform, "url": link.url}
            for link in user_profile.social_links
        ],
    }


@router.get("/api/users/users/{user_id}", response_model=ProfileData)
async def get_user(
    user_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Profile)
        .options(
            selectinload(Profile.specializations), selectinload(Profile.social_links)
        )
        .where(Profile.id == user_id)
    )
    profile = result.scalar()

    user_data = keycloak_admin.get_user(user_id)

    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": profile.id,
        "username": user_data["username"],
        "email": user_data["email"],
        "firstName": user_data["firstName"],
        "lastName": user_data["lastName"],
        "picture": profile.picture,
        "description": profile.description,
        "about_me": profile.about_me,
        "location": profile.location,
        "specializations": [spec.id for spec in profile.specializations],
        "social_links": [
            {"id": link.id, "platform": link.platform, "url": link.url}
            for link in profile.social_links
        ],
    }


@router.put("/api/users/users/{user_id}", response_model=ProfileData)
async def update_user(
    user_id: str,
    user_data: ProfileData,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Profile)
        .options(
            selectinload(Profile.specializations), selectinload(Profile.social_links)
        )
        .where(Profile.id == user_id)
    )
    profile = result.scalar()

    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    result = await db.execute(
        select(Specialization).where(Specialization.id.in_(user_data.specializations))
    )
    specializations = result.scalars().all()
    profile.about_me = user_data.about_me
    profile.description = user_data.description
    profile.location = user_data.location
    profile.specializations.clear()
    profile.specializations.extend(specializations)
    await db.commit()

    response = keycloak_admin.update_user(
        user_id,
        {
            "email": user_data.email,
            "firstName": user_data.firstName,
            "lastName": user_data.lastName,
        },
    )

    result = await db.execute(
        select(Profile)
        .options(
            selectinload(Profile.specializations), selectinload(Profile.social_links)
        )
        .where(Profile.id == user_id)
    )
    profile: Profile = result.scalar()
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    # Opcjonalnie indeksujemy użytkownika w Elasticsearch
    await index_user(
        get_es_instance(),
        user_id,
        f"{user_data.firstName} {user_data.lastName}",
        user_data.about_me or "",
    )

    return {
        "id": profile.id,
        "username": user_data.username,
        "email": user_data.email,
        "firstName": user_data.firstName,
        "lastName": user_data.lastName,
        "picture": profile.picture,
        "description": profile.description,
        "about_me": profile.about_me,
        "location": profile.location,
        "specializations": [spec.id for spec in profile.specializations],
        "social_links": [
            {"id": link.id, "platform": link.platform, "url": link.url}
            for link in profile.social_links
        ],
    }

@router.patch("/api/users/users/{user_id}", response_model=ProfileData)
async def patch_user(
    user_id: str,
    user_patch: ProfilePatch,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Pobierz profil z bazy danych wraz z relacjami
    result = await db.execute(
        select(Profile)
        .options(selectinload(Profile.specializations), selectinload(Profile.social_links))
        .where(Profile.id == user_id)
    )
    profile = result.scalar()

    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    # Aktualizacja pól, jeśli zostały przesłane
    if user_patch.about_me is not None:
        profile.about_me = user_patch.about_me
    if user_patch.description is not None:
        profile.description = user_patch.description
    if user_patch.location is not None:
        profile.location = user_patch.location
    if user_patch.username is not None:
        profile.username = user_patch.username  # Jeśli masz takie pole w modelu, w przeciwnym razie pomiń

    # Aktualizacja specjalizacji: jeśli przesłano listę, pobieramy odpowiadające obiekty
    if user_patch.specializations is not None:
        spec_result = await db.execute(
            select(Specialization).where(Specialization.id.in_(user_patch.specializations))
        )
        specializations = spec_result.scalars().all()
        profile.specializations.clear()
        profile.specializations.extend(specializations)

    await db.commit()

    # Aktualizacja danych w Keycloak (tylko jeśli przesłano odpowiednie pola)
    update_data = {}
    if user_patch.email is not None:
        update_data["email"] = user_patch.email
    if user_patch.firstName is not None:
        update_data["firstName"] = user_patch.firstName
    if user_patch.lastName is not None:
        update_data["lastName"] = user_patch.lastName

    if update_data:
        response = keycloak_admin.update_user(user_id, update_data)
        # Możesz opcjonalnie sprawdzić status odpowiedzi

    # Ponowne pobranie profilu z bazy, aby mieć aktualne dane wraz z relacjami
    result = await db.execute(
        select(Profile)
        .options(selectinload(Profile.specializations), selectinload(Profile.social_links))
        .where(Profile.id == user_id)
    )
    profile = result.scalar()
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    # Opcjonalne indeksowanie w Elasticsearch
    await index_user(
        get_es_instance(),
        user_id,
        f"{user_patch.firstName or profile.firstName} {user_patch.lastName or profile.lastName}",
        user_patch.about_me or profile.about_me or "",
    )

    return {
        "id": profile.id,
        "username": user_patch.username or getattr(profile, "username", None),
        "email": user_patch.email or getattr(profile, "email", None),
        "firstName": user_patch.firstName or getattr(profile, "firstName", None),
        "lastName": user_patch.lastName or getattr(profile, "lastName", None),
        "picture": profile.picture,
        "description": profile.description,
        "about_me": profile.about_me,
        "location": profile.location,
        "specializations": [spec.id for spec in profile.specializations],
        "social_links": [
            {"id": link.id, "platform": link.platform, "url": link.url}
            for link in profile.social_links
        ],
    }

@router.get("/api/users/search", response_model=list[SearchHit])
async def search_users(query: str = "", _=Depends(get_current_user)):
    REQUEST_COUNT.inc()
    es = get_es_instance()
    response = await es.search(
        index="users",
        body={
            "query": {
                "query_string": {
                    "fields": ["username", "about_me"],
                    "query": f"*{query}*",
                },
            }
        },
    )
    hits = [hit for hit in response["hits"]["hits"]]

    # if not ids:
    #     return []

    # result = await db.execute(
    #     select(Profile)
    #     .options(selectinload(Profile.specializations))
    #     .where(Profile.id.in_(ids))
    # )

    # profiles = result.scalars().all()

    return [
        {
            "id": hit["_id"],
            "name": hit["_source"]["username"],
            "description": hit["_source"]["about_me"],
            "type": "user",
            "location": "",
        }
        for hit in hits
    ]


@router.post("/api/users/users/current/picture", status_code=status.HTTP_201_CREATED)
async def upload_media(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    minio_client=Depends(get_minio_client),
):
    allowed_extensions = {".jpg", ".jpeg", ".png"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Niedozwolony format pliku: {ext}",
        )

    unique_filename = f"{uuid.uuid4()}{ext}"
    user, profile = user

    try:
        file_data = await file.read()
        file_size = len(file_data)
        file_stream = BytesIO(file_data)
        minio_client.put_object(
            MINIO_BUCKET,
            unique_filename,
            file_stream,
            file_size,
            content_type=file.content_type,
        )
    except S3Error as e:
        print(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Błąd podczas uploadu do MinIO",
        )

    media_url = f"http://localhost:9000/{MINIO_BUCKET}/{unique_filename}"

    user = await db.execute(select(Profile).where(Profile.id == user["sub"]))
    user = user.scalar()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.picture = media_url
    await db.commit()

    return {"url": media_url}

@router.get("/admin/api/users/users/{user_id}", response_model=ProfileData)
async def admin_get_user(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Profile).where(Profile.id == user_id))
    profile = result.scalar()

    user_data = keycloak_admin.get_user(user_id)

    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": profile.id,
        "username": user_data["username"],
        "email": user_data["email"],
        "firstName": user_data["firstName"],
        "lastName": user_data["lastName"],
        "picture": profile.picture,
        "location": profile.location,
    }
 
