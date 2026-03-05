"""
温泉リスト管理サーバー

起動:
    uv run python src/spring_server.py

ブラウザで http://localhost:8001 を開く。

API エンドポイント:
    GET    /api/springs              全温泉一覧
    POST   /api/springs              新規作成
    GET    /api/springs/{id}         ID で取得
    PUT    /api/springs/{id}         ID で更新
    GET    /api/springs/name/{name}  名前で検索（部分一致）
    PUT    /api/springs/name/{name}  名前で更新（完全一致、一意）
"""

import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

import spring_db
from models.spring_models import SpringFeature, SpringFeatureCollection


app = FastAPI(title="温泉リスト管理サーバー", docs_url="/api/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# ルート
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def root() -> HTMLResponse:
    return HTMLResponse((ROOT / "spring.html").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 一覧・検索
# ---------------------------------------------------------------------------

@app.get("/api/springs", response_model=SpringFeatureCollection)
def list_springs() -> SpringFeatureCollection:
    """全温泉を GeoJSON FeatureCollection で返す"""
    return spring_db.list_all()


@app.get("/api/springs/name/{name}", response_model=list[SpringFeature])
def search_by_name(name: str) -> list[SpringFeature]:
    """名前（部分一致）で温泉を検索"""
    return spring_db.get_by_name(name)


@app.get("/api/springs/{id}", response_model=SpringFeature)
def get_spring(id: int) -> SpringFeature:
    """ID で温泉を取得"""
    feature = spring_db.get_by_id(id)
    if feature is None:
        raise HTTPException(status_code=404, detail=f"id={id} が見つかりません")
    return feature


# ---------------------------------------------------------------------------
# 作成・更新
# ---------------------------------------------------------------------------

@app.post("/api/springs", response_model=SpringFeature, status_code=201)
def create_spring(data: SpringFeature) -> SpringFeature:
    """温泉を新規作成（id は自動採番）"""
    return spring_db.create(data)


@app.put("/api/springs/{id}", response_model=SpringFeature)
def update_spring_by_id(id: int, data: SpringFeature) -> SpringFeature:
    """ID で温泉を更新"""
    try:
        return spring_db.update_by_id(id, data)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.put("/api/springs/name/{name}", response_model=SpringFeature)
def update_spring_by_name(name: str, data: SpringFeature) -> SpringFeature:
    """名前（完全一致・一意）で温泉を更新"""
    try:
        return spring_db.update_by_name(name, data)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


# ---------------------------------------------------------------------------
# 削除
# ---------------------------------------------------------------------------

@app.delete("/api/springs/{id}", status_code=204)
def delete_spring_by_id(id: int) -> None:
    """ID で温泉を削除"""
    try:
        spring_db.delete_by_id(id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/api/springs/name/{name}", status_code=204)
def delete_spring_by_name(name: str) -> None:
    """名前（完全一致・一意）で温泉を削除"""
    try:
        spring_db.delete_by_name(name)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


# ---------------------------------------------------------------------------
# エントリポイント
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, workers=1)
