# Geoportal Expansión Urbana de Lima · Geospatial_Perú
**Abrir:** doble clic en `index.html` (autocontenido; el mapa mundial necesita internet).

## Datos reales (recomendado)
1. `pip install earthengine-api` y `earthengine authenticate` (cuenta con GEE y proyecto de Google Cloud).
2. (Opcional, mejora mucho) copia límites distritales reales en `data/distritos.geojson` (IGN/INEI; propiedad NOMBDIST o DISTRITO).
3. `python py/gee_expansion.py TU_PROYECTO`  → calcula km² construidos por distrito 1975-2020 (GHSL) y baja la huella urbana por época.
4. `python py/make_data.py` y `python py/build_single.py`  → regenera `index.html`.

Sin esos pasos se ve una SERIE DEMO ilustrativa con límites aproximados (el geoportal lo avisa).
Estructura: template.html · css/ · js/ · data/ · assets/ · py/
