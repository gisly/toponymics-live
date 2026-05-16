"""
Экспорт контента из WordPress через REST API с очисткой от инжектированного спама.

Запуск:
    python wp_export.py

Результат:
    ./wp_export/
        pages.json
        posts.json
        media.json
        media/  — скачанные файлы
"""
import json
import re
import sys
from pathlib import Path
import time

import requests

BASE = "https://toponymics-live.net/wp-json/wp/v2"
OUT = Path("./wp_export")
OUT.mkdir(exist_ok=True)
(OUT / "media").mkdir(exist_ok=True)

# Список доменов, обнаруженных в инжекте footer'а
SPAM_DOMAINS = [
    "pornlake", "eromoms", "arabicpornsex", "sexcamslive", "diabloporn",
    "pornichka", "indianfuck", "porndad", "hentai-naruto", "eropornstars",
    "sexyindianporno", "hindi-porno", "mobhentai", "pornmovieswatch",
    "arabpussyporn", "xpussy", "xvideoco", "xnxx",
]

# Известные фразовые маркеры инжекта (грубо, но эффективно)
SPAM_PHRASES = [
    r"jungle fucking", r"mallu reshma", r"hindu ladies", r"myhotsite video",
    r"indian mom", r"futanari maid", r"pv sindhu hot", r"maluxvideo",
    r"alpha porn", r"hentai magnas", r"telugu muslim sex", r"سكس",
    r"بزاز", r"النيك",
]


def clean_text(text):
    """Удаляет фрагменты со спам-доменами и спам-фразами."""
    if not text:
        return text
    # Убираем ссылки на спам-домены целиком (всё что между разделителями)
    for domain in SPAM_DOMAINS:
        # Удаляем строки, содержащие домен
        text = re.sub(rf"[^\n]*{re.escape(domain)}[^\n]*\n?", "", text, flags=re.IGNORECASE)
    # Удаляем строки со спам-фразами
    for phrase in SPAM_PHRASES:
        text = re.sub(rf"[^\n]*{phrase}[^\n]*\n?", "", text, flags=re.IGNORECASE)
    return text.strip()


def clean_item(item):
    """Чистит rendered-поля у объекта WP."""
    for field in ("title", "content", "excerpt"):
        if field in item and isinstance(item[field], dict):
            item[field]["rendered"] = clean_text(item[field].get("rendered", ""))
    return item


def fetch_all(endpoint, lang=None):
    """Постранично выгружает endpoint."""
    items, page = [], 1
    while True:
        params = {"per_page": 100, "page": page, "_embed": 1}
        if lang:
            params["lang"] = lang  # для Polylang; WPML может требовать другой параметр
        try:
            r = requests.get(f"{BASE}/{endpoint}", params=params, timeout=30)
        except requests.RequestException as e:
            print(f"  Сетевая ошибка: {e}", file=sys.stderr)
            break

        if r.status_code == 400:
            # Обычно — конец пагинации
            break
        if not r.ok:
            print(f"  Status {r.status_code} for page {page}", file=sys.stderr)
            break

        batch = r.json()
        if not isinstance(batch, list) or not batch:
            break
        items.extend(batch)
        page += 1
        time.sleep(0.5)  # вежливость
    return items


def download_media(items):
    """Скачивает файлы из media-эндпоинта."""
    for m in items:
        url = m.get("source_url")
        if not url:
            continue
        fname = url.split("/")[-1]
        target = OUT / "media" / fname
        if target.exists():
            continue
        try:
            r = requests.get(url, timeout=60)
            if r.ok:
                target.write_bytes(r.content)
                print(f"  ↓ {fname}")
        except requests.RequestException as e:
            print(f"  Не скачано {url}: {e}", file=sys.stderr)


if __name__ == "__main__":
    # Языки — добавь сюда коды, которые поддерживает текущий многоязычный плагин
    LANGUAGES = [None, "en"]  # None = основной язык

    for lang in LANGUAGES:
        suffix = f"_{lang}" if lang else ""
        for endpoint in ("pages", "posts", "media"):
            print(f"Выгружаем {endpoint}{suffix}…")
            items = fetch_all(endpoint, lang=lang)
            cleaned = [clean_item(item) for item in items]
            outfile = OUT / f"{endpoint}{suffix}.json"
            outfile.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2))
            print(f"  → {len(cleaned)} → {outfile}")

            if endpoint == "media":
                print("  Скачиваем файлы…")
                download_media(items)

    print("\nГотово. Содержимое в ./wp_export/")
    print("Дальше — пиши импортер wp_to_wagtail.py для переноса в Wagtail.")
