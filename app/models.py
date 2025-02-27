from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, ForeignKey, String, Table
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


class Specialization(Base):
    __tablename__ = "specializations"

    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    short_description = Column(String)

    profiles = relationship(
        "Profile", secondary=profile_specialization, back_populates="specializations"
    )
