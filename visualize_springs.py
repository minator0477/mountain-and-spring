"""
温泉訪問履歴の可視化スクリプト
- 過去1年間に訪れた温泉: オレンジ色（北から順に番号付き）
- それ以外: 灰色
- 左右欄に番号付き温泉名一覧（リスト幅に合わせて描画範囲を自動拡張）
出力: output/springs_visited.png
"""

import json
import os
from datetime import date, timedelta

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import japanize_matplotlib
import contextily as ctx
from dateutil.parser import parse as parse_date


INPUT_FILE = "data/result/springs.gpkg"
OUTPUT_DIR = "output"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "springs_visited.png")

COLOR_RECENT = "#FF8C00"
COLOR_OTHER = "#A0A0A0"
MARKER_SIZE = 80
EDGE_COLOR = "white"
EDGE_WIDTH = 0.8

LIST_FONTSIZE = 13.5
LINE_HEIGHT = 0.052      # リスト行間 (axes fraction)
MAP_MARGIN_FRAC = 0.02   # リスト端と地図データの間の余白 (axes fraction)
LIST_SIDE_PAD_PX = 8     # リストと axes 端の余白 (px)


def most_recent_visit(visits_json: str) -> date | None:
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
    latest = most_recent_visit(visits_json)
    if latest and latest >= cutoff:
        return COLOR_RECENT
    return COLOR_OTHER


def measure_list_width_px(ax, fig, items: list) -> float:
    """リストの最長テキスト幅をピクセルで返す（仮配置 → 計測 → 削除）。"""
    if not items:
        return 0.0
    bbox_style = dict(boxstyle="round,pad=0.2", facecolor="white",
                      alpha=0.75, edgecolor="none")
    probes = [
        ax.text(0, 0, f"{num}. {name}",
                transform=ax.transAxes, ha="left", va="top",
                fontsize=LIST_FONTSIZE, bbox=bbox_style)
        for num, name in items
    ]
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    max_w = max(t.get_window_extent(renderer=renderer).width for t in probes)
    for t in probes:
        t.remove()
    return max_w


def draw_list(ax, items: list, x_frac: float) -> None:
    bbox_style = dict(boxstyle="round,pad=0.2", facecolor="white",
                      alpha=0.75, edgecolor="none")
    for rank, (num, name) in enumerate(items):
        yf = 0.97 - rank * LINE_HEIGHT
        ax.text(x_frac, yf, f"{num}. {name}",
                transform=ax.transAxes,
                ha="left", va="top",
                fontsize=LIST_FONTSIZE, zorder=7,
                bbox=bbox_style)


def main():
    today = date.today()
    cutoff = today - timedelta(days=365)

    gdf = gpd.read_file(INPUT_FILE)
    gdf = gdf[gdf["visits"].apply(most_recent_visit).notna()].copy()
    gdf["color"] = gdf["visits"].apply(lambda v: classify(v, cutoff))

    gdf_web = gdf.to_crs(epsg=3857)

    fig, ax = plt.subplots(figsize=(12, 10))

    # マーカー描画（灰色 → オレンジ）
    for color, zorder in [(COLOR_OTHER, 3), (COLOR_RECENT, 4)]:
        subset = gdf_web[gdf_web["color"] == color]
        subset.plot(ax=ax, color=color, markersize=MARKER_SIZE,
                    zorder=zorder, edgecolor=EDGE_COLOR, linewidth=EDGE_WIDTH)

    # ── 番号付け・左右振り分け ─────────────────────────────────────────────
    gdf_recent = gdf_web[gdf_web["color"] == COLOR_RECENT].copy()

    xs_all = [g.x for g in gdf_web.geometry]
    ys_all = [g.y for g in gdf_web.geometry]
    x_data_min, x_data_max = min(xs_all), max(xs_all)
    y_data_min, y_data_max = min(ys_all), max(ys_all)
    mid_x_geo = (x_data_min + x_data_max) / 2

    # 北→南の順に番号を振る
    numbered = sorted(
        [(g.x, g.y, name)
         for g, name in zip(gdf_recent.geometry, gdf_recent["name"])],
        key=lambda p: -p[1],
    )
    numbered = [(i + 1, px, py, name) for i, (px, py, name) in enumerate(numbered)]

    left_items  = sorted([(n, nm) for n, px, py, nm in numbered if px <= mid_x_geo])
    right_items = sorted([(n, nm) for n, px, py, nm in numbered if px > mid_x_geo])

    # ── リスト幅を測定し、xlim を自動算出（basemap 追加前に確定）─────────
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    ax_w_px = ax.get_window_extent(renderer=renderer).width

    left_w_px  = measure_list_width_px(ax, fig, left_items)
    right_w_px = measure_list_width_px(ax, fig, right_items)

    # 各リストが占める axes fraction
    left_list_start  = 0.01
    left_list_end    = left_list_start + (left_w_px + LIST_SIDE_PAD_PX) / ax_w_px
    right_list_start = 1.0 - (right_w_px + LIST_SIDE_PAD_PX) / ax_w_px
    right_list_end   = 1.0  # noqa: F841 (右端)

    # 地図エリア: [left_list_end + margin, right_list_start - margin]
    map_west_frac = left_list_end  + MAP_MARGIN_FRAC
    map_east_frac = right_list_start - MAP_MARGIN_FRAC
    available_frac = max(map_east_frac - map_west_frac, 0.3)

    # spring データが地図エリア内に収まる xlim を計算
    data_xrange = x_data_max - x_data_min
    total_xrange = data_xrange / available_frac
    xlim_min = x_data_min - map_west_frac * total_xrange
    xlim_max = xlim_min + total_xrange

    # ylim: データ範囲 ± 15%
    data_yrange = y_data_max - y_data_min
    ypad = data_yrange * 0.15

    ax.set_xlim(xlim_min, xlim_max)
    ax.set_ylim(y_data_min - ypad, y_data_max + ypad)

    # ── basemap（確定した xlim で取得）───────────────────────────────────
    texts_before = {id(t) for t in ax.texts}
    try:
        ctx.add_basemap(ax, source=ctx.providers.Esri.OceanBasemap, zoom=9)
    except Exception as e:
        print(f"basemap の読み込みに失敗しました（オフライン？）: {e}")
    credit_texts = [t for t in ax.texts if id(t) not in texts_before]

    # ── マップ上に番号バッジを描画 ────────────────────────────────────────
    for num, px, py, _ in numbered:
        ax.text(px, py, str(num),
                ha="center", va="center",
                fontsize=10.5, fontweight="bold", color="white",
                zorder=6,
                bbox=dict(boxstyle="circle,pad=0.15",
                          facecolor=COLOR_RECENT, edgecolor="white",
                          linewidth=0.8))

    # ── 左右の温泉名一覧を描画 ────────────────────────────────────────────
    draw_list(ax, left_items,  left_list_start)
    draw_list(ax, right_items, right_list_start)

    # 凡例
    recent_count = (gdf["color"] == COLOR_RECENT).sum()
    other_count  = (gdf["color"] == COLOR_OTHER).sum()
    legend_handles = [
        Line2D([0], [0], marker="o", color="w",
               markerfacecolor=COLOR_RECENT, markeredgecolor=EDGE_COLOR,
               markeredgewidth=EDGE_WIDTH, markersize=10,
               label=f"過去1年以内 ({recent_count}件)"),
        Line2D([0], [0], marker="o", color="w",
               markerfacecolor=COLOR_OTHER, markeredgecolor=EDGE_COLOR,
               markeredgewidth=EDGE_WIDTH, markersize=10,
               label=f"それ以外 ({other_count}件)"),
    ]
    ax.set_title("訪問温泉マップ", fontsize=16, pad=12)
    ax.set_axis_off()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fig.tight_layout()

    # クレジットの上端を測定し、凡例がその下に重ならない y 位置を決定
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    ax_bb = ax.get_window_extent(renderer=renderer)

    if credit_texts:
        credit_top_px = max(t.get_window_extent(renderer=renderer).y1
                            for t in credit_texts)
        legend_y = (credit_top_px - ax_bb.y0) / ax_bb.height + 0.01
    else:
        legend_y = 0.01

    ax.legend(handles=legend_handles,
              bbox_to_anchor=(0.99, legend_y),
              loc="lower right",
              fontsize=11, framealpha=0.9)

    fig.savefig(OUTPUT_FILE, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"保存しました: {OUTPUT_FILE}")
    print(f"  過去1年以内: {recent_count}件  /  それ以外: {other_count}件")


if __name__ == "__main__":
    main()
