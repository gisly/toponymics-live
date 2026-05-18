"""
Импортёр WordPress контента в Wagtail.

Использование:
    docker compose exec django python manage.py import_wp \\
        --export-dir /app/wp_export \\
        --markup /app/wp_export/markup.csv \\
        [--dry-run] [--update-existing]

Что делает:
1. Читает CSV-разметку с указаниями WAGTAIL_TYPE / WAGTAIL_PARENT / ACTION
2. Топологически сортирует страницы по родителям
3. Создаёт страницы нужных типов в правильной иерархии
4. Конвертирует WP HTML в StreamField блоки (paragraph, heading, image, quote)
5. Скачивает картинки в Wagtail Images, привязывает к страницам
6. Создаёт переводы через wagtail-localize для пар english_of:<id>
7. Пишет подробный markdown-лог: что куда легло, какие блоки создались

Идемпотентность: повторный запуск с --update-existing обновит существующие
страницы по url. Без флага — пропустит уже существующие.
"""
from __future__ import annotations

import csv
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from django.core.files.images import ImageFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify
from wagtail.images.models import Image as WagtailImage
from wagtail.models import Locale, Page, Site

from apps.content.models import ArticlePage, EventPage, HomePage, ProjectPage, TeamMemberPage
from apps.content.utils.html_to_streamfield import HtmlToStreamField

logger = logging.getLogger(__name__)


# ─── Маппинг WAGTAIL_TYPE → Page класс ─────────────────────────────────


PAGE_TYPE_MAP = {
    "HomePage": HomePage,
    "ProjectPage": ProjectPage,
    "ArticlePage": ArticlePage,
    "TeamMemberPage": TeamMemberPage,
    "EventPage": EventPage,
}


# ─── Разобранная строка разметки ───────────────────────────────────────


@dataclass
class MarkupRow:
    """Одна строка из markup.csv после парсинга."""

    wp_id: int
    language: str          # 'RU' или 'EN'
    url: str
    title: str
    word_count: int
    wagtail_type: str | None   # 'HomePage', 'ProjectPage', ... или None
    wagtail_parent: str        # 'root', '<wp_id>', или ''
    action: str                # 'import', 'skip', 'update_home', 'english_of:N', ...
    notes: str

    @property
    def lang_code(self) -> str:
        return "ru" if self.language.startswith("RU") else "en"


@dataclass
class ImportStats:
    """Статистика для финального отчёта."""

    pages_created: int = 0
    pages_updated: int = 0
    pages_skipped: int = 0
    pages_failed: int = 0
    translations_linked: int = 0
    images_uploaded: int = 0
    blocks_created: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ─── Management Command ────────────────────────────────────────────────


class Command(BaseCommand):
    help = "Импорт страниц из WP-экспорта в Wagtail на основе CSV-разметки"

    def add_arguments(self, parser):
        parser.add_argument(
            "--export-dir", required=True, type=Path,
            help="Папка с WP-экспортом (pages.json, posts.json, media/)",
        )
        parser.add_argument(
            "--markup", required=True, type=Path,
            help="CSV-файл с разметкой страниц",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Не сохранять в БД, только показать что будет сделано",
        )
        parser.add_argument(
            "--update-existing", action="store_true",
            help="Обновить страницы, которые уже есть в Wagtail (по slug+parent)",
        )
        parser.add_argument(
            "--log-output", type=Path, default=None,
            help="Куда писать markdown-лог (по умолчанию: рядом с markup.csv)",
        )

    def handle(self, *args, **options):
        self.export_dir: Path = options["export_dir"]
        self.markup_path: Path = options["markup"]
        self.dry_run: bool = options["dry_run"]
        self.update_existing: bool = options["update_existing"]
        self.log_output: Path = options["log_output"] or (
            self.markup_path.parent / f"import_log_{datetime.now():%Y%m%d_%H%M%S}.md"
        )

        # Проверки
        if not self.export_dir.exists():
            raise CommandError(f"Папка не найдена: {self.export_dir}")
        if not self.markup_path.exists():
            raise CommandError(f"CSV не найден: {self.markup_path}")

        self.media_dir = self.export_dir / "media"
        self.stats = ImportStats()
        self.log_lines: list[str] = []

        self._log_header("Импорт WordPress → Wagtail")
        self.log(f"- Экспорт: `{self.export_dir.absolute()}`")
        self.log(f"- Разметка: `{self.markup_path.absolute()}`")
        self.log(f"- Dry-run: **{'да' if self.dry_run else 'нет'}**")
        self.log(f"- Обновлять существующие: {'да' if self.update_existing else 'нет'}")
        self.log("")

        # Загрузка
        self.markup_rows = self._load_markup()

        # У этого проекта (toponymics-live.net) английские страницы лежат
        # в общем pages.json — Polylang/похожий плагин не разделил их по lang.
        # Различаем по URL-маркеру: всё с '/en/' в link — английское.
        # На случай "правильного" экспорта с разделением — поддерживаем и pages_en.json.
        all_pages = self._load_wp_json("pages.json")
        extra_en_pages = self._load_wp_json("pages_en.json")  # обычно []

        ru_pages = [p for p in all_pages if "/en/" not in p.get("link", "")]
        en_pages_from_main = [p for p in all_pages if "/en/" in p.get("link", "")]
        en_pages = en_pages_from_main + extra_en_pages

        self.wp_pages = ru_pages
        self.wp_pages_en = en_pages
        self.wp_media = self._load_wp_json("media.json")

        # Индекс для быстрого доступа по WP id — обе языковые версии
        self.wp_by_id: dict[int, dict] = {p["id"]: p for p in ru_pages + en_pages}

        self.log(f"Загружено: разметки {len(self.markup_rows)} строк, "
                 f"WP-страниц {len(ru_pages)} (RU) + {len(en_pages)} (EN), "
                 f"медиа-записей {len(self.wp_media)}.")
        if en_pages_from_main:
            self.log(f"  ({len(en_pages_from_main)} английских страниц извлечено "
                     f"из общего pages.json по URL-маркеру '/en/')")

        # Маппинг WP URL → локальный файл (для резолва картинок в контенте)
        self.url_to_local: dict[str, Path] = self._build_media_index()

        # Шаг 1: импортируем все страницы по action=import (без переводов)
        self._log_header("Шаг 1: создание страниц")
        # Wagtail Page ID для каждого WP ID — нужно для родителей и переводов
        self.wp_id_to_wagtail_page: dict[int, Page] = {}

        # Топосортировка: сначала те, у кого parent='root', потом дочки
        import_rows = [r for r in self.markup_rows if r.action in ("import", "update_home")]
        sorted_rows = self._topological_sort(import_rows)

        for row in sorted_rows:
            try:
                page = self._import_page(row)
                if page:
                    self.wp_id_to_wagtail_page[row.wp_id] = page
            except Exception as e:
                self.stats.pages_failed += 1
                self.stats.errors.append(f"id={row.wp_id} '{row.title}': {e}")
                self.log(f"  ❌ **Ошибка**: id={row.wp_id} '{row.title}': `{e}`")
                logger.exception("Failed to import page")

        # Шаг 2: связываем переводы
        self._log_header("Шаг 2: связывание переводов")
        translation_rows = [r for r in self.markup_rows if r.action.startswith("english_of:")]

        # Сортируем по топологии родителей в RU-дереве: если RU id=662 (About)
        # перевели перед RU id=49 (Контакты), то и EN-переводы должны идти в
        # том же порядке — иначе wagtail-localize не сможет привязать
        # английского ребёнка к ещё не существующему английскому родителю.
        ru_id_order = {row.wp_id: i for i, row in enumerate(sorted_rows)}

        def translation_sort_key(row):
            # Извлекаем RU id из "english_of:NNN"
            try:
                ru_id = int(row.action.partition(":")[2])
            except ValueError:
                return float("inf")
            return ru_id_order.get(ru_id, float("inf"))

        translation_rows.sort(key=translation_sort_key)

        for row in translation_rows:
            try:
                self._link_translation(row)
            except Exception as e:
                self.stats.errors.append(f"Перевод id={row.wp_id}: {e}")
                self.log(f"  ❌ **Ошибка перевода**: id={row.wp_id}: `{e}`")
                logger.exception("Failed to link translation")

        # Финальный отчёт
        self._write_summary()
        self._save_log()

        if self.stats.errors:
            self.stdout.write(self.style.WARNING(
                f"\nИмпорт завершён с {len(self.stats.errors)} ошибками. "
                f"См. {self.log_output}"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\n✓ Импорт завершён успешно. См. {self.log_output}"
            ))

    # ─── Загрузка данных ────────────────────────────────────────────────

    def _load_markup(self) -> list[MarkupRow]:
        rows = []
        with self.markup_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                if not r.get("id") or not r.get("id").strip():
                    continue
                try:
                    rows.append(MarkupRow(
                        wp_id=int(r["id"]),
                        language=r.get("language", "RU"),
                        url=r.get("url", ""),
                        title=r.get("title", ""),
                        word_count=int(r.get("word_count") or 0),
                        wagtail_type=r.get("WAGTAIL_TYPE", "").strip() or None,
                        wagtail_parent=r.get("WAGTAIL_PARENT", "").strip(),
                        action=r.get("ACTION", "").strip(),
                        notes=r.get("NOTES", ""),
                    ))
                except ValueError as e:
                    self.log(f"⚠ Невалидная строка в CSV: {r} ({e})")
        return rows

    def _load_wp_json(self, filename: str) -> list[dict]:
        path = self.export_dir / filename
        if not path.exists():
            return []
        return json.loads(path.read_text())

    def _build_media_index(self) -> dict[str, Path]:
        """Строит маппинг source_url → локальный путь по media.json."""
        index = {}
        for m in self.wp_media:
            src = m.get("source_url")
            if not src:
                continue
            filename = src.rsplit("/", 1)[-1]
            from urllib.parse import unquote
            filename = unquote(filename)
            local = self.media_dir / filename
            if local.exists():
                index[src] = local
        return index

    # ─── Топологическая сортировка ──────────────────────────────────────

    def _topological_sort(self, rows: list[MarkupRow]) -> list[MarkupRow]:
        """Возвращает строки в порядке, где родители идут перед детьми."""
        by_id = {r.wp_id: r for r in rows}
        result = []
        visited = set()

        def visit(row: MarkupRow):
            if row.wp_id in visited:
                return
            visited.add(row.wp_id)
            parent = row.wagtail_parent
            if parent and parent != "root":
                try:
                    parent_id = int(parent)
                    if parent_id in by_id:
                        visit(by_id[parent_id])
                except ValueError:
                    pass
            result.append(row)

        for row in rows:
            visit(row)
        return result

    # ─── Импорт одной страницы ──────────────────────────────────────────

    def _import_page(self, row: MarkupRow) -> Page | None:
        """Создаёт или обновляет одну Wagtail-страницу."""
        wp_data = self.wp_by_id.get(row.wp_id)
        if not wp_data:
            raise ValueError(f"WP-страница id={row.wp_id} не найдена в pages.json")

        self.log(f"\n### id={row.wp_id} `{row.title}` → {row.wagtail_type}")

        # Готовим контент: HTML → StreamField блоки
        content_html = wp_data.get("content", {}).get("rendered", "") if isinstance(wp_data.get("content"), dict) else ""
        converter = HtmlToStreamField(media_dir=self.media_dir, source_url_to_local={
            url: path for url, path in self.url_to_local.items()
        })
        conv_result = converter.convert(content_html, page_id=row.wp_id)

        self.log(f"- HTML → {len(conv_result.blocks)} блоков, {len(conv_result.pending_images)} картинок")
        for w in conv_result.warnings:
            self.log(f"  - ⚠ {w}")
            self.stats.warnings.append(f"id={row.wp_id}: {w}")

        # Загружаем картинки в Wagtail Images (или, в dry-run, пропускаем)
        image_objs: list[WagtailImage | None] = []
        for local_path, alt, caption in conv_result.pending_images:
            img = self._upload_image(local_path, alt) if not self.dry_run else None
            image_objs.append(img)
            if img:
                self.stats.images_uploaded += 1

        # Подменяем плейсхолдеры на реальные image ID
        final_blocks = []
        for block_type, value in conv_result.blocks:
            if block_type == "__image_placeholder__":
                idx = value
                if idx < len(image_objs) and image_objs[idx]:
                    final_blocks.append(("image", image_objs[idx].id))
                    self._count_block("image")
            else:
                final_blocks.append((block_type, value))
                self._count_block(block_type)

        # Слаг
        slug = wp_data.get("slug") or slugify(row.title)

        # Особый случай: update_home — обновляем дефолтную HomePage
        if row.action == "update_home":
            return self._update_existing_homepage(row, wp_data, final_blocks)

        # Обычный случай: создаём страницу нужного типа
        page_class = PAGE_TYPE_MAP.get(row.wagtail_type)
        if not page_class:
            raise ValueError(f"Неизвестный WAGTAIL_TYPE: {row.wagtail_type}")

        # Родитель
        parent_page = self._resolve_parent(row)
        self.log(f"- Родитель: `{parent_page}` (path={parent_page.path})")

        # Не дублируем, если уже есть
        existing = parent_page.get_children().filter(slug=slug).first()
        if existing:
            if not self.update_existing:
                self.log(f"- Уже существует, пропускаем (используй --update-existing для обновления)")
                self.stats.pages_skipped += 1
                return existing.specific
            else:
                self.log(f"- Обновляем существующую страницу")
                page = existing.specific
                self._fill_page(page, page_class, row, wp_data, final_blocks)
                if not self.dry_run:
                    page.save_revision().publish()
                self.stats.pages_updated += 1
                return page

        # Создание новой
        page = page_class(
            title=row.title,
            slug=slug,
            locale=Locale.objects.get(language_code="ru"),
        )
        self._fill_page(page, page_class, row, wp_data, final_blocks)

        if self.dry_run:
            self.log(f"- [DRY-RUN] Создал бы `{page_class.__name__}` slug=`{slug}`")
        else:
            parent_page.add_child(instance=page)
            page.save_revision().publish()
            self.log(f"- ✓ Создана `{page_class.__name__}` (Wagtail id={page.id}, url={page.url})")
            self.stats.pages_created += 1

        return page

    def _fill_page(self, page: Page, page_class: type, row: MarkupRow,
                   wp_data: dict, blocks: list[tuple[str, Any]]):
        """Заполняет поля страницы в зависимости от её типа."""
        page.title = row.title

        # По умолчанию показываем в меню — кроме footer-only страниц
        # (политика, условия использования и т.п.)
        footer_only_keywords = ("footer", "policy", "политик", "правила")
        notes_lower = (row.notes or "").lower()
        is_footer_only = any(kw in notes_lower for kw in footer_only_keywords)
        page.show_in_menus = not is_footer_only

        # У всех Page-типов есть body как StreamField
        if hasattr(page, "body"):
            page.body = self._blocks_to_streamfield_value(blocks, page_class, "body")

        # У HomePage и ProjectPage — поле intro (RichText)
        if hasattr(page, "intro"):
            excerpt_html = wp_data.get("excerpt", {}).get("rendered", "") if isinstance(wp_data.get("excerpt"), dict) else ""
            page.intro = excerpt_html.strip() if isinstance(page.intro, str) or page.intro is None or hasattr(page, "intro") else ""

        # ArticlePage специфика
        if isinstance(page, ArticlePage):
            page.publish_date = self._parse_wp_date(wp_data.get("date"))

    def _blocks_to_streamfield_value(self, blocks: list, page_class: type, field_name: str):
        """Превращает [(type, value)] список в значение для StreamField."""
        return [
            {"type": btype, "value": bvalue}
            for btype, bvalue in blocks
            if btype != "__image_placeholder__"  # на всякий случай
        ]

    def _resolve_parent(self, row: MarkupRow) -> Page:
        """Находит Wagtail-родителя по WAGTAIL_PARENT."""
        if row.wagtail_parent in ("", "root"):
            # Корневые страницы — дочки HomePage. Если её ещё нет, используем
            # корневую Page (depth=1) — туда добавится первая страница.
            home = HomePage.objects.first()
            if home:
                return home
            # HomePage ещё не создан — берём корневую служебную Page
            root_page = Page.objects.filter(depth=1).first()
            if not root_page:
                raise CommandError("В Wagtail вообще нет корневой страницы. Прогони `migrate`.")
            return root_page

        try:
            parent_wp_id = int(row.wagtail_parent)
        except ValueError:
            raise CommandError(f"WAGTAIL_PARENT='{row.wagtail_parent}' — не число и не 'root'")

        parent_page = self.wp_id_to_wagtail_page.get(parent_wp_id)
        if not parent_page:
            raise CommandError(
                f"Родитель WP id={parent_wp_id} ещё не создан (для строки id={row.wp_id}). "
                f"Проверь топосортировку и убедись, что parent размечен в CSV с action=import."
            )
        return parent_page

    def _update_existing_homepage(self, row: MarkupRow, wp_data: dict,
                                  blocks: list[tuple[str, Any]]) -> Page:
        """Создаёт или обновляет HomePage из контента id=160.

        Если HomePage уже есть — обновляет её.
        Если есть только дефолтная Wagtail-страница "Welcome" — заменяет её
        новой HomePage и переключает Site root на неё.
        """
        existing_home = HomePage.objects.first()
        if existing_home:
            existing_home.title = row.title
            self._fill_page(existing_home, HomePage, row, wp_data, blocks)
            if not self.dry_run:
                existing_home.save_revision().publish()
            self.log(f"- ✓ Обновлена существующая HomePage (id={existing_home.id})")
            self.stats.pages_updated += 1
            return existing_home

        # HomePage нет — создаём как дочку корневой Page
        root_page = Page.objects.filter(depth=1).first()
        if not root_page:
            raise CommandError("Нет корневой Page (depth=1). Прогони `migrate`.")

        slug = wp_data.get("slug") or "home"
        new_home = HomePage(
            title=row.title,
            slug=slug,
            locale=Locale.objects.get(language_code="ru"),
        )
        self._fill_page(new_home, HomePage, row, wp_data, blocks)

        if self.dry_run:
            self.log(f"- [DRY-RUN] Создал бы HomePage slug=`{slug}`")
            return new_home

        # ВАЖНО: удалить дефолтную "Welcome to Wagtail" ДО создания нашей HomePage,
        # иначе будет конфликт slug. Дефолтная — это любой ребёнок root_page,
        # у которого тип не HomePage (обычно она с slug='home').
        from django.contrib.contenttypes.models import ContentType
        homepage_ct = ContentType.objects.get_for_model(HomePage)
        for default_page in root_page.get_children().exclude(content_type=homepage_ct):
            self.log(f"- ✓ Удаляем дефолтную страницу '{default_page.title}' (slug={default_page.slug})")
            default_page.delete()

        # ВАЖНО: после delete() treebeard-кеш в root_page устарел.
        # Перечитываем из БД, иначе add_child() упадёт на _inc_path.
        root_page.refresh_from_db()

        root_page.add_child(instance=new_home)
        new_home.save_revision().publish()
        self.log(f"- ✓ Создана HomePage (id={new_home.id})")

        # Переключаем Site root на нашу HomePage.
        # Если дефолтный Site был удалён вместе с дефолтной страницей —
        # пересоздаём его.
        site = Site.objects.filter(is_default_site=True).first()
        if site:
            site.root_page = new_home
            site.save()
            self.log(f"- ✓ Site default root переключён на новую HomePage")
        else:
            Site.objects.create(
                hostname="localhost",
                port=80,
                is_default_site=True,
                root_page=new_home,
                site_name="Топонимика",
            )
            self.log(f"- ✓ Создан default Site → HomePage")

        self.stats.pages_created += 1
        return new_home

    # ─── Картинки ────────────────────────────────────────────────────────

    def _upload_image(self, local_path: Path, alt: str) -> WagtailImage | None:
        """Загружает локальный файл в Wagtail Images."""
        if not local_path.exists():
            return None

        # Проверяем, не загружали ли уже (по имени файла)
        existing = WagtailImage.objects.filter(title=local_path.name).first()
        if existing:
            return existing

        with local_path.open("rb") as f:
            wagtail_image = WagtailImage(
                title=alt or local_path.stem,
                file=ImageFile(f, name=local_path.name),
            )
            wagtail_image.save()
        return wagtail_image

    # ─── Переводы ────────────────────────────────────────────────────────

    def _link_translation(self, row: MarkupRow):
        """Связывает английскую страницу с русской как перевод через wagtail-localize."""
        # Парсим english_of:<id>
        prefix, _, ru_id_str = row.action.partition(":")
        try:
            ru_wp_id = int(ru_id_str)
        except ValueError:
            raise ValueError(f"Невалидный action: {row.action}")

        ru_page = self.wp_id_to_wagtail_page.get(ru_wp_id)
        if not ru_page:
            self.log(f"  ⚠ Не нашли русскую страницу для перевода id={ru_wp_id}")
            return

        wp_en = self.wp_by_id.get(row.wp_id)
        if not wp_en:
            self.log(f"  ⚠ Не нашли английский WP-контент id={row.wp_id}")
            return

        self.log(f"\n### Перевод id={row.wp_id} '{row.title}' → пара для RU id={ru_wp_id}")

        # Импортируем wagtail_localize здесь, чтобы команда работала даже без неё
        try:
            from wagtail_localize.operations import translate_object
        except ImportError:
            self.log(f"  ⚠ wagtail_localize не установлен — пропускаем")
            return

        en_locale = Locale.objects.filter(language_code="en").first()
        if not en_locale:
            en_locale = Locale.objects.create(language_code="en")

        # Конвертируем английский контент
        content_html = wp_en.get("content", {}).get("rendered", "") if isinstance(wp_en.get("content"), dict) else ""
        converter = HtmlToStreamField(media_dir=self.media_dir, source_url_to_local=self.url_to_local)
        conv_result = converter.convert(content_html)

        # Готовим image-блоки (для англ. версии могут быть свои картинки)
        image_objs = []
        for local_path, alt, caption in conv_result.pending_images:
            img = self._upload_image(local_path, alt) if not self.dry_run else None
            image_objs.append(img)
            if img:
                self.stats.images_uploaded += 1
        final_blocks = []
        for btype, value in conv_result.blocks:
            if btype == "__image_placeholder__":
                idx = value
                if idx < len(image_objs) and image_objs[idx]:
                    final_blocks.append(("image", image_objs[idx].id))
            else:
                final_blocks.append((btype, value))

        if self.dry_run:
            self.log(f"  [DRY-RUN] Связал бы перевод EN id={row.wp_id} ↔ RU id={ru_wp_id}")
            return

        # Проверим, нет ли уже английского перевода
        try:
            en_translation = ru_page.get_translation(en_locale)
            self.log(f"  - Перевод уже существует, обновляем контент")
        except Page.DoesNotExist:
            # Создаём через wagtail-localize
            translate_object(ru_page, [en_locale])
            ru_page.refresh_from_db()
            en_translation = ru_page.get_translation(en_locale)
            self.log(f"  - Создан английский перевод")

        # Обновляем поля английского перевода
        en_specific = en_translation.specific
        en_specific.title = row.title

        # Slug: берём английский из WP-данных, не оставляем дублирование русского
        wp_slug = wp_en.get("slug")
        if wp_slug and wp_slug != en_specific.slug:
            # Проверим, что slug не занят другой страницей того же родителя
            parent = en_specific.get_parent()
            sibling_conflict = (
                parent.get_children()
                .filter(slug=wp_slug)
                .exclude(pk=en_specific.pk)
                .exists()
            )
            if not sibling_conflict:
                en_specific.slug = wp_slug
                self.log(f"  - slug: {en_specific.slug!r} → `{wp_slug}`")
            else:
                self.log(f"  - ⚠ slug `{wp_slug}` уже занят у соседа, оставляем `{en_specific.slug}`")

        if hasattr(en_specific, "body"):
            en_specific.body = self._blocks_to_streamfield_value(final_blocks, type(en_specific), "body")
        en_specific.save_revision().publish()

        self.stats.translations_linked += 1
        self.log(f"  ✓ Перевод связан: EN '{row.title}' ↔ RU '{ru_page.title}'")

    # ─── Утилиты ─────────────────────────────────────────────────────────

    def _parse_wp_date(self, date_str: str | None):
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
        except (ValueError, AttributeError):
            return None

    def _count_block(self, block_type: str):
        self.stats.blocks_created[block_type] = self.stats.blocks_created.get(block_type, 0) + 1

    # ─── Логирование ─────────────────────────────────────────────────────

    def log(self, msg: str):
        self.log_lines.append(msg)
        self.stdout.write(msg)

    def _log_header(self, title: str):
        self.log(f"\n## {title}\n")

    def _write_summary(self):
        self._log_header("Сводка")
        s = self.stats
        self.log(f"- Страниц создано: **{s.pages_created}**")
        self.log(f"- Страниц обновлено: **{s.pages_updated}**")
        self.log(f"- Страниц пропущено (уже существуют): {s.pages_skipped}")
        self.log(f"- Страниц с ошибками: **{s.pages_failed}**")
        self.log(f"- Переводов связано: **{s.translations_linked}**")
        self.log(f"- Картинок загружено: **{s.images_uploaded}**")
        if s.blocks_created:
            self.log("\n**Блоков создано по типам:**")
            for btype, count in sorted(s.blocks_created.items(), key=lambda x: -x[1]):
                self.log(f"  - `{btype}`: {count}")
        if s.warnings:
            self.log(f"\n**Предупреждений: {len(s.warnings)}**")
            for w in s.warnings[:20]:
                self.log(f"  - {w}")
            if len(s.warnings) > 20:
                self.log(f"  - ... и ещё {len(s.warnings) - 20}")
        if s.errors:
            self.log(f"\n**Ошибки: {len(s.errors)}**")
            for e in s.errors:
                self.log(f"  - {e}")

    def _save_log(self):
        self.log_output.parent.mkdir(parents=True, exist_ok=True)
        self.log_output.write_text("\n".join(self.log_lines), encoding="utf-8")
        self.stdout.write(f"\nЛог записан: {self.log_output}")
