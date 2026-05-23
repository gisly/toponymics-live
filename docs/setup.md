# Полная инструкция по развёртыванию

Всё с нуля до работающего сайта на твоём компьютере, ~10 минут активного времени плюс ожидание Docker'а.

---

## Что должно быть на машине

- **Docker Desktop** (Windows/Mac) или **Docker Engine + Docker Compose** (Linux). Проверь:
  ```bash
  docker --version          # должно быть 24+
  docker compose version    # должно быть 2.20+
  ```
- **Git** (для клонирования и commit'ов)
- **~3 ГБ свободного места** (на образы и БД)
- **Что-то для редактирования файлов** — VS Code, Sublime, vim
- Желательно — `curl` и `psql` для отладки

Ничего другого ставить **не нужно**: ни Python, ни Node, ни Postgres локально — всё внутри Docker.

---

## Шаг 1. Распаковать архив и создать репозиторий

```bash
# В любой удобной директории
tar xzf toponymics-live-v3.tar.gz
cd toponymics-live

# Git
git init
git add .
git commit -m "Initial skeleton with Wagtail+templates+importer"

# Создай приватный репо на GitHub/Codeberg и добавь его как remote
git remote add origin git@github.com:gisly/toponymics-live.git  # подставь свой URL
git push -u origin main
```

## Шаг 2. Сконфигурировать `.env`

```bash
cp .env.example .env
```

Открой `.env` и отредактируй. Для **локальной разработки** достаточно:

```bash
DJANGO_SECRET_KEY=local-dev-secret-key-change-when-deploying-to-production
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,django,new.toponymics-live.net,toponymics-live.net
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:5173,http://localhost:8000,https://new.toponymics-live.net

POSTGRES_DB=toponymics
POSTGRES_USER=toponymics
POSTGRES_PASSWORD=local-password-only
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

REDIS_URL=redis://redis:6379/0

VITE_API_BASE_URL=http://localhost:8000
VITE_PMTILES_URL=/pmtiles/russia-asian.pmtiles
VITE_MAP_STYLE_URL=/map-style/style.json

MEDIA_ROOT=/app/media
```

Для прода потом сгенерируешь `DJANGO_SECRET_KEY` через `openssl rand -base64 64`.

## Шаг 3. Подготовить данные миграции

Создай папку и положи туда WP-экспорт и разметку:

```bash
mkdir -p data-migration
# Сюда положи:
#   data-migration/wp_export/pages.json
#   data-migration/wp_export/media.json
#   data-migration/wp_export/posts.json
#   data-migration/wp_export/media/   ← скачанные картинки
#   data-migration/markup.csv         ← размеченный CSV

ls data-migration/
# должно быть:
#   markup.csv
#   wp_export/
```

Если у тебя уже есть готовый экспорт от прошлых шагов — положи его сюда. Если нет — пропусти этот шаг, импортёр можно запустить позже.

## Шаг 4. Поднять стек

```bash
docker compose up -d --build
```

Что произойдёт (займёт 3-5 минут при первом запуске):

1. Скачаются образы `postgres:16-alpine`, `redis:7-alpine`, `node:20-alpine`, `python:3.12-slim`
2. Соберётся образ Django (поставится Wagtail, DRF, и другие Python зависимости)
3. Запустятся 4 сервиса: `postgres`, `redis`, `tailwind`, `django`
4. `tailwind` поставит npm-зависимости (~76 пакетов) и соберёт CSS, потом перейдёт в watch-режим
5. `django` применит миграции, соберёт статику, запустит сервер на порту 8000

Проверь, что всё ОК:

```bash
docker compose ps
# Все 4 сервиса должны быть Up
# Если tailwind показывает "exited" — это нормально после первой сборки, можно его остановить
```

Логи (в отдельном окне, чтобы видеть что происходит):
```bash
docker compose logs -f django
# Ctrl+C чтобы выйти из лога (контейнер останется работать)
```

## Шаг 5. Создать суперпользователя

```bash
docker compose exec django python manage.py createsuperuser
```

Введёшь имя/email/пароль — это будет твой Wagtail-admin аккаунт. Для коллеги создашь отдельный аккаунт через Wagtail-админку позже.

## Шаг 6. (Опционально) Заполнить демо-данными

Если хочешь быстро увидеть карту с примерами топонимов до настоящего импорта:

```bash
docker compose exec django python manage.py seed_demo
```

Создаст 2 региона, 6 типов объектов и 3 топонима в Эвенкии.

## Шаг 7. Импортировать WordPress (если есть экспорт)

```bash
# Сначала dry-run чтобы увидеть, что произойдёт
docker compose exec django python manage.py import_wp \
  --export-dir /data-migration/wp_export \
  --markup /data-migration/markup.csv \
  --dry-run

# Открой созданный лог рядом с markup.csv:
cat data-migration/import_log_*.md | tail -60

# Если всё ок — без --dry-run:
docker compose exec django python manage.py import_wp \
  --export-dir /data-migration/wp_export \
  --markup /data-migration/markup.csv
```

В итоге у тебя должно быть:
- 14 страниц (1 HomePage + 5 ProjectPage + 8 ArticlePage)
- 11 переводов EN
- ~14 картинок в Wagtail Images
- 0 ошибок

## Шаг 8. Открыть в браузере

| URL | Что там |
|---|---|
| http://localhost:8000/ | → редирект на `/ru/` |
| http://localhost:8000/ru/ | главная по-русски |
| http://localhost:8000/en/ | English homepage |
| http://localhost:8000/ru/o-proekte/ | раздел «О проекте» |
| http://localhost:8000/cms/ | **Wagtail-админка** (логин твоим суперюзером) |
| http://localhost:8000/api/toponyms/geojson/ | API топонимов в GeoJSON |
| http://localhost:8000/django-admin/ | Django admin (для тебя) |

## Шаг 9. Карта (опционально, нужен PMTiles файл)

Карта живёт отдельным React-фронтом. Чтобы её увидеть:

```bash
# 1. Скачать PMTiles файл для Сибири
mkdir -p pmtiles-local
# Заходишь на https://app.protomaps.com/downloads/small_planet
# Выбираешь bbox (West=80, South=50, East=150, North=75 для широкой Сибири)
# Получаешь файл .pmtiles на email — скачиваешь
# Кладёшь в pmtiles-local/russia-asian.pmtiles

# 2. Запустить frontend
docker compose --profile map up -d frontend

# 3. Открыть http://localhost:5173/map
```

Если PMTiles нет — карта покажет серый фон, но точки топонимов всё равно будут видны (если seed_demo заполнил).

---

## Повседневные команды

```bash
# Старт/стоп
docker compose up -d              # запустить всё
docker compose stop               # остановить (данные сохранятся)
docker compose start              # снова запустить
docker compose down               # остановить и удалить контейнеры (данные ОСТАНУТСЯ — в volume)
docker compose down -v            # полный снос вместе с БД (опасно — потеряешь данные!)

# Логи
docker compose logs -f django     # смотреть логи Django в реальном времени
docker compose logs --tail=50 tailwind   # последние 50 строк tailwind

# Зайти внутрь контейнера для shell
docker compose exec django bash
docker compose exec django python manage.py shell

# Применить новые миграции (если изменила модели)
docker compose exec django python manage.py makemigrations
docker compose exec django python manage.py migrate

# Пересобрать CSS вручную
docker compose exec tailwind npm run build:css

# Пересобрать Django контейнер (после изменения Dockerfile или pyproject.toml)
docker compose build django
docker compose up -d django

# Полный рестарт
docker compose restart django
```

---

## Что внутри проекта

```
toponymics-live/
├── docker-compose.yaml        ← orchestration
├── .env                       ← секреты (gitignore'но)
├── .env.example               ← пример без секретов
├── backend/                   ← Django + Wagtail
│   ├── manage.py
│   ├── pyproject.toml         ← Python зависимости
│   ├── package.json           ← Tailwind зависимости
│   ├── tailwind.config.js
│   ├── toponymics/            ← settings, urls
│   ├── apps/
│   │   ├── content/           ← Wagtail Page-модели + шаблоны + impоrtёр
│   │   ├── toponyms/          ← модели топонимов и карт
│   │   └── api/               ← DRF для топонимов
│   ├── templates/             ← общие шаблоны (base, 404, includes/)
│   ├── static/                ← CSS, favicon
│   └── Dockerfile
├── frontend/                  ← React + Vite (карта)
├── map-style/                 ← MapLibre стили
├── data-migration/            ← WP экспорт и разметка
│   ├── wp_export/
│   ├── markup.csv
│   ├── wp_export.py           ← скрипт экспорта из WP REST API
│   └── wp_analyze.py          ← скрипт анализа
├── infrastructure/
│   └── scripts/
│       └── vps-init.sh        ← скрипт первой настройки VPS
└── docs/
    └── deployment.md
```

---

## Troubleshooting

**`docker compose up` падает: «port already allocated»**
У тебя что-то уже слушает на 5432, 6379 или 8000. Найди и останови:
```bash
sudo lsof -iTCP -sTCP:LISTEN | grep -E "(5432|6379|8000)"
```
Или закомментируй `ports:` соответствующего сервиса в `docker-compose.yaml`.

**Django контейнер постоянно перезапускается**
```bash
docker compose logs --tail=30 django
```
Скорее всего ошибка в settings или миграциях. Покажи мне лог.

**404 на любой странице после импорта**
Проверь, что Site.root_page правильно указан:
```bash
docker compose exec django python manage.py shell -c "
from wagtail.models import Site
for s in Site.objects.all():
    print(s.hostname, s.port, '→', s.root_page.title, 'live=', s.root_page.live)
"
```
Если `live=False` или нет default Site — повтори импорт с `--update-existing`.

**Tailwind CSS не подхватывается, стили серые**
```bash
docker compose logs tailwind | tail -20
# должна быть строка "Done in XXXms"
# Если нет — посмотри ошибки. Возможно, перезапусти:
docker compose restart tailwind
```
И собери статику заново:
```bash
docker compose exec django python manage.py collectstatic --noinput
```

**Картинки не показываются**
Проверь `media-local/`:
```bash
ls media-local/images/
ls media-local/original_images/
```
Если пусто — импорт картинок не отработал, перезапусти `import_wp` с `--update-existing`.

**Хочу начать заново**
```bash
docker compose down -v          # удалит ВСЕ данные
rm -rf postgres-data/ redis-data/ media-local/
docker compose up -d --build    # с нуля
```

---

## Что дальше (после первого запуска)

Когда увидела сайт работающим:

1. **Прокликай все 14 страниц** в браузере — проверь как контент отрендерился
2. **Открой Wagtail-админку**, попробуй отредактировать одну страницу — нравится ли коллеге будет работать
3. **Создай аккаунт для коллеги** (Settings → Users → Add user, роль Editor)
4. **Реши, нужна ли карта прямо сейчас** — если да, скачай PMTiles
5. **Подумай о production-деплое** — нужен VPS, домен, SSL. Это отдельная инструкция (`infrastructure/scripts/vps-init.sh` уже есть).

Если что-то непонятно или ломается — напиши мне с логами и я разберусь.
