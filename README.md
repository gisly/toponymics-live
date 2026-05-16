# toponymics-live

Цифровая платформа индигенной топонимики. Wagtail (контент) + Django REST (топонимы) + React/MapLibre (фронт) + PMTiles (карта).

## Quickstart (локально)

Требуется: Docker, Docker Compose, Git.

```bash
git clone <url> toponymics-live
cd toponymics-live
cp .env.example .env
# Отредактируй .env при необходимости (для локалки можно оставить как есть)
docker compose up --build
```

После того как все сервисы поднимутся:

- Wagtail-админка: http://localhost:8000/cms/ (логин/пароль создаются при первом запуске, см. ниже)
- Django REST API: http://localhost:8000/api/
- React SPA (dev): http://localhost:5173/

### Первый запуск — суперюзер

После `docker compose up` в новом терминале:

```bash
docker compose exec django python manage.py createsuperuser
```

## Структура

```
backend/         — Django + Wagtail (Python 3.12)
frontend/        — React + Vite + TypeScript (Node 20)
map-style/       — MapLibre style.json и связанные ресурсы
infrastructure/  — nginx config, deployment scripts
data-migration/  — одноразовые скрипты миграции из WP/старой БД
docs/            — документация проекта
```

## Production

См. `docs/deployment.md` (будет позже).

## Лицензия

Код: MIT (см. LICENSE).
Контент сайта: CC BY-SA 4.0.
