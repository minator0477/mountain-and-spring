# Python 3.13 をベースに Node.js も同居させる
FROM python:3.13-slim

# Node.js 22 LTS のインストール
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# uv のインストール
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# 依存定義ファイルを先にコピーしてレイヤーキャッシュを活用
COPY pyproject.toml package.json ./

# Python 依存インストール
RUN uv sync --no-dev

# DuckDB spatial 拡張をビルド時にインストール（実行時に LOAD するだけで使えるようにする）
RUN uv run python -c "import duckdb; con = duckdb.connect(); con.execute('INSTALL spatial;'); con.close()"

# Node.js 依存インストール（vite が devDependencies なので省略不可）
RUN npm install

# アプリケーションファイルをコピー
COPY . .

# フロントエンドをビルド
RUN npm run build

ENV APP_ENV=production
EXPOSE 8000
CMD ["uv", "run", "python", "src/server.py"]
