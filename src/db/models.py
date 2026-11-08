from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    journeys: Mapped[list["JourneyLog"]] = relationship(back_populates="user")


class JourneyLog(Base):
    __tablename__ = "journey_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    origin_place: Mapped[str] = mapped_column(String(255))
    dest_place: Mapped[str] = mapped_column(String(255))
    distance_km: Mapped[float] = mapped_column(Float)
    elevation_gain_m: Mapped[float] = mapped_column(Float)
    # Route preferences used to compute the route
    elevation_weight: Mapped[float] = mapped_column(Float)
    wind_weight: Mapped[float] = mapped_column(Float)
    allow_parks: Mapped[bool] = mapped_column(Boolean)
    max_against_traffic_blocks: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    is_started: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    user: Mapped[User] = relationship(back_populates="journeys")


class JourneyTelemetry(Base):
    __tablename__ = "journey_telemetry"

    id: Mapped[int] = mapped_column(primary_key=True)
    journey_id: Mapped[int] = mapped_column(ForeignKey("journey_logs.id"), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    speed_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
