

#!/usr/bin/env python3
"""Genera estadísticas y mapas históricos de expansión urbana de Lima."""

import json
import os
import sys
import urllib.request
from pathlib import Path

import ee

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "py"))

from make_data import DIST, YEARS, geojson_rings, voronoi_rings

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

# Extensión de Lima y Callao: [oeste, sur, este, norte].
BOUNDS = [-77.25, -12.58, -76.55, -11.55]

PALETTE = ["ffe9a8", "fdae61", "e8503a", "7f0f2a"]


def initialize_gee():
    """Inicializa Earth Engine con la cuenta de servicio."""
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
            "No se encontró el correo de la cuenta de servicio."
        )

    credentials = ee.ServiceAccountCredentials(email, str(key_path))
    ee.Initialize(credentials, project=PROJECT)

    print(f"Earth Engine conectado: {PROJECT}")


def build_feature_collection():
    """Crea la colección de polígonos distritales."""
    rings = {**voronoi_rings(), **geojson_rings()}
    features = []

    for district in DIST:
        name = district[0]
        district_rings = rings.get(name)

        if not district_rings:
            raise ValueError(
                f"No se encontró geometría para el distrito: {name}"
            )

        polygons = []

        for ring in district_rings:
            # El código original de make_data.py almacena [lat, lon].
            # Earth Engine requiere [lon, lat].
            coordinates = [[lon, lat] for lat, lon in ring]

            if len(coordinates) < 4:
                raise ValueError(
                    f"Anillo incompleto para el distrito {name}"
                )

            polygons.append([coordinates])

        geometry = ee.Geometry.MultiPolygon(
            polygons,
            proj="EPSG:4326",
            geodesic=False,
        )

        features.append(
            ee.Feature(geometry, {"name": name})
        )

    return ee.FeatureCollection(features)


def get_year_image(year):
    """Carga la imagen GHSL correspondiente a una época concreta."""
    image_id = f"{COLLECTION_ID}/{year}"
    image = ee.Image(image_id)

    # Comprueba que la imagen y su banda se pueden consultar.
    band_names = image.bandNames().getInfo()

    if "built_surface" not in band_names:
        raise RuntimeError(
            f"La imagen {image_id} no contiene built_surface."
        )

    return image.select("built_surface")


def download_raster(image, year):
    """Descarga el mapa de superficie construida de una época."""
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

    if not content or not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError(
            f"La descarga del raster de {year} no devolvió un PNG válido."
        )

    (D / f"raster_{year}.png").write_bytes(content)


def main():
    initialize_gee()
    D.mkdir(parents=True, exist_ok=True)

    districts = build_feature_collection()
    built = {district[0]: [] for district in DIST}

    for year in YEARS:
        print(f"Procesando {year}...")

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
            for feature in statistics["features"]
        }

        for name in built:
            value = values.get(name)

            if value is None:
                raise RuntimeError(
                    f"No se obtuvo estadística para {name} en {year}."
                )

            # built_surface está en m²; convertir a km².
            built[name].append(round(float(value) / 1_000_000, 3))

        download_raster(image, year)
        print(f"Época {year}: completada.")

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

    # Escritura temporal para evitar dejar un JSON parcial.
    temporary_file = D / "expansion_gee.tmp"

    temporary_file.write_text(
        json.dumps(output, ensure_ascii=False),
        encoding="utf-8",
    )

    temporary_file.replace(D / "expansion_gee.json")

    print("OK: data/expansion_gee.json generado correctamente.")


if __name__ == "__main__":
    main()

