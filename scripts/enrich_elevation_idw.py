"""
One-time enrichment of data/montevideo.graphml with real topography.

Strategy: fetch real elevations for ~1,500 strategic sample nodes from the
Open-Meteo Elevation API (batched at the API's hard cap of 100 coordinates
per request, ~16 sequential requests), then infer elevations for all
remaining nodes via Inverse Distance Weighting (IDW) spatial interpolation
using a KDTree over the sample points.

Usage:
    uv run python scripts/enrich_elevation_idw.py

Resumable by design: fetched sample elevations are persisted to
data/elevation_samples_cache.json (node_id -> real elevation in meters) as
soon as each batch succeeds. If the API rate-limits mid-run, the script stops
fetching immediately, keeps everything fetched so far, and runs IDW using
those samples. The NEXT run loads the cache, skips already-fetched sample
nodes, and only requests the ones still missing — so repeated runs
incrementally complete the full sample set instead of refetching from zero.
"""

from __future__ import annotations

import json
import logging
import math
import sys
import time
from pathlib import Path

import networkx as nx
import numpy as np
import osmnx as ox
import requests
from scipy.spatial import cKDTree

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRAPH_CACHE_PATH = PROJECT_ROOT / "data" / "montevideo.graphml"
SAMPLES_CACHE_PATH = PROJECT_ROOT / "data" / "elevation_samples_cache.json"

OPEN_METEO_ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
BATCH_SIZE = 100  # Open-Meteo hard cap: max 100 coordinates per request
BATCH_DELAY_SECONDS = 1.0
MAX_GRADE = 0.25
GRID_CELL_METERS = 100.0
IDW_K_NEIGHBORS = 8
IDW_POWER = 2

# Known coastal anchor points (Rambla Sur -> Pocitos -> Buceo -> Cerro coast). Expect ~0-10m.
COASTAL_ANCHORS = [
    (-34.9155, -56.2400),  # Cerro de Montevideo coast (bay)
    (-34.9100, -56.2250),
    (-34.9075, -56.2100),
    (-34.9060, -56.1996),  # Rambla Sur / Centro
    (-34.9080, -56.1850),
    (-34.9109, -56.1700),
    (-34.9109, -56.1506),  # Pocitos
    (-34.9150, -56.1400),  # Rambla Este / Buceo
    (-34.9060, -56.1250),
    (-34.9000, -56.1100),
]

# Known high-elevation landmarks: Cerro de Montevideo peak (~130m) and Cuchilla Grande
# foothills / ridges to the north of the city (within Montevideo bounds, ~80-120m).
HIGHLAND_ANCHORS = [
    (-34.8555, -56.2665),  # Cerro de Montevideo peak
    (-34.8500, -56.2007),  # Prado / Cerro-adjacent high ground
    (-34.8200, -56.2500),  # Colón / Pasaje (north-west highlands)
    (-34.8150, -56.2100),
    (-34.8300, -56.1900),
    (-34.8100, -56.1700),  # Northern ridge towards Cuchilla Grande
    (-34.8250, -56.1500),
]

CRITICAL_ANCHORS = COASTAL_ANCHORS + HIGHLAND_ANCHORS
NODES_PER_ANCHOR = 20  # 17 anchors * 20 ~= 340 critical nodes (~20% of ~1500)


def _project_meters(lats: np.ndarray, lons: np.ndarray, ref_lat: float) -> tuple[np.ndarray, np.ndarray]:
    """Simple equirectangular projection to meters, adequate at Montevideo's scale."""
    ref_rad = math.radians(ref_lat)
    x = lons * 111_320.0 * math.cos(ref_rad)
    y = lats * 110_540.0
    return x, y


def _select_grid_samples(
    node_ids: np.ndarray, xs: np.ndarray, ys: np.ndarray, target_count: int
) -> set[int]:
    """Uniform spatial grid: one closest-to-center node per ~100m x 100m cell."""
    x_min, x_max = xs.min(), xs.max()
    y_min, y_max = ys.min(), ys.max()

    n_cols = max(1, int((x_max - x_min) / GRID_CELL_METERS) + 1)
    n_rows = max(1, int((y_max - y_min) / GRID_CELL_METERS) + 1)

    col_idx = np.clip(((xs - x_min) / GRID_CELL_METERS).astype(int), 0, n_cols - 1)
    row_idx = np.clip(((ys - y_min) / GRID_CELL_METERS).astype(int), 0, n_rows - 1)
    cell_id = row_idx * n_cols + col_idx

    cell_center_x = x_min + (col_idx + 0.5) * GRID_CELL_METERS
    cell_center_y = y_min + (row_idx + 0.5) * GRID_CELL_METERS
    dist_to_center = (xs - cell_center_x) ** 2 + (ys - cell_center_y) ** 2

    best_per_cell: dict[int, tuple[float, int]] = {}
    for i in range(len(node_ids)):
        cid = int(cell_id[i])
        d = float(dist_to_center[i])
        if cid not in best_per_cell or d < best_per_cell[cid][0]:
            best_per_cell[cid] = (d, i)

    selected_indices = [idx for _, idx in best_per_cell.values()]

    if len(selected_indices) > target_count:
        rng = np.random.default_rng(seed=42)
        selected_indices = list(rng.choice(selected_indices, size=target_count, replace=False))

    return {int(node_ids[i]) for i in selected_indices}


def _select_critical_samples(
    node_ids: np.ndarray, xs: np.ndarray, ys: np.ndarray, ref_lat: float
) -> set[int]:
    """Topographic extremes: nodes nearest to known coastal / highland anchor points."""
    tree = cKDTree(np.column_stack([xs, ys]))
    critical: set[int] = set()

    for lat, lon in CRITICAL_ANCHORS:
        ax, ay = _project_meters(np.array([lat]), np.array([lon]), ref_lat)
        _, idxs = tree.query([ax[0], ay[0]], k=NODES_PER_ANCHOR)
        idxs = np.atleast_1d(idxs)
        for i in idxs:
            critical.add(int(node_ids[i]))

    return critical


def _load_samples_cache() -> dict[int, float]:
    """Load previously fetched sample elevations (node_id -> elevation), if any."""
    if not SAMPLES_CACHE_PATH.exists():
        return {}
    try:
        with SAMPLES_CACHE_PATH.open() as f:
            raw = json.load(f)
        return {int(k): float(v) for k, v in raw.items()}
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        logger.warning("Could not read samples cache (%s), starting fresh: %s", SAMPLES_CACHE_PATH, exc)
        return {}


def _save_samples_cache(cache: dict[int, float]) -> None:
    """Persist fetched sample elevations to disk immediately after each successful batch."""
    SAMPLES_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SAMPLES_CACHE_PATH.open("w") as f:
        json.dump({str(k): v for k, v in cache.items()}, f)


def _fetch_elevations_batch(lats: list[float], lons: list[float]) -> list[float] | None:
    """Single POST request to Open-Meteo. No retries: any error/limit aborts immediately."""
    try:
        response = requests.post(
            OPEN_METEO_ELEVATION_URL,
            json={"latitude": lats, "longitude": lons},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        elevations = data.get("elevation")
        if elevations is None or len(elevations) != len(lats):
            logger.error("Unexpected Open-Meteo response shape: %s", data)
            return None
        return [float(e) for e in elevations]
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        logger.error("Open-Meteo HTTP error (status=%s): %s. Aborting — no changes written.", status, exc)
        return None
    except (requests.RequestException, ValueError, KeyError) as exc:
        logger.error("Open-Meteo request failed: %s. Aborting — no changes written.", exc)
        return None


def main() -> int:
    if not GRAPH_CACHE_PATH.exists():
        logger.error("Graph cache not found at %s. Aborting.", GRAPH_CACHE_PATH)
        return 1

    logger.info("Loading cached graph: %s", GRAPH_CACHE_PATH)
    G = ox.load_graphml(GRAPH_CACHE_PATH)

    node_ids = np.array(list(G.nodes()))
    lats = np.array([G.nodes[n]["y"] for n in node_ids], dtype=float)
    lons = np.array([G.nodes[n]["x"] for n in node_ids], dtype=float)
    ref_lat = float(lats.mean())
    xs, ys = _project_meters(lats, lons, ref_lat)

    logger.info("Graph has %d nodes. Selecting ~1,500 strategic samples...", len(node_ids))

    critical_ids = _select_critical_samples(node_ids, xs, ys, ref_lat)
    grid_target = max(0, int(1500 * 0.8))
    grid_ids = _select_grid_samples(node_ids, xs, ys, grid_target)

    sample_ids = grid_ids | critical_ids
    logger.info(
        "Sample selection: %d grid + %d critical = %d unique sample nodes",
        len(grid_ids), len(critical_ids), len(sample_ids),
    )

    sample_ids_list = list(sample_ids)
    id_to_index = {nid: i for i, nid in enumerate(node_ids)}
    total_samples = len(sample_ids_list)

    # --- Resume from cache: only fetch samples we don't already have ---
    samples_cache = _load_samples_cache()
    pending_ids = [nid for nid in sample_ids_list if nid not in samples_cache]
    cached_count = total_samples - len(pending_ids)
    if cached_count:
        logger.info("Resuming: %d/%d sample elevations already cached, %d pending.", cached_count, total_samples, len(pending_ids))

    if pending_ids:
        pending_indices = [id_to_index[nid] for nid in pending_ids]
        pending_lats = lats[pending_indices]
        pending_lons = lons[pending_indices]
        n_batches = math.ceil(len(pending_ids) / BATCH_SIZE)
        logger.info("Fetching %d pending sample elevations in %d batch(es)...", len(pending_ids), n_batches)

        for batch_num, start in enumerate(range(0, len(pending_ids), BATCH_SIZE)):
            if batch_num > 0:
                time.sleep(BATCH_DELAY_SECONDS)
            batch_ids = pending_ids[start : start + BATCH_SIZE]
            batch_lats = pending_lats[start : start + BATCH_SIZE].tolist()
            batch_lons = pending_lons[start : start + BATCH_SIZE].tolist()
            logger.info("Batch %d/%d: requesting %d points...", batch_num + 1, n_batches, len(batch_lats))

            result = _fetch_elevations_batch(batch_lats, batch_lons)
            if result is None:
                logger.warning(
                    "API limit or error hit on batch %d/%d. Stopping fetch — keeping %d samples "
                    "fetched so far (saved to %s). Re-run this script later to fetch the rest.",
                    batch_num + 1, n_batches, len(samples_cache), SAMPLES_CACHE_PATH,
                )
                break

            for nid, elev in zip(batch_ids, result, strict=True):
                samples_cache[nid] = elev
            _save_samples_cache(samples_cache)
            logger.info("Batch %d/%d: OK (%d elevations received, cache saved)", batch_num + 1, n_batches, len(result))

    available_ids = [nid for nid in sample_ids_list if nid in samples_cache]
    if not available_ids:
        logger.error("No sample elevations available (cache empty and fetch failed). Aborting — no changes written.")
        return 1

    sample_indices = [id_to_index[nid] for nid in available_ids]
    sample_elevations_arr = np.array([samples_cache[nid] for nid in available_ids], dtype=float)
    logger.info(
        "✓ Using %d/%d sample elevations (real, fetched from API). min=%.1fm max=%.1fm mean=%.1fm",
        len(available_ids), total_samples,
        sample_elevations_arr.min(), sample_elevations_arr.max(), sample_elevations_arr.mean(),
    )

    # --- IDW interpolation for all nodes ---
    logger.info("Running IDW interpolation (k=%d, power=%d) for %d nodes...", IDW_K_NEIGHBORS, IDW_POWER, len(node_ids))
    t0 = time.perf_counter()

    sample_xy = np.column_stack([xs[sample_indices], ys[sample_indices]])
    tree = cKDTree(sample_xy)
    all_xy = np.column_stack([xs, ys])

    k = min(IDW_K_NEIGHBORS, len(available_ids))
    distances, neighbor_idx = tree.query(all_xy, k=k)
    if k == 1:
        distances = distances[:, None]
        neighbor_idx = neighbor_idx[:, None]

    exact_match = distances[:, 0] < 1e-6
    weights = 1.0 / np.where(distances == 0, 1e-12, distances) ** IDW_POWER
    neighbor_elevs = sample_elevations_arr[neighbor_idx]
    interpolated = np.sum(weights * neighbor_elevs, axis=1) / np.sum(weights, axis=1)
    interpolated = np.where(exact_match, neighbor_elevs[:, 0], interpolated)

    elapsed = time.perf_counter() - t0
    logger.info(
        "✓ IDW interpolation done in %.2fs. min=%.1fm max=%.1fm mean=%.1fm",
        elapsed, interpolated.min(), interpolated.max(), interpolated.mean(),
    )

    for i, nid in enumerate(node_ids):
        G.nodes[nid]["elevation"] = float(interpolated[i])

    # --- Recompute edge grades from the new elevations ---
    logger.info("Recomputing edge grades...")
    for u, v, _key, data in G.edges(keys=True, data=True):
        length = data.get("length", 0.0)
        try:
            length = float(length)
        except (TypeError, ValueError):
            length = 0.0
        if length <= 0:
            data["grade"] = 0.0
            continue
        elev_u = G.nodes[u]["elevation"]
        elev_v = G.nodes[v]["elevation"]
        grade = (elev_v - elev_u) / length
        data["grade"] = max(-MAX_GRADE, min(MAX_GRADE, grade))

    logger.info("Saving enriched graph to %s ...", GRAPH_CACHE_PATH)
    ox.save_graphml(G, GRAPH_CACHE_PATH)

    still_pending = total_samples - len(available_ids)
    logger.info(
        "✓ DONE. %d nodes enriched with IDW-interpolated real topography "
        "(%d real samples used, %d interpolated). Grades recomputed on %d edges.",
        len(node_ids), len(available_ids), len(node_ids) - len(available_ids), G.number_of_edges(),
    )
    if still_pending:
        logger.info(
            "%d/%d target sample nodes still lack real elevations (skipped due to API limit). "
            "Re-run this script later — it will resume fetching only those and re-interpolate with more real data.",
            still_pending, total_samples,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
