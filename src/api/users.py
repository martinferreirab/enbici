from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.auth.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from src.db.database import get_db
from src.db.models import JourneyLog, User

router = APIRouter(tags=["users"])


class Credentials(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=72)  # bcrypt limit


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class JourneyCreate(BaseModel):
    origin_place: str = Field(..., min_length=1, max_length=255)
    dest_place: str = Field(..., min_length=1, max_length=255)
    distance_km: float = Field(..., ge=0)
    elevation_gain_m: float = Field(..., ge=0)
    elevation_weight: float = Field(..., ge=0, le=10)
    wind_weight: float = Field(..., ge=0, le=10)
    allow_parks: bool
    max_against_traffic_blocks: int = Field(..., ge=0, le=3)


class JourneyOut(JourneyCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: Credentials, db: Session = Depends(get_db)) -> TokenResponse:
    username = body.username.strip().lower()
    user = User(username=username, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already taken")
    return TokenResponse(access_token=create_access_token(user.id), username=username)


@router.post("/login", response_model=TokenResponse)
def login(body: Credentials, db: Session = Depends(get_db)) -> TokenResponse:
    username = body.username.strip().lower()
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return TokenResponse(access_token=create_access_token(user.id), username=username)


@router.post("/users/me/routes", response_model=JourneyOut, status_code=201)
def save_route(
    body: JourneyCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JourneyLog:
    journey = JourneyLog(user_id=user.id, **body.model_dump())
    db.add(journey)
    db.commit()
    return journey


@router.get("/users/me/routes", response_model=list[JourneyOut])
def list_routes(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[JourneyLog]:
    stmt = select(JourneyLog).where(JourneyLog.user_id == user.id).order_by(JourneyLog.timestamp.desc())
    return list(db.scalars(stmt))
