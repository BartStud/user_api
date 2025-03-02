from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.auth import get_current_user
from app.db import get_db
from app.models import Profile, SocialLink


class SocialLinkBase(BaseModel):
    platform: str
    url: str


class SocialLinkCreate(SocialLinkBase):
    pass


class SocialLinkUpdate(SocialLinkBase):
    pass


class SocialLinkOut(SocialLinkBase):
    id: int

    class Config:
        orm_mode = True


router = APIRouter()


@router.get(
    "/api/users/users/{profile_id}/social-links", response_model=list[SocialLinkOut]
)
async def get_social_links(
    user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return user[1].social_links


@router.post(
    "/api/users/users/current/social-links",
    response_model=SocialLinkOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_social_link(
    social_link: SocialLinkCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    new_link = SocialLink(
        profile_id=user[0]["sub"], platform=social_link.platform, url=social_link.url
    )
    db.add(new_link)
    await db.commit()
    await db.refresh(new_link)
    return new_link


@router.put(
    "/api/users/users/current/social-links/{link_id}", response_model=SocialLinkOut
)
async def update_social_link(
    link_id: int,
    social_link: SocialLinkUpdate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SocialLink).where(
            SocialLink.id == link_id, SocialLink.profile_id == user[0]["sub"]
        )
    )
    link = result.scalars().first()
    if not link:
        raise HTTPException(status_code=404, detail="Social link not found")

    link.platform = social_link.platform
    link.url = social_link.url

    await db.commit()
    await db.refresh(link)
    return link


@router.delete(
    "/api/users/users/current/social-links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_social_link(
    link_id: int, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(SocialLink).where(
            SocialLink.id == link_id, SocialLink.profile_id == user[0]["sub"]
        )
    )
    link = result.scalars().first()
    if not link:
        raise HTTPException(status_code=404, detail="Social link not found")

    await db.delete(link)
    await db.commit()
    return {"detail": "Social link deleted"}
