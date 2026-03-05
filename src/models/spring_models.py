"""
温泉データの Pydantic モデル定義

階層構造:
    SpringType            … 泉質（Enum）
    FacilityType          … 施設種別（Enum）
    SpringProperties      … 温泉1件のプロパティ（GeoJSON Feature.properties）
    SpringFeature         … GeoJSON Feature（温泉1件）
    SpringFeatureCollection … GeoJSON FeatureCollection（全温泉）

共通モデル（Visit, PointGeometry）は geojson_models から import する。
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel

from models.geojson_models import PointGeometry, Visit


# ---------------------------------------------------------------------------
# 泉質
# ---------------------------------------------------------------------------

class SpringType(Enum):
    """泉質"""
    SIMPLE_THERMAL_SPRING = '単純温泉'
    CHLORIDE_SPRING = '塩化物泉'
    BICARBONATE_SPRING = '炭酸水素塩泉'
    SULFATE_SPRING = '硫酸塩泉'
    CARBON_DIOXIDE_SPRING = '二酸化炭素泉'
    IRON_CONTAINING_SPRING = '含鉄泉'
    IODINE_CONTAINING_SALINE_SPRING = '含ヨウ素塩泉'
    ACIDIC_SPRING = '酸性泉'
    SULFUR_SPRING = '硫黄泉'
    RADDON_SPRING = '放射能泉'


# ---------------------------------------------------------------------------
# 施設タイプ
# ---------------------------------------------------------------------------

class FacilityType(Enum):
    """施設種別"""
    SPA = 'スパ'
    NEIGHBORHOOD_PUBLIC_BATHHOUSE = '下町銭湯'


# ---------------------------------------------------------------------------
# 温泉プロパティ
# ---------------------------------------------------------------------------

class SpringProperties(BaseModel):
    """GeoJSON Feature.properties — 温泉1件のデータ"""
    name: str
    yomi: str
    spring_type: list[SpringType] | None = None
    facility_type: FacilityType | None = None
    # 入湯記録
    count: int | None = None
    visits: list[Visit] | None = None


# ---------------------------------------------------------------------------
# GeoJSON Feature / FeatureCollection
# ---------------------------------------------------------------------------

class SpringFeature(BaseModel):
    """GeoJSON Feature — 温泉1件"""
    type: Literal["Feature"] = "Feature"
    id: int | None = None  # GPKG fid（新規作成時は None）
    geometry: PointGeometry
    properties: SpringProperties


class SpringFeatureCollection(BaseModel):
    """GeoJSON FeatureCollection — 全温泉のコレクション"""
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[SpringFeature]
