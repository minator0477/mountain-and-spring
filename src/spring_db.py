"""
温泉データ CRUD 操作

読み込み: DuckDB + spatial 拡張（ST_Read で GPKG を読む）
書き込み: fiona（GPKG への確実な書き出し）
バリデーション: Pydantic（spring_models）
"""

import json
import threading
from pathlib import Path

import duckdb
import fiona
from fiona.crs import from_epsg

from models.geojson_models import PointGeometry, Visit
from models.spring_models import (
    FacilityType,
    SpringFeature,
    SpringFeatureCollection,
    SpringProperties,
    SpringType,
)

ROOT = Path(__file__).parent.parent
GPKG_PATH = ROOT / "data/result/springs.gpkg"
LAYER_NAME = "springs"

SCHEMA = {
    "geometry": "Point",
    "properties": {
        "id": "int",
        "name": "str",
        "yomi": "str",
        "spring_type": "str",
        "facility_type": "str",
        "count": "int",
        "visits": "str",  # JSON 文字列 [{date, note}, ...]
    },
}

_lock = threading.Lock()


# ---------------------------------------------------------------------------
# 内部ヘルパー
# ---------------------------------------------------------------------------

def _read_rows() -> list[tuple]:
    """DuckDB で GPKG を読み込み全行を返す"""
    if not GPKG_PATH.exists():
        return []
    con = duckdb.connect()
    con.execute("LOAD spatial;")
    try:
        rows = con.execute(f"""
            SELECT id,
                   ST_X(geom) AS lng,
                   ST_Y(geom) AS lat,
                   name, yomi, spring_type, facility_type, count, visits
            FROM ST_Read('{GPKG_PATH}')
        """).fetchall()
    finally:
        con.close()
    return rows


def _parse_spring_type(value: str | None) -> list[SpringType] | None:
    """新フォーマット（JSON配列）・旧フォーマット（単一文字列）の両方に対応"""
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, ValueError):
        # 旧フォーマット: 単一文字列をそのまま使用
        return [SpringType(value)]
    if isinstance(parsed, list):
        return [SpringType(t) for t in parsed]
    # JSON文字列として保存されていた場合
    return [SpringType(parsed)]


def _row_to_feature(row: tuple) -> SpringFeature:
    id_, lng, lat, name, yomi, spring_type, facility_type, count, visits_str = row
    return SpringFeature(
        id=id_,
        geometry=PointGeometry(coordinates=(lng, lat)),
        properties=SpringProperties(
            name=name,
            yomi=yomi,
            spring_type=_parse_spring_type(spring_type),
            facility_type=FacilityType(facility_type) if facility_type else None,
            count=count,
            visits=[Visit(**v) for v in json.loads(visits_str)] if visits_str else None,
        ),
    )


def _write_all(features: list[SpringFeature]) -> None:
    """全フィーチャを GPKG に書き出す（fiona）"""
    GPKG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with fiona.open(
        str(GPKG_PATH), "w",
        driver="GPKG",
        crs=from_epsg(4326),
        schema=SCHEMA,
        layer=LAYER_NAME,
    ) as dst:
        for f in features:
            p = f.properties
            dst.write({
                "geometry": {
                    "type": "Point",
                    "coordinates": f.geometry.coordinates,
                },
                "properties": {
                    "id": f.id,
                    "name": p.name,
                    "yomi": p.yomi,
                    "spring_type": json.dumps([t.value for t in p.spring_type], ensure_ascii=False) if p.spring_type else None,
                    "facility_type": p.facility_type.value if p.facility_type else None,
                    "count": p.count,
                    "visits": json.dumps(
                        [v.model_dump() for v in p.visits], ensure_ascii=False
                    ) if p.visits else None,
                },
            })


def _next_id(features: list[SpringFeature]) -> int:
    if not features:
        return 1
    return max((f.id for f in features if f.id is not None), default=0) + 1


def _load() -> list[SpringFeature]:
    return [_row_to_feature(r) for r in _read_rows()]


# ---------------------------------------------------------------------------
# CRUD 公開 API
# ---------------------------------------------------------------------------

def list_all() -> SpringFeatureCollection:
    """全温泉を取得"""
    with _lock:
        return SpringFeatureCollection(features=_load())


def get_by_id(id: int) -> SpringFeature | None:
    """ID で温泉を取得"""
    with _lock:
        return next((f for f in _load() if f.id == id), None)


def get_by_name(name: str) -> list[SpringFeature]:
    """名前で温泉を検索（部分一致）"""
    with _lock:
        return [f for f in _load() if name in f.properties.name]


def create(data: SpringFeature) -> SpringFeature:
    """温泉を新規作成（id は自動採番）"""
    with _lock:
        features = _load()
        new_feature = data.model_copy(update={"id": _next_id(features)})
        features.append(new_feature)
        _write_all(features)
        return new_feature


def update_by_id(id: int, data: SpringFeature) -> SpringFeature:
    """ID で温泉を更新"""
    with _lock:
        features = _load()
        idx = next((i for i, f in enumerate(features) if f.id == id), None)
        if idx is None:
            raise KeyError(f"id={id} が見つかりません")
        updated = data.model_copy(update={"id": id})
        features[idx] = updated
        _write_all(features)
        return updated


def delete_by_id(id: int) -> None:
    """ID で温泉を削除"""
    with _lock:
        features = _load()
        filtered = [f for f in features if f.id != id]
        if len(filtered) == len(features):
            raise KeyError(f"id={id} が見つかりません")
        _write_all(filtered)


def delete_by_name(name: str) -> None:
    """名前（完全一致・一意）で温泉を削除"""
    with _lock:
        features = _load()
        hits = [f for f in features if f.properties.name == name]
        if not hits:
            raise KeyError(f"name='{name}' が見つかりません")
        if len(hits) > 1:
            raise ValueError(f"name='{name}' が複数ヒットしました（id={[f.id for f in hits]}）")
        _write_all([f for f in features if f.properties.name != name])


def update_by_name(name: str, data: SpringFeature) -> SpringFeature:
    """名前（完全一致）で温泉を更新。複数ヒット時はエラー"""
    with _lock:
        features = _load()
        hits = [i for i, f in enumerate(features) if f.properties.name == name]
        if not hits:
            raise KeyError(f"name='{name}' が見つかりません")
        if len(hits) > 1:
            raise ValueError(f"name='{name}' が複数ヒットしました（id={[features[i].id for i in hits]}）")
        updated = data.model_copy(update={"id": features[hits[0]].id})
        features[hits[0]] = updated
        _write_all(features)
        return updated
