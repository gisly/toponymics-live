"""
Анализатор экспорта WordPress (выгруженного через wp_export.py).

Что делает:
- Сводная статистика по pages/posts/media на каждом языке
- Дерево страниц по URL-структуре
- Распознавание custom post types
- Поиск shortcodes и WP-блоков
- Проверка остатков спам-инжекта
- Генерация CSV для ручной разметки страниц (стратегия B)

Запуск:
    cd data-migration/
    python wp_analyze.py [путь_к_wp_export]

По умолчанию ищет в ./wp_export/

Результаты:
    wp_export/analysis_report.md   — человекочитаемый отчёт
    wp_export/pages_for_review.csv — таблица для разметки страниц
"""
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


# ─── Конфиг ──────────────────────────────────────────────────────────────


WP_EXPORT_DIR = Path(sys.argv[1] if len(sys.argv) > 1 else "./wp_export")

# Языки, которые могли быть в экспорте (в виде суффиксов файлов)
LANGUAGES = ["", "_en"]  # "" = основной язык (русский)

# Известные спам-маркеры (если что-то пропустилось при экспорте)
SPAM_MARKERS = [
    "pornlake", "eromoms", "diabloporn", "indianfuck", "hentai",
    "jungle fucking", "mallu reshma", "futanari", "telugu muslim",
    "سكس", "بزاز",
]

# Регулярки для shortcodes и WP блоков
SHORTCODE_RE = re.compile(r"\[(\w+)[\s\]]")
WP_BLOCK_RE = re.compile(r"<!--\s*wp:(\S+)")
IMG_TAG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)


# ─── HTML helpers ────────────────────────────────────────────────────────


class TextExtractor(HTMLParser):
    """Извлекает только текстовое содержимое из HTML."""

    def __init__(self):
        super().__init__()
        self.text = []

    def handle_data(self, data):
        self.text.append(data)

    def get_text(self):
        return " ".join("".join(self.text).split())


def html_to_text(html: str) -> str:
    """HTML → чистый текст для подсчёта слов и поиска маркеров."""
    if not html:
        return ""
    p = TextExtractor()
    try:
        p.feed(html)
    except Exception:
        return html
    return p.get_text()


# ─── Загрузка экспорта ───────────────────────────────────────────────────


def load_export(lang_suffix: str) -> dict:
    """Грузит pages.json / posts.json / media.json для конкретного языка."""
    result = {}
    for endpoint in ("pages", "posts", "media"):
        filepath = WP_EXPORT_DIR / f"{endpoint}{lang_suffix}.json"
        if not filepath.exists():
            result[endpoint] = []
            continue
        try:
            result[endpoint] = json.loads(filepath.read_text())
        except json.JSONDecodeError as e:
            print(f"  ⚠ Не удалось прочитать {filepath}: {e}", file=sys.stderr)
            result[endpoint] = []
    return result


# ─── Аналитика ───────────────────────────────────────────────────────────


def page_summary(item: dict) -> dict:
    """Извлекает ключевые данные одного WP-элемента."""
    title = item.get("title", {}).get("rendered", "") if isinstance(item.get("title"), dict) else str(item.get("title", ""))
    content_html = item.get("content", {}).get("rendered", "") if isinstance(item.get("content"), dict) else ""
    excerpt_html = item.get("excerpt", {}).get("rendered", "") if isinstance(item.get("excerpt"), dict) else ""

    content_text = html_to_text(content_html)
    word_count = len(content_text.split())

    shortcodes = sorted(set(SHORTCODE_RE.findall(content_html)))
    wp_blocks = sorted(set(WP_BLOCK_RE.findall(content_html)))
    images = IMG_TAG_RE.findall(content_html)

    # Проверка на остатки спама
    spam_hits = [m for m in SPAM_MARKERS if m.lower() in content_html.lower() or m.lower() in title.lower()]

    return {
        "id": item.get("id"),
        "slug": item.get("slug", ""),
        "type": item.get("type", ""),  # 'page', 'post', или custom post type
        "status": item.get("status", ""),
        "parent": item.get("parent", 0),
        "url": item.get("link", ""),
        "title": title.strip(),
        "word_count": word_count,
        "n_images": len(images),
        "shortcodes": shortcodes,
        "wp_blocks": wp_blocks,
        "has_excerpt": bool(excerpt_html.strip()),
        "spam_hits": spam_hits,
        "date": item.get("date", ""),
        "modified": item.get("modified", ""),
        "menu_order": item.get("menu_order", 0),
        # Для разметки человеком
        "_content_preview": content_text[:200],
    }


def build_url_tree(items: list[dict]) -> dict:
    """Строит дерево родитель → дети по полю parent."""
    tree = defaultdict(list)
    for item in items:
        tree[item.get("parent") or 0].append(item)
    return dict(tree)


def render_tree(tree: dict, items_by_id: dict, root_id: int = 0, depth: int = 0, lines: list = None) -> list:
    """Рекурсивно отрисовывает дерево страниц."""
    if lines is None:
        lines = []
    for child in tree.get(root_id, []):
        prefix = "  " * depth + ("└─ " if depth else "")
        title = child["title"][:60] or f"(no title #{child['id']})"
        lines.append(f"{prefix}{title}  [{child['type']}, id={child['id']}]")
        render_tree(tree, items_by_id, child["id"], depth + 1, lines)
    return lines


# ─── Основная работа ─────────────────────────────────────────────────────


def main():
    if not WP_EXPORT_DIR.exists():
        print(f"❌ Папка не найдена: {WP_EXPORT_DIR}")
        print(f"   Передай путь параметром или положи экспорт в ./wp_export/")
        sys.exit(1)

    report_lines = ["# Анализ экспорта WordPress\n"]
    report_lines.append(f"Источник: `{WP_EXPORT_DIR.absolute()}`\n")

    # Список медиафайлов на диске
    media_dir = WP_EXPORT_DIR / "media"
    if media_dir.exists():
        media_files = list(media_dir.iterdir())
        report_lines.append(f"\n## Медиа на диске\n")
        report_lines.append(f"Файлов: **{len(media_files)}**")
        total_size_mb = sum(f.stat().st_size for f in media_files if f.is_file()) / 1024 / 1024
        report_lines.append(f"Суммарный размер: {total_size_mb:.1f} МБ\n")

        # Распределение по типам
        ext_counts = Counter(f.suffix.lower() for f in media_files if f.is_file())
        report_lines.append("По типам:")
        for ext, count in ext_counts.most_common():
            report_lines.append(f"  - `{ext or '(no ext)'}`: {count}")
        report_lines.append("")

    all_summaries = []  # для CSV

    for lang_suffix in LANGUAGES:
        lang_label = "RU (default)" if lang_suffix == "" else lang_suffix[1:].upper()
        report_lines.append(f"\n## Язык: {lang_label}\n")

        data = load_export(lang_suffix)
        if not any([data["pages"], data["posts"], data["media"]]):
            report_lines.append(f"_Экспорт не найден или пустой._\n")
            continue

        report_lines.append(f"- Страниц (pages): **{len(data['pages'])}**")
        report_lines.append(f"- Постов (posts): **{len(data['posts'])}**")
        report_lines.append(f"- Медиа-записей: **{len(data['media'])}**")

        all_items = data["pages"] + data["posts"]
        summaries = [page_summary(item) for item in all_items]

        for s in summaries:
            s["language"] = lang_label

        all_summaries.extend(summaries)

        # Распределение по post types
        type_counts = Counter(s["type"] for s in summaries)
        report_lines.append(f"\n**Post types:**")
        for ptype, count in type_counts.most_common():
            report_lines.append(f"  - `{ptype}`: {count}")

        # Статусы
        status_counts = Counter(s["status"] for s in summaries)
        report_lines.append(f"\n**Статусы:**")
        for status, count in status_counts.most_common():
            report_lines.append(f"  - `{status}`: {count}")

        # Спам
        spam_pages = [s for s in summaries if s["spam_hits"]]
        if spam_pages:
            report_lines.append(f"\n**⚠ Спам-маркеры найдены в {len(spam_pages)} страницах:**")
            for s in spam_pages[:10]:
                report_lines.append(f"  - id={s['id']} '{s['title']}': {s['spam_hits']}")
            if len(spam_pages) > 10:
                report_lines.append(f"  - ... и ещё {len(spam_pages) - 10}")
        else:
            report_lines.append(f"\n✓ Спам-маркеров не найдено.")

        # Shortcodes
        all_shortcodes = Counter()
        for s in summaries:
            for sc in s["shortcodes"]:
                all_shortcodes[sc] += 1
        if all_shortcodes:
            report_lines.append(f"\n**Shortcodes (топ-15):**")
            for sc, count in all_shortcodes.most_common(15):
                report_lines.append(f"  - `[{sc}]`: {count}")

        # WP-блоки
        all_blocks = Counter()
        for s in summaries:
            for b in s["wp_blocks"]:
                all_blocks[b] += 1
        if all_blocks:
            report_lines.append(f"\n**Gutenberg блоки (топ-15):**")
            for b, count in all_blocks.most_common(15):
                report_lines.append(f"  - `wp:{b}`: {count}")

        # Дерево страниц
        items_by_id = {item["id"]: item for item in all_items}
        page_summaries = [s for s in summaries if s["type"] == "page"]
        if page_summaries:
            # Привести summaries обратно к формату для tree (нужен parent, id, title, type)
            pseudo_items = [
                {"id": s["id"], "parent": s["parent"], "title": s["title"], "type": s["type"]}
                for s in page_summaries
            ]
            tree = build_url_tree(pseudo_items)
            tree_lines = render_tree(tree, items_by_id)
            if tree_lines:
                report_lines.append(f"\n**Дерево страниц:**\n```")
                report_lines.extend(tree_lines[:80])
                if len(tree_lines) > 80:
                    report_lines.append(f"... и ещё {len(tree_lines) - 80} строк")
                report_lines.append("```")

        # Самые длинные страницы (вероятно — главные нарративы)
        longest = sorted(summaries, key=lambda x: -x["word_count"])[:10]
        report_lines.append(f"\n**Самые длинные страницы:**")
        for s in longest:
            report_lines.append(f"  - {s['word_count']} слов: `{s['title']}` (id={s['id']}, type={s['type']})")

    # ─── Запись отчёта и CSV ─────────────────────────────────────────────

    report_path = WP_EXPORT_DIR / "analysis_report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\n✓ Отчёт записан: {report_path}")

    # CSV для разметки
    csv_path = WP_EXPORT_DIR / "pages_for_review.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "language", "type", "status", "url", "title",
            "word_count", "n_images", "parent_id",
            "WAGTAIL_TYPE",       # <- для тебя
            "WAGTAIL_PARENT",     # <- для тебя
            "ACTION",             # <- для тебя: import | skip | merge_into:<id>
            "NOTES",              # <- для тебя
            "shortcodes", "wp_blocks", "spam_hits",
            "preview",
        ])
        for s in all_summaries:
            writer.writerow([
                s["id"], s["language"], s["type"], s["status"], s["url"], s["title"],
                s["word_count"], s["n_images"], s["parent"],
                "",  # WAGTAIL_TYPE — пусто
                "",  # WAGTAIL_PARENT — пусто
                "",  # ACTION — пусто
                "",  # NOTES — пусто
                ", ".join(s["shortcodes"]),
                ", ".join(s["wp_blocks"]),
                ", ".join(s["spam_hits"]),
                s["_content_preview"],
            ])

    print(f"✓ CSV для разметки: {csv_path}")
    print(f"\nДальше: открой {csv_path.name} в LibreOffice/Excel,")
    print(f"  заполни колонки WAGTAIL_TYPE / WAGTAIL_PARENT / ACTION для каждой строки,")
    print(f"  сохрани и передай дальше в импортер.")


if __name__ == "__main__":
    main()
