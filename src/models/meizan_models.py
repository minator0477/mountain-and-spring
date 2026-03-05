"""
名山データの Pydantic モデル定義

階層構造:
    MeizanProperties      … 山1件のプロパティ（GeoJSON Feature.properties）
    MeizanFeature         … GeoJSON Feature（山1件）
    MeizanFeatureCollection … GeoJSON FeatureCollection（全山）

共通モデル（Visit, PointGeometry）は geojson_models から import する。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from models.geojson_models import PointGeometry, Visit


# ---------------------------------------------------------------------------
# 山プロパティ
# ---------------------------------------------------------------------------

class MeizanProperties(BaseModel):
    """GeoJSON Feature.properties — 山1件のデータ"""
    no: int
    name: str
    yomi: str
    elev_m: int
    location: str
    region: str
    note: str
    # --with-records 時のみ付与
    count: int | None = None
    visits: list[Visit] | None = None


# ---------------------------------------------------------------------------
# GeoJSON Feature / FeatureCollection
# ---------------------------------------------------------------------------

class MeizanFeature(BaseModel):
    """GeoJSON Feature — 山1件"""
    type: Literal["Feature"] = "Feature"
    geometry: PointGeometry
    properties: MeizanProperties


class MeizanFeatureCollection(BaseModel):
    """GeoJSON FeatureCollection — 全山のコレクション"""
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[MeizanFeature]
