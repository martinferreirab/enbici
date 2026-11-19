"""Configuración central del backend: todo sale de variables de entorno (o de `<repo>/.env`).

Ver `.env.example` para la lista completa. Las variables ya exportadas en la shell (o
inyectadas por systemd/AWS) tienen prioridad sobre `.env`.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def _env(name: str, default: str) -> str:
    """Como os.getenv, pero una variable vacía (`FOO=` en .env) cuenta como no definida."""
    return os.getenv(name) or default


ENV = _env("ENBICI_ENV", "development").strip().lower()
IS_PRODUCTION = ENV == "production"

# Archivos que el servidor escribe en runtime (SQLite, log de consultas, secreto JWT de dev).
# Los datos del grafo siguen en <repo>/data, que es parte del repo.
STATE_DIR = Path(_env("ENBICI_STATE_DIR", str(ROOT / "data"))).resolve()
DB_PATH = STATE_DIR / "enbici.db"
QUERY_LOG_PATH = STATE_DIR / "consultas_rutas.csv"

HOST = _env("ENBICI_HOST", "0.0.0.0")
PORT = int(_env("ENBICI_PORT", "8000"))
CORS_ORIGINS = [o.strip() for o in _env("ENBICI_CORS_ORIGINS", "*").split(",") if o.strip()]

# Intentos de /login y /register por IP dentro de la ventana (en segundos).
AUTH_RATE_LIMIT = int(_env("ENBICI_AUTH_RATE_LIMIT", "10"))
AUTH_RATE_WINDOW_S = int(_env("ENBICI_AUTH_RATE_WINDOW_S", "60"))


def jwt_secret() -> str:
    """`ENBICI_JWT_SECRET`; obligatorio en producción. En desarrollo se autogenera en STATE_DIR."""
    if env := os.getenv("ENBICI_JWT_SECRET"):
        return env
    if IS_PRODUCTION:
        raise RuntimeError("ENBICI_JWT_SECRET es obligatorio con ENBICI_ENV=production")
    path = STATE_DIR / ".jwt_secret"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(secrets.token_hex(32))
        path.chmod(0o600)
    return path.read_text().strip()


def imm_credentials() -> tuple[str, str] | None:
    """Credenciales OAuth de la API de la IM (ómnibus). Opcionales: sin ellas se rutea sin buses.

    Se leen en cada llamada (no al importar) para que los tests puedan parchear el entorno.
    """
    client_id = os.getenv("MONTEVIDEO_CLIENT_ID")
    client_secret = os.getenv("MONTEVIDEO_CLIENT_SECRET")
    return (client_id, client_secret) if client_id and client_secret else None
