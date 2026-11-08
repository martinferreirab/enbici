from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "enbici.db"

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},  # FastAPI runs sync endpoints in a threadpool
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    from src.db import models  # noqa: F401  (register tables on Base.metadata)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
    _add_missing_journey_columns()


def _add_missing_journey_columns() -> None:
    """create_all no altera tablas existentes: agrega las columnas de estado de viaje a un .db viejo."""
    from sqlalchemy import inspect, text

    existing = {c["name"] for c in inspect(engine).get_columns("journey_logs")}
    with engine.begin() as conn:
        for col in ("is_started", "is_completed"):
            if col not in existing:
                conn.execute(text(f"ALTER TABLE journey_logs ADD COLUMN {col} BOOLEAN NOT NULL DEFAULT 0"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
