
import os
import ee
import google.auth

from flask import Flask, jsonify, send_from_directory


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ID del proyecto de Google Cloud
GEE_PROJECT_ID = os.environ.get("GEE_PROJECT_ID")

# Ruta del archivo secreto de Google Earth Engine en Render
GEE_SERVICE_ACCOUNT_FILE = os.environ.get(
    "GEE_SERVICE_ACCOUNT_FILE",
    "/etc/secrets/gee-service-account.json"
)


# ============================================================
# PÁGINA PRINCIPAL
# ============================================================

@app.route("/")
def inicio():
    """Muestra la página principal del geoportal."""
    return send_from_directory(BASE_DIR, "index.html")


# ============================================================
# ARCHIVOS ESTÁTICOS
# ============================================================

@app.route("/<folder>/<path:filename>")
def archivos(folder, filename):
    """Sirve CSS, JavaScript, imágenes y archivos de datos."""

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

    directorio = os.path.join(BASE_DIR, folder)

    return send_from_directory(
        directorio,
        filename
    )


# ============================================================
# ESTADO DEL SERVIDOR
# ============================================================

@app.route("/api/health")
def health():
    """Comprueba que el backend de Flask esté funcionando."""

    return jsonify({
        "status": "ok",
        "message": "Backend Python funcionando"
    })


# ============================================================
# DIAGNÓSTICO DE CREDENCIALES
# ============================================================

@app.route("/api/gee-diagnostico")
def gee_diagnostico():
    """
    Comprueba la configuración de Earth Engine sin mostrar
    el contenido de la llave privada.
    """

    directorio_secrets = "/etc/secrets"
    archivo_existe = os.path.isfile(
        GEE_SERVICE_ACCOUNT_FILE
    )

    archivos_secretos = []

    if os.path.isdir(directorio_secrets):
        archivos_secretos = os.listdir(
            directorio_secrets
        )

    return jsonify({
        "status": "ok",
        "project_id_configurado": bool(GEE_PROJECT_ID),
        "ruta_credenciales": GEE_SERVICE_ACCOUNT_FILE,
        "archivo_credenciales_existe": archivo_existe,
        "directorio_secrets_existe": os.path.isdir(
            directorio_secrets
        ),
        "archivos_secretos": archivos_secretos
    })


# ============================================================
# PRUEBA DE CONEXIÓN CON GOOGLE EARTH ENGINE
# ============================================================

@app.route("/api/gee-test")
def gee_test():
    """
    Verifica las credenciales e intenta consultar
    una colección de imágenes Sentinel-2.
    """

    project_id = os.environ.get("GEE_PROJECT_ID")

    json_path = os.environ.get(
        "GEE_SERVICE_ACCOUNT_FILE",
        "/etc/secrets/gee-service-account.json"
    )

    # --------------------------------------------------------
    # 1. Comprobar el ID del proyecto
    # --------------------------------------------------------

    if not project_id:
        return jsonify({
            "status": "error",
            "message": "Falta configurar GEE_PROJECT_ID"
        }), 503

    # --------------------------------------------------------
    # 2. Comprobar la existencia del archivo JSON
    # --------------------------------------------------------

    if not os.path.isfile(json_path):
        directorio_secrets = "/etc/secrets"

        archivos_secretos = (
            os.listdir(directorio_secrets)
            if os.path.isdir(directorio_secrets)
            else []
        )

        return jsonify({
            "status": "error",
            "message": "No se encontró el archivo de credenciales",
            "ruta_comprobada": json_path,
            "directorio_secrets_existe": os.path.isdir(
                directorio_secrets
            ),
            "archivos_secretos": archivos_secretos
        }), 503

    # --------------------------------------------------------
    # 3. Autenticar e inicializar Earth Engine
    # --------------------------------------------------------

    try:
        credentials, _ = (
            google.auth.load_credentials_from_file(
                json_path
            )
        )

        ee.Initialize(
            credentials=credentials,
            project=project_id
        )

        # ----------------------------------------------------
        # 4. Consultar imágenes Sentinel-2
        # ----------------------------------------------------

        resultado = (
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
        # 5. Respuesta satisfactoria
        # ----------------------------------------------------

        return jsonify({
            "status": "ok",
            "message": "Google Earth Engine conectado",
            "project_id": project_id,
            "coleccion": "COPERNICUS/S2_SR_HARMONIZED",
            "periodo": {
                "inicio": "2024-06-01",
                "fin": "2024-07-01"
            },
            "imagenes_encontradas": resultado
        })

    except Exception:
        # El detalle técnico queda en los logs de Render.
        # No se devuelve información privada al navegador.

        app.logger.exception(
            "Error al conectar con Google Earth Engine"
        )

        return jsonify({
            "status": "error",
            "message": (
                "Falló la conexión con Earth Engine. "
                "Revisa los logs de Render."
            )
        }), 500


# ============================================================
# EJECUCIÓN LOCAL
# ============================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )

