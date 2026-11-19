"""Smoke test HTTP de la API contra un servidor corriendo (local o AWS).

    uv run python scripts/smoke_test_api.py                       # http://127.0.0.1:8000
    uv run python scripts/smoke_test_api.py https://api.ejemplo.uy --production

Crea usuarios `smoke_<random>` y viajes en la BD del servidor. Para no ensuciar la BD de dev,
levantar el server con `ENBICI_STATE_DIR=/tmp/enbici_smoke`. El último check agota el rate
limit de /login para tu IP durante ~1 minuto.
"""

from __future__ import annotations

import argparse
import secrets
import sys
import threading
import time

import requests

ORIGIN = {"origin_lat": -34.9060, "origin_lon": -56.1996}  # Plaza Independencia
DEST = {"dest_lat": -34.8947, "dest_lon": -56.1520}  # Tres Cruces
TIMEOUT = 120

failures: list[str] = []


def check(name: str, ok: bool, info: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{f'  ({info})' if info else ''}")
    if not ok:
        failures.append(name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base_url", nargs="?", default="http://127.0.0.1:8000")
    ap.add_argument("--production", action="store_true", help="espera /docs deshabilitado")
    args = ap.parse_args()
    base = args.base_url.rstrip("/")
    s = requests.Session()

    print(f"== {base}")
    print("-- salud y docs")
    r = s.get(f"{base}/health", timeout=10)
    check("GET /health", r.status_code == 200 and r.json().get("graph_loaded") is True, r.text)
    r = s.get(f"{base}/docs", timeout=10)
    want = 404 if args.production else 200
    check(f"GET /docs -> {want}", r.status_code == want, str(r.status_code))

    print("-- ruteo")
    t0 = time.perf_counter()
    r = s.get(f"{base}/route", params={**ORIGIN, **DEST, "bus_weight": 0}, timeout=TIMEOUT)
    body = r.json()
    check(
        "GET /route bus_weight=0",
        r.status_code == 200 and body["live_buses_near_route"] is None and len(body["route_coordinates"]) > 1,
        f"{r.status_code}, {body.get('distance_km', 0):.2f} km, {time.perf_counter() - t0:.1f}s",
    )
    check("map_url null sin include_map", body.get("map_url") is None, str(body.get("map_url")))

    t0 = time.perf_counter()
    r = s.get(f"{base}/route", params={**ORIGIN, **DEST, "bus_weight": 3}, timeout=TIMEOUT)
    body = r.json()
    buses = body.get("live_buses_near_route")
    check(
        "GET /route bus_weight=3",
        r.status_code == 200 and (buses is None or isinstance(buses, int)),
        f"live_buses_near_route={buses}{' (sin datos IMM: ¿faltan credenciales?)' if buses is None else ''}, "
        f"{time.perf_counter() - t0:.1f}s",
    )

    r = s.get(f"{base}/route", params={**ORIGIN, **DEST, "bus_weight": 11}, timeout=TIMEOUT)
    check("GET /route bus_weight=11 -> 422", r.status_code == 422, str(r.status_code))
    r = s.get(f"{base}/route", params=DEST, timeout=TIMEOUT)
    check("GET /route sin origen -> 400", r.status_code == 400, str(r.status_code))

    r = s.get(f"{base}/route", params={**ORIGIN, **DEST, "include_map": "true"}, timeout=TIMEOUT)
    map_url = r.json().get("map_url") if r.ok else None
    ok_map = bool(map_url) and s.get(f"{base}{map_url}", timeout=10).status_code == 200
    check("GET /route include_map=true + GET map_url", ok_map, str(map_url))

    r = s.get(
        f"{base}/route",
        params={"origin_place": "Plaza Independencia", "dest_place": "Tres Cruces", "bus_weight": 1},
        timeout=TIMEOUT,
    )
    check("GET /route por nombre (Nominatim)", r.status_code == 200, f"{r.status_code} {r.text[:120] if not r.ok else ''}")

    # Mientras se calcula una ruta, el server tiene que seguir respondiendo otros requests.
    slow = threading.Thread(
        target=lambda: requests.get(f"{base}/route", params={**ORIGIN, **DEST, "wind_weight": 5}, timeout=TIMEOUT)
    )
    slow.start()
    time.sleep(0.3)
    t0 = time.perf_counter()
    r = requests.get(f"{base}/health", timeout=30)
    health_s = time.perf_counter() - t0
    slow.join()
    check("/health responde durante un /route en curso", r.ok and health_s < 1.0, f"{health_s:.2f}s")

    print("-- usuarios y viajes")
    user, pwd = f"smoke_{secrets.token_hex(4)}", secrets.token_urlsafe(12)
    r = s.post(f"{base}/register", json={"username": user, "password": pwd}, timeout=10)
    check("POST /register -> 201", r.status_code == 201, str(r.status_code))
    r = s.post(f"{base}/register", json={"username": user, "password": pwd}, timeout=10)
    check("POST /register duplicado -> 409", r.status_code == 409, str(r.status_code))
    r = s.post(f"{base}/login", json={"username": user, "password": pwd}, timeout=10)
    check("POST /login -> 200", r.status_code == 200, str(r.status_code))
    auth = {"Authorization": f"Bearer {r.json().get('access_token', '')}"}
    r = s.post(f"{base}/login", json={"username": user, "password": "wrong-password"}, timeout=10)
    check("POST /login password incorrecta -> 401", r.status_code == 401, str(r.status_code))

    journey = {
        "origin_place": "Plaza Independencia", "dest_place": "Tres Cruces",
        "distance_km": 5.1, "elevation_gain_m": 40.0,
        "elevation_weight": 5, "wind_weight": 0, "bus_weight": 2.5,
        "allow_parks": True, "max_against_traffic_blocks": 0,
    }
    r = s.post(f"{base}/users/me/routes", json=journey, timeout=10)
    check("POST /users/me/routes sin token -> 401", r.status_code == 401, str(r.status_code))
    r = s.post(f"{base}/users/me/routes", json=journey, headers=auth, timeout=10)
    saved = r.json()
    check("POST /users/me/routes con bus_weight=2.5", r.status_code == 201 and saved.get("bus_weight") == 2.5, r.text[:120])
    jid = saved.get("id")
    r = s.get(f"{base}/users/me/routes", headers=auth, timeout=10)
    check("GET /users/me/routes incluye el viaje", r.ok and any(j["id"] == jid for j in r.json()), str(r.status_code))
    r = s.post(f"{base}/users/me/routes/{jid}/start", headers=auth, timeout=10)
    check("POST .../start", r.ok and r.json()["is_started"] is True, str(r.status_code))
    r = s.post(f"{base}/users/me/routes/{jid}/telemetry", json={"lat": -34.9, "lon": -56.19, "speed_ms": 4.2}, headers=auth, timeout=10)
    check("POST .../telemetry -> 201", r.status_code == 201, str(r.status_code))
    r = s.post(f"{base}/users/me/routes/{jid}/finish", headers=auth, timeout=10)
    check("POST .../finish", r.ok and r.json()["is_completed"] is True, str(r.status_code))

    other = s.post(f"{base}/register", json={"username": f"smoke_{secrets.token_hex(4)}", "password": pwd}, timeout=10)
    if other.status_code == 201:
        r = s.post(f"{base}/users/me/routes/{jid}/start", headers={"Authorization": f"Bearer {other.json()['access_token']}"}, timeout=10)
        check("viaje de otro usuario -> 404", r.status_code == 404, str(r.status_code))
    else:
        check("viaje de otro usuario -> 404", False, f"no se pudo registrar 2º usuario: {other.status_code}")

    print("-- rate limit (/login)")
    codes = [s.post(f"{base}/login", json={"username": user, "password": "wrong-password"}, timeout=10).status_code for _ in range(15)]
    check("POST /login repetido -> 429", 429 in codes, f"{codes}")

    print(f"\n{'OK' if not failures else 'FALLARON ' + str(len(failures))}: {', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
