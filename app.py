

import os
import ee

from flask import Flask, jsonify, send_from_directory


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

GEE_PROJECT_ID = os.environ.get("GEE_PROJECT_ID")

GEE_SERVICE_ACCOUNT_FILE = os.environ.get(
    "GEE_SERVICE_ACCOUNT_FILE",
    "/etc/secrets/gee-service-account.json"
)

GEE_SERVICE_ACCOUNT_EMAIL = os.environ.get(
    "GEE_SERVICE_ACCOUNT_EMAIL",
    "geoportal-gee@geoportal-gee-peru.iam.gserviceaccount.com"
)


# ============================================================
# PÁGINA PRINCIPAL
# ============================================================

@app.route("/")
def inicio():
    """Muestra el geoportal."""

    return send_from_directory(
        BASE_DIR,
        "index.html"
    )


# ============================================================
# ARCHIVOS ESTÁTICOS
# ============================================================

@app.route("/<folder>/<path:filename>")
def archivos(folder, filename):
    """Sirve CSS, JavaScript, imágenes y datos."""

    carpetas_permitidas = {
        "assets",
        "css",
        "js",
        "data"
    }

    if folder not in carpetas_permitidas:
        return jsonify({
            "status": "error",
            "message": "Ruta no permitida"
        }), 404

    directorio = os.path.join(
        BASE_DIR,
        folder
    )

    return send_from_directory(
        directorio,
        filename
    )


# ============================================================
# ESTADO DEL SERVIDOR
# ============================================================

@app.route("/api/health")
def health():
    """Comprueba que Flask esté funcionando."""

    return jsonify({
        "status": "ok",
        "message": "Backend Python funcionando"
    })


# ============================================================
# DIAGNÓSTICO DE CONFIGURACIÓN
# ============================================================

@app.route("/api/gee-diagnostico")
def gee_diagnostico():
    """Comprueba la configuración sin mostrar secretos."""

    directorio_secrets = "/etc/secrets"

    directorio_existe = os.path.isdir(
        directorio_secrets
    )

    archivos_secretos = (
        os.listdir(directorio_secrets)
        if directorio_existe
        else []
    )

    archivo_existe = os.path.isfile(
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
        "ruta_credenciales": GEE_SERVICE_ACCOUNT_FILE,
        "archivo_credenciales_existe": archivo_existe,
        "directorio_secrets_existe": directorio_existe,
        "archivos_secretos": archivos_secretos
    })


# ============================================================
# CONEXIÓN CON GOOGLE EARTH ENGINE
# ============================================================

@app.route("/api/gee-test")
def gee_test():
    """Autentica Earth Engine y consulta Sentinel-2."""

    project_id = os.environ.get(
        "GEE_PROJECT_ID"
    )

    json_path = os.environ.get(
        "GEE_SERVICE_ACCOUNT_FILE",
        "/etc/secrets/gee-service-account.json"
    )

    service_account_email = os.environ.get(
        "GEE_SERVICE_ACCOUNT_EMAIL",
        "geoportal-gee@geoportal-gee-peru.iam.gserviceaccount.com"
    )

    # --------------------------------------------------------
    # 1. Validar configuración
    # --------------------------------------------------------

    if not project_id:
        return jsonify({
            "status": "error",
            "message": "Falta configurar GEE_PROJECT_ID"
        }), 503

    if not os.path.isfile(json_path):
        return jsonify({
            "status": "error",
            "message": "No se encontró el archivo de credenciales",
            "ruta_comprobada": json_path,
            "directorio_secrets_existe": os.path.isdir(
                "/etc/secrets"
            )
        }), 503

    # --------------------------------------------------------
    # 2. Autenticar e inicializar Earth Engine
    # --------------------------------------------------------

    try:
        credentials = ee.ServiceAccountCredentials(
            service_account_email,
            json_path
        )

        ee.Initialize(
            credentials=credentials,
            project=project_id
        )

        # ----------------------------------------------------
        # 3. Consultar colección Sentinel-2
        # ----------------------------------------------------

        cantidad_imagenes = (
            ee.ImageCollection(
                "COPERNICUS/S2_SR_HARMONIZED"
            )
            .filterDate(
                "2024-06-01",
                "2024-07-01"
            )
            .limit(1)
            .size()
            .getInfo()
        )

        # ----------------------------------------------------
        # 4. Respuesta de éxito
        # ----------------------------------------------------

        return jsonify({
            "status": "ok",
            "message": "Google Earth Engine conectado correctamente",
            "project_id": project_id,
            "cuenta_servicio": service_account_email,
            "coleccion": "COPERNICUS/S2_SR_HARMONIZED",
            "periodo": {
                "inicio": "2024-06-01",
                "fin": "2024-07-01"
            },
            "imagenes_encontradas": cantidad_imagenes
        })

    except Exception as error:
        # El detalle técnico se guarda en los logs de Render.
        # No se devuelve la excepción completa al navegador.

        app.logger.exception(
            "Error al conectar con Google Earth Engine"
        )

        # Identificar el tipo de error sin revelar credenciales.
        return jsonify({
            "status": "error",
            "message": "Falló la conexión con Earth Engine",
            "tipo_error": type(error).__name__,
            "detalle": str(error)[:500]
        }), 500


# ============================================================
# EJECUCIÓN LOCAL
# ============================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get("PORT", 5000)
        ),
        debug=False
    )

