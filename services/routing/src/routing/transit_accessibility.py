"""Calculate public-transit accessibility routes and export them as JSON."""

import argparse
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path
from time import perf_counter
from typing import List, Optional, Tuple
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer
from pydantic import BaseModel
from scipy.sparse import bmat, coo_matrix, csr_matrix, load_npz, save_npz
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point
from shapely.ops import substring

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "input"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "output" / "transit_accessibility"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute IDF transit journeys from one origin and export JSON."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Input root containing IDFM-gtfs-0511/ and osm/.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for JSON results.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Directory for reusable graph and commune caches (defaults to --output-dir).",
    )
    parser.add_argument(
        "--service-date",
        default="2026-11-08",
        help="GTFS service date in YYYY-MM-DD format (default: 2026-11-08).",
    )
    parser.add_argument(
        "--departure-time",
        default="02:00:00",
        help="Departure time in GTFS HH:MM:SS format.",
    )
    parser.add_argument("--origin-lat", type=float, default=48.853563)
    parser.add_argument("--origin-lon", type=float, default=2.372961)
    parser.add_argument(
        "--all-communes",
        action="store_true",
        help="Use every Île-de-France town hall instead of the 3 sample destinations.",
    )
    parser.add_argument(
        "--max-destinations",
        type=int,
        default=None,
        help="Optional cap for quick test runs.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    started_at = perf_counter()
    GTFS_FOLDER = args.data_dir / "IDFM-gtfs-0511"
    SERVICE_DATE = date.fromisoformat(args.service_date)
    DEPARTURE_TIME = args.departure_time
    ORIGIN_LAT = args.origin_lat
    ORIGIN_LON = args.origin_lon
    WALK_SPEED_M_S = 1.3
    TRANSFER_MAX_WALK_MIN = 5
    SHAPE_STOP_SNAP_MAX_M = 500
    EARTH_RADIUS_M = 6_371_000
    DIST_RECH_ARRET = 2_400
    WALK_MAX_SNAP_M = 100
    FOLDER_EXPORT = args.output_dir
    CACHE_DIR = args.cache_dir if args.cache_dir is not None else FOLDER_EXPORT
    FOLDER_EXPORT.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    required_gtfs_files = (
        "agency.txt", "calendar.txt", "calendar_dates.txt", "routes.txt",
        "shapes.txt", "stop_times.txt", "stops.txt", "trips.txt",
    )
    missing_files = [name for name in required_gtfs_files if not (GTFS_FOLDER / name).is_file()]
    if missing_files:
        raise FileNotFoundError(
            f"GTFS incomplete dans {GTFS_FOLDER}; fichiers manquants : {', '.join(missing_files)}"
        )
    roads_file = args.data_dir / "osm" / "gis_osm_roads_free_1.shp"
    if not roads_file.is_file():
        raise FileNotFoundError(f"Shapefile OSM introuvable : {roads_file}")

    # %% GTFS helpers
    @dataclass
    class Connection:
        from_stop:str
        to_stop:str
        dep_time:int
        arr_time:int

    def gtfs_time_to_seconds(t):
        if pd.isna(t):
            return None
        t = str(t).strip()
        if not t:
            return None
        try:
            h,m,s = map(int,t.split(':'))
            return h*3600+m*60+s
        except Exception:
            return None
    # %% Load GTFS tables
    stops_df = pd.read_csv(f"{GTFS_FOLDER}/stops.txt", dtype=str)
    calendar_df = pd.read_csv(f"{GTFS_FOLDER}/calendar.txt", dtype=str)
    trips_df = pd.read_csv(f"{GTFS_FOLDER}/trips.txt", dtype=str)
    calendar_dates_df = pd.read_csv(f"{GTFS_FOLDER}/calendar_dates.txt", dtype=str)
    st = pd.read_csv(f"{GTFS_FOLDER}/stop_times.txt", dtype=str)
    # %% Clean stop times
    st = st.dropna(subset=['departure_time','arrival_time'])
    #st = st[st['departure_time'].astype(str).str.match(r'^\d+:\d+:\d+$', na=False)]
    #st = st[st['arrival_time'].astype(str).str.match(r'^\d+:\d+:\d+$', na=False)]
    # %% Select active services
    def active_services(service_date):
        day_map = {
            0: "monday",
            1: "tuesday",
            2: "wednesday",
            3: "thursday",
            4: "friday",
            5: "saturday",
            6: "sunday"
        }
        gtfs_day = day_map[service_date.weekday()]
        d = int(service_date.strftime("%Y%m%d"))
        active = set()
        for r in calendar_df.itertuples():
            if (
                int(r.start_date)
                <= d <=
                int(r.end_date)
            ):
                if int(getattr(r, gtfs_day)) == 1:
                    active.add(
                        r.service_id
                    )
        return active

    services = active_services(SERVICE_DATE)
    active_trips = trips_df[trips_df.service_id.isin(services)]
    # %% Build connections
    active_trip_ids = set(active_trips["trip_id"])
    full_st = st[st.trip_id.isin(active_trip_ids)].copy()
    full_st["stop_sequence"] = full_st["stop_sequence"].astype(int)
    full_st = full_st.sort_values(["trip_id", "stop_sequence"])

    connection_rows = []
    for _, group in full_st.groupby("trip_id"):
        rows = list(group.itertuples())
        for i in range(len(rows) - 1):
            dep = gtfs_time_to_seconds(rows[i].departure_time)
            arr = gtfs_time_to_seconds(rows[i + 1].arrival_time)
            if dep is None or arr is None:
                continue
            connection_rows.append((rows[i].stop_id, rows[i + 1].stop_id, dep, arr, rows[i].trip_id))

    print("Nb connexions :", len(connection_rows))
    # %% Index connections
    connections_df = pd.DataFrame(
        connection_rows,
        columns=[
            "from_stop",
            "to_stop",
            "dep_time",
            "arr_time",
            "trip_id"
        ]
    )

    stop_ids = sorted(stops_df.keys())
    stop_to_idx = {
        stop_id: i
        for i, stop_id in enumerate(stop_ids)
    }

    idx_to_stop = {
        i: stop_id
        for stop_id, i in stop_to_idx.items()
    }

    connections_df["from_idx"] = (
        connections_df["from_stop"]
        .map(stop_to_idx)
    )

    connections_df["to_idx"] = (
        connections_df["to_stop"]
        .map(stop_to_idx)
    )

    physical_stops = stops_df[
        stops_df["location_type"].astype(str) == "0"
    ]

    stops = {

        r.stop_id: {

            "lat": float(r.stop_lat),

            "lon": float(r.stop_lon)

        }

        for r in physical_stops.itertuples()
    }

    stop_ids = sorted(stops.keys())

    stop_to_idx = {

        stop_id: i

        for i, stop_id in enumerate(stop_ids)

    }

    connections_df["from_idx"] = (
        connections_df["from_stop"]
        .map(stop_to_idx)
    )

    connections_df["to_idx"] = (
        connections_df["to_stop"]
        .map(stop_to_idx)
    )

    connections_int = (
        connections_df[
            [
                "from_idx",
                "to_idx",
                "dep_time",
                "arr_time",
                "trip_id"
            ]
        ]
        .astype(
            {
                "from_idx": np.int32,
                "to_idx": np.int32,
                "dep_time": np.int32,
                "arr_time": np.int32
            }
        )
        .sort_values("dep_time", kind="stable")
        .reset_index(drop=True)
    )
    # %% Build stop and transfer indexes
    physical_stops = stops_df[
        stops_df["location_type"].astype(str) == "0"
    ]

    stops = {
        r.stop_id: {
            "lat": float(r.stop_lat),
            "lon": float(r.stop_lon)
        }
        for r in physical_stops.itertuples()
    }

    stop_ids = sorted(stops.keys())

    coords = np.array([
        [
            stops[s]["lat"],
            stops[s]["lon"]
        ]
        for s in stop_ids
    ])

    tree = cKDTree(coords)

    # Transferts piétons entre arrêts : rayon euclidien en mètres (Lambert-93).


    transfer_transformer = Transformer.from_crs(
        "EPSG:4326", "EPSG:2154", always_xy=True
    )
    stop_x, stop_y = transfer_transformer.transform(
        coords[:, 1], coords[:, 0]
    )
    stop_xy = np.column_stack((stop_x, stop_y))
    transfer_max_walk_m = TRANSFER_MAX_WALK_MIN * 60 * WALK_SPEED_M_S
    transfer_pairs = cKDTree(stop_xy).query_pairs(
        r=transfer_max_walk_m,
        output_type="ndarray"
    )
    pair_delta = stop_xy[transfer_pairs[:, 0]] - stop_xy[transfer_pairs[:, 1]]
    pair_time_s = np.hypot(pair_delta[:, 0], pair_delta[:, 1]) / WALK_SPEED_M_S
    transfer_from = np.concatenate((transfer_pairs[:, 0], transfer_pairs[:, 1]))
    transfer_to = np.concatenate((transfer_pairs[:, 1], transfer_pairs[:, 0]))
    transfer_time_s = np.concatenate((pair_time_s, pair_time_s))
    transfer_order = np.argsort(transfer_from, kind="stable")
    transfer_neighbors = transfer_to[transfer_order]
    transfer_times = transfer_time_s[transfer_order]
    transfer_indptr = np.zeros(len(stop_ids) + 1, dtype=np.int64)
    transfer_indptr[1:] = np.cumsum(
        np.bincount(transfer_from, minlength=len(stop_ids))
    )

    def relax_direct_transfers(
        stop_idx,
        stop_arrival_s,
        arrival_times,
        stop_label_ids=None,
        labels=None,
        parent_label_id=None
    ):
        start = transfer_indptr[stop_idx]
        end = transfer_indptr[stop_idx + 1]
        neighbors = transfer_neighbors[start:end]
        candidates = stop_arrival_s + transfer_times[start:end]
        improved = candidates < arrival_times[neighbors]
        improved_neighbors = neighbors[improved]
        improved_candidates = candidates[improved]
        arrival_times[improved_neighbors] = improved_candidates
        if stop_label_ids is not None and labels is not None:
            if parent_label_id is None or parent_label_id < 0:
                raise ValueError(f"Aucun prédécesseur de transport enregistré pour l'arrêt {stop_idx}.")
            for neighbor, arrival_s in zip(improved_neighbors, improved_candidates):
                labels.append({
                    "kind": "walk_transfer",
                    "parent_id": parent_label_id,
                    "from_stop_idx": int(stop_idx),
                    "to_stop_idx": int(neighbor),
                    "dep_s": float(stop_arrival_s),
                    "arr_s": float(arrival_s),
                })
                stop_label_ids[neighbor] = len(labels) - 1

    print(
        f"Correspondances à pied : {TRANSFER_MAX_WALK_MIN} min maximum "
        f"({transfer_max_walk_m:.0f} m à {WALK_SPEED_M_S:.1f} m/s), "
        f"{len(transfer_pairs):,} paires d'arrêts."
    )
    # %% Find origin stops
    def haversine(lat1,lon1,lat2,lon2):
        dlat=radians(lat2-lat1)
        dlon=radians(lon2-lon1)
        a=sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
        return 2*EARTH_RADIUS_M*atan2(sqrt(a),sqrt(1-a))

    idxs = tree.query_ball_point([ORIGIN_LAT, ORIGIN_LON], DIST_RECH_ARRET/111320)
    # %% Initialize baseline arrivals
    n_stops = len(stop_ids)

    arrival = np.full(
        n_stops,
        np.inf,
        dtype=np.float64
    )

    departure_time = gtfs_time_to_seconds(
        DEPARTURE_TIME
    )

    for idx in idxs:

        stop_lat = coords[idx][0]
        stop_lon = coords[idx][1]

        d = haversine(
            ORIGIN_LAT,
            ORIGIN_LON,
            stop_lat,
            stop_lon
        )

        arrival[idx] = (
            departure_time +
            d / 1.3
        )

    # Les transferts piétons ne sont propagés qu'après une arrivée en transport collectif.
    # %% Run baseline CSA
    for row in connections_int.itertuples(index=False):

        f = row.from_idx
        t = row.to_idx

        dep = row.dep_time
        arr_t = row.arr_time

        if arrival[f] <= dep:

            if arr_t < arrival[t]:

                arrival[t] = arr_t
                relax_direct_transfers(t, arr_t, arrival)
    # %% Sample destinations
    destinations = [
        ('Tour Eiffel',48.8584, 2.2945),  # Tour Eiffel
        ('Gare du Nord',48.8766, 2.3522),  # Gare du Nord
        ('Orly',48.7247, 2.2587),  # Orly
    ]
    # %% Load commune town hall destinations
    USE_COMMUNE_MAIRIES = args.all_communes
    COMMUNES_IDF_MAIRIES_JSON = CACHE_DIR / "communes_idf_mairies.json"

    def load_idf_commune_mairies():
        if COMMUNES_IDF_MAIRIES_JSON.is_file():
            with COMMUNES_IDF_MAIRIES_JSON.open(encoding="utf-8") as communes_file:
                communes = json.load(communes_file)
        else:
            url = (
                "https://geo.api.gouv.fr/communes?codeRegion=11"
                "&fields=nom,code,mairie&format=json"
            )
            request = Request(
                url,
                headers={"User-Agent": "hackaviz-2026-transit-accessibility/1.0"},
            )
            try:
                with urlopen(request, timeout=60) as response:
                    communes = json.load(response)
            except Exception as exc:
                raise RuntimeError(
                    f"Impossible de télécharger les coordonnées des mairies : {url}"
                ) from exc
            if not isinstance(communes, list) or not communes:
                raise ValueError("L'API n'a renvoyé aucune commune d'Île-de-France.")
            COMMUNES_IDF_MAIRIES_JSON.parent.mkdir(parents=True, exist_ok=True)
            COMMUNES_IDF_MAIRIES_JSON.write_text(
                json.dumps(communes, ensure_ascii=False), encoding="utf-8"
            )

        if not isinstance(communes, list) or not communes:
            raise ValueError(
                f"Le cache des mairies est vide ou invalide : {COMMUNES_IDF_MAIRIES_JSON}"
            )

        destinations = []
        missing_mairies = []
        for commune in communes:
            if not isinstance(commune, dict):
                missing_mairies.append("<commune invalide>")
                continue
            town_hall = commune.get("mairie")
            coordinates = town_hall.get("coordinates") if isinstance(town_hall, dict) else None
            if (
                not commune.get("nom")
                or not commune.get("code")
                or not isinstance(town_hall, dict)
                or town_hall.get("type") != "Point"
                or not isinstance(coordinates, list)
                or len(coordinates) < 2
            ):
                missing_mairies.append(commune.get("code", "<code inconnu>"))
                continue
            longitude, latitude = map(float, coordinates[:2])
            if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
                raise ValueError(
                    f"Coordonnées de mairie invalides pour {commune['code']}: {coordinates}"
                )
            destinations.append(
                (f"{commune['nom']} ({commune['code']})", latitude, longitude)
            )

        if missing_mairies:
            raise ValueError(
                f"Coordonnées de mairie manquantes ou invalides pour "
                f"{len(missing_mairies)} commune(s) : {missing_mairies[:10]}"
            )
        if not destinations:
            raise ValueError("Aucune destination de mairie n'a pu être calculée.")
        return destinations

    if USE_COMMUNE_MAIRIES:
        destinations = load_idf_commune_mairies()
        print(f"Destinations configurées : {len(destinations):,} mairies d'Île-de-France.")
    else:
        print("Destinations de test conservées ; utilisez --all-communes pour les mairies.")
    if args.max_destinations is not None:
        if args.max_destinations < 1:
            raise ValueError("--max-destinations doit être supérieur ou égal à 1.")
        destinations = destinations[:args.max_destinations]
        print(f"Limitation du calcul à {len(destinations):,} destinations.")
    # %% Build or load walking graph
    WALK_ROADS_FILE = roads_file
    WALK_GRAPH_CACHE = CACHE_DIR / "walking_graph_idf_lambert.npz"
    WALK_NODES_CACHE = CACHE_DIR / "walking_graph_idf_lambert_nodes.npy"
    WALK_EXCLUDED_CLASSES = {
        "motorway", "motorway_link", "trunk", "trunk_link",
        "busway", "raceway", "construction", "unknown"
    }

    if not WALK_ROADS_FILE.is_file():
        raise FileNotFoundError(
            f"Shapefile OSM introuvable : {WALK_ROADS_FILE.resolve()}. "
            "Vérifiez le chemin de données indiqué par --data-dir."
        )

    Path(FOLDER_EXPORT).mkdir(parents=True, exist_ok=True)

    if WALK_GRAPH_CACHE.is_file() and WALK_NODES_CACHE.is_file():
        walk_graph = load_npz(WALK_GRAPH_CACHE).tocsr()
        walk_node_xy = np.load(WALK_NODES_CACHE)
    else:
        roads = gpd.read_file(
            WALK_ROADS_FILE,
            engine="pyogrio",
            columns=["fclass"]
        )
        roads = roads.loc[
            ~roads["fclass"].isin(WALK_EXCLUDED_CLASSES)
        ].to_crs(epsg=2154)

        # Chaque arête relie deux sommets consécutifs d'une géométrie OSM.
        line_parts = shapely.get_parts(roads.geometry.array)
        xy, part_id = shapely.get_coordinates(line_parts, return_index=True)
        same_part = part_id[:-1] == part_id[1:]
        start_xy = xy[:-1][same_part]
        end_xy = xy[1:][same_part]
        edge_length_m = np.hypot(
            end_xy[:, 0] - start_xy[:, 0],
            end_xy[:, 1] - start_xy[:, 1]
        )
        nonzero = edge_length_m > 0
        start_xy = start_xy[nonzero]
        end_xy = end_xy[nonzero]
        edge_length_m = edge_length_m[nonzero]
        del xy, part_id, same_part, line_parts, roads

        n_edges = len(edge_length_m)
        walk_node_xy, node_ids = np.unique(
            np.concatenate((start_xy, end_xy), axis=0),
            axis=0,
            return_inverse=True
        )
        edge_from = node_ids[:n_edges]
        edge_to = node_ids[n_edges:]
        del node_ids, start_xy, end_xy

        # Dédupliquer les segments identiques avant de créer le graphe non orienté.
        edge_low = np.minimum(edge_from, edge_to)
        edge_high = np.maximum(edge_from, edge_to)
        edge_key = edge_low * len(walk_node_xy) + edge_high
        _, first_edge = np.unique(edge_key, return_index=True)
        edge_from = edge_low[first_edge]
        edge_to = edge_high[first_edge]
        edge_length_m = edge_length_m[first_edge]
        del edge_low, edge_high, edge_key, first_edge

        graph_rows = np.concatenate((edge_from, edge_to))
        graph_cols = np.concatenate((edge_to, edge_from))
        graph_lengths_m = np.concatenate((edge_length_m, edge_length_m))
        walk_graph = coo_matrix(
            (graph_lengths_m, (graph_rows, graph_cols)),
            shape=(len(walk_node_xy), len(walk_node_xy))
        ).tocsr()
        save_npz(WALK_GRAPH_CACHE, walk_graph, compressed=True)
        np.save(WALK_NODES_CACHE, walk_node_xy)

    walk_tree = cKDTree(walk_node_xy)
    print(
        f"Graphe piéton : {walk_graph.shape[0]:,} nœuds, "
        f"{walk_graph.nnz // 2:,} arêtes ; cache : {WALK_GRAPH_CACHE}"
    )
    # %% Prepare destination and origin walking routes
    WALK_MAX_SNAP_M = 100
    walk_transformer = Transformer.from_crs(
        "EPSG:4326", "EPSG:2154", always_xy=True
    )

    # La liste d'exemple existante peut être remplacée par toutes les adresses.
    destinations_df = pd.DataFrame(
        destinations,
        columns=["name", "lat", "lon"]
    )
    destination_x, destination_y = walk_transformer.transform(
        destinations_df["lon"].to_numpy(),
        destinations_df["lat"].to_numpy()
    )
    destination_xy = np.column_stack((destination_x, destination_y))

    stop_lon = np.array([stops[stop_id]["lon"] for stop_id in stop_ids])
    stop_lat = np.array([stops[stop_id]["lat"] for stop_id in stop_ids])
    stop_x, stop_y = walk_transformer.transform(stop_lon, stop_lat)
    stop_xy = np.column_stack((stop_x, stop_y))
    stop_tree_lambert = cKDTree(stop_xy)
    stop_snap_m, stop_node = walk_tree.query(stop_xy)

    origin_x, origin_y = walk_transformer.transform(ORIGIN_LON, ORIGIN_LAT)
    origin_snap_m, origin_node = walk_tree.query([origin_x, origin_y])
    if origin_snap_m > WALK_MAX_SNAP_M:
        raise ValueError(
            f"L'origine est à {origin_snap_m:.0f} m du réseau piéton "
            f"(maximum autorisé : {WALK_MAX_SNAP_M} m)."
        )

    # Un calcul de plus courts chemins pour toutes les destinations.
    walk_distance_from_origin_m, origin_walk_predecessor = dijkstra(
        walk_graph,
        directed=False,
        indices=int(origin_node),
        return_predecessors=True
    )
    destination_snap_m, destination_node = walk_tree.query(destination_xy)
    walk_time_s = (
        walk_distance_from_origin_m[destination_node]
        + origin_snap_m
        + destination_snap_m
    ) / WALK_SPEED_M_S
    walk_time_s[destination_snap_m > WALK_MAX_SNAP_M] = np.inf
    print(f"Accès piéton OSM calculé pour {len(destinations_df):,} destinations.")
    # %% Run CSA with OSM access
    origin_stop_idxs = np.asarray(
        stop_tree_lambert.query_ball_point(
            [origin_x, origin_y],
            r=DIST_RECH_ARRET
        ),
        dtype=int
    )
    origin_stop_idxs = origin_stop_idxs[
        stop_snap_m[origin_stop_idxs] <= WALK_MAX_SNAP_M
    ]
    if not len(origin_stop_idxs):
        raise ValueError(
            "Aucun arrêt dans le rayon d'accès ne peut être rattaché au réseau piéton."
        )

    arrival = np.full(len(stop_ids), np.inf, dtype=np.float64)
    route_labels = []
    route_label_at_stop = np.full(len(stop_ids), -1, dtype=np.int64)
    ride_arrival = np.full(len(stop_ids), np.inf, dtype=np.float64)
    ride_label_at_stop = np.full(len(stop_ids), -1, dtype=np.int64)
    arrival[origin_stop_idxs] = departure_time + (
        walk_distance_from_origin_m[stop_node[origin_stop_idxs]]
        + origin_snap_m
        + stop_snap_m[origin_stop_idxs]
    ) / WALK_SPEED_M_S
    for idx in origin_stop_idxs:
        route_labels.append({
            "kind": "walk_access",
            "parent_id": None,
            "from_stop_idx": None,
            "to_stop_idx": int(idx),
            "dep_s": float(departure_time),
            "arr_s": float(arrival[idx]),
            "trip_id": None,
        })
        route_label_at_stop[idx] = len(route_labels) - 1
    for row in connections_int.itertuples(index=False):
        if arrival[row.from_idx] <= row.dep_time:
            improves_boarding_arrival = row.arr_time < arrival[row.to_idx]
            improves_transit_arrival = row.arr_time < ride_arrival[row.to_idx]
            if not (improves_boarding_arrival or improves_transit_arrival):
                continue
            parent_label_id = int(route_label_at_stop[row.from_idx])
            if parent_label_id < 0:
                raise ValueError(f"Aucun prédécesseur pour l'arrêt de départ {row.from_idx}.")
            route_labels.append({
                "kind": "ride",
                "parent_id": parent_label_id,
                "from_stop_idx": int(row.from_idx),
                "to_stop_idx": int(row.to_idx),
                "dep_s": float(row.dep_time),
                "arr_s": float(row.arr_time),
                "trip_id": row.trip_id,
            })
            ride_label_id = len(route_labels) - 1
            if improves_transit_arrival:
                ride_arrival[row.to_idx] = row.arr_time
                ride_label_at_stop[row.to_idx] = ride_label_id
            if improves_boarding_arrival:
                arrival[row.to_idx] = row.arr_time
                route_label_at_stop[row.to_idx] = ride_label_id
            relax_direct_transfers(
                row.to_idx, row.arr_time, arrival, route_label_at_stop, route_labels,
                parent_label_id=ride_label_id
            )

    print(
        f"CSA recalculé avec accès OSM : "
        f"{np.isfinite(arrival).sum():,} arrêts atteignables."
    )
    # %% Compute destination egress routes
    reachable_stop_idxs = np.flatnonzero(
        np.isfinite(ride_arrival) & (stop_snap_m <= WALK_MAX_SNAP_M)
    )
    if not len(reachable_stop_idxs):
        raise ValueError("Aucun arrêt atteignable à initialiser comme source du Dijkstra.")

    # Convertir les coûts initiaux (temps TC + rattachement au graphe) en mètres équivalents.
    source_nodes = stop_node[reachable_stop_idxs]
    source_cost_m = (
        (ride_arrival[reachable_stop_idxs] - departure_time) * WALK_SPEED_M_S
        + stop_snap_m[reachable_stop_idxs]
    )
    # scipy.sparse.csgraph traite les zéros comme des absences d'arête.
    MULTISOURCE_EPSILON_M = 1e-6
    source_cost_m += MULTISOURCE_EPSILON_M
    source_order = np.lexsort((source_cost_m, source_nodes))
    ordered_nodes = source_nodes[source_order]
    unique_source_nodes, first_source = np.unique(ordered_nodes, return_index=True)
    unique_source_cost_m = source_cost_m[source_order[first_source]]
    unique_source_stop_idxs = reachable_stop_idxs[source_order[first_source]]

    n_walk_nodes = walk_graph.shape[0]
    super_source_edges = coo_matrix(
        (
            unique_source_cost_m,
            (np.zeros(len(unique_source_nodes), dtype=int), unique_source_nodes)
        ),
        shape=(1, n_walk_nodes)
    ).tocsr()
    augmented_walk_graph = bmat(
        [
            [walk_graph, None],
            [super_source_edges, csr_matrix((1, 1))]
        ],
        format="csr"
    )
    best_total_cost_m, walk_predecessor = dijkstra(
        augmented_walk_graph,
        directed=True,
        indices=n_walk_nodes,
        return_predecessors=True
    )
    source_stop_for_node = np.full(n_walk_nodes, -1, dtype=int)
    source_stop_for_node[unique_source_nodes] = unique_source_stop_idxs

    transit_time_s = np.full(len(destinations_df), np.inf, dtype=float)
    destination_final_stop_idxs = np.full(len(destinations_df), -1, dtype=int)
    destination_egress_node_paths = [None] * len(destinations_df)
    egress_fallback_count = 0

    for destination_idx, destination_node_idx in enumerate(destination_node):
        if destination_snap_m[destination_idx] > WALK_MAX_SNAP_M:
            continue

        candidate_stop_idxs = np.asarray(
            stop_tree_lambert.query_ball_point(
                destination_xy[destination_idx],
                r=DIST_RECH_ARRET
            ),
            dtype=int
        )
        candidate_stop_idxs = candidate_stop_idxs[
            np.isfinite(ride_arrival[candidate_stop_idxs])
            & (stop_snap_m[candidate_stop_idxs] <= WALK_MAX_SNAP_M)
        ]
        if not len(candidate_stop_idxs):
            continue

        node = int(destination_node_idx)
        while node >= 0 and walk_predecessor[node] != n_walk_nodes:
            node = int(walk_predecessor[node])
        winning_stop_idx = source_stop_for_node[node] if node >= 0 else -1

        if winning_stop_idx in candidate_stop_idxs:
            best_total_m = (
                best_total_cost_m[destination_node_idx]
                - MULTISOURCE_EPSILON_M
                + destination_snap_m[destination_idx]
            )
            final_stop_idx = int(winning_stop_idx)
            egress_source_node = int(node)
            egress_path = [int(destination_node_idx)]
            while egress_path[-1] != egress_source_node:
                predecessor = int(walk_predecessor[egress_path[-1]])
                if predecessor < 0:
                    raise ValueError("Impossible de reconstruire le chemin piéton de sortie.")
                egress_path.append(predecessor)
            egress_path.reverse()
        else:
            egress_fallback_count += 1
            distance_from_destination_m, destination_predecessor = dijkstra(
                walk_graph,
                directed=False,
                indices=int(destination_node_idx),
                return_predecessors=True
            )
            candidate_cost_m = (
                (ride_arrival[candidate_stop_idxs] - departure_time) * WALK_SPEED_M_S
                + stop_snap_m[candidate_stop_idxs]
                + distance_from_destination_m[stop_node[candidate_stop_idxs]]
            )
            best_candidate_m = np.min(candidate_cost_m)
            if not np.isfinite(best_candidate_m):
                continue
            best_total_m = best_candidate_m + destination_snap_m[destination_idx]
            final_stop_idx = int(candidate_stop_idxs[np.argmin(candidate_cost_m)])
            egress_source_node = int(stop_node[final_stop_idx])
            egress_path = [egress_source_node]
            while egress_path[-1] != int(destination_node_idx):
                predecessor = int(destination_predecessor[egress_path[-1]])
                if predecessor < 0:
                    raise ValueError("Impossible de reconstruire le chemin piéton de sortie.")
                egress_path.append(predecessor)

        transit_time_s[destination_idx] = best_total_m / WALK_SPEED_M_S
        destination_final_stop_idxs[destination_idx] = final_stop_idx
        destination_egress_node_paths[destination_idx] = egress_path

    comparison = destinations_df.copy()
    comparison["walk_osm_min"] = walk_time_s / 60
    comparison["transit_min"] = transit_time_s / 60
    comparison["fastest_mode"] = np.where(
        walk_time_s < transit_time_s,
        "Marche OSM",
        "TC"
    )
    inaccessible = ~np.isfinite(walk_time_s) & ~np.isfinite(transit_time_s)
    comparison.loc[inaccessible, "fastest_mode"] = "inaccessible"
    comparison.sort_values(
        ["fastest_mode", "walk_osm_min"],
        inplace=True,
        ignore_index=True
    )
    print(f"Recherches Dijkstra de repli pour respecter le rayon : {egress_fallback_count:,}")
    print(comparison.to_string(index=False))
    # %% Reconstruct route geometries
    projected_to_wgs84 = Transformer.from_crs(
        "EPSG:2154", "EPSG:4326", always_xy=True
    )
    geometry_catalog = {}
    route_step_rows = []
    service_day_start = datetime.combine(SERVICE_DATE, datetime.min.time())

    def make_projected_line(coordinates):
        coordinates = np.asarray(coordinates, dtype=float)
        if len(coordinates) == 1:
            coordinates = np.vstack((coordinates, coordinates))
        keep = np.r_[True, np.any(np.diff(coordinates, axis=0) != 0, axis=1)]
        coordinates = coordinates[keep]
        if len(coordinates) == 1:
            coordinates = np.vstack((coordinates, coordinates))
        return LineString(coordinates)

    def graph_node_path(predecessors, start_node, end_node):
        node = int(end_node)
        path = [node]
        while node != int(start_node):
            node = int(predecessors[node])
            if node < 0:
                raise ValueError("Les nœuds demandés ne sont pas reliés dans le graphe piéton.")
            path.append(node)
        path.reverse()
        return path

    def register_geometry(geometry_id, geometry, source):
        if geometry_id not in geometry_catalog:
            geometry_catalog[geometry_id] = {
                "geometry_id": geometry_id,
                "geometry_source": source,
                "geometry": geometry,
            }
        return geometry_id

    def add_route_step(
        traveler_id, destination_name, order, mode, start_s, end_s,
        from_stop_id, to_stop_id, trip_id, geometry_id
    ):
        route_step_rows.append({
            "traveler_id": traveler_id,
            "destination": destination_name,
            "step_order": order,
            "mode": mode,
            "start_s": float(start_s),
            "end_s": float(end_s),
            "start_time": (service_day_start + timedelta(seconds=float(start_s))).isoformat(),
            "end_time": (service_day_start + timedelta(seconds=float(end_s))).isoformat(),
            "from_stop_id": from_stop_id,
            "to_stop_id": to_stop_id,
            "trip_id": trip_id,
            "geometry_id": geometry_id,
        })

    for destination_idx, destination in destinations_df.iterrows():
        destination_name = str(destination["name"])
        traveler_id = f"destination_{destination_idx}"
        order = 0

        if walk_time_s[destination_idx] < transit_time_s[destination_idx]:
            node_path = graph_node_path(
                origin_walk_predecessor,
                origin_node,
                destination_node[destination_idx]
            )
            line_xy = np.vstack((
                [origin_x, origin_y],
                walk_node_xy[node_path],
                destination_xy[destination_idx]
            ))
            geometry_id = register_geometry(
                f"direct_walk:{destination_idx}",
                make_projected_line(line_xy),
                "osm_walk",
            )
            add_route_step(
                traveler_id, destination_name, order, "walk_direct",
                departure_time, departure_time + walk_time_s[destination_idx],
                "ORIGIN", f"DESTINATION:{destination_idx}", None, geometry_id
            )
            continue

        final_stop_idx = destination_final_stop_idxs[destination_idx]
        if final_stop_idx < 0:
            continue
        label_id = int(ride_label_at_stop[final_stop_idx])
        if label_id < 0:
            raise ValueError(f"Aucun chemin CSA enregistré vers l'arrêt {stop_ids[final_stop_idx]}.")

        label_chain = []
        while label_id is not None:
            label = route_labels[label_id]
            label_chain.append(label)
            label_id = label["parent_id"]
        label_chain.reverse()
        current_time_s = float(departure_time)
        pending_ride = None

        def flush_ride(ride):
            if ride is None:
                return
            ride["geometry_id"] = None
            ride["geometry_source"] = None
            ride["from_xy"] = stop_xy[ride["from_stop_idx"]]
            ride["to_xy"] = stop_xy[ride["to_stop_idx"]]
            ride["from_stop_id"] = stop_ids[ride["from_stop_idx"]]
            ride["to_stop_id"] = stop_ids[ride["to_stop_idx"]]

        def emit_ride(ride, step_order, current_time_s):
            if ride is None:
                return step_order, current_time_s
            flush_ride(ride)
            if ride["start_s"] > current_time_s:
                wait_stop_idx = ride["from_stop_idx"]
                wait_geometry_id = register_geometry(
                    f"stop_point:{stop_ids[wait_stop_idx]}",
                    Point(stop_xy[wait_stop_idx]),
                    "gtfs_stop_point",
                )
                add_route_step(
                    traveler_id, destination_name, step_order, "wait",
                    current_time_s, ride["start_s"],
                    stop_ids[wait_stop_idx], stop_ids[wait_stop_idx],
                    None, wait_geometry_id
                )
                step_order += 1
            route_step_rows.append({
                "traveler_id": traveler_id,
                "destination": destination_name,
                "step_order": step_order,
                "mode": "transit",
                "start_s": float(ride["start_s"]),
                "end_s": float(ride["end_s"]),
                "start_time": (service_day_start + timedelta(seconds=float(ride["start_s"]))).isoformat(),
                "end_time": (service_day_start + timedelta(seconds=float(ride["end_s"]))).isoformat(),
                "from_stop_id": ride["from_stop_id"],
                "to_stop_id": ride["to_stop_id"],
                "trip_id": ride["trip_id"],
                "geometry_id": None,
                "_from_xy": ride["from_xy"],
                "_to_xy": ride["to_xy"],
            })
            return step_order + 1, ride["end_s"]

        for label in label_chain:
            if label["kind"] == "ride":
                can_merge = (
                    pending_ride is not None
                    and pending_ride["trip_id"] == label["trip_id"]
                    and pending_ride["to_stop_idx"] == label["from_stop_idx"]
                )
                if can_merge:
                    pending_ride["to_stop_idx"] = label["to_stop_idx"]
                    pending_ride["end_s"] = label["arr_s"]
                else:
                    order, current_time_s = emit_ride(
                        pending_ride, order, current_time_s
                    )
                    pending_ride = {
                        "trip_id": label["trip_id"],
                        "from_stop_idx": label["from_stop_idx"],
                        "to_stop_idx": label["to_stop_idx"],
                        "start_s": label["dep_s"],
                        "end_s": label["arr_s"],
                    }
                continue

            if pending_ride is not None:
                order, current_time_s = emit_ride(
                    pending_ride, order, current_time_s
                )
                pending_ride = None

            kind = label["kind"]
            from_stop_idx = label["from_stop_idx"]
            to_stop_idx = label["to_stop_idx"]
            if kind == "walk_access":
                node_path = graph_node_path(
                    origin_walk_predecessor,
                    origin_node,
                    stop_node[to_stop_idx]
                )
                line_xy = np.vstack((
                    [origin_x, origin_y],
                    walk_node_xy[node_path],
                    stop_xy[to_stop_idx]
                ))
                geometry_id = register_geometry(
                    f"access:{stop_ids[to_stop_idx]}",
                    make_projected_line(line_xy),
                    "osm_walk",
                )
                mode = "walk_access"
            elif kind == "walk_transfer":
                geometry_id = register_geometry(
                    f"transfer:{stop_ids[from_stop_idx]}:{stop_ids[to_stop_idx]}",
                    make_projected_line([stop_xy[from_stop_idx], stop_xy[to_stop_idx]]),
                    "euclidean_transfer",
                )
                mode = "walk_transfer"
            else:
                raise ValueError(f"Type de label inattendu : {kind}")

            add_route_step(
                traveler_id, destination_name, order, mode,
                label["dep_s"], label["arr_s"],
                "ORIGIN" if kind == "walk_access" else stop_ids[from_stop_idx],
                stop_ids[to_stop_idx], None, geometry_id
            )
            order += 1
            current_time_s = label["arr_s"]

        if pending_ride is not None:
            order, current_time_s = emit_ride(
                pending_ride, order, current_time_s
            )

        egress_path = destination_egress_node_paths[destination_idx]
        if egress_path is not None:
            line_xy = np.vstack((
                stop_xy[final_stop_idx],
                walk_node_xy[egress_path],
                destination_xy[destination_idx]
            ))
            geometry_id = register_geometry(
                f"egress:{stop_ids[final_stop_idx]}:{destination_idx}",
                make_projected_line(line_xy),
                "osm_walk",
            )
            add_route_step(
                traveler_id, destination_name, order, "walk_egress",
                ride_arrival[final_stop_idx], departure_time + transit_time_s[destination_idx],
                stop_ids[final_stop_idx], f"DESTINATION:{destination_idx}", None, geometry_id
            )

    if not route_step_rows:
        raise ValueError("Aucun itinéraire accessible à reconstruire pour les destinations fournies.")

    route_steps_df = pd.DataFrame(route_step_rows)
    ride_rows = route_steps_df.loc[route_steps_df["mode"] == "transit"]
    selected_trip_ids = set(ride_rows["trip_id"].dropna().astype(str))
    trip_shape_ids = {}
    shape_lines = {}
    shapes_file = Path(GTFS_FOLDER) / "shapes.txt"

    if selected_trip_ids:
        if not shapes_file.is_file():
            raise FileNotFoundError(f"Fichier GTFS des tracés introuvable : {shapes_file.resolve()}")
        if "shape_id" not in trips_df.columns:
            raise ValueError("La table trips.txt ne contient pas de colonne shape_id.")

        trip_shape_ids = (
            trips_df.loc[trips_df["trip_id"].astype(str).isin(selected_trip_ids), ["trip_id", "shape_id"]]
            .set_index("trip_id")["shape_id"]
            .to_dict()
        )
        missing_trip_shapes = sorted(
            trip_id for trip_id in selected_trip_ids
            if trip_id not in trip_shape_ids or pd.isna(trip_shape_ids[trip_id])
        )
        if missing_trip_shapes:
            raise ValueError(
                f"{len(missing_trip_shapes)} trajet(s) utilisé(s) n'ont pas de shape_id dans trips.txt. "
                f"Exemples : {missing_trip_shapes[:10]}"
            )
        trip_shape_ids = {str(trip_id): str(shape_id) for trip_id, shape_id in trip_shape_ids.items()}
        required_shape_ids = set(trip_shape_ids.values())
        shape_chunks = []
        for chunk in pd.read_csv(
            shapes_file,
            usecols=["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"],
            dtype={"shape_id": str, "shape_pt_lat": float, "shape_pt_lon": float},
            chunksize=500_000
        ):
            selected = chunk.loc[chunk["shape_id"].isin(required_shape_ids)]
            if not selected.empty:
                shape_chunks.append(selected)
        if shape_chunks:
            shape_points = pd.concat(shape_chunks, ignore_index=True)
            for shape_id, points in shape_points.groupby("shape_id", sort=False):
                points = points.sort_values("shape_pt_sequence")
                x, y = walk_transformer.transform(
                    points["shape_pt_lon"].to_numpy(),
                    points["shape_pt_lat"].to_numpy()
                )
                if len(x) >= 2:
                    shape_lines[str(shape_id)] = LineString(np.column_stack((x, y)))

        missing_shape_ids = sorted(required_shape_ids - set(shape_lines))
        if missing_shape_ids:
            raise ValueError(
                f"{len(missing_shape_ids)} shape_id référencé(s) par les trajets retenus sont absents ou incomplets dans shapes.txt. "
                f"Exemples : {missing_shape_ids[:10]}"
            )

    def nearby_shape_measures(shape_line, point, max_distance_m):
        coordinates = np.asarray(shape_line.coords, dtype=float)
        segments = np.diff(coordinates, axis=0)
        segment_lengths = np.linalg.norm(segments, axis=1)
        nonzero = segment_lengths > 0
        segment_starts = coordinates[:-1][nonzero]
        segments = segments[nonzero]
        segment_lengths = segment_lengths[nonzero]
        cumulative_lengths = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(coordinates, axis=0), axis=1))]
        point_xy = np.asarray(point.coords[0], dtype=float)
        fractions = np.clip(
            np.sum((point_xy - segment_starts) * segments, axis=1)
            / np.square(segment_lengths),
            0.0,
            1.0,
        )
        projected_xy = segment_starts + fractions[:, None] * segments
        distances = np.linalg.norm(projected_xy - point_xy, axis=1)
        original_segment_idxs = np.flatnonzero(nonzero)
        measures = (
            cumulative_lengths[original_segment_idxs]
            + fractions * segment_lengths
        )
        candidates = sorted(
            (float(measure), float(distance))
            for measure, distance in zip(measures, distances)
            if distance <= max_distance_m
        )
        unique_candidates = []
        for measure, distance in candidates:
            if unique_candidates and abs(measure - unique_candidates[-1][0]) < 0.01:
                if distance < unique_candidates[-1][1]:
                    unique_candidates[-1] = (measure, distance)
            else:
                unique_candidates.append((measure, distance))
        return unique_candidates, float(distances.min())

    def ordered_shape_segment(shape_line, from_point, to_point, max_distance_m):
        best = None
        nearest_distances = []
        for candidate_line in (
            shape_line,
            LineString(list(shape_line.coords)[::-1]),
        ):
            starts, start_nearest = nearby_shape_measures(
                candidate_line, from_point, max_distance_m
            )
            ends, end_nearest = nearby_shape_measures(
                candidate_line, to_point, max_distance_m
            )
            nearest_distances.append((start_nearest, end_nearest))
            for start_measure, start_distance in starts:
                for end_measure, end_distance in ends:
                    if end_measure <= start_measure:
                        continue
                    score = (
                        start_distance ** 2 + end_distance ** 2,
                        end_measure - start_measure,
                    )
                    if best is None or score < best[0]:
                        best = (score, candidate_line, start_measure, end_measure)
        if best is None:
            nearest = min(nearest_distances, key=lambda pair: max(pair))
            raise ValueError(
                f"Aucun segment orientable trouvé sur le shape_id pour le trajet "
                f"({nearest[0]:.0f} m et {nearest[1]:.0f} m des arrêts ; "
                f"maximum autorisé : {max_distance_m:.0f} m)."
            )
        return best[1], best[2], best[3]

    for row_idx, ride in ride_rows.iterrows():
        shape_id = trip_shape_ids.get(str(ride["trip_id"]))
        shape_line = shape_lines[shape_id]
        from_point = Point(ride["_from_xy"])
        to_point = Point(ride["_to_xy"])
        shape_line, start_measure, end_measure = ordered_shape_segment(
            shape_line, from_point, to_point, SHAPE_STOP_SNAP_MAX_M
        )
        if shape_line.distance(from_point) > SHAPE_STOP_SNAP_MAX_M or shape_line.distance(to_point) > SHAPE_STOP_SNAP_MAX_M:
            raise ValueError(
                f"Un arrêt est à plus de {SHAPE_STOP_SNAP_MAX_M:.0f} m du tracé GTFS {shape_id} "
                f"pour trip_id {ride['trip_id']}. Vérifiez les données stops/shapes."
            )
        ride_geometry = substring(shape_line, start_measure, end_measure)
        if ride_geometry.geom_type != "LineString" or ride_geometry.length == 0:
            raise ValueError(
                f"Segment vide ou invalide dans shape_id {shape_id} "
                f"pour trip_id {ride['trip_id']}."
            )
        geometry_source = "gtfs_shape"
        geometry_id = register_geometry(
            f"ride:{ride['trip_id']}:{ride['from_stop_id']}:{ride['to_stop_id']}:{start_measure:.3f}:{end_measure:.3f}",
            ride_geometry,
            geometry_source,
        )
        route_steps_df.at[row_idx, "geometry_id"] = geometry_id

    route_steps_df.drop(columns=["_from_xy", "_to_xy"], errors="ignore", inplace=True)
    route_steps_df.sort_values(
        ["traveler_id", "step_order"], inplace=True, ignore_index=True
    )
    route_geometries_gdf = gpd.GeoDataFrame(
        list(geometry_catalog.values()),
        geometry="geometry",
        crs="EPSG:2154"
    ).to_crs("EPSG:4326")
    print(
        f"Itinéraires reconstruits : {route_steps_df['traveler_id'].nunique():,} voyageurs, "
        f"{len(route_steps_df):,} étapes, {len(route_geometries_gdf):,} géométries réutilisables."
    )
    # %% Validate and export JSON journeys
    class LocationModel(BaseModel):
        latitude: float
        longitude: float

    class DestinationModel(LocationModel):
        name: str

    class LegModel(BaseModel):
        mode: str
        start_time: datetime
        end_time: datetime
        from_stop: Optional[str]
        to_stop: Optional[str]
        gtfs_trip_id: Optional[str]
        point_range: Tuple[int, int]

    class JourneyModel(BaseModel):
        journey_id: str
        destination: DestinationModel
        start_time: datetime
        end_time: datetime
        legs: List[LegModel]
        coordinates: List[Tuple[float, float]]
        offsets_s: List[float]

    class JourneyDocumentModel(BaseModel):
        origin: LocationModel
        departure_time: datetime
        journeys: List[JourneyModel]

    paris_tz = ZoneInfo("Europe/Paris")
    service_day_start = datetime.combine(SERVICE_DATE, time.min, tzinfo=paris_tz)
    departure_datetime = service_day_start + timedelta(seconds=float(departure_time))
    route_geometry_by_id = {
        geometry_id: item["geometry"]
        for geometry_id, item in geometry_catalog.items()
    }
    journey_models = []

    for destination_idx, destination_row in destinations_df.iterrows():
        traveler_id = f"destination_{destination_idx}"
        steps = route_steps_df.loc[
            route_steps_df["traveler_id"] == traveler_id
        ].sort_values("step_order")
        if steps.empty:
            continue

        journey_start_s = float(steps.iloc[0]["start_s"])
        coordinates = []
        offsets_s = []
        legs = []

        for _, step in steps.iterrows():
            geometry_id = step["geometry_id"]
            if pd.isna(geometry_id) or geometry_id not in route_geometry_by_id:
                raise ValueError(
                    f"Géométrie manquante pour {traveler_id}, étape {step['step_order']}."
                )
            geometry = route_geometry_by_id[geometry_id]
            if geometry.geom_type == "Point":
                xy = np.asarray([geometry.coords[0], geometry.coords[0]], dtype=float)
            elif geometry.geom_type == "LineString":
                xy = np.asarray(geometry.coords, dtype=float)
                if len(xy) == 1:
                    xy = np.vstack((xy, xy))
            else:
                raise ValueError(
                    f"Type de géométrie non pris en charge ({geometry.geom_type}) "
                    f"pour {traveler_id}, étape {step['step_order']}."
                )

            leg_start_s = float(step["start_s"])
            leg_end_s = float(step["end_s"])
            segment_lengths = np.linalg.norm(np.diff(xy, axis=0), axis=1)
            cumulative_lengths = np.r_[0.0, np.cumsum(segment_lengths)]
            if cumulative_lengths[-1] > 0:
                fractions = cumulative_lengths / cumulative_lengths[-1]
            else:
                fractions = np.linspace(0.0, 1.0, len(xy))
            leg_offsets = (
                leg_start_s - journey_start_s
                + fractions * (leg_end_s - leg_start_s)
            )
            lon, lat = projected_to_wgs84.transform(xy[:, 0], xy[:, 1])
            point_start = len(coordinates)
            coordinates.extend(
                (round(float(x), 6), round(float(y), 6))
                for x, y in zip(lon, lat)
            )
            offsets_s.extend(round(float(value), 1) for value in leg_offsets)
            point_end = len(coordinates)

            def optional_string(value):
                return None if pd.isna(value) else str(value)

            legs.append(LegModel(
                mode=str(step["mode"]),
                start_time=service_day_start + timedelta(seconds=leg_start_s),
                end_time=service_day_start + timedelta(seconds=leg_end_s),
                from_stop=optional_string(step["from_stop_id"]),
                to_stop=optional_string(step["to_stop_id"]),
                gtfs_trip_id=optional_string(step["trip_id"]),
                point_range=(point_start, point_end),
            ))

        if len(coordinates) != len(offsets_s):
            raise ValueError(f"Nombre de coordonnées et d'offsets incohérent pour {traveler_id}.")
        journey_models.append(JourneyModel(
            journey_id=f"j-{len(journey_models) + 1}",
            destination=DestinationModel(
                name=str(destination_row["name"]),
                latitude=float(destination_row["lat"]),
                longitude=float(destination_row["lon"]),
            ),
            start_time=service_day_start + timedelta(seconds=journey_start_s),
            end_time=service_day_start + timedelta(seconds=float(steps.iloc[-1]["end_s"])),
            legs=legs,
            coordinates=coordinates,
            offsets_s=offsets_s,
        ))

    journey_document = JourneyDocumentModel(
        origin=LocationModel(latitude=ORIGIN_LAT, longitude=ORIGIN_LON),
        departure_time=departure_datetime,
        journeys=journey_models,
    )
    Path(FOLDER_EXPORT).mkdir(parents=True, exist_ok=True)
    journeys_json_file = Path(FOLDER_EXPORT) / "journeys.json"
    journey_payload = (
        journey_document.model_dump(mode="json")
        if hasattr(journey_document, "model_dump")
        else journey_document.dict()
    )
    def json_default(value):
        if isinstance(value, datetime):
            return value.isoformat()
        raise TypeError(f"Type non sérialisable : {type(value).__name__}")

    journeys_json_file.write_text(
        json.dumps(journey_payload, indent=2, ensure_ascii=False, default=json_default),
        encoding="utf-8",
    )

    route_geometries_projected = route_geometries_gdf.to_crs("EPSG:2154")
    route_geometry_by_id = dict(zip(
        route_geometries_projected["geometry_id"],
        route_geometries_projected.geometry
    ))

    def traveler_position_at(traveler_id, service_seconds):
        """Retourne la position WGS84 du voyageur à un instant en secondes de service."""
        steps = route_steps_df.loc[
            (route_steps_df["traveler_id"] == traveler_id)
            & (route_steps_df["start_s"] <= service_seconds)
            & (route_steps_df["end_s"] >= service_seconds)
        ]
        if steps.empty:
            return None
        step = steps.iloc[0]
        geometry = route_geometry_by_id[step["geometry_id"]]
        if step["mode"] == "wait" or step["end_s"] <= step["start_s"]:
            point = geometry if geometry.geom_type == "Point" else geometry.interpolate(0)
        else:
            fraction = (service_seconds - step["start_s"]) / (step["end_s"] - step["start_s"])
            point = geometry.interpolate(fraction, normalized=True)
        lon, lat = projected_to_wgs84.transform(point.x, point.y)
        return Point(lon, lat)

    if len(journey_document.journeys) != len(journey_models):
        raise ValueError("La validation Pydantic des trajets a échoué.")
    print(f"JSON des trajets : {journeys_json_file} ({len(journey_models):,} trajets)")
    # %% Report runtime
    t = perf_counter() - started_at
    print(f"Durée totale de calcul : {t:.1f} s")

if __name__ == "__main__":
    main()