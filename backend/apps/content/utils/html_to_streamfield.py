"""
Преобразование WordPress HTML в Wagtail StreamField блоки.

Это самая нетривиальная часть импорта: WP-контент идёт как один большой HTML
с классами темы, Gutenberg-комментариями, shortcodes и прочим мусором.
Цель — разобрать его на семантически осмысленные блоки нашего NarrativeStreamBlock.

Поддерживаемые входы:
- Чистые параграфы <p>
- Заголовки <h1>..<h6>
- Списки <ul>, <ol> (остаются как rich text)
- Цитаты <blockquote>
- Изображения <img> — конвертируются в image block, скачиваются файлы
- Галереи [gallery ids="1,2,3"] — каждая картинка как отдельный image block
- Gutenberg-блоки <!-- wp:* --> — игнорируются как обёртки, содержимое обрабатывается

Что НЕ поддерживается (выкидывается с логом):
- <iframe>, <script> — соображения безопасности
- Неизвестные shortcodes — фиксируются в логе
- Inline-стили — теряются (мы хотим чистый контент)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup, NavigableString, Tag

logger = logging.getLogger(__name__)


# ─── Конфиг ──────────────────────────────────────────────────────────────


# Какие inline-теги сохраняем в rich text параграфах
ALLOWED_INLINE_TAGS = {"a", "b", "strong", "i", "em", "u", "br", "code", "sub", "sup", "span",
                       "ul", "ol", "li", "p"}

# Какие атрибуты сохраняем у разрешённых тегов
ALLOWED_ATTRS = {
    "a": ["href", "title"],
    "img": ["src", "alt", "title"],
}

# Регулярка для shortcode типа [gallery ids="1,2,3"]
SHORTCODE_RE = re.compile(r"\[(\w+)([^\]]*)\]")


# ─── Результат конвертации ───────────────────────────────────────────────


@dataclass
class ConversionResult:
    """То, что возвращает HTML→StreamField конвертер."""

    # Готовые StreamField блоки в формате [(block_type, value), ...]
    blocks: list[tuple[str, object]] = field(default_factory=list)

    # Локальные пути к картинкам, которые надо добавить как Wagtail Images
    # перед сохранением страницы. Формат: [(local_path, alt, caption), ...]
    pending_images: list[tuple[Path, str, str]] = field(default_factory=list)

    # Предупреждения для лога
    warnings: list[str] = field(default_factory=list)


# ─── Конвертер ───────────────────────────────────────────────────────────


class HtmlToStreamField:
    """Преобразует WordPress HTML в список блоков NarrativeStreamBlock."""

    def __init__(self, media_dir: Path, source_url_to_local: dict[str, Path] | None = None):
        """
        Args:
            media_dir: папка с уже скачанными WP-медиа (для резолва картинок)
            source_url_to_local: маппинг WP source_url → локальный файл,
                если у тебя есть media.json с метаданными
        """
        self.media_dir = media_dir
        self.source_url_to_local = source_url_to_local or {}
        self.result = ConversionResult()

    def convert(self, html: str, page_id: int | None = None) -> ConversionResult:
        """Главный метод: HTML → ConversionResult."""
        self.result = ConversionResult()

        if not html or not html.strip():
            return self.result

        # 1. Удаляем Gutenberg-комментарии <!-- wp:* --> и <!-- /wp:* -->
        html = re.sub(r"<!--\s*/?wp:[^>]*-->", "", html)

        # 2. Парсим
        soup = BeautifulSoup(html, "html.parser")

        # 3. Обрабатываем shortcodes [gallery ...] на верхнем уровне
        # Заменяем их специальными плейсхолдерами, которые потом превратятся в блоки
        self._extract_shortcodes_to_blocks(soup)

        # 4. Идём по элементам верхнего уровня и конвертируем
        # Если корень — body, идём по его детям; иначе по всем top-level элементам
        root = soup.body if soup.body else soup
        for element in root.children:
            self._convert_element(element)

        # 5. Финальная зачистка: если последний блок — пустой параграф, удаляем
        while self.result.blocks and self._is_empty_block(self.result.blocks[-1]):
            self.result.blocks.pop()

        return self.result

    # ─── Обработка отдельных элементов ──────────────────────────────────

    def _convert_element(self, element) -> None:
        """Конвертирует один HTML элемент в один или несколько блоков."""

        # Текстовые узлы на верхнем уровне (пробелы между блоками) — игнорируем
        if isinstance(element, NavigableString):
            text = str(element).strip()
            if text:
                self._add_paragraph(f"<p>{text}</p>")
            return

        if not isinstance(element, Tag):
            return

        tag = element.name.lower()

        # Заголовки
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            heading_text = element.get_text(strip=True)
            if heading_text:
                self.result.blocks.append(("heading", heading_text))
            return

        # Параграфы
        if tag == "p":
            # Внутри могут быть картинки — выносим их в отдельные image-блоки
            self._handle_paragraph_with_images(element)
            return

        # Списки — оставляем как rich text внутри параграфа
        if tag in ("ul", "ol"):
            clean_html = self._clean_inline_html(element)
            if clean_html.strip():
                self.result.blocks.append(("paragraph", clean_html))
            return

        # Цитаты
        if tag == "blockquote":
            text = element.get_text(strip=True)
            # Ищем источник: <cite>, <footer>, или последний <p> курсивом
            attribution = ""
            cite = element.find(["cite", "footer"])
            if cite:
                attribution = cite.get_text(strip=True)
                # Удалим из основного текста
                text = text.replace(attribution, "").strip()
            if text:
                self.result.blocks.append(("quote", {"text": text, "attribution": attribution}))
            return

        # Картинки на верхнем уровне (часто WP их так делает)
        if tag == "img":
            self._add_image_from_tag(element)
            return

        # figure (Gutenberg-style) — обычно содержит img + figcaption
        if tag == "figure":
            img = element.find("img")
            if img:
                caption = ""
                figcaption = element.find("figcaption")
                if figcaption:
                    caption = figcaption.get_text(strip=True)
                self._add_image_from_tag(img, caption=caption)
            return

        # Наши плейсхолдеры от shortcodes
        if tag == "x-gallery-placeholder":
            urls = (element.get("data-urls") or "").split("|")
            for url in urls:
                if url.strip():
                    self._add_image_from_url(url.strip())
            return

        # <div>, <section> — рекурсивно по детям
        if tag in ("div", "section", "article"):
            for child in element.children:
                self._convert_element(child)
            return

        # iframe, script — пропускаем с warning
        if tag in ("iframe", "script", "style"):
            self.result.warnings.append(f"Пропущен тег <{tag}> (безопасность)")
            return

        # Всё остальное — пытаемся достать текст
        text = element.get_text(strip=True)
        if text:
            self._add_paragraph(f"<p>{text}</p>")

    def _handle_paragraph_with_images(self, p_tag: Tag) -> None:
        """Параграф может содержать изображения — их надо вынести в image-блоки.
        Также — псевдо-списки на маркерах ►•◦→★ и псевдо-цитаты в угловых кавычках.
        """
        images = p_tag.find_all("img")
        if not images:
            clean_html = self._clean_inline_html(p_tag)
            text_content = BeautifulSoup(clean_html, "html.parser").get_text(strip=True)
            if text_content:
                # Попробуем распознать псевдо-список или цитату до того,
                # как просто положить как paragraph
                if self._try_emit_pseudo_quote(text_content):
                    return
                if self._try_emit_pseudo_list(text_content, clean_html):
                    return
                self.result.blocks.append(("paragraph", clean_html))
            return

        # Если есть картинки — извлекаем их и собираем остатки текста
        for img in images:
            self._add_image_from_tag(img)
            img.extract()

        # Что осталось от параграфа
        remaining_html = self._clean_inline_html(p_tag)
        remaining_text = BeautifulSoup(remaining_html, "html.parser").get_text(strip=True)
        if remaining_text:
            if self._try_emit_pseudo_quote(remaining_text):
                return
            if self._try_emit_pseudo_list(remaining_text, remaining_html):
                return
            self.result.blocks.append(("paragraph", remaining_html))

    # ─── Распознавание псевдо-списков и псевдо-цитат ───────────────────

    # Маркеры, после которых может идти пункт списка
    _LIST_MARKERS = ["►", "▶", "•", "◦", "★", "✦", "✱"]

    def _try_emit_pseudo_list(self, text_content: str, original_html: str) -> bool:
        """Если в параграфе ≥2 одинаковых маркера ►/•/◦ — разбиваем в настоящий <ul>.

        Возвращает True если разобрали (и блок уже добавлен), иначе False.
        """
        # Считаем вхождения каждого маркера
        for marker in self._LIST_MARKERS:
            count = text_content.count(marker)
            if count < 2:
                continue

            # Разбиваем по этому маркеру. Берём из чистого текста, не из HTML,
            # потому что inline-форматирование в псевдо-списках почти никогда не критично.
            parts = [p.strip() for p in text_content.split(marker) if p.strip()]
            if len(parts) < 2:
                continue

            # Первый кусок — это "вступление" перед списком, например
            # "The GIS platform enables:"
            # Если в нём есть текст — это intro, оформляем отдельным параграфом
            intro = parts[0]
            list_items = parts[1:]

            # Эвристика: если первая часть слишком короткая (нет вступления —
            # маркер был в самом начале), не делаем отдельный параграф
            if intro and len(intro) > 1:
                # Убираем хвостовые двоеточия для красоты — оставим как есть
                self.result.blocks.append(("paragraph", f"<p>{intro}</p>"))

            # Строим настоящий <ul>
            lis = "".join(f"<li>{item}</li>" for item in list_items)
            self.result.blocks.append(("paragraph", f"<ul>{lis}</ul>"))
            return True

        return False

    def _try_emit_pseudo_quote(self, text_content: str) -> bool:
        """Если параграф обёрнут в угловые/двойные кавычки и достаточно длинный —
        преобразуем в quote-блок.

        Признаки:
        - Начинается с ❪ ❮ « „ и заканчивается ❫ ❯ » " (или похожими)
        - Длина минимум ~30 символов (короткие "..." не цитата)
        """
        if len(text_content) < 30:
            return False

        # Парные кавычки: открывающая → закрывающая
        quote_pairs = [
            ("❪", "❫"), ("❮", "❯"), ("«", "»"), ("„", "“"), ("“", "”"),
            ("‹", "›"),
        ]

        for open_q, close_q in quote_pairs:
            if text_content.startswith(open_q) and text_content.rstrip().endswith(close_q):
                # Снимаем кавычки и пробелы
                inner = text_content[len(open_q):-len(close_q)].strip()
                if inner:
                    self.result.blocks.append(("quote", {
                        "text": inner,
                        "attribution": "",
                    }))
                    return True

        return False

    # ─── Конец распознавания ────────────────────────────────────────────

    def _add_paragraph(self, html: str) -> None:
        """Добавляет блок параграфа с очисткой HTML."""
        clean = self._clean_inline_html(BeautifulSoup(html, "html.parser"))
        text_check = BeautifulSoup(clean, "html.parser").get_text(strip=True)
        if text_check:
            self.result.blocks.append(("paragraph", clean))

    def _clean_inline_html(self, soup_or_tag) -> str:
        """Чистит inline HTML: оставляет только разрешённые теги и атрибуты."""
        if isinstance(soup_or_tag, Tag):
            for tag in soup_or_tag.find_all(True):
                if tag.name not in ALLOWED_INLINE_TAGS and tag.name != "p":
                    # Заменяем на содержимое
                    tag.unwrap()
                else:
                    # Чистим атрибуты
                    allowed = ALLOWED_ATTRS.get(tag.name, [])
                    tag.attrs = {k: v for k, v in tag.attrs.items() if k in allowed}
            return str(soup_or_tag)
        return str(soup_or_tag)

    # ─── Картинки ────────────────────────────────────────────────────────

    def _add_image_from_tag(self, img_tag: Tag, caption: str = "") -> None:
        """Регистрирует картинку из <img> для последующей загрузки в Wagtail Images."""
        src = img_tag.get("src", "")
        alt = img_tag.get("alt", "")
        if not src:
            return
        self._add_image_from_url(src, alt=alt, caption=caption)

    def _add_image_from_url(self, url: str, alt: str = "", caption: str = "") -> None:
        """Резолвит URL → локальный файл и добавляет в pending_images."""
        local_path = self._resolve_url_to_local(url)
        if not local_path:
            self.result.warnings.append(f"Картинка не найдена локально: {url}")
            return

        self.result.pending_images.append((local_path, alt, caption))
        # Блок добавляется в финале, когда мы узнаем wagtail Image ID.
        # Пока ставим плейсхолдер с номером, который потом заменим.
        placeholder_idx = len(self.result.pending_images) - 1
        self.result.blocks.append(("__image_placeholder__", placeholder_idx))

    def _resolve_url_to_local(self, url: str) -> Path | None:
        """Преобразует URL картинки в локальный путь в media_dir."""
        # Если был передан явный маппинг — используем
        if url in self.source_url_to_local:
            local = self.source_url_to_local[url]
            return local if local.exists() else None

        # Иначе пытаемся по имени файла
        parsed = urlparse(url)
        filename = unquote(parsed.path.split("/")[-1])
        if not filename:
            return None

        candidate = self.media_dir / filename
        if candidate.exists():
            return candidate

        # WP часто добавляет суффиксы размеров: image-300x200.jpg
        # Попробуем найти оригинал без суффикса
        m = re.match(r"^(.+?)-\d+x\d+(\.[a-zA-Z0-9]+)$", filename)
        if m:
            base = m.group(1) + m.group(2)
            candidate = self.media_dir / base
            if candidate.exists():
                return candidate

        return None

    # ─── Shortcodes ──────────────────────────────────────────────────────

    def _extract_shortcodes_to_blocks(self, soup: BeautifulSoup) -> None:
        """Находит [gallery ids="..."] и подобное, заменяет на плейсхолдеры в soup."""
        # Ищем по всему тексту строки с shortcodes
        for text_node in list(soup.find_all(string=True)):
            text = str(text_node)
            if "[" not in text:
                continue

            new_parts = []
            last_end = 0
            for match in SHORTCODE_RE.finditer(text):
                shortcode_name = match.group(1).lower()
                shortcode_attrs = match.group(2)

                # Текст до shortcode
                if match.start() > last_end:
                    new_parts.append(("text", text[last_end:match.start()]))

                # Обработка известных shortcodes
                if shortcode_name == "gallery":
                    # Извлекаем ids и резолвим к локальным URL
                    ids_match = re.search(r'ids=["\']([^"\']+)["\']', shortcode_attrs)
                    if ids_match:
                        # Без media.json мы не можем зарезолвить id → URL.
                        # Так что просто оставляем сообщение в лог.
                        self.result.warnings.append(
                            f"[gallery] с ids={ids_match.group(1)} — нужен media.json для резолва"
                        )
                    # Удаляем shortcode из текста (placeholder будет пустой)
                    new_parts.append(("placeholder", None))
                else:
                    # Неизвестный или ложный shortcode (например текст в скобках)
                    # Не логируем, чтобы не засорять — большинство ложные
                    # Оставляем как обычный текст
                    new_parts.append(("text", match.group(0)))

                last_end = match.end()

            # Хвост
            if last_end < len(text):
                new_parts.append(("text", text[last_end:]))

            # Если ничего интересного не нашли — оставляем как было
            if not any(p[0] == "placeholder" for p in new_parts):
                continue

            # Заменяем text_node на последовательность из text + placeholder элементов
            parent = text_node.parent
            for kind, value in new_parts:
                if kind == "text" and value:
                    new_text = soup.new_string(value)
                    text_node.insert_before(new_text)
                elif kind == "placeholder":
                    # Создаём свой тег-плейсхолдер
                    ph = soup.new_tag("x-gallery-placeholder")
                    text_node.insert_before(ph)
            text_node.extract()

    # ─── Утилиты ─────────────────────────────────────────────────────────

    def _is_empty_block(self, block: tuple[str, object]) -> bool:
        """Проверка на пустой блок (для финальной зачистки)."""
        block_type, value = block
        if block_type == "paragraph":
            if isinstance(value, str):
                stripped = BeautifulSoup(value, "html.parser").get_text(strip=True)
                return not stripped
        return False
