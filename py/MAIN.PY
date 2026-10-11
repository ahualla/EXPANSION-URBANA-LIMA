
import os
import ee
import google.auth

from flask import Flask, jsonify, send_from_directory

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@app.route("/")
def inicio():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/<folder>/<path:filename>")
def archivos(folder, filename):
    if folder not in {"assets", "css", "js", "data"}:
        return jsonify({"error": "Ruta no permitida"}), 404

    return send_from_directory(
        os.path.join(BASE_DIR, folder),
        filename
    )


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "message": "Backend Python funcionando"
    })


@app.route("/api/gee-test")
def gee_test():
    project_id = os.environ.get("GEE_PROJECT_ID")
    json_path = os.environ.get(
        "GEE_SERVICE_ACCOUNT_FILE",
        "/etc/secrets/gee-service-account.json"
    )

    if not project_id:
        return jsonify({
            "status": "error",
            "message": "Falta configurar GEE_PROJECT_ID"
        }), 503

    if not os.path.isfile(json_path):
        return jsonify({
            "status": "error",
            "message": "No se encontró el archivo de credenciales"
        }), 503

    try:
        credentials = (
            google.auth.load_credentials_from_file(
                json_path
            )[0]
        )

        ee.Initialize(
            credentials=credentials,
            project=project_id
        )

        resultado = (
            ee.ImageCollection(
                "COPERNICUS/S2_SR_HARMONIZED"
            )
            .filterDate("2024-06-01", "2024-07-01")
            .limit(1)
            .size()
            .getInfo()
        )

        return jsonify({
            "status": "ok",
            "message": "Google Earth Engine conectado",
            "imagenes_encontradas": resultado
        })

    except Exception:
        app.logger.exception("Error al conectar con Earth Engine")

        return jsonify({
            "status": "error",
            "message": "Falló la conexión con Earth Engine. Revisa los logs."
        }), 500
