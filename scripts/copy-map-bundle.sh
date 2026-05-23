#!/usr/bin/env bash
# Копирует собранный UMD-бандл карты из frontend/dist-lib/ в backend/static/map/,
# чтобы Django мог раздать его как статику.
#
# Запускать после `npm run build:lib` в frontend.
#
# Использование (из корня репозитория):
#   bash scripts/copy-map-bundle.sh
#
# Или в Docker:
#   docker compose exec frontend npm run build:lib
#   bash scripts/copy-map-bundle.sh
#   docker compose exec django python manage.py collectstatic --noinput

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT_DIR/frontend/dist-lib"
DST="$ROOT_DIR/backend/static/map"

if [ ! -d "$SRC" ]; then
    echo "❌ Не найдена папка $SRC."
    echo "   Запусти сначала: docker compose exec frontend npm run build:lib"
    exit 1
fi

mkdir -p "$DST"

echo "→ Копирую $SRC/* в $DST/"
cp -v "$SRC/toponymics-map.umd.js" "$DST/"
cp -v "$SRC/toponymics-map.css" "$DST/"

# Sourcemap копируем, если есть (полезно при отладке, в проде можно не копировать).
if [ -f "$SRC/toponymics-map.umd.js.map" ]; then
    cp -v "$SRC/toponymics-map.umd.js.map" "$DST/"
fi

echo "✓ Готово."
echo "  Дальше: docker compose exec django python manage.py collectstatic --noinput"
