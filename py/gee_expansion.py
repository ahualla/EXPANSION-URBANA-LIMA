#!/usr/bin/env python3
"""Extrae la expansión urbana REAL con Google Earth Engine (JRC GHSL GHS-BUILT-S R2023A, 100 m, épocas 1975-2020)
y descarga la huella urbana por época como PNG transparente.
Requisitos: pip install earthengine-api · earthengine authenticate · proyecto de Cloud con GEE habilitado.
Uso: python py/gee_expansion.py TU_PROYECTO_GEE   (luego: python py/make_data.py && python py/build_single.py)"""
import ee, json, sys, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_data import DIST, YEARS, D, voronoi_rings, geojson_rings
ee.Initialize(project=sys.argv[1] if len(sys.argv) > 1 else None)
rings = {**voronoi_rings(), **geojson_rings()}
fc = ee.FeatureCollection([ee.Feature(ee.Geometry.MultiPolygon([[[[lo, la] for la, lo in r]] for r in rings[n]]), {"name": n}) for n, *_ in DIST])
bb = [-77.25, -12.58, -76.55, -11.55]; region = ee.Geometry.Rectangle(bb)
coll = ee.ImageCollection("JRC/GHSL/P2023A/GHS_BUILT_S")
built = {n: [] for n, *_ in DIST}; D.mkdir(exist_ok=True)
for y in YEARS:
    img = coll.filter(ee.Filter.calendarRange(y, y, "year")).first().select("built_surface")
    for f in img.reduceRegions(fc, ee.Reducer.sum(), scale=100).getInfo()["features"]:
        built[f["properties"]["name"]].append(round((f["properties"]["sum"] or 0)/1e6, 3))   # m² -> km²
    url = img.selfMask().getThumbURL({"region": region, "dimensions": 1100, "format": "png", "min": 0, "max": 6000,
                                      "palette": ["#ffe9a8", "#fdae61", "#e8503a", "#7f0f2a"]})
    (D/f"raster_{y}.png").write_bytes(urllib.request.urlopen(url, timeout=120).read()); print("época", y, "ok")
(D/"expansion_gee.json").write_text(json.dumps({"years": YEARS, "bbox": [[bb[1], bb[0]], [bb[3], bb[2]]], "built": built}, ensure_ascii=False), encoding="utf-8")
print("Listo -> ahora ejecuta: python py/make_data.py && python py/build_single.py")
