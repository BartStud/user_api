from io import BytesIO
import os
from typing import List, Optional
from pydantic import BaseModel

import uuid
from fastapi import APIRouter, File, HTTPException, Depends, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth import get_current_user
from app.minio import MINIO_BUCKET, get_minio_client
from models import MediaType, Service, ServiceMedia
from app.db import get_db
from minio.error import S3Error


class ServiceBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    times: List[int] = []


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    times: Optional[List[int]] = None


class ServiceResponse(ServiceBase):
    id: str
    profile_id: str

    class Config:
        orm_mode = True


router = APIRouter(prefix="/api/services", tags=["services"])


@router.post("/current", response_model=ServiceResponse)
async def create_service(
    service_in: ServiceCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user, _ = user
    new_service = Service(
        id=str(uuid.uuid4()),
        name=service_in.name,
        description=service_in.description,
        price=service_in.price,
        times=service_in.times,
        profile_id=user["sub"],
    )
    db.add(new_service)
    await db.commit()
    await db.refresh(new_service)
    return new_service


@router.get("/", response_model=List[ServiceResponse])
async def get_all_services(
    user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Service))
    services = result.scalars().all()
    return services


@router.get("/{service_id}", response_model=ServiceResponse)
async def get_service(
    service_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Service).where(Service.id == service_id))
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


@router.put("/{service_id}", response_model=ServiceResponse)
async def update_service(
    service_id: str,
    service_in: ServiceUpdate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Service).where(
            Service.id == service_id, Service.profile_id == user[0]["sub"]
        )
    )
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    if service_in.name is not None:
        service.name = service_in.name
    if service_in.description is not None:
        service.description = service_in.description
    if service_in.price is not None:
        service.price = service_in.price
    if service_in.times is not None:
        service.times = service_in.times

    await db.commit()
    await db.refresh(service)
    return service


@router.delete("/{service_id}")
async def delete_service(
    service_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Service).where(
            Service.id == service_id, Service.profile_id == user[0]["sub"]
        )
    )
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    await db.delete(service)
    await db.commit()
    return {"detail": "Service deleted successfully"}


ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov"}


@router.post("/api/services/{service_id}/media", status_code=status.HTTP_201_CREATED)
async def upload_service_media(
    service_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    minio_client=Depends(get_minio_client),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Service).where(
            Service.id == service_id, Service.profile_id == current_user[0]["sub"]
        )
    )
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        media_type = MediaType.image
    elif ext in ALLOWED_VIDEO_EXTENSIONS:
        media_type = MediaType.video
    else:
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Błąd podczas uploadu do MinIO",
        ) from e

    media_url = f"http://localhost:9000/{MINIO_BUCKET}/{unique_filename}"

    new_media = ServiceMedia(
        id=str(uuid.uuid4()),
        service_id=service_id,
        media_type=media_type,
        media_url=media_url,
    )
    db.add(new_media)
    await db.commit()
    await db.refresh(new_media)

    return {"url": media_url, "media_type": media_type.value, "id": new_media.id}
