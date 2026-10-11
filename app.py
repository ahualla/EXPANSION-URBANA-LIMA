```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Backend Flask del Geoportal de Expansión Urbana de Lima.

Funciones:
- Servir la página principal.
- Servir archivos estáticos.
- Comprobar el estado del servidor.
- Diagnosticar los archivos de datos.
- Comprobar las credenciales de Google Earth Engine.
- Probar la conexión con la colección GHSL.
- Verificar la disponibilidad de los datos históricos.
"""

import json
import os
from pathlib import Path

import ee
from flask import Flask, jsonify, send_from_directory


# ============================================================
# 1. CONFIGURACIÓN GENERAL
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

STATIC_FOLDERS = {
    "assets",
    "css",
    "js",
    "data",
}


# ============================================================
# 2. PÁGINA PRINCIPAL
# ============================================================

@app.route("/", methods=["GET"])
def inicio():
    """Muestra la página principal del geoportal."""

    index_path = BASE_DIR / "index.html"

    if not index_path.is_file():
        return jsonify({
            "status": "error",
            "message": "No se encontró el archivo index.html.",
        }), 404

    return send_from_directory(
        str(BASE_DIR),
        "index.html",
    )


# ============================================================
# 3. ARCHIVOS ESTÁTICOS
# ============================================================

@app.route("/<folder>/<path:filename>", methods=["GET"])
def archivos(folder, filename):
    """Sirve archivos de las carpetas autorizadas."""

    if folder not in STATIC_FOLDERS:
        return jsonify({
            "status": "error",
            "message": "Ruta no permitida",
        }), 404

    directory = BASE_DIR / folder

    if not directory.is_dir():
        return jsonify({
            "status": "error",
            "message": "No existe la carpeta solicitada.",
        }), 404

    return send_from_directory(
        str(directory),
        filename,
    )


# ============================================================
# 4. ESTADO DEL SERVIDOR
# ============================================================

@app.route("/api/health", methods=["GET"])
def health():
    """Comprueba que el backend esté funcionando."""

    return jsonify({
        "status": "ok",
        "message": "Backend Python funcionando.",
        "project": "Geoportal de Expansión Urbana de Lima",
    })


# ============================================================
# 5. DIAGNÓSTICO DE ARCHIVOS
# ============================================================

@app.route("/api/expansion-debug", methods=["GET"])
def expansion_debug():
    """
    Comprueba la existencia de los archivos del geoportal.

    No modifica archivos ni ejecuta procesos de Earth Engine.
    """

    expected_files = [
        "expansion_gee.json",
        "data.js",
        "data.json",
        "raster_1975.png",
        "raster_1980.png",
        "raster_1985.png",
        "raster_1990.png",
        "raster_1995.png",
        "raster_2000.png",
        "raster_2005.png",
        "raster_2010.png",
        "raster_2015.png",
        "raster_2020.png",
    ]

    files_status = {
        filename: (DATA_DIR / filename).is_file()
        for filename in expected_files
    }

    return jsonify({
        "status": "ok",
        "directorio_data": str(DATA_DIR),
        "data_dir_existe": DATA_DIR.is_dir(),
        "index_html_existe": (BASE_DIR / "index.html").is_file(),
        "expansion_gee_existe": (
            DATA_DIR / "expansion_gee.json"
        ).is_file(),
        "data_js_existe": (DATA_DIR / "data.js").is_file(),
        "data_json_existe": (DATA_DIR / "data.json").is_file(),
        "archivos": files_status,
    })


# ============================================================
# 6. ESTADO DE LOS DATOS DE EXPANSIÓN URBANA
# ============================================================

@app.route("/api/expansion-status", methods=["GET"])
def expansion_status():
    """
    Comprueba si existen los datos históricos de expansión urbana.
    """

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
        with json_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        years = data.get("years", [])
        built = data.get("built", {})

        valid_structure = (
            isinstance(years, list)
            and len(years) > 0
            and isinstance(built, dict)
            and len(built) > 0
        )

        missing_rasters = [
            year
            for year in years
            if not (
                DATA_DIR / f"raster_{year}.png"
            ).is_file()
        ]

        return jsonify({
            "status": "ok" if valid_structure else "warning",
            "datos_reales_disponibles": valid_structure,
            "coleccion": GEE_COLLECTION,
            "epocas": years,
            "cantidad_distritos": (
                len(built)
                if isinstance(built, dict)
                else 0
            ),
            "raster_faltantes": missing_rasters,
            "message": (
                "Se encontró el archivo con datos históricos."
                if valid_structure
                else "El archivo existe, pero su estructura está incompleta."
            ),
        }), 200

    except (
        OSError,
        json.JSONDecodeError,
        AttributeError,
        TypeError,
    ) as error:

        app.logger.exception(
            "No se pudieron leer los datos de expansión."
        )

        return jsonify({
            "status": "error",
            "message": "No se pudieron leer los datos de expansión.",
            "tipo_error": type(error).__name__,
        }), 500


# ============================================================
# 7. DIAGNÓSTICO DE CREDENCIALES
# ============================================================

@app.route("/api/gee-diagnostico", methods=["GET"])
def gee_diagnostico():
    """
    Comprueba la configuración de Earth Engine.

    Nunca devuelve el contenido del archivo de credenciales.
    """

    credentials_path = Path(
        GEE_SERVICE_ACCOUNT_FILE
    )

    return jsonify({
        "status": "ok",
        "project_id_configurado": bool(
            GEE_PROJECT_ID
        ),
        "cuenta_servicio_configurada": bool(
            GEE_SERVICE_ACCOUNT_EMAIL
        ),
        "archivo_credenciales_existe": (
            credentials_path.is_file()
        ),
        "directorio_secrets_existe": (
            Path("/etc/secrets").is_dir()
        ),
        "ruta_credenciales": str(
            credentials_path
        ),
    })


# ============================================================
# 8. PRUEBA DE CONEXIÓN CON GOOGLE EARTH ENGINE
# ============================================================

@app.route("/api/gee-test", methods=["GET"])
def gee_test():
    """
    Autentica Earth Engine y consulta la colección GHSL.

    Esta ruta solo prueba la conexión; no genera los mapas
    ni el archivo expansion_gee.json.
    """

    if not GEE_PROJECT_ID:
        return jsonify({
            "status": "error",
            "message": "Falta configurar GEE_PROJECT_ID.",
        }), 503

    credentials_path = Path(
        GEE_SERVICE_ACCOUNT_FILE
    )

    if not credentials_path.is_file():
        return jsonify({
            "status": "error",
            "message": "No se encontró el archivo de credenciales.",
            "ruta_comprobada": str(
                credentials_path
            ),
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

        collection = ee.ImageCollection(
            GEE_COLLECTION
        )

        image_count = (
            collection
            .filterDate(
                "2020-01-01",
                "2021-01-01",
            )
            .limit(1)
            .size()
            .getInfo()
        )

        return jsonify({
            "status": "ok",
            "message": (
                "Google Earth Engine conectado correctamente."
            ),
            "project_id": GEE_PROJECT_ID,
            "cuenta_servicio": (
                GEE_SERVICE_ACCOUNT_EMAIL
            ),
            "coleccion": GEE_COLLECTION,
            "periodo_consultado": {
                "inicio": "2020-01-01",
                "fin": "2021-01-01",
            },
            "imagenes_encontradas": image_count,
        }), 200

    except Exception as error:
        app.logger.exception(
            "Error al conectar con Google Earth Engine."
        )

        return jsonify({
            "status": "error",
            "message": (
                "Falló la conexión con Earth Engine."
            ),
            "tipo_error": type(error).__name__,
        }), 500


# ============================================================
# 9. MANEJO DE ERRORES HTTP
# ============================================================

@app.errorhandler(404)
def not_found(error):
    """Devuelve una respuesta JSON para rutas inexistentes."""

    return jsonify({
        "status": "error",
        "message": "La ruta o el recurso solicitado no existe.",
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Devuelve una respuesta JSON para errores internos."""

    app.logger.exception(
        "Se produjo un error interno en el servidor."
    )

    return jsonify({
        "status": "error",
        "message": "Se produjo un error interno en el servidor.",
    }), 500


# ============================================================
# 10. EJECUCIÓN LOCAL
# ============================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get("PORT", "5000")
        ),
        debug=False,
    )
```
