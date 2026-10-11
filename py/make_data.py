

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
    D / "distrito.json",
    ROOT / "distritos.geojson",
    ROOT / "distrito.json",
]


def find_geojson():
    """Encuentra el archivo GeoJSON de los distritos."""
    for path in GEOJSON_CANDIDATES:
        if path.is_file():
            return path
    return None


def normalize_name(value):
    """Normaliza los nombres para evitar espacios inconsistentes."""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def feature_name(feature):
    """Identifica el nombre del distrito en distintas estructuras GeoJSON."""
    props = feature.get("properties") or {}

    preferred_keys = (
        "_geoportal_name",
        "name", "NAME", "Name",
        "nombre", "NOMBRE", "Nombre",
        "distrito", "DISTRITO", "Distrito",
        "NOMBDIST", "NOM_DIST", "NOMB_DIST",
        "NAME_2", "name_2", "NAME_3",
        "DIST", "DISTRICT", "district",
        "nom_dist", "ubigeo_name",
    )

    for key in preferred_keys:
        value = props.get(key)
        if value is not None and str(value).strip():
            return normalize_name(value)

    # Buscar campos que probablemente contengan el nombre.
    for key, value in props.items():
        key_lower = str(key).lower()
        if (
            value is not None
            and isinstance(value, (str, int))
            and str(value).strip()
            and any(word in key_lower for word in (
                "dist", "nombre", "name", "nom_"
            ))
        ):
            return normalize_name(value)

    # Último recurso: usar el identificador del elemento.
    feature_id = feature.get("id")
    if feature_id is not None:
        return f"Distrito {normalize_name(feature_id)}"

    return normalize_name(props.get("_geoportal_fallback", ""))


def polygon_parts(geometry):
    """Devuelve los polígonos de una geometría GeoJSON."""
    if not isinstance(geometry, dict):
        return []

    kind = geometry.get("type")
    coords = geometry.get("coordinates") or []

    if kind == "Polygon":
        return [coords]

    if kind == "MultiPolygon":
        return coords

    return []


def outer_rings(geometry):
    """Obtiene anillos exteriores en orden GeoJSON [longitud, latitud]."""
    result = []

    for polygon in polygon_parts(geometry):
        if polygon and polygon[0]:
            result.append(polygon[0])

    return result


def ring_points(ring):
    """Convierte las coordenadas de un anillo en puntos numéricos válidos."""
    points = []

    for point in ring or []:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue

        try:
            lon = float(point[0])
            lat = float(point[1])
        except (TypeError, ValueError):
            continue

        if (
            math.isfinite(lon)
            and math.isfinite(lat)
            and -180 <= lon <= 180
            and -90 <= lat <= 90
        ):
            points.append((lon, lat))

    return points


def ring_centroid(ring):
    """Calcula un centro aproximado a partir de los vértices."""
    points = ring_points(ring)

    if not points:
        return None

    lon = sum(p[0] for p in points) / len(points)
    lat = sum(p[1] for p in points) / len(points)

    return lat, lon


def ring_area_km2(ring):
    """Estima el área de un anillo en kilómetros cuadrados."""
    points = ring_points(ring)

    if len(points) < 3:
        return 0.0

    lat0 = sum(lat for _, lat in points) / len(points)
    km_lon = 111.32 * math.cos(math.radians(lat0))
    km_lat = 110.574

    xy = [
        (lon * km_lon, lat * km_lat)
        for lon, lat in points
    ]

    area = 0.0

    for i in range(len(xy)):
        x1, y1 = xy[i]
        x2, y2 = xy[(i + 1) % len(xy)]
        area += x1 * y2 - x2 * y1

    return abs(area) / 2.0


def load_features():
    """Lee y valida las entidades del GeoJSON."""
    path = find_geojson()

    if path is None:
        expected = D / "distritos.geojson"
        raise FileNotFoundError(
            f"No se encontró el GeoJSON. Ruta esperada: {expected}"
        )

    try:
        content = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"No se pudo leer el GeoJSON {path}: {exc}"
        ) from exc

    if content.get("type") == "FeatureCollection":
        features = content.get("features") or []
    elif content.get("type") == "Feature":
        features = [content]
    else:
        raise ValueError(
            f"{path} no contiene un GeoJSON FeatureCollection válido."
        )

    valid = []

    for index, feature in enumerate(features, start=1):
        if not isinstance(feature, dict):
            continue

        geometry = feature.get("geometry") or {}
        rings = outer_rings(geometry)

        if not rings or not any(ring_points(ring) for ring in rings):
            continue

        props = feature.setdefault("properties", {})

        if not isinstance(props, dict):
            props = {}
            feature["properties"] = props

        # Conservar el nombre original cuando existe.
        name = feature_name(feature)

        if not name:
            name = f"Distrito {index:03d}"

        props["_geoportal_name"] = name
        valid.append(feature)

    print(f"GeoJSON encontrado: {path}")
    print(f"Elementos originales: {len(features)}")
    print(f"Elementos con geometría válida: {len(valid)}")

    if features:
        first_props = features[0].get("properties") or {}
        print(f"Campos del GeoJSON: {list(first_props.keys())}")

    if not valid:
        raise ValueError(
            "El GeoJSON no contiene polígonos válidos. "
            "Verifica sus geometrías y coordenadas."
        )

    names = [feature_name(feature) for feature in valid]

    if len(names) != len(set(names)):
        raise ValueError(
            "El GeoJSON contiene nombres de distrito duplicados. "
            "Cada polígono debe tener un nombre único."
        )

    return valid


def geojson_rings():
    """Carga los límites originales de los distritos."""
    result = {}

    for feature in load_features():
        name = feature_name(feature)
        rings = outer_rings(feature.get("geometry") or {})

        if rings:
            result[name] = rings

    return result


def build_districts():
    """Construye la lista DIST a partir del GeoJSON."""
    districts = []

    for feature in load_features():
        name = feature_name(feature)
        rings = outer_rings(feature.get("geometry") or {})

        if not rings:
            continue

        # Centro del primer polígono.
        centroid = ring_centroid(rings[0])

        if centroid is None:
            continue

        lat, lon = centroid

        # Sumar las áreas aproximadas de los polígonos exteriores.
        area = sum(ring_area_km2(ring) for ring in rings)

        if area <= 0:
            area = 1.0

        # Estos parámetros solo sirven para la serie DEMO.
        districts.append((
            name,
            lat,
            lon,
            area,
            0.45,
            2000,
            10,
        ))

    print(f"Distritos construidos: {len(districts)}")
    return districts


# Se construye al importar el módulo.
DIST = build_districts()


def voronoi_rings():
    """
    Genera cuadrados aproximados como respaldo.
    No representan límites administrativos oficiales.
    """
    result = {}

    for name, lat, lon, area, fraction, t0, slope in DIST:
        radius_km = min(
            5.0,
            max(0.8, math.sqrt(max(area, 1.0)) / 2.0),
        )

        dlat = radius_km / 110.574
        dlon = radius_km / max(
            20.0,
            111.32 * math.cos(math.radians(lat)),
        )

        result[name] = [[
            [lon - dlon, lat - dlat],
            [lon + dlon, lat - dlat],
            [lon + dlon, lat + dlat],
            [lon - dlon, lat + dlat],
            [lon - dlon, lat - dlat],
        ]]

    return result


def main():
    real = geojson_rings()
    vor = voronoi_rings()

    if not DIST:
        raise ValueError(
            "No se encontraron distritos válidos en distritos.geojson."
        )

    gee_file = D / "expansion_gee.json"
    gee = None

    if gee_file.exists():
        candidate = json.loads(
            gee_file.read_text(encoding="utf-8")
        )

        years_candidate = candidate.get("years")
        built_candidate = candidate.get("built")

        if (
            not isinstance(years_candidate, list)
            or not years_candidate
        ):
            raise ValueError(
                "expansion_gee.json no contiene años válidos."
            )

        if not isinstance(built_candidate, dict):
            raise ValueError(
                "expansion_gee.json no contiene un objeto built válido."
            )

        missing = [
            name
            for name, *_ in DIST
            if (
                name not in built_candidate
                or not isinstance(built_candidate[name], list)
                or len(built_candidate[name]) != len(years_candidate)
            )
        ]

        if missing:
            raise ValueError(
                "Faltan datos GHSL para estos distritos: "
                + ", ".join(missing)
            )

        gee = candidate

    years = gee["years"] if gee else YEARS
    bbox = gee.get("bbox") if gee else None

    rasters_complete = bool(
        gee
        and bbox
        and all(
            (D / f"raster_{year}.png").is_file()
            for year in years
        )
    )

    rasters = None

    if rasters_complete:
        rasters = {
            year: "data:image/png;base64,"
            + base64.b64encode(
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

    json_without_rasters = {
        key: value
        for key, value in data.items()
        if key != "rasters"
    }

    (D / "data.json").write_text(
        json.dumps(json_without_rasters, ensure_ascii=False),
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
