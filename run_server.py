"""Punto de entrada de la API. Host/puerto desde ENBICI_HOST / ENBICI_PORT (ver .env.example).

Un único worker a propósito: el grafo, la caché de ómnibus, el rate limit y SQLite viven en el proceso.
"""

import os
from pathlib import Path

import uvicorn

from src.config import HOST, PORT

if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent)  # rutas relativas (data/, output/) siempre desde la raíz del repo
    uvicorn.run(
        "src.api.app:app",
        host=HOST,
        port=PORT,
        workers=1,
        proxy_headers=True,  # IP real del cliente detrás de Caddy (solo confía en 127.0.0.1)
        reload=False,
        log_level="info",
    )
