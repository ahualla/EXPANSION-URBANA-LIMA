


#!/usr/bin/env python3
"""Backend Flask del Geoportal de Expansión Urbana de Lima."""

import json
import os
from pathlib import Path

import ee
from flask import Flask, jsonify, send_from_directory


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

GEE_PROJECT_ID = os.environ.get(
    "GEE_PROJECT_ID",
    "geoportal-gee-peru",
)

GEE_SERVICE_ACCOUNT_FILE = os.environ.get(
    "GEE_SERVICE_ACCOUNT_FILE",
    os.environ.get(
        "GOOGLE_APPLICATION_CREDENTIALS",
        "/etc/secrets/gee-service-account.json",
    ),
)

GEE_SERVICE_ACCOUNT_EMAIL = os.environ.get(
    "GEE_SERVICE_ACCOUNT_EMAIL",
    "geoportal-gee@geoportal-gee-peru.iam.gserviceaccount.com",
)

GEE_COLLECTION = "JRC/GHSL/P2023A/GHS_BUILT_S"

STATIC_FOLDERS = {"assets", "css", "js", "data"}


# ============================================================
# PÁGINA PRINCIPAL
# ============================================================

@app.route("/")
def inicio():
    """Muestra la página principal del geoportal."""
    return send_from_directory(str(BASE_DIR), "index.html")


# ============================================================
# ARCHIVOS ESTÁTICOS
# ============================================================

@app.route("/<folder>/<path:filename>")
def archivos(folder, filename):
    """Sirve archivos estáticos de las carpetas autorizadas."""

    if folder not in STATIC_FOLDERS:
        return jsonify({
            "status": "error",
            "message": "Ruta no permitida",
        }), 404

    return send_from_directory(
        str(BASE_DIR / folder),
        filename,
    )


# ============================================================
# ESTADO DEL SERVIDOR
# ============================================================

@app.route("/api/health")
def health():
    """Comprueba que el backend esté funcionando."""

    return jsonify({
        "status": "ok",
        "message": "Backend Python funcionando",
        "project": "Geoportal de Expansión Urbana de Lima",
    })


# ============================================================
# ESTADO DE LOS DATOS DE EXPANSIÓN URBANA
# ============================================================

@app.route("/api/expansion-status")
def expansion_status():
    """Comprueba si existen los datos generados por Earth Engine."""

    json_path = DATA_DIR / "expansion_gee.json"

    if not json_path.is_file():
        return jsonify({
            "status": "warning",
            "datos_reales_disponibles": False,
            "message": (
                "No se encontró expansion_gee.json. "
                "Todavía no se han generado los datos históricos de GHSL."
            ),
        }), 200

    try:
        with json_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        years = data.get("years", [])
        built = data.get("built", {})
        missing_rasters = [
            year for year in years
            if not (DATA_DIR / f"raster_{year}.png").is_file()
        ]

        return jsonify({
            "status": "ok",
            "datos_reales_disponibles": bool(years and built),
            "coleccion": GEE_COLLECTION,
            "epocas": years,
            "cantidad_distritos": len(built),
            "raster_faltantes": missing_rasters,
            "message": (
                "Datos históricos encontrados."
                if years and built
                else "El archivo existe, pero está incompleto."
            ),
        })

    except (OSError, json.JSONDecodeError, TypeError) as error:
        app.logger.exception("No se pudieron leer los datos de expansión.")

        return jsonify({
            "status": "error",
            "message": "No se pudieron leer los datos de expansión.",
            "tipo_error": type(error).__name__,
        }), 500


# ============================================================
# DIAGNÓSTICO DE CREDENCIALES
# ============================================================

@app.route("/api/gee-diagnostico")
def gee_diagnostico():
    """Comprueba la configuración sin devolver secretos."""

    secret_directory = Path("/etc/secrets")
    credentials_path = Path(GEE_SERVICE_ACCOUNT_FILE)

    return jsonify({
        "status": "ok",
        "project_id_configurado": bool(GEE_PROJECT_ID),
        "cuenta_servicio_configurada": bool(
            GEE_SERVICE_ACCOUNT_EMAIL
        ),
        "archivo_credenciales_existe": credentials_path.is_file(),
        "directorio_secrets_existe": secret_directory.is_dir(),
        "ruta_credenciales": str(credentials_path),
    })


# ============================================================
# CONEXIÓN CON GOOGLE EARTH ENGINE
# ============================================================

@app.route("/api/gee-test")
def gee_test():
    """Autentica Earth Engine y consulta la colección de GHSL."""

    if not GEE_PROJECT_ID:
        return jsonify({
            "status": "error",
            "message": "Falta configurar GEE_PROJECT_ID.",
        }), 503

    credentials_path = Path(GEE_SERVICE_ACCOUNT_FILE)

    if not credentials_path.is_file():
        return jsonify({
            "status": "error",
            "message": "No se encontró el archivo de credenciales.",
            "ruta_comprobada": str(credentials_path),
        }), 503

    try:
        credentials = ee.ServiceAccountCredentials(
            GEE_SERVICE_ACCOUNT_EMAIL,
            str(credentials_path),
        )

        ee.Initialize(
            credentials=credentials,
            project=GEE_PROJECT_ID,
        )

        collection = ee.ImageCollection(GEE_COLLECTION)

        image_count = (
            collection
            .filterDate("2020-01-01", "2021-01-01")
            .limit(1)
            .size()
            .getInfo()
        )

        return jsonify({
            "status": "ok",
            "message": "Google Earth Engine conectado correctamente.",
            "project_id": GEE_PROJECT_ID,
            "cuenta_servicio": GEE_SERVICE_ACCOUNT_EMAIL,
            "coleccion": GEE_COLLECTION,
            "periodo_consultado": {
                "inicio": "2020-01-01",
                "fin": "2021-01-01",
            },
            "imagenes_encontradas": image_count,
        })

    except Exception as error:
        app.logger.exception(
            "Error al conectar con Google Earth Engine."
        )

        return jsonify({
            "status": "error",
            "message": "Falló la conexión con Earth Engine.",
            "tipo_error": type(error).__name__,
        }), 500


# ============================================================
# EJECUCIÓN LOCAL
# ============================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=False,
    )
