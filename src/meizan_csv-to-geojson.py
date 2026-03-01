"""
名山 CSV → GeoPackage 変換スクリプト

使い方:
    uv run python src/meizan_csv-to-geojson.py              # 登頂記録なし
    uv run python src/meizan_csv-to-geojson.py --with-records  # 登頂記録を統合

入力:
    data/original/public/100meizan02.csv
    data/original/public/200meizan02.csv
    data/original/public/300meizan02.csv
    data/original/private/meizan-record.csv  ← --with-records 時のみ使用

出力:
    data/result/meizan.gpkg

--with-records 時に追加されるプロパティ:
    count  : 登頂記録の件数（0 = 未登頂）
    visits : 登頂記録の一覧（JSON 文字列） [{date, note}, ...]
"""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import fiona

from models import (
    MeizanFeature,
    MeizanProperties,
    PointGeometry,
    Visit,
)

BASE_DIR = Path(__file__).parent.parent
MEIZAN_DIR = Path("./data/original/public")

INPUT_FILES = [
    MEIZAN_DIR /  "100meizan02.csv",
    MEIZAN_DIR / "200meizan02.csv",
    MEIZAN_DIR / "300meizan02.csv",
]

RECORD_FILE = Path("./data/original/private/meizan-record.csv")

OUTPUT_FILE = Path("./data/result/meizan.gpkg")

GPKG_SCHEMA = {
    "geometry": "Point",
    "properties": {
        "no": "int",
        "name": "str",
        "yomi": "str",
        "elev_m": "int",
        "location": "str",
        "region": "str",
        "note": "str",
        "count": "int",
        "visits": "str",  # JSON 文字列 [{date, note}, ...]
    },
}


def load_records(path: Path) -> dict[int, list[Visit]]:
    """meizan-record.csv を読み込み、{山頂ID: [Visit, ...]} を返す"""
    records: dict[int, list[Visit]] = defaultdict(list)
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            summit_id = int(row["山頂ID"])
            records[summit_id].append(Visit(date=row["年月日"], note=row["備考"]))
    return records


def csv_row_to_feature(row: dict, records: dict[int, list[Visit]] | None) -> MeizanFeature:
    """CSV の1行を MeizanFeature に変換する"""
    no = int(row["No"])
    visits = records.get(no, []) if records is not None else None

    properties = MeizanProperties(
        no=no,
        name=row["山名"],
        yomi=row["よみがな"],
        elev_m=int(row["標高（m）"]),
        location=row["所在地"],
        region=row["地域名"],
        note=row["備考"],
        count=len(visits) if visits is not None else None,
        visits=visits if visits is not None else None,
    )

    return MeizanFeature(
        geometry=PointGeometry(coordinates=(float(row["東経"]), float(row["北緯"]))),
        properties=properties,
    )


def write_gpkg(features: list[MeizanFeature], path: Path) -> None:
    """MeizanFeature のリストを GeoPackage に書き出す"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with fiona.open(path, "w", driver="GPKG", crs="EPSG:4326", schema=GPKG_SCHEMA) as dst:
        for feat in features:
            p = feat.properties
            dst.write({
                "geometry": {
                    "type": "Point",
                    "coordinates": feat.geometry.coordinates,
                },
                "properties": {
                    "no": p.no,
                    "name": p.name,
                    "yomi": p.yomi,
                    "elev_m": p.elev_m,
                    "location": p.location,
                    "region": p.region,
                    "note": p.note,
                    "count": p.count,
                    "visits": json.dumps(
                        [v.model_dump() for v in p.visits], ensure_ascii=False
                    ) if p.visits is not None else None,
                },
            })


def main():
    parser = argparse.ArgumentParser(description="名山 CSV → GeoPackage 変換")
    parser.add_argument(
        "--with-records",
        action="store_true",
        help="登頂記録 (meizan-record.csv) を統合して count / visits プロパティを追加する",
    )
    args = parser.parse_args()

    records = load_records(RECORD_FILE) if args.with_records else None

    features: list[MeizanFeature] = []
    for path in INPUT_FILES:
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 空行を除外
                if not row["No"].strip():
                    continue
                features.append(csv_row_to_feature(row, records))

    write_gpkg(features, OUTPUT_FILE)

    print(f"変換完了: {len(features)} 件 → {OUTPUT_FILE}")
    if args.with_records:
        visited = sum(1 for feat in features if feat.properties.count and feat.properties.count > 0)
        print(f"登頂記録あり: {visited} 山 / 未登頂: {len(features) - visited} 山")


if __name__ == "__main__":
    main()
