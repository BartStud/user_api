import enum
import uuid
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import ARRAY, Column, Date, DateTime, Enum, Float, ForeignKey, Integer, Numeric, String, Table, Text, func
from sqlalchemy.orm import relationship


Base = declarative_base()

profile_specialization = Table(
    "profile_specialization",
    Base.metadata,
    Column("profile_id", String, ForeignKey("profiles.id"), primary_key=True),
    Column(
        "specialization_id", String, ForeignKey("specializations.id"), primary_key=True
    ),
)


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(String, primary_key=True, index=True)
    description = Column(String)
    about_me = Column(String)
    location = Column(String)
    picture = Column(String)

    specializations = relationship(
        "Specialization", secondary=profile_specialization, back_populates="profiles"
    )

    services = relationship(
        "Service", back_populates="profile", cascade="all, delete-orphan"
    )

    social_links = relationship(
        "SocialLink", back_populates="profile", cascade="all, delete-orphan"
    )

    pets = relationship("Pet", back_populates="owner", cascade="all, delete-orphan")



class SocialLink(Base):
    __tablename__ = "social_links"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(String, ForeignKey("profiles.id"), nullable=False)
    platform = Column(String, nullable=False)
    url = Column(String, nullable=False)

    profile = relationship("Profile", back_populates="social_links")


class Specialization(Base):
    __tablename__ = "specializations"

    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    short_description = Column(String)

    profiles = relationship(
        "Profile", secondary=profile_specialization, back_populates="specializations"
    )


class MediaType(enum.Enum):
    image = "image"
    video = "video"


class Service(Base):
    __tablename__ = "services"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(String)
    price = Column(Numeric, nullable=False)
    times = Column(ARRAY(Integer))

    profile_id = Column(String, ForeignKey("profiles.id"), nullable=False)
    profile = relationship("Profile", back_populates="services")

    media = relationship(
        "ServiceMedia", back_populates="service", cascade="all, delete-orphan"
    )


class ServiceMedia(Base):
    __tablename__ = "service_media"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    service_id = Column(String, ForeignKey("services.id"), nullable=False)
    media_type = Column(Enum(MediaType), nullable=False)
    media_url = Column(String, nullable=False)

    service = relationship("Service", back_populates="media")


class Pet(Base):
    __tablename__ = "pets"

    id = Column(String, primary_key=True, index=True, default=func.uuid_generate_v4())
    name = Column(String, nullable=False)
    species = Column(String, nullable=False)
    breed = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    weight = Column(Float, nullable=True)
    owner_id = Column(String, ForeignKey("profiles.id"), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    owner = relationship("Profile", back_populates="pets")
 