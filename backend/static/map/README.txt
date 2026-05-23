Сюда копируется собранный UMD-бандл карты:
- toponymics-map.umd.js
- toponymics-map.css

Файлы кладутся скриптом scripts/copy-map-bundle.sh после `npm run build:lib`.
В .gitignore стоит исключение для этих файлов — собранные артефакты не коммитим.
