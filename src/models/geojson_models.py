"""
GeoJSON 共通 Pydantic モデル

meizan_models / spring_models など複数のドメインモデルで共有する。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# 訪問記録（登頂・入湯など）
# ---------------------------------------------------------------------------

class Visit(BaseModel):
    """1回の訪問記録"""
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
