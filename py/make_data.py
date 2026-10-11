
def main():
    real = geojson_rings()
    vor = voronoi_rings()

    gee_file = D / "expansion_gee.json"
    gee = None

    if gee_file.exists():
        candidate = json.loads(gee_file.read_text(encoding="utf-8"))

        years_candidate = candidate.get("years")
        built_candidate = candidate.get("built")

        if not isinstance(years_candidate, list) or not years_candidate:
            raise ValueError("expansion_gee.json no contiene años válidos.")

        if not isinstance(built_candidate, dict):
            raise ValueError("expansion_gee.json no contiene built válido.")

        missing = [
            name for name, *_ in DIST
            if name not in built_candidate
            or len(built_candidate[name]) != len(years_candidate)
        ]

        if missing:
            raise ValueError(
                "Faltan datos reales o épocas para estos distritos: "
                + ", ".join(missing)
            )

        gee = candidate

    years = gee["years"] if gee else YEARS
    bbox = gee.get("bbox") if gee else None

    rasters_complete = bool(
        gee
        and bbox
        and all((D / f"raster_{year}.png").is_file() for year in years)
    )

    rasters = None
    if rasters_complete:
        rasters = {
            year: "data:image/png;base64," + base64.b64encode(
                (D / f"raster_{year}.png").read_bytes()
            ).decode("ascii")
            for year in years
        }

    deps = []
    for name, lat, lon, area, fraction, t0, slope in DIST:
        if gee:
            built = gee["built"][name]
        else:
            built = [
                round(
                    area * fraction
                    / (1 + math.exp(-(year - t0) / slope)),
                    3,
                )
                for year in years
            ]

        deps.append({
            "name": name,
            "lat": lat,
            "lon": lon,
            "area": area,
            "rings": real.get(name) or vor[name],
            "built": built,
        })

    data = {
        "demo": not bool(gee),
        "updated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "years": years,
        "bbox": bbox,
        "rasters": rasters,
        "geom": (
            "reales (distritos.geojson)"
            if real
            else "aproximados (zonas de Voronoi, referenciales)"
        ),
        "source": (
            "JRC GHSL GHS-BUILT-S R2023A (100 m)"
            if gee
            else "SERIE DEMO ilustrativa"
        ),
        "deps": deps,
    }

    D.mkdir(parents=True, exist_ok=True)

    (D / "data.json").write_text(
        json.dumps(
            {key: value for key, value in data.items() if key != "rasters"},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    (D / "data.js").write_text(
        "window.LIMA_DATA = "
        + json.dumps(data, ensure_ascii=False)
        + ";",
        encoding="utf-8",
    )

    print(
        "OK | "
        + ("datos GHSL reales" if gee else "DEMO ilustrativa")
        + " | límites "
        + data["geom"]
    )


if __name__ == "__main__":
    main()

