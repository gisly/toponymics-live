# map-style/

MapLibre GL JS стиль карты для проекта.

## Что здесь

- `style.json` — стартовый минимальный стиль (только background). После загрузки `siberia.pmtiles` его надо расширить полным набором слоёв.

## Как получить PMTiles файл для Сибири

Вариант 1: Скачать с Protomaps build.
1. Открыть https://app.protomaps.com/downloads/small_planet
2. Выбрать bbox (например, 80,50,150,75 — широкая Сибирь)
3. Скачать `.pmtiles` файл (~2-5 ГБ)
4. Положить в `pmtiles-local/siberia.pmtiles` (для dev) или на VPS в `/opt/toponymics/pmtiles/`

Вариант 2: Собрать самой через planetiler.
1. Скачать `https://download.geofabrik.de/asia/russia/siberian-fed-district-latest.osm.pbf`
2. `java -jar planetiler.jar --download --area=siberia --output=siberia.pmtiles`
3. На сборку — несколько часов, 8 ГБ RAM временно

## Как редактировать стиль

1. Установить Maputnik локально: https://github.com/maplibre/maputnik
2. Запустить локально или использовать https://maplibre.org/maputnik/
3. Открыть `style.json` (Open → File)
4. Задать data source как `pmtiles://siberia.pmtiles` (потребуется локальный сервер с CORS)
5. Импортировать стартовый набор слоёв из Protomaps schema:
   - https://github.com/protomaps/basemaps/tree/main/styles
6. Кастомизировать цвета, шрифты, видимость на zoom-уровнях под бренд проекта
7. Экспортировать обратно в этот файл

## Какие шрифты нужны

Для эвенкийских топонимов на карте нужны SDF-глифы (Signed Distance Field) с покрытием:
- U+0400–U+04FF (кириллица)
- U+0250–U+02AF (IPA Extensions)
- U+1D00–U+1D7F (Phonetic Extensions)

Стартово используется CDN с OpenMapTiles fonts. Для production стоит сгенерировать свои SDF из Noto Sans + Charis SIL через `node-fontnik` и положить в `frontend/public/fonts/{fontstack}/{range}.pbf`, обновив `glyphs` URL в стиле.
