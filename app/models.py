import enum
import uuid
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import ARRAY, Column, Enum, ForeignKey, Integer, Numeric, String, Table
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
