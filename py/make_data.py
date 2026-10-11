#!/usr/bin/env python3
"""Geospatial_Perú · Geoportal Expansión Urbana de Lima · genera data/data.js
Prioridad de insumos (si existen en data/):  distritos.geojson (límites reales) · expansion_gee.json + raster_AAAA.png (datos reales GHSL, ver gee_expansion.py)
Sin ellos: zonas aproximadas (Voronoi) y serie DEMO ilustrativa.   Uso: python py/make_data.py"""
import json, math, base64, unicodedata, datetime as dt
from pathlib import Path
D = Path(__file__).resolve().parent.parent / "data"
YEARS = list(range(1975, 2021, 5))
# nombre, lat, lon, área km², fracción final urbanizable, año medio de urbanización, pendiente (años)  [parámetros solo para la serie DEMO]
DIST = [("Lima Cercado",-12.046,-77.030,21.9,.92,1935,12),("Ancón",-11.73,-77.17,299,.14,2000,12),("Ate",-12.03,-76.92,77.7,.55,1980,12),
("Barranco",-12.14,-77.02,3.3,.97,1925,12),("Breña",-12.058,-77.05,3.2,.97,1930,12),("Carabayllo",-11.87,-77.04,346.9,.24,1995,12),
("Chaclacayo",-11.98,-76.77,39.5,.35,1970,15),("Chorrillos",-12.17,-77.01,38.9,.72,1965,12),("Cieneguilla",-12.09,-76.80,240,.16,1995,12),
("Comas",-11.94,-77.05,48.8,.88,1968,8),("El Agustino",-12.04,-77.00,12.5,.9,1965,8),("Independencia",-11.99,-77.05,14.6,.85,1968,8),
("Jesús María",-12.07,-77.05,4.6,.95,1935,12),("La Molina",-12.08,-76.91,65.8,.55,1972,14),("La Victoria",-12.07,-77.02,8.7,.97,1935,12),
("Lince",-12.08,-77.04,3.0,.97,1930,12),("Los Olivos",-11.97,-77.07,18.3,.88,1972,8),("Lurigancho-Chosica",-11.95,-76.70,236.5,.25,1985,14),
("Lurín",-12.28,-76.87,180.2,.22,1998,12),("Magdalena del Mar",-12.09,-77.07,3.6,.95,1935,12),("Miraflores",-12.12,-77.03,9.6,.97,1930,12),
("Pachacámac",-12.23,-76.86,160.2,.2,1998,11),("Pucusana",-12.48,-76.80,37.8,.3,1990,14),("Pueblo Libre",-12.075,-77.065,4.4,.96,1930,12),
("Puente Piedra",-11.86,-77.075,71.2,.45,1993,10),("Punta Hermosa",-12.33,-76.82,119.5,.12,1995,12),("Punta Negra",-12.36,-76.79,130.5,.15,1998,10),
("Rímac",-12.03,-77.03,11.9,.9,1940,12),("San Bartolo",-12.39,-76.78,45,.3,1990,12),("San Borja",-12.10,-77.00,9.9,.95,1965,10),
("San Isidro",-12.10,-77.04,11.1,.93,1940,12),("San Juan de Lurigancho",-11.98,-77.00,131.3,.8,1978,8),("San Juan de Miraflores",-12.15,-76.97,24,.85,1972,8),
("San Luis",-12.075,-77.00,3.5,.96,1950,10),("San Martín de Porres",-12.00,-77.09,36.9,.8,1968,9),("San Miguel",-12.08,-77.09,10.7,.92,1950,10),
("Santa Anita",-12.04,-76.97,10.7,.85,1982,6),("Santa María del Mar",-12.40,-76.77,9.8,.55,1992,10),("Santa Rosa",-11.80,-77.17,21.5,.25,1998,10),
("Santiago de Surco",-12.14,-76.99,52.1,.88,1965,12),("Surquillo",-12.11,-77.02,3.5,.96,1935,12),("Villa El Salvador",-12.21,-76.94,35.5,.78,1980,7),
("Villa María del Triunfo",-12.16,-76.94,70.6,.6,1978,10),("Callao",-12.05,-77.12,147,.62,1955,14)]
OUTLINE = [(-77.19,-11.62),(-76.95,-11.80),(-76.80,-11.90),(-76.62,-11.93),(-76.60,-12.05),(-76.70,-12.15),(-76.72,-12.30),(-76.66,-12.42),(-76.76,-12.53),
 (-76.82,-12.50),(-76.79,-12.38),(-76.82,-12.33),(-76.90,-12.28),(-76.99,-12.22),(-77.03,-12.19),(-77.05,-12.13),(-77.11,-12.07),(-77.15,-12.05),(-77.15,-11.92),(-77.18,-11.80)]
def norm(t): return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn").replace("-", " ").strip()
def _clip(poly, a, b, c):
    out = []
    for i in range(len(poly)):
        p, q = poly[i], poly[(i+1) % len(poly)]; fp, fq = a*p[0]+b*p[1]-c, a*q[0]+b*q[1]-c
        if fp <= 0: out.append(p)
        if fp*fq < 0: t = fp/(fp-fq); out.append((p[0]+t*(q[0]-p[0]), p[1]+t*(q[1]-p[1])))
    return out
def voronoi_rings():
    res = {}
    for n, la, lo, *_ in DIST:
        poly = list(OUTLINE)
        for m, la2, lo2, *_ in DIST:
            if m != n: poly = _clip(poly, lo2-lo, la2-la, ((lo2**2+la2**2)-(lo**2+la**2))/2)
        res[n] = [[[round(y,4), round(x,4)] for x, y in poly]]
    return res
def geojson_rings():
    f = D/"distritos.geojson"
    if not f.exists(): return {}
    names = {norm(n): n for n, *_ in DIST}; out = {}
    for ft in json.loads(f.read_text(encoding="utf-8"))["features"]:
        pr = ft["properties"]; nm = next((pr[k] for k in ("NOMBDIST","DISTRITO","NAME_3","nombdist","distrito","name") if k in pr), "")
        k = norm(nm); k = names.get(k) or next((v for kk, v in names.items() if kk.startswith(k) or k.startswith(kk)), None) if k else None
        if not k: continue
        g = ft["geometry"]; polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            ring = poly[0]; st = max(1, len(ring)//300)
            out.setdefault(k, []).append([[round(y,4), round(x,4)] for x, y in ring[::st]])
    return out
def main():
    real = geojson_rings(); vor = voronoi_rings(); gee = None
    if (D/"expansion_gee.json").exists(): gee = json.loads((D/"expansion_gee.json").read_text(encoding="utf-8"))
    years = gee["years"] if gee else YEARS; ras = None; bbox = gee.get("bbox") if gee else None
    if gee and bbox and all((D/f"raster_{y}.png").exists() for y in years):
        ras = {y: "data:image/png;base64," + base64.b64encode((D/f"raster_{y}.png").read_bytes()).decode() for y in years}
    deps = []
    for n, la, lo, area, f, t0, s in DIST:
        if gee and n in gee["built"]: built = gee["built"][n]
        else: built = [round(area*f/(1+math.exp(-(y-t0)/s)), 3) for y in years]
        deps.append({"name": n, "lat": la, "lon": lo, "area": area, "rings": real.get(n) or vor[n], "built": built})
    data = {"demo": not gee, "updated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "years": years, "bbox": bbox, "rasters": ras,
            "geom": "reales (distritos.geojson)" if real else "aproximados (zonas de Voronoi, referenciales)",
            "source": "JRC GHSL GHS-BUILT-S R2023A (100 m)" if gee else "SERIE DEMO ilustrativa", "deps": deps}
    D.mkdir(exist_ok=True)
    (D/"data.json").write_text(json.dumps({k: v for k, v in data.items() if k != "rasters"}, ensure_ascii=False), encoding="utf-8")
    (D/"data.js").write_text("window.LIMA_DATA=" + json.dumps(data, ensure_ascii=False) + ";", encoding="utf-8")
    print("OK | DEMO" if data["demo"] else "OK | datos GHSL", "| límites", data["geom"])
if __name__ == "__main__": main()
