# Развёртывание

Краткие заметки. Полный production-setup будет позже.

## Локальная разработка

```bash
git clone <url> toponymics-live
cd toponymics-live
cp .env.example .env
docker compose up --build
```

После того как сервисы поднялись:

```bash
# Создать суперюзера
docker compose exec django python manage.py createsuperuser

# Залить демо-данные (несколько регионов, типов и топонимов)
docker compose exec django python manage.py seed_demo

# Открыть в браузере:
# http://localhost:8000/cms/    — Wagtail
# http://localhost:8000/api/    — DRF browsable API
# http://localhost:5173/        — React SPA
# http://localhost:5173/map     — карта (будет показывать background; топонимы появятся после seed_demo)
```

## Карта — PMTiles

См. `map-style/README.md` для инструкций по получению `russia-asian.pmtiles`.

Положи файл в `pmtiles-local/russia-asian.pmtiles` — он автоматически замаппится в контейнер frontend как `/pmtiles/russia-asian.pmtiles`.

## Production (на VPS)

Будет реализовано отдельно: `docker-compose.prod.yaml` + Caddy/nginx + Let's Encrypt + бэкапы.

Заготовка плана:

1. Hetzner CX22 + Volume 40 ГБ (Falkenstein или Nürnberg)
2. DNS: `new.toponymics-live.net` → IP VPS
3. На VPS: установить Docker, склонировать репозиторий
4. Скопировать `.env.example` → `.env`, заполнить production-значения (SECRET_KEY, пароли БД, домены)
5. `docker compose -f docker-compose.prod.yaml up -d --build`
6. `docker compose exec django python manage.py createsuperuser`
7. Caddy получит Let's Encrypt сертификат автоматически
8. После проверки — переключить DNS `toponymics-live.net` на новый IP
