

import base64
import datetime as dt
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
YEARS = list(range(1975, 2021, 5))

GEOJSON_CANDIDATES = [
    D / "distritos.geojson",
    ROOT / "distritos.geojson",
    ROOT / "data" / "distritos.geojson",
]

def find_geojson():
    for path in GEOJSON_CANDIDATES:
        if path.is_file():
            return path
    return None


def normalize_name(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def feature_name(feature):
    props = feature.get("properties") or {}

    for key in (
        "name", "NAME", "nombre", "NOMBRE",
        "distrito", "DISTRITO", "NOMBDIST",
        "NAME_2", "name_2", "DIST"
    ):
        value = props.get(key)
        if value:
            return normalize_name(value)

    return ""


def polygon_parts(geometry):
    if not geometry:
        return []

    kind = geometry.get("type")
    coords = geometry.get("coordinates") or []

    if kind == "Polygon":
        return [coords]

    if kind == "MultiPolygon":
        return coords

    return []


def outer_rings(geometry):
    """Devuelve los anillos exteriores en coordenadas GeoJSON [lon, lat]."""
    result = []

    for polygon in polygon_parts(geometry):
        if polygon and polygon[0]:
            result.append(polygon[0])

    return result


def ring_centroid(ring):
    points = [
        (float(p[0]), float(p[1]))
        for p in ring
        if isinstance(p, (list, tuple)) and len(p) >= 2
    ]

    if not points:
        return None

    # Centro aproximado por promedio de vértices.
    lon = sum(p[0] for p in points) / len(points)
    lat = sum(p[1] for p in points) / len(points)

    return lat, lon


def ring_area_km2(ring):
    """Área aproximada del anillo en km²."""
    points = [
        (float(p[0]), float(p[1]))
        for p in ring
        if isinstance(p, (list, tuple)) and len(p) >= 2
    ]

    if len(points) < 3:
        return 0.0

    lat0 = sum(lat for _, lat in points) / len(points)
    km_lon = 111.32 * math.cos(math.radians(lat0))
    km_lat = 110.574

    xy = [(lon * km_lon, lat * km_lat) for lon, lat in points]

    area = 0.0
    for i in range(len(xy)):
        x1, y1 = xy[i]
        x2, y2 = xy[(i + 1) % len(xy)]
        area += x1 * y2 - x2 * y1

    return abs(area) / 2.0


def load_features():
    path = find_geojson()

    if path is None:
        return []

    content = json.loads(path.read_text(encoding="utf-8"))

    if content.get("type") == "FeatureCollection":
        features = content.get("features", [])
    elif content.get("type") == "Feature":
        features = [content]
    else:
        raise ValueError(
            f"{path} no contiene un GeoJSON Feature o FeatureCollection válido."
        )

    return [
        feature for feature in features
        if feature.get("geometry") and feature_name(feature)
    ]


def geojson_rings():
    """Carga los límites reales disponibles en distritos.geojson."""
    result = {}

    for feature in load_features():
        name = feature_name(feature)
        rings = outer_rings(feature.get("geometry") or {})

        if rings:
            # Una lista de anillos exteriores por distrito.
            result[name] = rings

    return result


def voronoi_rings():
    """
    Crea polígonos cuadrados referenciales alrededor de los centroides.
    Solo se usan si no hay geometría distrital disponible.
    No son límites administrativos oficiales.
    """
    result = {}

    for name, lat, lon, area, fraction, t0, slope in DIST:
        # Tamaño aproximado según el área; limitado para evitar polígonos enormes.
        radius_km = min(5.0, max(0.8, math.sqrt(max(area, 1.0)) / 2.0))
        dlat = radius_km / 110.574
        dlon = radius_km / max(
            20.0, 111.32 * math.cos(math.radians(lat))
        )

        result[name] = [[
            [lon - dlon, lat - dlat],
            [lon + dlon, lat - dlat],
            [lon + dlon, lat + dlat],
            [lon - dlon, lat + dlat],
            [lon - dlon, lat - dlat],
        ]]

    return result


def build_districts():
    """Construye DIST a partir de las geometrías disponibles."""
    districts = []

    for feature in load_features():
        name = feature_name(feature)
        rings = outer_rings(feature.get("geometry") or {})

        if not rings:
            continue

        centroid = ring_centroid(rings[0])
        if centroid is None:
            continue

        lat, lon = centroid
        area = sum(ring_area_km2(ring) for ring in rings)

        if area <= 0:
            area = 1.0

        # Parámetros ilustrativos usados únicamente si no hay datos GHSL.
        districts.append((
            name,
            lat,
            lon,
            area,
            0.45,
            2000,
            10,
        ))

    return districts


DIST = build_districts()


def main():
    real = geojson_rings()
    vor = voronoi_rings()

    if not DIST:
        raise FileNotFoundError(
            "No se encontraron distritos. Añade un GeoJSON de distritos "
            "en data/distritos.geojson y verifica que sus propiedades "
            "incluyan el nombre de cada distrito."
        )

    gee_file = D / "expansion_gee.json"
    gee = None

    if gee_file.exists():
        candidate = json.loads(gee_file.read_text(encoding="utf-8"))

        years_candidate = candidate.get("years")
        built_candidate = candidate.get("built")

        if not isinstance(years_candidate, list) or not years_candidate:
            raise ValueError("expansion_gee.json no contiene años válidos.")

        if not isinstance(built_candidate, dict):
            raise ValueError("expansion_gee.json no contiene built válido.")

        missing = [
            name for name, *_ in DIST
            if name not in built_candidate
            or not isinstance(built_candidate[name], list)
            or len(built_candidate[name]) != len(years_candidate)
        ]

        if missing:
            raise ValueError(
                "Faltan datos reales o épocas para estos distritos: "
                + ", ".join(missing)
            )

        gee = candidate

    years = gee["years"] if gee else YEARS
    bbox = gee.get("bbox") if gee else None

    rasters_complete = bool(
        gee
        and bbox
        and all((D / f"raster_{year}.png").is_file() for year in years)
    )

    rasters = None
    if rasters_complete:
        rasters = {
            year: "data:image/png;base64," + base64.b64encode(
                (D / f"raster_{year}.png").read_bytes()
            ).decode("ascii")
            for year in years
        }

    deps = []

    for name, lat, lon, area, fraction, t0, slope in DIST:
        if gee:
            built = gee["built"][name]
        else:
            built = [
                round(
                    area * fraction
                    / (1 + math.exp(-(year - t0) / slope)),
                    3,
                )
                for year in years
            ]

        deps.append({
            "name": name,
            "lat": lat,
            "lon": lon,
            "area": round(area, 3),
            "rings": real.get(name) or vor[name],
            "built": built,
        })

    data = {
        "demo": not bool(gee),
        "updated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "years": years,
        "bbox": bbox,
        "rasters": rasters,
        "geom": (
            "reales (distritos.geojson)"
            if real
            else "aproximados (zonas referenciales)"
        ),
        "source": (
            "JRC GHSL GHS-BUILT-S P2023A"
            if gee
            else "SERIE DEMO ilustrativa; no son datos observados"
        ),
        "deps": deps,
    }

    D.mkdir(parents=True, exist_ok=True)

    (D / "data.json").write_text(
        json.dumps(
            {key: value for key, value in data.items() if key != "rasters"},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    (D / "data.js").write_text(
        "window.LIMA_DATA = "
        + json.dumps(data, ensure_ascii=False)
        + ";",
        encoding="utf-8",
    )

    print(
        "OK | "
        + ("datos GHSL reales" if gee else "DEMO ilustrativa")
        + " | límites "
        + data["geom"]
    )


if __name__ == "__main__":
    main()

