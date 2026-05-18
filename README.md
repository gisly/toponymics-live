# toponymics-live

Цифровая платформа индигенной топонимики коренных народов Сибири.

**Стек:**
- Wagtail 6 (CMS, многоязычный контент через wagtail-localize)
- Django 5 + DRF (API для топонимов и рукописных карт)
- PostgreSQL 16, Redis 7
- Tailwind CSS (стили для шаблонов)
- React + Vite + MapLibre GL JS (карта на странице Платформа)

## Быстрый старт

**Полная пошаговая инструкция:** [`docs/setup.md`](docs/setup.md)

Если коротко:
```bash
cp .env.example .env
docker compose up -d --build
docker compose exec django python manage.py createsuperuser
```

После этого:
- `http://localhost:8000/ru/` — сайт по-русски
- `http://localhost:8000/en/` — English
- `http://localhost:8000/cms/` — Wagtail-админка
- `http://localhost:8000/api/` — REST API

## Структура проекта

```
backend/           Django + Wagtail (Python 3.12)
  apps/
    content/       Wagtail Page-модели, шаблоны, WP-импортёр
    toponyms/      модели топонимов и рукописных карт
    api/           DRF для топонимов
  templates/       общие Jinja-шаблоны (base, 404, includes/)
  static/          CSS, favicon

frontend/          React + Vite (карта)
map-style/         MapLibre стиль
data-migration/    скрипты экспорта/анализа/импорта WordPress контента
infrastructure/    скрипты деплоя на VPS
docs/              документация (setup, deployment)
```

## Документация

- [`docs/setup.md`](docs/setup.md) — установка и запуск с нуля
- [`docs/deployment.md`](docs/deployment.md) — деплой на VPS (TBD)
- [`infrastructure/scripts/vps-init.sh`](infrastructure/scripts/vps-init.sh) — скрипт первой настройки сервера

## Лицензия

Код: MIT (см. LICENSE).
Контент сайта: CC BY-SA 4.0.
