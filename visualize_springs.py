"""
温泉訪問履歴の可視化スクリプト
- 過去1年間に訪れた温泉: オレンジ色
- それ以外: 灰色
出力: output/springs_visited.png
"""

import json
import os
from datetime import datetime, date, timedelta

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import japanize_matplotlib
import contextily as ctx
from dateutil.parser import parse as parse_date


INPUT_FILE = "data/result/springs.gpkg"
OUTPUT_DIR = "output"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "springs_visited.png")

COLOR_RECENT = "#FF8C00"   # オレンジ（過去1年）
COLOR_OTHER = "#A0A0A0"    # 灰色（それ以外）
MARKER_SIZE = 80
EDGE_COLOR = "white"
EDGE_WIDTH = 0.8


def most_recent_visit(visits_json: str) -> date | None:
    """visits フィールドから最新の訪問日を返す。未訪問の場合は None。"""
    if not isinstance(visits_json, str):
        return None
    try:
        entries = json.loads(visits_json)
    except (json.JSONDecodeError, TypeError):
        return None
    dates = []
    for entry in entries:
        raw = entry.get("date", "")
        if raw:
            try:
                dates.append(parse_date(raw).date())
            except ValueError:
                pass
    return max(dates) if dates else None


def classify(visits_json: str, cutoff: date) -> str:
    """cutoff 以降に訪問があればオレンジ、なければ灰色を返す。"""
    latest = most_recent_visit(visits_json)
    if latest and latest >= cutoff:
        return COLOR_RECENT
    return COLOR_OTHER


def main():
    today = date.today()
    cutoff = today - timedelta(days=365)

    # データ読み込み
    gdf = gpd.read_file(INPUT_FILE)

    # 訪問済みのみ対象（visits が空の行を除外）
    gdf = gdf[gdf["visits"].apply(most_recent_visit).notna()].copy()

    # 色の決定
    gdf["color"] = gdf["visits"].apply(lambda v: classify(v, cutoff))

    # Web メルカトルに変換（basemap 用）
    gdf_web = gdf.to_crs(epsg=3857)

    # 図の作成
    fig, ax = plt.subplots(figsize=(12, 10))

    # 灰色を先に描画し、オレンジを上に重ねる
    for color, zorder in [(COLOR_OTHER, 3), (COLOR_RECENT, 4)]:
        subset = gdf_web[gdf_web["color"] == color]
        subset.plot(
            ax=ax,
            color=color,
            markersize=MARKER_SIZE,
            zorder=zorder,
            edgecolor=EDGE_COLOR,
            linewidth=EDGE_WIDTH,
        )

    # 東西方向の描画範囲を拡張
    xmin, xmax = ax.get_xlim()
    xpad = (xmax - xmin) * 0.5
    ax.set_xlim(xmin - xpad, xmax + xpad)

    # basemap の追加
    try:
        ctx.add_basemap(
            ax,
            source=ctx.providers.Esri.OceanBasemap,
            zoom=9,
        )
    except Exception as e:
        print(f"basemap の読み込みに失敗しました（オフライン？）: {e}")

    # 凡例
    recent_count = (gdf["color"] == COLOR_RECENT).sum()
    other_count = (gdf["color"] == COLOR_OTHER).sum()
    legend_handles = [
        Line2D(
            [0], [0],
            marker="o", color="w",
            markerfacecolor=COLOR_RECENT, markeredgecolor=EDGE_COLOR,
            markeredgewidth=EDGE_WIDTH, markersize=10,
            label=f"過去1年以内 ({recent_count}件)",
        ),
        Line2D(
            [0], [0],
            marker="o", color="w",
            markerfacecolor=COLOR_OTHER, markeredgecolor=EDGE_COLOR,
            markeredgewidth=EDGE_WIDTH, markersize=10,
            label=f"それ以外 ({other_count}件)",
        ),
    ]
    ax.legend(
        handles=legend_handles,
        loc="upper left",
        fontsize=11,
        framealpha=0.9,
    )

    # タイトルと軸
    ax.set_title("訪問温泉マップ", fontsize=16, pad=12)
    ax.set_axis_off()

    # 出力
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUTPUT_FILE, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"保存しました: {OUTPUT_FILE}")
    print(f"  過去1年以内: {recent_count}件  /  それ以外: {other_count}件")


if __name__ == "__main__":
    main()
