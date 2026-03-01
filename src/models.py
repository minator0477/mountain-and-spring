"""
名山データの Pydantic モデル定義

階層構造:
    Visit                 … 1回の登頂記録
    MeizanProperties      … 山1件のプロパティ（GeoJSON Feature.properties）
    PointGeometry         … GeoJSON Point ジオメトリ
    MeizanFeature         … GeoJSON Feature（山1件）
    MeizanFeatureCollection … GeoJSON FeatureCollection（全山）
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# 登頂記録
# ---------------------------------------------------------------------------

class Visit(BaseModel):
    """1回の登頂記録"""
    date: str  # "YYYY/MM/DD"
    note: str

    @field_validator("date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        from datetime import datetime
        datetime.strptime(v, "%Y/%m/%d")
        return v


# ---------------------------------------------------------------------------
# GeoJSON 構成要素
# ---------------------------------------------------------------------------

class PointGeometry(BaseModel):
    """GeoJSON Point ジオメトリ"""
    type: Literal["Point"] = "Point"
    coordinates: tuple[float, float]  # (経度, 緯度)


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


class MeizanFeature(BaseModel):
    """GeoJSON Feature — 山1件"""
    type: Literal["Feature"] = "Feature"
    geometry: PointGeometry
    properties: MeizanProperties


class MeizanFeatureCollection(BaseModel):
    """GeoJSON FeatureCollection — 全山のコレクション"""
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[MeizanFeature]
