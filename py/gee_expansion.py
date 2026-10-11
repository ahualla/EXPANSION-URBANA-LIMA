
#!/usr/bin/env python3
"""Genera datos de expansión urbana de Lima usando Google Earth Engine.

Entradas:
    py/make_data.py (define DIST, YEARS, D, etc.)

Salidas:
    data/expansion_gee.json
    data/raster_AAAA.png

Variables de entorno en Render:
    GEE_PROJECT_ID=geoportal-gee-peru
    GOOGLE_APPLICATION_CREDENTIALS=/etc/secrets/gee-service-account.json
"""

import json
import os
import sys
import urllib.request
from pathlib import Path

import ee

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "py"))

from make_data import D, DIST, YEARS, geojson_rings, voronoi_rings

PROJECT = os.environ.get("GEE_PROJECT_ID", "geoportal-gee-peru")
KEY_FILE = os.environ.get(
    "GOOGLE_APPLICATION_CREDENTIALS",
    "/etc/secrets/gee-service-account.json",
)
SERVICE_ACCOUNT = os.environ.get("GEE_SERVICE_ACCOUNT")

# Extensión geográfica del área de análisis: Lima y Callao.
BOUNDS = [-77.25, -12.58, -76.55, -11.55]

COLLECTION_ID = "JRC/GHSL/P2023A/GHS_BUILT_S"


def initialize_gee():
    """Inicializa Earth Engine usando las credenciales de Render."""
    if not Path(KEY_FILE).is_file():
        raise FileNotFoundError(
            f"No se encontró el archivo de credenciales: {KEY_FILE}. "
            "Comprueba la configuración Secret Files de Render."
        )

    import json as json_module

    with open(KEY_FILE, "r", encoding="utf-8") as f:
        credentials_data = json_module.load(f)

    email = SERVICE_ACCOUNT or credentials_data.get("client_email")
    if not email:
        raise RuntimeError(
            "No se encontró client_email en el archivo de credenciales."
        )

    credentials = ee.ServiceAccountCredentials(email, KEY_FILE)
    ee.Initialize(credentials, project=PROJECT)

    print(f"Earth Engine conectado. Proyecto: {PROJECT}")


def build_feature_collection():
    """Construye los polígonos de análisis por distrito."""
    rings = {**voronoi_rings(), **geojson_rings()}
    features = []

    for district in DIST:
        name = district[0]
        district_rings = rings.get(name)

        if not district_rings:
            print(f"Aviso: sin geometría para {name}; se omite.")
            continue

        polygons = []
        for ring in district_rings:
            # Los anillos del archivo de origen están en [latitud, longitud].
            coordinates = [[lon, lat] for lat, lon in ring]
            if len(coordinates) >= 3:
                polygons.append([coordinates])

        if not polygons:
            continue

        geometry = ee.Geometry.MultiPolygon(polygons, None, False)
        features.append(
            ee.Feature(geometry, {"name": name})
        )

    if not features:
        raise RuntimeError("No se pudieron crear los polígonos de análisis.")

    return ee.FeatureCollection(features)


def main():
    initialize_gee()
    D.mkdir(parents=True, exist_ok=True)

    districts = build_feature_collection()
    collection = ee.ImageCollection(COLLECTION_ID)

    image_count = collection.size().getInfo()
    if not image_count:
        raise RuntimeError(
            f"La colección {COLLECTION_ID} no contiene imágenes accesibles."
        )

    region = ee.Geometry.Rectangle(BOUNDS)
    built_by_district = {district[0]: [] for district in DIST}

    for year in YEARS:
        print(f"Procesando época {year}...")

        annual = collection.filter(
            ee.Filter.calendarRange(year, year, "year")
        )

        if annual.size().getInfo() == 0:
            raise RuntimeError(
                f"No se encontró una imagen de GHSL para {year}. "
                "Verifica las épocas disponibles en la colección."
            )

        image = ee.Image(annual.first()).select("built_surface")

        # Suma la superficie construida por distrito.
        stats = image.reduceRegions(
            collection=districts,
            reducer=ee.Reducer.sum(),
            scale=100,
            tileScale=4,
        ).getInfo()

        values = {
            feature["properties"]["name"]: feature["properties"].get("sum")
            for feature in stats["features"]
        }

        for name in built_by_district:
            value = values.get(name)
            # La banda built_surface se expresa en m².
            built_by_district[name].append(
                round(float(value) / 1_000_000, 3)
                if value is not None
                else None
            )

        thumbnail_url = image.selfMask().getThumbURL({
            "region": region,
            "dimensions": 1100,
            "format": "png",
            "min": 0,
            "max": 6000,
            "palette": [
                "ffe9a8",
                "fdae61",
                "e8503a",
                "7f0f2a",
            ],
        })

        request = urllib.request.Request(
            thumbnail_url,
            headers={"User-Agent": "GeoportalExpansionUrbana/1.0"},
        )

        with urllib.request.urlopen(request, timeout=180) as response:
            content = response.read()

        if not content:
            raise RuntimeError(f"El raster de {year} llegó vacío.")

        (D / f"raster_{year}.png").write_bytes(content)
        print(f"Época {year}: raster y estadísticas generados.")

    output = {
        "years": YEARS,
        "bbox": [
            [BOUNDS[1], BOUNDS[0]],
            [BOUNDS[3], BOUNDS[2]],
        ],
        "built": built_by_district,
    }

    (D / "expansion_gee.json").write_text(
        json.dumps(output, ensure_ascii=False),
        encoding="utf-8",
    )

    print("Proceso terminado: data/expansion_gee.json")


if __name__ == "__main__":
    main()
