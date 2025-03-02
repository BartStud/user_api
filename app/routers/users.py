import os
import uuid
from typing import Optional

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


class ProfileData(BaseModel):
    # keycloak data
    id: str | None = None
    name: str | None = None
    email: str | None = None
    firstName: str | None = None
    lastName: str | None = None
    username: str | None = None

    # profile data
    description: str | None = None
    about_me: str | None = None
    specializations: list[str] = []


class SearchHit(BaseModel):
    id: str
    name: str
    description: str
    type: str
    location: str


@router.get("/api/users/users/current", response_model=ProfileData)
async def get_current_user_data(
    user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    user, profile = user
    user_profile = await db.execute(
        select(Profile)
        .options(selectinload(Profile.specializations))
        .where(Profile.id == user["sub"])
    )
    user_profile = user_profile.scalar()

    if not user_profile:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user["sub"],
        "email": user["email"],
        "firstName": user["given_name"],
        "lastName": user["family_name"],
        "username": user["preferred_username"],
        "picture": user_profile.picture,
        "description": user_profile.description,
        "about_me": user_profile.about_me,
        "location": user_profile.location,
        "specializations": [spec.id for spec in user_profile.specializations],
    }


@router.get("/api/users/users/{user_id}", response_model=ProfileData)
async def get_user(
    user_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Profile)
        .options(selectinload(Profile.specializations))
        .where(Profile.id == user_id)
    )
    profile = result.scalar()

    user_data = keycloak_admin.get_user(user_id)

    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    print(user_data)
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
    }


@router.put("/api/users/users/{user_id}", response_model=ProfileData)
async def update_user(
    user_id: str,
    user_data: ProfileData,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await db.execute(
        select(Profile)
        .options(selectinload(Profile.specializations))
        .where(Profile.id == user_id)
    )
    profile = profile.scalar()

    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    result = await db.execute(
        select(Specialization).where(Specialization.id.in_(user_data.specializations))
    )
    specializations = result.scalars().all()
    # with db.no_autoflush:
    profile.about_me = user_data.about_me
    profile.description = user_data.description
    # profile.specializations.append(specializations)
    # attributes.set_committed_value(profile, "specializations", specializations)
    profile.specializations.clear()
    profile.specializations.extend(specializations)
    await db.commit()
    # await db.refresh(profile)

    response = keycloak_admin.update_user(
        user_id,
        {
            "email": user_data.email,
            "firstName": user_data.firstName,
            "lastName": user_data.lastName,
        },
    )
    # if not response["ok"]:
    #     raise HTTPException(status_code=500, detail="Błąd synchronizacji z Keycloak")

    result = await db.execute(
        select(Profile)
        .options(selectinload(Profile.specializations))
        .where(Profile.id == user_id)
    )

    await index_user(
        get_es_instance(),
        user_id,
        f"{user_data.firstName} {user_data.lastName}",
        user_data.about_me or "",
    )

    profile: Profile = result.scalar()
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    specializations_ids = [spec.id for spec in profile.specializations]

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
        "specializations": specializations_ids,
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
