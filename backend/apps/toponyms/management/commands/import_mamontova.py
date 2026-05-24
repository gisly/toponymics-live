"""
Импорт топонимов из Excel-таблицы Н. Мамонтовой
(Tugur-Chumikan / Iengra, 2017-2018).

Использование:
    python manage.py import_mamontova /path/to/Mamontova.xlsx
    python manage.py import_mamontova /path/to/file.xlsx --dry-run
    python manage.py import_mamontova /path/to/file.xlsx --sheets Koryakin_Torom,Lekhanov_Iengra

Что делает:
- Из листа "Общий список карт" берёт перечень рукописных карт.
- Для каждого тематического листа:
  * парсит имя информанта из первой непустой строки колонки `author`
  * создаёт/находит HistoricalMap (имя = название листа, например "Koryakin_Torom")
  * по строкам создаёт Place + Toponym (БЕЗ дедупликации — дубли допустимы)
- Перезапускаемо: при повторном запуске HistoricalMap с тем же именем
  очищается (связанные Place/Toponym удаляются) и заливается заново.

Сканы карт нужно загружать вручную через админку Wagtail
(Snippets → Рукописные карты → Scanned image).

Решения по конкретным случаям:
- "left side", "The system of ..." в колонке author — это секционные
  комментарии, пишем в Place.location_comment.
- Map=no — топоним всё равно привязываем к HistoricalMap (но без number_on_map).
- Без координат — не создаём (только в БД, на карте не покажется).
  Чтобы импортировать всё, добавь флаг --include-empty-coords.
- FeatureType автосоздаётся, если такого нет.
"""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

try:
    import pandas as pd
except ImportError as e:
    raise CommandError("pandas не установлен. Установите: pip install pandas openpyxl") from e

from apps.toponyms.models import (
    FeatureType,
    HistoricalMap,
    Language,
    Person,
    Place,
    SourceReference,
    Toponym,
)


# ─── Маппинги для нормализации ──────────────────────────────────────────

LANG_MAP = {
    "эвенк": "evn", "эвенк.": "evn", "эвенкийский": "evn",
    "якут": "sah", "якут.": "sah", "якутский": "sah",
    "рус": "ru", "рус.": "ru", "русский": "ru",
}

# Маппинг русских названий типов на slug/EN — для autocreate FeatureType.
# Все названия — с маленькой буквы (договорённость по проекту).
# Если типа нет в маппинге — slug генерируется автоматически из transliteration.
FEATURE_TYPE_HINTS = {
    "река": ("river", "река", "river"),
    "горный перевал": ("mountain-passage", "горный перевал", "mountain passage"),
    "возвышенность": ("elevation", "возвышенность", "elevation"),
    "поселение": ("settlement", "поселение", "settlement"),
    "settlement": ("settlement", "поселение", "settlement"),
    "море": ("sea", "море", "sea"),
    "озеро": ("lake", "озеро", "lake"),
    "залив": ("bay", "залив", "bay"),
    "мыс": ("cape", "мыс", "cape"),
    "коса": ("sand-bar", "коса", "sand bar"),
    "остров": ("island", "остров", "island"),
    "сопка": ("hill", "сопка", "hill"),
    "пещера": ("cave", "пещера", "cave"),
    "распадок": ("glen", "распадок", "glen"),
    "лес (ельник)": ("spruce-forest", "лес (ельник)", "spruce forest"),
    "болотистая местность": ("marshes", "болотистая местность", "marshes"),
    "священное место": ("sacred-place", "священное место", "sacred place"),
    "экотоп": ("ecotope", "экотоп", "ecotope"),
    "наледь": ("aufeis", "наледь", "aufeis"),
}

# Колонка `author` иногда содержит секционный заголовок, а не имя информанта.
# Это эвристика: если в строке есть запятая И первое слово начинается с большой
# буквы кириллицей/латиницей И длиной до 15 — скорее всего ФИО.
# Простая защита: список «явно не имён» — мы их сразу отсеиваем.
SECTION_LABEL_HINTS = (
    "left side", "right side", "the system of", "охотничья территория",
)


def is_section_label(value: str) -> bool:
    """
    True, если значение в колонке `author` это секционный комментарий,
    а не имя информанта.

    Эвристика: если в строке есть запятая и часть ДО запятой выглядит как
    ФИО (2 слова с заглавных букв) — это имя + контекст, не section label,
    даже если в комментарии есть слова вроде "охотничья территория".
    """
    if not value:
        return False
    v = value.strip()

    # Сначала проверяем структуру "ФИО, контекст"
    if "," in v:
        before_comma = v.split(",", 1)[0].strip()
        words = before_comma.split()
        # 2 слова, первые буквы заглавные → ФИО
        if 2 <= len(words) <= 3 and all(w[:1].isupper() for w in words if w):
            return False

    lower = v.lower()
    return any(hint in lower for hint in SECTION_LABEL_HINTS)


def parse_person_name(raw: str) -> tuple[str, str, str, str]:
    """
    Разбирает строку вроде "Корякин Владимир (Вовкандя), Тором"
    в (first_name, patronymic, last_name, comment).

    Алгоритм:
    - всё после запятой → comment (село/контекст)
    - в скобках → добавляется в comment (прозвище и т.п.)
    - оставшееся ФИО без скобок → разбираем по словам:
        * 1 слово  → last_name
        * 2 слова  → если первое слово выглядит как фамилия (по эвристике:
                     заглавная кириллицей + длиннее 4 символов и заканчивается
                     характерным суффиксом) — first=2-е, last=1-е.
                     Иначе — first=1-е, last=2-е.
        * 3 слова  → first, patronymic, last (или first, last + что-то ещё)
    """
    raw = raw.strip()
    comment_parts: list[str] = []

    # Запятая отделяет ФИО от контекста ("..., Тором")
    if "," in raw:
        name_part, after_comma = raw.split(",", 1)
        comment_parts.append(after_comma.strip())
    else:
        name_part = raw

    # Скобки → в комментарий
    paren_matches = re.findall(r"\(([^)]*)\)", name_part)
    if paren_matches:
        comment_parts.extend(paren_matches)
        name_part = re.sub(r"\([^)]*\)", "", name_part).strip()

    # Нормализуем пробелы
    name_part = re.sub(r"\s+", " ", name_part).strip()
    words = name_part.split()

    last_suffixes = (
        "ов", "ев", "ёв", "ин", "ын", "ий", "ой", "ский", "цкий", "енко", "ук", "юк",
        "ова", "ева", "ёва", "ина", "ына", "ая", "ская", "цкая",
    )

    def looks_like_lastname(w: str) -> bool:
        wl = w.lower()
        return any(wl.endswith(s) for s in last_suffixes)

    if len(words) == 0:
        first, patr, last = "—", "", raw or "—"
    elif len(words) == 1:
        first, patr, last = "—", "", words[0]
    elif len(words) == 2:
        if looks_like_lastname(words[0]) and not looks_like_lastname(words[1]):
            # "Корякин Владимир" → first=Владимир, last=Корякин
            first, patr, last = words[1], "", words[0]
        else:
            # "Yakov Lekhanov", "Степан Сафронов" → first=1, last=2
            first, patr, last = words[0], "", words[1]
    elif len(words) == 3:
        # "Степан Иванович Сафронов" or "Степан Сафронов Тором"
        if looks_like_lastname(words[2]):
            first, patr, last = words[0], words[1], words[2]
        elif looks_like_lastname(words[0]):
            first, patr, last = words[1], words[2], words[0]
        else:
            first, patr, last = words[0], "", " ".join(words[1:])
    else:
        # 4+ — берём первое как имя, последнее как фамилию
        first, patr, last = words[0], "", " ".join(words[1:])

    comment = "; ".join(filter(None, comment_parts))
    return first, patr, last, comment


def normalize_language_iso(raw: Optional[str]) -> tuple[Optional[str], bool]:
    """
    Возвращает (iso, is_uncertain).
    "якут ?" → ("sah", True). "эвенк" → ("evn", False). None → (None, False).
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None, False
    s = str(raw).strip().lower()
    is_uncertain = "?" in s
    s_clean = s.replace("?", "").strip()
    iso = LANG_MAP.get(s_clean)
    return iso, is_uncertain


def parse_yesno(raw) -> Optional[bool]:
    """Парсит значение колонки Map (yes/no). None если непонятно."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).strip().lower()
    if s.startswith("yes"):
        return True
    if s.startswith("no"):
        return False
    return None


def parse_decimal(raw) -> Optional[Decimal]:
    """Аккуратно парсим число (могут быть пробелы, запятая, текст)."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    try:
        if isinstance(raw, (int, float)):
            return Decimal(str(raw))
        s = str(raw).strip().replace(",", ".")
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


# ─── Команда ────────────────────────────────────────────────────────────


class Command(BaseCommand):
    help = "Импорт топонимов из Excel-таблицы Мамонтовой"

    def add_arguments(self, parser):
        parser.add_argument("xlsx_path", type=str, help="Путь к .xlsx")
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Только парсинг и логи — без записи в БД",
        )
        parser.add_argument(
            "--sheets", type=str, default=None,
            help="Запятая-разделённый список листов для импорта (по умолчанию — все)",
        )
        parser.add_argument(
            "--include-empty-coords", action="store_true",
            help="Импортировать топонимы без координат (по умолчанию пропускаются)",
        )

    def handle(self, *args, **opts):
        xlsx_path = Path(opts["xlsx_path"])
        if not xlsx_path.exists():
            raise CommandError(f"Файл не найден: {xlsx_path}")

        self.dry_run = opts["dry_run"]
        self.include_empty = opts["include_empty_coords"]

        sheets_filter = (
            set(opts["sheets"].split(",")) if opts["sheets"] else None
        )

        # Счётчики для финального отчёта
        self.stats = {
            "maps_created": 0, "maps_replaced": 0,
            "places_created": 0, "toponyms_created": 0,
            "persons_created": 0, "feature_types_created": 0,
            "rows_skipped_no_name": 0, "rows_skipped_no_coords": 0,
            "warnings": 0,
        }

        self.stdout.write(self.style.NOTICE(f"→ Открываю {xlsx_path.name}"))
        if self.dry_run:
            self.stdout.write(self.style.WARNING("  DRY-RUN: ничего не будет записано"))

        xl = pd.ExcelFile(xlsx_path)
        theme_sheets = [s for s in xl.sheet_names if s != "Общий список карт"]
        if sheets_filter:
            theme_sheets = [s for s in theme_sheets if s in sheets_filter]
            missing = sheets_filter - set(xl.sheet_names)
            if missing:
                self.warn(f"Листы не найдены и пропущены: {missing}")

        if self.dry_run:
            # В dry-run ничего не пишем в БД, поэтому транзакция не нужна.
            # Достаточно перебрать листы и собрать статистику + предупреждения.
            for sheet_name in theme_sheets:
                self.import_sheet(xl, sheet_name)
            self.stdout.write(self.style.WARNING("\n  DRY-RUN: ничего не записано в БД"))
        else:
            # Атомарная транзакция: если упало в середине — БД не меняется.
            with transaction.atomic():
                for sheet_name in theme_sheets:
                    self.import_sheet(xl, sheet_name)

        self.print_summary()

    # ─── Импорт одного листа ────────────────────────────────────────────

    def import_sheet(self, xl: pd.ExcelFile, sheet_name: str) -> None:
        self.stdout.write(self.style.HTTP_INFO(f"\n=== Лист: {sheet_name} ==="))

        df = pd.read_excel(xl, sheet_name=sheet_name, header=None)
        if df.shape[0] < 4:
            self.warn(f"  Слишком мало строк, пропускаю")
            return

        # Заголовки в строке 2 (0-индексация). Строим map col_name -> idx.
        headers: dict[str, int] = {}
        for j in range(df.shape[1]):
            val = df.iloc[2, j]
            if pd.notna(val):
                headers[str(val).strip()] = j

        def col(name: str) -> Optional[int]:
            """Ищет колонку по точному и частичному совпадению."""
            if name in headers:
                return headers[name]
            for k, v in headers.items():
                if k.startswith(name) or name in k:
                    return v
            return None

        # Проверяем критичные колонки
        author_col = col("author")
        name_col = col("place names in Evenki") or col("place names")
        lat_col = col("Latitude")
        lon_col = col("Longitude")
        if author_col is None or name_col is None:
            self.warn(f"  Не найдены критичные колонки (author, place names). Пропуск.")
            return

        # Парсим имя информанта: первая непустая ячейка в колонке author,
        # которая НЕ секционный заголовок.
        informant_name = None
        for i in range(3, df.shape[0]):
            v = df.iloc[i, author_col]
            if pd.notna(v) and not is_section_label(str(v)):
                informant_name = str(v).strip()
                break
        if not informant_name:
            self.warn(f"  Не удалось найти имя информанта. Пропуск листа.")
            return

        informant = self.get_or_create_person(informant_name)
        self.stdout.write(f"  Информант: {informant.full_name}")

        # Создаём или заменяем HistoricalMap (имя = sheet_name)
        hmap = self.get_or_replace_historical_map(sheet_name, informant)
        self.stdout.write(f"  Карта: {hmap}")

        # Перебираем строки данных, отслеживая текущий «секционный» комментарий
        current_section_comment = ""
        rows_in_sheet = 0
        for i in range(3, df.shape[0]):
            row = df.iloc[i]
            author_val = row[author_col]
            if pd.notna(author_val):
                raw_author = str(author_val).strip()
                if is_section_label(raw_author):
                    current_section_comment = raw_author
                    continue
                # реальное имя — это либо тот же информант, либо новый (редко)
                # для упрощения: НЕ меняем informant в середине листа

            # Имя топонима — обязательно
            name_val = row[name_col]
            if pd.isna(name_val) or not str(name_val).strip():
                continue

            self.import_row(
                row, headers, hmap, informant, current_section_comment, sheet_name, i
            )
            rows_in_sheet += 1

        self.stdout.write(f"  Обработано строк с данными: {rows_in_sheet}")

    # ─── Импорт одной строки ────────────────────────────────────────────

    def import_row(
        self, row: pd.Series, headers: dict, hmap: HistoricalMap,
        informant: Person, section_comment: str, sheet_name: str, row_idx: int,
    ) -> None:
        def cell(col_name: str):
            for k, idx in headers.items():
                if k == col_name or k.startswith(col_name):
                    v = row[idx]
                    return v if pd.notna(v) else None
            return None

        name = str(cell("place names in Evenki") or "").strip()
        translit = str(cell("transliteration") or "").strip()
        trans_ru = str(cell("translation in Russian") or "").strip()
        trans_en = str(cell("translation in English") or "").strip()
        affix = str(cell("Affix") or "").strip()
        obj_ru = str(cell("Объект") or "").strip()
        obj_en = str(cell("Object") or "").strip()
        lang_raw = cell("Язык") or cell("Language")
        map_raw = cell("Map (yes / no)")
        number_on_map = str(cell("number on the map") or "").strip()
        comment = str(cell("Comment") or "").strip()
        official = str(cell("Official name") or cell("Official names") or "").strip()
        lat = parse_decimal(cell("Latitude"))
        lon = parse_decimal(cell("Longitude"))
        precise_raw = cell("Precise")
        source_text = str(cell("Source") or "").strip()
        note = str(cell("Note") or "").strip()

        # Координаты
        if lat is None or lon is None:
            if not self.include_empty:
                self.stats["rows_skipped_no_coords"] += 1
                return
        is_approx = (precise_raw is not None and str(precise_raw).strip() == "0")

        # Тип объекта (по русскому имени, fallback — английский)
        ftype_raw = obj_ru or obj_en
        if not ftype_raw:
            self.warn(f"  [{sheet_name}:{row_idx}] '{name}' — нет типа объекта (Объект/Object). Пропуск.")
            return
        ftype = self.get_or_create_feature_type(ftype_raw)

        # Язык
        iso, lang_uncertain = normalize_language_iso(lang_raw)
        if iso is None:
            # Эвристика: если в Excel имя в эвенкийской кириллице, скорее всего evn
            iso = "evn"
            self.warn(
                f"  [{sheet_name}:{row_idx}] '{name}' — язык не указан, "
                f"использую evn по умолчанию"
            )
        try:
            language = Language.objects.get(iso=iso)
        except Language.DoesNotExist:
            self.warn(f"  Язык '{iso}' не найден в БД. Пропуск строки.")
            return

        # Источник координат
        source = None
        if source_text:
            source, _ = SourceReference.objects.get_or_create(
                description=source_text
            )

        # Карта — привязываем всегда (по решению пункта 2)
        place_map = hmap
        # number_on_map — только если на карте Yes
        on_map = parse_yesno(map_raw)
        final_number = number_on_map if (on_map is True and number_on_map) else ""

        # Location comment: собираем секционный + основной + Note + Official
        loc_comment_parts = []
        if section_comment:
            loc_comment_parts.append(f"[{section_comment}]")
        if comment:
            loc_comment_parts.append(comment)
        if note:
            loc_comment_parts.append(f"Note: {note}")
        if official:
            loc_comment_parts.append(f"Официальное название: {official}")
        location_comment = "\n".join(loc_comment_parts)

        # СОЗДАЁМ Place (без дедупликации — дубли допустимы)
        if self.dry_run:
            self.stats["places_created"] += 1
            self.stats["toponyms_created"] += 1
            return

        place = Place.objects.create(
            latitude=lat,
            longitude=lon,
            feature_type=ftype,
            historical_map=place_map,
            is_coordinates_approximate=is_approx,
            location_comment=location_comment,
        )
        self.stats["places_created"] += 1

        # СОЗДАЁМ Toponym
        topo_name = name
        topo_name_latin = translit if iso == "evn" else ""

        # Если язык спорный — пишем это в motivation_comment
        motivation_comment = ""
        if lang_uncertain:
            motivation_comment = "Язык в источнике указан со знаком вопроса."

        Toponym.objects.create(
            place=place,
            name=topo_name,
            language=language,
            name_latin=topo_name_latin,
            translation_ru=trans_ru,
            translation_en=trans_en,
            motivation_comment=motivation_comment,
            source=source,
            historical_map=place_map,
            informant=informant,
            number_on_map=final_number,
        )
        self.stats["toponyms_created"] += 1

    # ─── Помощники: get_or_create ───────────────────────────────────────

    def get_or_create_person(self, raw_name: str) -> Person:
        first, patr, last, comment = parse_person_name(raw_name)
        existing = Person.objects.filter(
            first_name=first, patronymic=patr, last_name=last,
        ).first()
        if existing:
            return existing
        if self.dry_run:
            self.stdout.write(f"  [dry] Person: {first} {patr} {last}")
            return Person(first_name=first, patronymic=patr, last_name=last, comment=comment)
        person = Person.objects.create(
            first_name=first, patronymic=patr, last_name=last, comment=comment,
        )
        self.stats["persons_created"] += 1
        return person

    def get_or_create_feature_type(self, raw: str) -> FeatureType:
        key = raw.strip().lower()
        if key in FEATURE_TYPE_HINTS:
            code, name_ru, name_en = FEATURE_TYPE_HINTS[key]
        else:
            # Авто-slug из транслитерации (русский → латиница)
            code = slugify(unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii") or raw)
            if not code:
                code = "other"
            # Принудительно нижний регистр — по договорённости проекта
            name_ru = raw.strip().lower()
            name_en = raw.strip().lower()  # пользователь поправит в админке

        existing = FeatureType.objects.filter(code=code).first()
        if existing:
            return existing
        if self.dry_run:
            self.stdout.write(f"  [dry] FeatureType: {code} ({name_ru})")
            return FeatureType(code=code, name_ru=name_ru, name_en=name_en)
        ftype = FeatureType.objects.create(
            code=code, name_ru=name_ru, name_en=name_en,
        )
        self.stats["feature_types_created"] += 1
        return ftype

    def get_or_replace_historical_map(self, sheet_name: str, author: Person) -> HistoricalMap:
        """
        Карты идентифицируем по area_name_ru = sheet_name.
        Если существует — удаляем связанные Place/Toponym (cascade) и
        обновляем поля карты, оставляя ту же запись (чтобы её внешние
        ссылки сохранились).
        """
        area_name_ru = sheet_name
        area_name_en = sheet_name  # технические имена листов уже на латинице
        existing = HistoricalMap.objects.filter(area_name_ru=area_name_ru).first()
        if existing:
            if self.dry_run:
                self.stdout.write(f"  [dry] HistoricalMap уже есть, будет очищена: {existing}")
                return existing
            # Удаляем связанные данные (Place каскадом удалит Toponym)
            existing.places.all().delete()
            # У Toponym есть прямая FK на HistoricalMap (не через Place);
            # такие записи (если есть) тоже зачищаем
            Toponym.objects.filter(historical_map=existing).delete()
            existing.author = author
            existing.collector = self.get_or_create_mamontova()
            existing.is_archive = False  # это полевая карта, не архивная
            existing.save()
            self.stats["maps_replaced"] += 1
            return existing

        if self.dry_run:
            self.stdout.write(f"  [dry] HistoricalMap: {area_name_ru}")
            # Возвращаем заглушку: dry-run всё равно откатится
            hm = HistoricalMap(
                area_name_ru=area_name_ru, area_name_en=area_name_en,
                author=author,
            )
            return hm

        hm = HistoricalMap.objects.create(
            area_name_ru=area_name_ru,
            area_name_en=area_name_en,
            author=author,
            collector=self.get_or_create_mamontova(),
            is_archive=False,
        )
        self.stats["maps_created"] += 1
        return hm

    def get_or_create_mamontova(self) -> Person:
        """Собиратель — Н. Мамонтова, общая для всех листов."""
        existing = Person.objects.filter(
            first_name="Надежда", last_name="Мамонтова",
        ).first()
        if existing:
            return existing
        if self.dry_run:
            return Person(first_name="Надежда", patronymic="Алексеевна", last_name="Мамонтова")
        return Person.objects.create(
            first_name="Надежда",
            patronymic="Алексеевна",
            last_name="Мамонтова",
            comment="Полевые исследования 2017–2018",
        )

    # ─── Логирование ────────────────────────────────────────────────────

    def warn(self, msg: str) -> None:
        self.stats["warnings"] += 1
        self.stdout.write(self.style.WARNING(msg))

    def print_summary(self) -> None:
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("Импорт завершён."))
        for k, v in self.stats.items():
            self.stdout.write(f"  {k}: {v}")
