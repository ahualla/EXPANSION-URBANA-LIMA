import json
import os
import sys
import urllib.request
from pathlib import Path

import ee

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

sys.path.insert(0, str(ROOT / "py"))


import make_data

# Inicializar los distritos antes de ejecutar Google Earth Engine.
DIST = make_data.build_districts() or make_data.DIST
YEARS = make_data.YEARS
geojson_rings = make_data.geojson_rings
voronoi_rings = make_data.voronoi_rings

D = ROOT / "data"



PROJECT = os.environ.get("GEE_PROJECT_ID", "geoportal-gee-peru")

KEY_FILE = os.environ.get(
    "GEE_SERVICE_ACCOUNT_FILE",
    os.environ.get(
        "GOOGLE_APPLICATION_CREDENTIALS",
        "/etc/secrets/gee-service-account.json",
    ),
)

SERVICE_ACCOUNT = os.environ.get(
    "GEE_SERVICE_ACCOUNT_EMAIL",
    os.environ.get("GEE_SERVICE_ACCOUNT"),
)

COLLECTION_ID = "JRC/GHSL/P2023A/GHS_BUILT_S"

# Extensión de Lima y Callao: oeste, sur, este, norte.
BOUNDS = [-77.25, -12.58, -76.55, -11.55]

PALETTE = ["ffe9a8", "fdae61", "e8503a", "7f0f2a"]


def initialize_gee():
    """Inicializa Google Earth Engine mediante una cuenta de servicio."""
    key_path = Path(KEY_FILE)

    if not key_path.is_file():
        raise FileNotFoundError(
            f"No existe el archivo de credenciales: {key_path}"
        )

    with key_path.open("r", encoding="utf-8") as file:
        key_data = json.load(file)

    email = SERVICE_ACCOUNT or key_data.get("client_email")

    if not email:
        raise RuntimeError(
            "No se encontró client_email en las credenciales."
        )

    credentials = ee.ServiceAccountCredentials(
        email,
        str(key_path),
    )

    ee.Initialize(credentials, project=PROJECT)

    print(f"Earth Engine conectado correctamente: {PROJECT}")


def validate_ring(ring, district_name):
    """
    Valida un anillo en coordenadas GeoJSON [longitud, latitud].
    No invierte el orden de las coordenadas.
    """
    if not isinstance(ring, (list, tuple)) or len(ring) < 4:
        raise ValueError(
            f"El anillo de {district_name} tiene menos de cuatro puntos."
        )

    coordinates = []

    for point in ring:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            raise ValueError(
                f"Coordenada inválida en el distrito {district_name}."
            )

        lon = float(point[0])
        lat = float(point[1])

        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError(
                f"Coordenada fuera de rango en {district_name}: "
                f"{[lon, lat]}"
            )

        coordinates.append([lon, lat])

    if coordinates[0] != coordinates[-1]:
        coordinates.append(coordinates[0])

    if len(coordinates) < 4:
        raise ValueError(
            f"El anillo de {district_name} no es un polígono válido."
        )

    return coordinates


def build_feature_collection():
    """Construye los polígonos que se utilizarán en las estadísticas."""
    real_rings = geojson_rings()
    fallback_rings = voronoi_rings()
    features = []

    if not DIST:
        raise ValueError(
            "No hay distritos en DIST. Revisa data/distritos.geojson "
            "y la definición de DIST en make_data.py."
        )

    for district in DIST:
        name = district[0]

        # Prioriza los límites distritales reales.
        district_rings = real_rings.get(name)

        if not district_rings:
            district_rings = fallback_rings.get(name)

        if not district_rings:
            raise ValueError(
                f"No se encontró geometría para el distrito: {name}"
            )

        polygons = []

        for ring in district_rings:
            coordinates = validate_ring(ring, name)

            # Cada polígono contiene su anillo exterior.
            polygons.append([coordinates])

        geometry = ee.Geometry.MultiPolygon(
            polygons,
            proj="EPSG:4326",
            geodesic=False,
        )

        features.append(
            ee.Feature(geometry, {"name": name})
        )

    print(f"Distritos preparados: {len(features)}")

    return ee.FeatureCollection(features)


def get_year_image(year):
    """Obtiene la imagen GHSL correspondiente al año solicitado."""
    image_id = f"{COLLECTION_ID}/{year}"
    image = ee.Image(image_id)

    band_names = image.bandNames().getInfo()

    if "built_surface" not in band_names:
        raise RuntimeError(
            f"La imagen {image_id} no contiene la banda built_surface. "
            f"Bandas encontradas: {band_names}"
        )

    return image.select("built_surface")


def download_raster(image, year):
    """Descarga el mapa PNG de superficie construida para un año."""
    region = ee.Geometry.Rectangle(
        BOUNDS,
        proj="EPSG:4326",
        geodesic=False,
    )

    url = image.selfMask().getThumbURL({
        "region": region,
        "dimensions": 1100,
        "format": "png",
        "min": 0,
        "max": 6000,
        "palette": PALETTE,
    })

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "GeoportalExpansionUrbana/1.0"},
    )

    with urllib.request.urlopen(request, timeout=180) as response:
        content = response.read()

    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError(
            f"La descarga del raster de {year} no devolvió un PNG válido."
        )

    raster_path = DATA_DIR / f"raster_{year}.png"
    raster_path.write_bytes(content)

    print(f"Raster guardado: {raster_path.name}")


def main():
    initialize_gee()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    districts = build_feature_collection()
    built = {district[0]: [] for district in DIST}

    for year in YEARS:
        print(f"Procesando año {year}...")

        image = get_year_image(year)

        statistics = image.reduceRegions(
            collection=districts,
            reducer=ee.Reducer.sum(),
            scale=100,
            tileScale=4,
        ).getInfo()

        values = {
            feature["properties"]["name"]:
                feature["properties"].get("sum")
            for feature in statistics.get("features", [])
        }

        for name in built:
            value = values.get(name)

            if value is None:
                raise RuntimeError(
                    f"No se obtuvo una estadística válida para "
                    f"{name} en {year}."
                )

            # built_surface está en m²: convertir a km².
            built[name].append(
                round(float(value) / 1_000_000, 3)
            )

        download_raster(image, year)
        print(f"Año {year} completado.")

    output = {
        "years": YEARS,
        "bbox": [
            [BOUNDS[1], BOUNDS[0]],
            [BOUNDS[3], BOUNDS[2]],
        ],
        "built": built,
        "source": COLLECTION_ID,
        "unit": "km2",
    }

    # Solo publica el JSON cuando todos los años se procesaron.
    temporary_file = DATA_DIR / "expansion_gee.tmp"
    final_file = DATA_DIR / "expansion_gee.json"

    temporary_file.write_text(
        json.dumps(output, ensure_ascii=False),
        encoding="utf-8",
    )

    temporary_file.replace(final_file)

    print(
        f"OK: {final_file.relative_to(ROOT)} generado correctamente."
    )


if __name__ == "__main__":
    main()

