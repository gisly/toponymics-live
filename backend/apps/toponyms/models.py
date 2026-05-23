"""
Доменные модели топонимики.

Архитектурная модель:
- Place (бывший GeoObject) — место на местности с координатами
- Toponym (бывший GeoName) — имя места, привязанное к языку.
  Одно место может иметь много имён на разных языках от разных информантов.
- Language — справочник языков с ISO-кодами
- FeatureType — тип географического объекта (река, гора, ...)
- MotivationType — мотив наименования (по реке, по форме, и т.д.)
- HistoricalMap — рукописная или историческая карта
- GeoSystem — географическая система (для группировки карт)
- Person — информант, автор или собиратель
- SourceReference — источник (литература, архив)
- Narration — рассказ о месте

Существенные изменения относительно legacy-схемы:
- Названия таблиц/моделей переименованы для ясности (Toponym вместо GeoName,
  Place вместо GeoObject)
- Эвенкийские имена имеют дополнительные поля для латиницы и IPA в одной записи
- Все text-поля без дублирования _ru/_en — используется одно поле, привязка
  к языку через Language FK
- Wagtail-совместимость через panels и Snippet registration в wagtail_hooks
"""
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import RichTextField, StreamField
from wagtail.search import index

from .blocks import NarrativeStreamBlock


# ─── Справочники ─────────────────────────────────────────────────────────


class Language(models.Model):
    """Язык. Используется для всех текстовых полей с привязкой к языку."""

    iso = models.CharField(
        "ISO 639", max_length=10, unique=True,
        help_text="Двух- или трёхбуквенный ISO-код: ru, en, evn, sah, ...",
    )
    name_ru = models.CharField("Название (рус)", max_length=100, unique=True)
    name_en = models.CharField("Название (англ)", max_length=100, unique=True)
    name_native = models.CharField(
        "Самоназвание", max_length=100, blank=True,
        help_text="Как язык называется на самом себе (для эвенкийского — Эвэды̄ турэ̄н)",
    )

    panels = [
        FieldPanel("iso"),
        FieldPanel("name_ru"),
        FieldPanel("name_en"),
        FieldPanel("name_native"),
    ]

    class Meta:
        verbose_name = "Язык"
        verbose_name_plural = "Языки"
        ordering = ["iso"]

    def __str__(self) -> str:
        return self.iso


class FeatureType(models.Model):
    """Тип географического объекта: река, гора, стойбище, тундра, ..."""

    code = models.SlugField("Код", max_length=50, unique=True)
    name_ru = models.CharField("Название (рус)", max_length=100)
    name_en = models.CharField("Название (англ)", max_length=100)
    description_ru = models.TextField("Описание (рус)", blank=True)
    description_en = models.TextField("Описание (англ)", blank=True)

    # Связь с языком, в рамках которого тип определён (для языко-специфичных категорий)
    language = models.ForeignKey(
        Language, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Язык, к которому относится тип",
    )

    icon = models.CharField(
        "Иконка (имя в спрайте)", max_length=50, blank=True,
        help_text="Имя иконки в MapLibre sprite-sheet, например 'river'",
    )
    default_color = models.CharField(
        "Цвет по умолчанию", max_length=20, blank=True,
        help_text="HEX-цвет для отображения на карте, например #2e7d32",
    )
    sort_order = models.IntegerField("Порядок", default=100)

    panels = [
        FieldPanel("code"),
        FieldPanel("name_ru"),
        FieldPanel("name_en"),
        FieldPanel("description_ru"),
        FieldPanel("description_en"),
        FieldPanel("language"),
        MultiFieldPanel(
            [FieldPanel("icon"), FieldPanel("default_color"), FieldPanel("sort_order")],
            heading="Отображение",
        ),
    ]

    class Meta:
        verbose_name = "Тип объекта"
        verbose_name_plural = "Типы объектов"
        ordering = ["sort_order", "name_ru"]

    def __str__(self) -> str:
        return self.name_ru


class MotivationType(models.Model):
    """Мотив наименования: по чему названо место.

    Например: "по реке", "по форме горы", "по событию", "по растению".
    """

    short_name_ru = models.CharField("Короткое имя (рус)", max_length=200, unique=True)
    short_name_en = models.CharField("Короткое имя (англ)", max_length=200, unique=True)
    comment_ru = models.TextField("Комментарий (рус)", blank=True)
    comment_en = models.TextField("Комментарий (англ)", blank=True)

    panels = [
        FieldPanel("short_name_ru"),
        FieldPanel("short_name_en"),
        FieldPanel("comment_ru"),
        FieldPanel("comment_en"),
    ]

    class Meta:
        verbose_name = "Мотив наименования"
        verbose_name_plural = "Мотивы наименования"
        ordering = ["short_name_ru"]

    def __str__(self) -> str:
        return self.short_name_ru


class SourceReference(models.Model):
    """Источник топонимических данных: литература, архив, экспедиция."""

    description = models.TextField(
        "Полное описание", unique=True,
        help_text="Библиографическая ссылка, описание архивного дела, "
                  "или экспедиционных данных",
    )

    panels = [FieldPanel("description")]

    class Meta:
        verbose_name = "Источник"
        verbose_name_plural = "Источники"
        ordering = ["description"]

    def __str__(self) -> str:
        return self.description[:80] + ("…" if len(self.description) > 80 else "")


class Person(models.Model):
    """Информант, собиратель, автор карты или нарратива."""

    first_name = models.CharField("Имя", max_length=200)
    patronymic = models.CharField("Отчество", max_length=200, blank=True)
    last_name = models.CharField("Фамилия", max_length=200)
    comment = models.TextField(
        "Комментарий", blank=True,
        help_text="Биографические сведения, аффилиация, год рождения",
    )

    panels = [
        FieldPanel("first_name"),
        FieldPanel("patronymic"),
        FieldPanel("last_name"),
        FieldPanel("comment"),
    ]

    class Meta:
        verbose_name = "Информант / автор"
        verbose_name_plural = "Информанты и авторы"
        ordering = ["last_name", "first_name"]

    @property
    def full_name(self) -> str:
        parts = [self.first_name]
        if self.patronymic:
            parts.append(self.patronymic)
        parts.append(self.last_name)
        return " ".join(parts)

    def __str__(self) -> str:
        return self.full_name


class GeoSystem(models.Model):
    """Географическая система — для группировки рукописных карт.

    Например: «Эвенкия», «Якутия», «Дальневосточный регион».
    Одна карта может относиться к нескольким системам.
    """

    name_ru = models.CharField("Название (рус)", max_length=200, unique=True)
    name_en = models.CharField("Название (англ)", max_length=200, unique=True)

    panels = [
        FieldPanel("name_ru"),
        FieldPanel("name_en"),
    ]

    class Meta:
        verbose_name = "География (система)"
        verbose_name_plural = "Географии (системы)"
        ordering = ["name_ru"]

    def __str__(self) -> str:
        return self.name_ru


# ─── Рукописные карты ───────────────────────────────────────────────────


class HistoricalMap(models.Model):
    """Рукописная карта или историческая карта.

    Содержит метаданные карты + опциональное изображение скана +
    координаты центра региона, который карта изображает.
    """

    area_name_ru = models.CharField("Регион (рус)", max_length=500)
    area_name_en = models.CharField("Регион (англ)", max_length=500)

    author = models.ForeignKey(
        Person, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="authored_maps",
        verbose_name="Автор карты",
    )
    collector = models.ForeignKey(
        Person, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="collected_maps",
        verbose_name="Собиратель",
    )

    date_collected = models.DateField("Дата получения", null=True, blank=True)
    place_collected = models.TextField("Место получения", blank=True)

    image_link = models.URLField("Ссылка на скан карты", blank=True)
    # Альтернатива — загрузка локально
    scanned_image = models.ImageField(
        "Скан карты (файл)",
        upload_to="historical_maps/%Y/",
        blank=True, null=True,
    )

    # Центр карты (для отображения "приблизительных" объектов)
    map_latitude = models.DecimalField(
        "Центр: широта", max_digits=9, decimal_places=6, null=True, blank=True,
    )
    map_longitude = models.DecimalField(
        "Центр: долгота", max_digits=9, decimal_places=6, null=True, blank=True,
    )

    comment_collected_ru = models.TextField("Комментарий (рус)", blank=True)
    comment_collected_en = models.TextField("Комментарий (англ)", blank=True)

    is_archive = models.BooleanField(
        "Архивная карта", default=False,
        help_text="Отметить, если карта получена из архива (для отличия от полевых данных)",
    )

    geo_systems = models.ManyToManyField(
        GeoSystem, blank=True, related_name="historical_maps",
        verbose_name="Географические системы",
    )

    search_fields = [
        index.SearchField("area_name_ru", boost=2),
        index.SearchField("area_name_en", boost=2),
        index.SearchField("place_collected"),
        index.SearchField("comment_collected_ru"),
        index.SearchField("comment_collected_en"),
        index.FilterField("is_archive"),
    ]

    panels = [
        MultiFieldPanel(
            [FieldPanel("area_name_ru"), FieldPanel("area_name_en")],
            heading="Регион (название)",
        ),
        MultiFieldPanel(
            [
                FieldPanel("author"),
                FieldPanel("collector"),
                FieldPanel("date_collected"),
                FieldPanel("place_collected"),
            ],
            heading="Источник",
        ),
        MultiFieldPanel(
            [FieldPanel("image_link"), FieldPanel("scanned_image")],
            heading="Изображение",
        ),
        MultiFieldPanel(
            [FieldPanel("map_latitude"), FieldPanel("map_longitude")],
            heading="Координаты центра",
        ),
        FieldPanel("comment_collected_ru"),
        FieldPanel("comment_collected_en"),
        FieldPanel("is_archive"),
        FieldPanel("geo_systems"),
    ]

    class Meta:
        verbose_name = "Рукописная карта"
        verbose_name_plural = "Рукописные карты"
        ordering = ["area_name_ru"]

    def __str__(self) -> str:
        return self.area_name_ru


# ─── Места и имена ──────────────────────────────────────────────────────


class Place(index.Indexed, models.Model):
    """Место на местности.

    Имеет координаты (или приблизительные через "is_coordinates_approximate"),
    тип объекта, привязку к рукописной карте.

    НЕ имеет имени напрямую — имена живут в Toponym с FK на Place.
    """

    latitude = models.DecimalField(
        "Широта", max_digits=9, decimal_places=6,
        null=True, blank=True,
        help_text="Может быть пустой, если точные координаты неизвестны",
    )
    longitude = models.DecimalField(
        "Долгота", max_digits=9, decimal_places=6,
        null=True, blank=True,
        help_text="Может быть пустой, если точные координаты неизвестны",
    )

    feature_type = models.ForeignKey(
        FeatureType, on_delete=models.PROTECT, related_name="places",
        verbose_name="Тип объекта",
    )

    historical_map = models.ForeignKey(
        HistoricalMap, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="places",
        verbose_name="Рукописная карта",
    )

    osm_id = models.BigIntegerField(
        "OSM ID", null=True, blank=True, db_index=True,
        help_text="ID объекта в OpenStreetMap (для связи с базой OSM)",
    )

    is_coordinates_approximate = models.BooleanField(
        "Координаты приблизительные", default=False,
        help_text="Отметить, если точные координаты неизвестны "
                  "и место указано в районе карты",
    )

    location_comment = models.TextField(
        "Комментарий к локализации", blank=True,
        help_text="Например: «5 км вверх по реке от Х», «на левом берегу»",
    )

    editor = models.ForeignKey(
        Person, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="edited_places",
        verbose_name="Редактор данных",
    )

    is_duplicate = models.BooleanField(
        "Дубликат", default=False,
        help_text="Отметить если место дублирует другую запись",
    )

    date_added = models.DateTimeField("Дата добавления", auto_now_add=True)
    date_updated = models.DateTimeField("Дата обновления", auto_now=True)

    search_fields = [
        index.SearchField("location_comment"),
        index.FilterField("feature_type_id"),
        index.FilterField("historical_map_id"),
        index.FilterField("is_coordinates_approximate"),
    ]

    panels = [
        MultiFieldPanel(
            [
                FieldPanel("latitude"),
                FieldPanel("longitude"),
                FieldPanel("is_coordinates_approximate"),
            ],
            heading="Координаты",
        ),
        FieldPanel("feature_type"),
        FieldPanel("historical_map"),
        FieldPanel("osm_id"),
        FieldPanel("location_comment"),
        FieldPanel("editor"),
        FieldPanel("is_duplicate"),
    ]

    class Meta:
        verbose_name = "Место"
        verbose_name_plural = "Места"
        ordering = ["-date_added"]
        indexes = [
            models.Index(fields=["latitude", "longitude"]),
            models.Index(fields=["feature_type", "historical_map"]),
        ]

    def __str__(self) -> str:
        # Главное имя места (на первом языке) или координаты
        first_name = self.toponyms.order_by("language__iso").first()
        if first_name:
            if self.latitude is not None and self.longitude is not None:
                return f"{first_name.name} ({self.latitude}, {self.longitude})"
            return f"{first_name.name} (координаты неизвестны)"
        if self.latitude is not None and self.longitude is not None:
            return f"({self.latitude}, {self.longitude})"
        return f"Место #{self.pk or '?'}"


class Toponym(index.Indexed, models.Model):
    """Имя места.

    Одно место (Place) может иметь много имён на разных языках от разных
    информантов. Каждое имя — отдельная запись Toponym.
    """

    place = models.ForeignKey(
        Place, on_delete=models.CASCADE, related_name="toponyms",
        verbose_name="Место",
    )

    name = models.CharField(
        "Имя (как записано)", max_length=300,
        help_text="Имя места на выбранном языке и в принятой для него орфографии",
    )

    language = models.ForeignKey(
        Language, on_delete=models.PROTECT, related_name="toponyms",
        verbose_name="Язык",
    )

    # ─ Эвенкийская специфика — заполняется когда language=evn ─────────
    # Это НЕ переводы, а альтернативные системы письма для эвенкийского.
    # Для русских/английских имён эти поля остаются пустыми.
    name_latin = models.CharField(
        "Латиница (для эвенкийского)", max_length=300, blank=True,
        help_text="Научная транслитерация. Автогенерируется из кириллицы.",
    )
    name_ipa = models.CharField(
        "IPA транскрипция (для эвенкийского)", max_length=300, blank=True,
        help_text="Фонетическая транскрипция в IPA",
    )

    # ─ Переводы ────────────────────────────────────────────────────────
    translation_ru = models.CharField(
        "Перевод (рус)", max_length=300, blank=True,
        help_text="Перевод значения имени на русский. Например, "
                  "«Бира» → «река»",
    )
    translation_en = models.CharField(
        "Перевод (англ)", max_length=300, blank=True,
    )

    # ─ Лингвистические сведения ────────────────────────────────────────
    motivation = models.ForeignKey(
        MotivationType, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="toponyms",
        verbose_name="Мотив наименования",
    )
    motivation_comment = models.TextField("Комментарий к мотивации", blank=True)
    linguistic_means = models.TextField(
        "Лингвистические средства", blank=True,
        help_text="Морфемный анализ, словообразовательная характеристика",
    )

    # ─ Источник и метаданные ────────────────────────────────────────────
    source = models.ForeignKey(
        SourceReference, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="toponyms",
        verbose_name="Источник",
    )
    historical_map = models.ForeignKey(
        HistoricalMap, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="toponyms",
        verbose_name="Карта (где записано)",
        help_text="На какой рукописной карте имя зафиксировано",
    )
    informant = models.ForeignKey(
        Person, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="contributed_toponyms",
        verbose_name="Информант",
    )
    number_on_map = models.CharField(
        "Номер на карте", max_length=20, blank=True,
        help_text="Номер точки на рукописной карте",
    )

    # Альтернативные формы — для записи диалектных вариантов одного имени
    alternative_forms = ArrayField(
        models.CharField(max_length=300),
        verbose_name="Альтернативные формы",
        default=list, blank=True,
        help_text="Диалектные варианты, орфографические вариации",
    )

    search_fields = [
        index.SearchField("name", boost=2),
        index.SearchField("name_latin"),
        index.SearchField("translation_ru"),
        index.SearchField("translation_en"),
        index.SearchField("motivation_comment"),
        index.AutocompleteField("name"),
        index.FilterField("language_id"),
        index.FilterField("motivation_id"),
        index.FilterField("historical_map_id"),
    ]

    panels = [
        FieldPanel("place"),
        MultiFieldPanel(
            [
                FieldPanel("name"),
                FieldPanel("language"),
            ],
            heading="Имя",
        ),
        MultiFieldPanel(
            [FieldPanel("name_latin"), FieldPanel("name_ipa")],
            heading="Эвенкийская специфика",
            classname="collapsible collapsed",
        ),
        MultiFieldPanel(
            [FieldPanel("translation_ru"), FieldPanel("translation_en")],
            heading="Переводы",
        ),
        MultiFieldPanel(
            [
                FieldPanel("motivation"),
                FieldPanel("motivation_comment"),
                FieldPanel("linguistic_means"),
            ],
            heading="Лингвистические сведения",
            classname="collapsible",
        ),
        MultiFieldPanel(
            [
                FieldPanel("source"),
                FieldPanel("historical_map"),
                FieldPanel("informant"),
                FieldPanel("number_on_map"),
                FieldPanel("alternative_forms"),
            ],
            heading="Источник и метаданные",
            classname="collapsible",
        ),
    ]

    class Meta:
        verbose_name = "Топоним (имя)"
        verbose_name_plural = "Топонимы (имена)"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["language", "name"]),
            models.Index(fields=["historical_map"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} [{self.language.iso}]"

    def save(self, *args, **kwargs):
        # Автогенерация латиницы из кириллицы для эвенкийского
        if (
            self.language_id
            and self.language.iso == "evn"
            and self.name
            and not self.name_latin
        ):
            self.name_latin = _transliterate_evn_cyr_to_lat(self.name)
        super().save(*args, **kwargs)


class Narration(models.Model):
    """Рассказ о месте — от информанта, может быть переведён."""

    place = models.ForeignKey(
        Place, on_delete=models.CASCADE, related_name="narrations",
        verbose_name="Место",
    )
    narrator = models.ForeignKey(
        Person, on_delete=models.PROTECT, related_name="narrations",
        verbose_name="Рассказчик",
    )
    text_original = models.TextField("Оригинальный текст")
    language_original = models.ForeignKey(
        Language, on_delete=models.PROTECT, related_name="original_narrations",
        verbose_name="Язык оригинала",
    )

    panels = [
        FieldPanel("place"),
        FieldPanel("narrator"),
        FieldPanel("language_original"),
        FieldPanel("text_original"),
    ]

    class Meta:
        verbose_name = "Нарратив"
        verbose_name_plural = "Нарративы"
        ordering = ["-id"]

    def __str__(self) -> str:
        preview = self.text_original[:60]
        return f"{self.narrator}: {preview}…"


class NarrationTranslation(models.Model):
    """Перевод нарратива на другой язык."""

    narration = models.ForeignKey(
        Narration, on_delete=models.CASCADE, related_name="translations",
        verbose_name="Оригинал",
    )
    language = models.ForeignKey(
        Language, on_delete=models.PROTECT, related_name="narration_translations",
        verbose_name="Язык перевода",
    )
    text = models.TextField("Текст перевода")

    panels = [
        FieldPanel("narration"),
        FieldPanel("language"),
        FieldPanel("text"),
    ]

    class Meta:
        verbose_name = "Перевод нарратива"
        verbose_name_plural = "Переводы нарративов"
        unique_together = [("narration", "language")]

    def __str__(self) -> str:
        return f"{self.narration} → {self.language.iso}"


# ─── Утилита транслитерации эвенкийского ─────────────────────────────────


_EVN_CYR_TO_LAT = {
    "ӈ": "ŋ", "Ӈ": "Ŋ",
    "ӣ": "ī", "Ӣ": "Ī",
    "ӯ": "ū", "Ӯ": "Ū",
    "ӓ": "ǟ", "Ӓ": "Ǟ",
    "ӧ": "ö", "Ӧ": "Ö",
    "ж": "ž", "Ж": "Ž",
    "ш": "š", "Ш": "Š",
    "ч": "č", "Ч": "Č",
    "щ": "šč", "Щ": "Šč",
    "ю": "ju", "Ю": "Ju",
    "я": "ja", "Я": "Ja",
    "ё": "jo", "Ё": "Jo",
    "э": "e", "Э": "E",
    "ы": "y", "Ы": "Y",
    "й": "j", "Й": "J",
    "ь": "ʹ", "Ъ": "ʺ", "ъ": "ʺ",
    "а": "a", "А": "A", "б": "b", "Б": "B", "в": "v", "В": "V",
    "г": "g", "Г": "G", "д": "d", "Д": "D", "е": "e", "Е": "E",
    "з": "z", "З": "Z", "и": "i", "И": "I", "к": "k", "К": "K",
    "л": "l", "Л": "L", "м": "m", "М": "M", "н": "n", "Н": "N",
    "о": "o", "О": "O", "п": "p", "П": "P", "р": "r", "Р": "R",
    "с": "s", "С": "S", "т": "t", "Т": "T", "у": "u", "У": "U",
    "ф": "f", "Ф": "F", "х": "h", "Х": "H", "ц": "c", "Ц": "C",
}


def _transliterate_evn_cyr_to_lat(text: str) -> str:
    """Простая посимвольная транслитерация эвенкийского кириллица→латиница."""
    return "".join(_EVN_CYR_TO_LAT.get(ch, ch) for ch in text)
