"""DuckDB + FastAPI タイルサーバー

開発:
    npm run dev          # uvicorn --reload で起動、ブラウザは http://localhost:8000

本番:
    npm run build        # Vite でフロントをビルド → dist/
    npm start            # FastAPI が dist/ を配信
"""


import json
import os
from pathlib import Path

import duckdb
import uvicorn
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).parent.parent
DIST = ROOT / "dist"
GPKG_PATH = str(ROOT / "data/result/meizan.gpkg")
SPRINGS_GPKG_PATH = ROOT / "data/result/springs.gpkg"


# ── FastAPI アプリ ─────────────────────────────────────────────────────────────

app = FastAPI(title="名山タイルサーバー")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
)


@app.get("/meizan.geojson")
def get_meizan() -> Response:
    """名山 GeoPackage を GeoJSON FeatureCollection として返す。"""
    con = duckdb.connect()
    con.execute("LOAD spatial;")
    rows = con.execute(
        f"""
        SELECT ST_AsGeoJSON(geom) AS geometry,
               no, name, yomi, elev_m, location, region, note, count, visits
        FROM ST_Read('{GPKG_PATH}')
        """
    ).fetchall()
    con.close()

    features = []
    for geom_str, no, name, yomi, elev_m, location, region, note, count, visits in rows:
        features.append({
            "type": "Feature",
            "geometry": json.loads(geom_str),
            "properties": {
                "no": no,
                "name": name,
                "yomi": yomi,
                "elev_m": elev_m,
                "location": location,
                "region": region,
                "note": note,
                "count": count,
                "visits": json.loads(visits) if visits else None,
            },
        })

    return Response(
        content=json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False),
        media_type="application/geo+json",
    )


@app.get("/springs.geojson")
def get_springs() -> Response:
    """温泉 GeoPackage を GeoJSON FeatureCollection として返す。"""
    if not SPRINGS_GPKG_PATH.exists():
        return Response(
            content=json.dumps({"type": "FeatureCollection", "features": []}, ensure_ascii=False),
            media_type="application/geo+json",
        )
    con = duckdb.connect()
    con.execute("LOAD spatial;")
    rows = con.execute(
        f"""
        SELECT id,
               ST_X(geom) AS lng,
               ST_Y(geom) AS lat,
               name, yomi, spring_type, facility_type, count, visits
        FROM ST_Read('{SPRINGS_GPKG_PATH}')
        """
    ).fetchall()
    con.close()

    features = []
    for id_, lng, lat, name, yomi, spring_type, facility_type, count, visits in rows:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "id": id_,
                "name": name,
                "yomi": yomi,
                "spring_type": json.loads(spring_type) if spring_type else None,
                "facility_type": facility_type,
                "count": count,
                "visits": json.loads(visits) if visits else None,
            },
        })

    return Response(
        content=json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False),
        media_type="application/geo+json",
    )


@app.get("/search")
def search_places(q: str = Query(..., min_length=1)) -> Response:
    """名山・温泉を名前・読みで部分一致検索する。"""
    q = q.strip()
    if not q:
        return Response(
            content=json.dumps({"results": []}, ensure_ascii=False),
            media_type="application/json",
        )
    pattern = f"%{q}%"
    results = []

    con = duckdb.connect()
    con.execute("LOAD spatial;")

    rows = con.execute(
        f"""
        SELECT ST_X(geom) AS lng, ST_Y(geom) AS lat,
               no, name, yomi, elev_m, count, visits
        FROM ST_Read('{GPKG_PATH}')
        WHERE name LIKE ? OR yomi LIKE ?
        ORDER BY no
        """,
        [pattern, pattern],
    ).fetchall()
    for lng, lat, no, name, yomi, elev_m, count, visits in rows:
        results.append({
            "type": "meizan",
            "lng": lng,
            "lat": lat,
            "no": no,
            "name": name,
            "yomi": yomi,
            "elev_m": elev_m,
            "count": count,
            "visits": json.loads(visits) if visits else None,
        })

    if SPRINGS_GPKG_PATH.exists():
        rows = con.execute(
            f"""
            SELECT ST_X(geom) AS lng, ST_Y(geom) AS lat,
                   id, name, yomi, spring_type, facility_type, count, visits
            FROM ST_Read('{SPRINGS_GPKG_PATH}')
            WHERE name LIKE ? OR yomi LIKE ?
            ORDER BY id
            """,
            [pattern, pattern],
        ).fetchall()
        for lng, lat, id_, name, yomi, spring_type, facility_type, count, visits in rows:
            results.append({
                "type": "spring",
                "lng": lng,
                "lat": lat,
                "id": id_,
                "name": name,
                "yomi": yomi,
                "spring_type": json.loads(spring_type) if spring_type else None,
                "facility_type": facility_type,
                "count": count,
                "visits": json.loads(visits) if visits else None,
            })

    con.close()
    return Response(
        content=json.dumps({"results": results}, ensure_ascii=False),
        media_type="application/json",
    )


# ── フロントエンド配信 ──────────────────────────────────────────────────────────
# npm run build 後は dist/ を StaticFiles でまとめて配信
# 未ビルド（開発時）は個別ファイルを直接配信

if DIST.exists() and os.getenv("APP_ENV") == "production":
    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="static")
else:
    @app.get("/style.css")
    def get_css() -> FileResponse:
        return FileResponse(ROOT / "style.css", media_type="text/css")

    @app.get("/main.js")
    def get_js() -> FileResponse:
        return FileResponse(ROOT / "main.js", media_type="application/javascript")

    @app.get("/")
    def index() -> HTMLResponse:
        return HTMLResponse((ROOT / "index.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, workers=1)
