# Render デプロイ時の起動競合状態と解決策

## 概要

Render にデプロイした直後、地図を開いても温泉・山のデータが表示されない問題が発生した。
しばらく待つと正常に表示されるようになる（約1分程度）。

---

## 症状

- 初回アクセス時に `/springs.geojson` または `/meizan.geojson` がエラーを返す
- ブラウザの地図に温泉・山のピンが表示されない
- しばらく経つと自然に解消する

### エラーログ

```
_duckdb.IOException: IO Error: GDAL Error (4): /app/data/result/springs.gpkg: No such file or directory

LINE 6:         FROM ST_Read('/app/data/result/springs.gpkg')
```

---

## 根本原因

**TOCTOU（Time-of-Check/Time-of-Use）競合状態**

修正前のコードは、リクエストのたびに以下の処理をしていた。

```python
@app.get("/springs.geojson")
def get_springs():
    if not SPRINGS_GPKG_PATH.exists():   # ① ファイル存在チェック
        return empty_response()
    con = duckdb.connect()
    rows = con.execute(
        f"SELECT ... FROM ST_Read('{SPRINGS_GPKG_PATH}')"  # ② ファイルを開く
    ).fetchall()
```

① と ② の間に時間差がある。Render のコンテナ起動直後は、以下のいずれかの状態が起きうる。

| 状況 | `Path.exists()` | GDAL でのオープン |
|------|----------------|-----------------|
| ファイルが完全に書き込み済み | True | 成功 |
| ファイルが書き込み中（部分的に存在） | **True** | **失敗** |
| ファイルが未存在 | False | スキップ（空を返す） |

「書き込み中」のケースでは Python の `exists()` が True を返しても、GDAL がファイルを正常に開けないため `IOException` が発生する。

---

## 解決策

**起動時にデータをメモリへキャッシュする**

サーバー起動イベント（`startup`）の中でデータを一度だけ読み込み、グローバル変数に GeoJSON 文字列として保持する。
各エンドポイントはキャッシュを返すだけにし、リクエスト時のファイルアクセスをなくした。

```python
_meizan_geojson: str | None = None
_springs_geojson: str | None = None

@app.on_event("startup")
def startup():
    global _meizan_geojson, _springs_geojson
    # spatial 拡張インストール
    con = duckdb.connect()
    con.execute("INSTALL spatial;")
    con.close()
    # データを起動時に一括読み込み
    _meizan_geojson = _load_meizan()
    if Path(SPRINGS_GPKG_PATH).exists():
        _springs_geojson = _load_springs()

@app.get("/springs.geojson")
def get_springs():
    content = _springs_geojson or json.dumps({"type": "FeatureCollection", "features": []})
    return Response(content=content, media_type="application/geo+json")
```

### 変更されたエンドポイント

| エンドポイント | 修正前 | 修正後 |
|--------------|--------|--------|
| `GET /meizan.geojson` | リクエストごとに DuckDB でファイル読み込み | 起動時キャッシュから返す |
| `GET /springs.geojson` | リクエストごとに DuckDB でファイル読み込み | 起動時キャッシュから返す |
| `GET /search` | リクエストごとに DuckDB でファイル検索 | メモリ内 JSON を走査 |

---

## 副次的な効果

- **レスポンス高速化** — ファイル I/O・DuckDB 接続のオーバーヘッドがゼロになる
- **安定性向上** — ファイルアクセスの競合状態が根本的に排除される
- **検索も高速化** — `/search` も毎回 DuckDB を起動しなくなった

---

## 注意点

- データはサーバー起動時にのみ読み込まれる。GPKGファイルを更新した場合はサーバーの再起動が必要。
- メモリ使用量はデータサイズに比例するが、名山（数百件）・温泉（数千件）程度であれば問題ない。
