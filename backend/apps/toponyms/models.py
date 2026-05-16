"""
Доменные модели топонимики.

Основные сущности:
- Region — географический регион
- FeatureType — тип объекта (река, гора, ...)
- HistoricalMap — рукописная или историческая карта
- Toponym — точка-топоним на современной карте
- ToponymOnMap — through-таблица "топоним на конкретной рукописной карте"
- MediaItem — медиа-объект (фото, аудио, видео)
"""
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import RichTextField, StreamField
from wagtail.models import TranslatableMixin
from wagtail.search import index

from .blocks import NarrativeStreamBlock


# ─── Справочники ─────────────────────────────────────────────────────────


class Region(TranslatableMixin, models.Model):
    """Географический регион — для группировки и фильтров на карте."""

    name = models.CharField("Название", max_length=200)
    slug = models.SlugField("URL-ключ", unique=True, max_length=200)
    description = RichTextField("Описание", blank=True)

    # bbox для центрирования карты — минимальные/максимальные координаты
    bbox_west = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    bbox_south = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    bbox_east = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    bbox_north = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    panels = [
        FieldPanel("name"),
        FieldPanel("slug"),
        FieldPanel("description"),
        MultiFieldPanel(
            [
                FieldPanel("bbox_west"),
                FieldPanel("bbox_south"),
                FieldPanel("bbox_east"),
                FieldPanel("bbox_north"),
            ],
            heading="Bounding box",
            classname="collapsible",
        ),
    ]

    class Meta(TranslatableMixin.Meta):
        verbose_name = "Регион"
        verbose_name_plural = "Регионы"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class FeatureType(TranslatableMixin, models.Model):
    """Тип географического объекта: река, гора, стойбище, тундра, ..."""

    code = models.SlugField("Код", max_length=50, unique=True)
    name = models.CharField("Название", max_length=100)
    icon = models.CharField(
        "Иконка (имя в спрайт-шите)", max_length=50, blank=True,
        help_text="Имя иконки в MapLibre sprite-sheet, например 'river' или 'mountain'",
    )
    default_color = models.CharField(
        "Цвет по умолчанию", max_length=20, blank=True,
        help_text="HEX-цвет для отображения на карте, например #2e7d32",
    )
    sort_order = models.IntegerField("Порядок", default=100)

    panels = [
        FieldPanel("code"),
        FieldPanel("name"),
        FieldPanel("icon"),
        FieldPanel("default_color"),
        FieldPanel("sort_order"),
    ]

    class Meta(TranslatableMixin.Meta):
        verbose_name = "Тип объекта"
        verbose_name_plural = "Типы объектов"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


# ─── Медиа ───────────────────────────────────────────────────────────────


class MediaItem(TranslatableMixin, models.Model):
    """Медиа-объект: фото, аудио, видео, документ.

    Привязки идут через обратные M2M на Toponym, HistoricalMap.
    """

    class MediaType(models.TextChoices):
        IMAGE = "image", "Изображение"
        AUDIO = "audio", "Аудио"
        VIDEO = "video", "Видео"
        DOCUMENT = "document", "Документ"

    type = models.CharField("Тип", max_length=20, choices=MediaType.choices)
    file = models.FileField("Файл", upload_to="media_items/%Y/%m/")
    caption = models.CharField("Подпись", max_length=500, blank=True)
    credit = models.CharField("Источник/автор", max_length=300, blank=True)
    license = models.CharField(
        "Лицензия", max_length=100, blank=True,
        help_text="Например: CC BY-SA 4.0, © Автор, public domain",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    panels = [
        FieldPanel("type"),
        FieldPanel("file"),
        FieldPanel("caption"),
        FieldPanel("credit"),
        FieldPanel("license"),
    ]

    class Meta(TranslatableMixin.Meta):
        verbose_name = "Медиа-объект"
        verbose_name_plural = "Медиа-объекты"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.get_type_display()}: {self.caption or self.file.name}"


# ─── Рукописная карта ────────────────────────────────────────────────────


class HistoricalMap(TranslatableMixin, index.Indexed, models.Model):
    """Рукописная или историческая карта.

    Загружается как изображение, может быть привязана к современной карте
    через georeference_data (GCP-точки в формате Allmaps Georeference Annotation).
    """

    class GeoreferenceStatus(models.TextChoices):
        NONE = "none", "Не привязана"
        PARTIAL = "partial", "Частичная привязка"
        FULL = "full", "Полная привязка"

    title = models.CharField("Название", max_length=300)
    slug = models.SlugField("URL-ключ", unique=True, max_length=300)
    description = StreamField(
        NarrativeStreamBlock(), blank=True, use_json_field=True,
        verbose_name="Описание",
    )

    creator = models.CharField(
        "Автор/информант", max_length=300, blank=True,
        help_text="Кто составил карту: имя информанта, коллектив, организация",
    )
    date_drawn = models.CharField(
        "Дата составления", max_length=100, blank=True,
        help_text="Может быть приблизительной: '1970-е', 'около 1965', точная дата",
    )
    date_collected = models.DateField("Дата получения в проект", null=True, blank=True)
    language = models.CharField(
        "Язык подписей на карте", max_length=10, blank=True,
        help_text="ISO-код: evn, ru, en, ...",
    )

    region = models.ForeignKey(
        Region, on_delete=models.PROTECT, related_name="historical_maps",
        verbose_name="Регион",
    )

    scanned_image = models.ImageField(
        "Скан карты (высокое разрешение)",
        upload_to="historical_maps/%Y/",
    )
    thumbnail = models.ImageField(
        "Превью",
        upload_to="historical_maps/thumbnails/%Y/",
        blank=True, null=True,
        help_text="Опционально — если не указано, генерируется автоматически из скана",
    )

    georeference_status = models.CharField(
        "Статус геопривязки", max_length=20,
        choices=GeoreferenceStatus.choices, default=GeoreferenceStatus.NONE,
    )
    georeference_data = models.JSONField(
        "Данные геопривязки", null=True, blank=True,
        help_text="Allmaps Georeference Annotation: GCP-точки и параметры преобразования",
    )

    related_media = models.ManyToManyField(
        MediaItem, blank=True, related_name="historical_maps",
        verbose_name="Связанные медиа",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Wagtail search
    search_fields = [
        index.SearchField("title", boost=2),
        index.SearchField("creator"),
        index.AutocompleteField("title"),
        index.FilterField("region_id"),
        index.FilterField("language"),
        index.FilterField("georeference_status"),
    ]

    panels = [
        MultiFieldPanel(
            [
                FieldPanel("title"),
                FieldPanel("slug"),
                FieldPanel("creator"),
                FieldPanel("date_drawn"),
                FieldPanel("date_collected"),
                FieldPanel("language"),
                FieldPanel("region"),
            ],
            heading="Метаданные",
        ),
        FieldPanel("description"),
        MultiFieldPanel(
            [FieldPanel("scanned_image"), FieldPanel("thumbnail")],
            heading="Изображения",
        ),
        MultiFieldPanel(
            [FieldPanel("georeference_status"), FieldPanel("georeference_data")],
            heading="Геопривязка",
            classname="collapsible",
        ),
        FieldPanel("related_media"),
    ]

    class Meta(TranslatableMixin.Meta):
        verbose_name = "Рукописная карта"
        verbose_name_plural = "Рукописные карты"
        ordering = ["-date_collected", "title"]

    def __str__(self) -> str:
        return self.title


# ─── Топоним ─────────────────────────────────────────────────────────────


class Toponym(index.Indexed, models.Model):
    """Топоним: точка на современной карте + параллельные формы имени.

    NB: Toponym не использует TranslatableMixin — параллельные имена
    хранятся как поля одной записи (это не "переводы", а разные системы письма).
    Поля etymology и narrative переводятся через related TranslatableMixin-объект.
    """

    class Confidence(models.TextChoices):
        HIGH = "high", "Высокая"
        MEDIUM = "medium", "Средняя"
        LOW = "low", "Низкая"
        UNKNOWN = "unknown", "Не определена"

    # ─ Имена ─────────────────────────────────────────────────────
    # Эвенкийские формы (3 системы письма)
    name_evn_cyrillic = models.CharField(
        "Эвенкийское (кириллица)", max_length=200, blank=True,
        help_text="Стандартная орфография РФ",
    )
    name_evn_latin = models.CharField(
        "Эвенкийское (латиница)", max_length=200, blank=True,
        help_text="Научная транслитерация (можно сгенерировать из кириллицы)",
    )
    name_evn_ipa = models.CharField(
        "Эвенкийское (IPA)", max_length=200, blank=True,
        help_text="Фонетическая транскрипция",
    )
    name_evn_variants = ArrayField(
        models.CharField(max_length=200),
        verbose_name="Альтернативные эвенкийские формы",
        default=list, blank=True,
        help_text="Диалектные варианты, исторические записи",
    )

    # Русские формы
    name_ru = models.CharField("Русское название", max_length=200)
    name_ru_variants = ArrayField(
        models.CharField(max_length=200),
        verbose_name="Альтернативные русские формы",
        default=list, blank=True,
    )

    # Английская транслитерация
    name_en = models.CharField("Английская запись", max_length=200, blank=True)

    # ─ Классификация ─────────────────────────────────────────────
    feature_type = models.ForeignKey(
        FeatureType, on_delete=models.PROTECT, related_name="toponyms",
        verbose_name="Тип объекта",
    )
    region = models.ForeignKey(
        Region, on_delete=models.PROTECT, related_name="toponyms",
        verbose_name="Регион",
    )

    # ─ География ─────────────────────────────────────────────────
    latitude = models.DecimalField("Широта", max_digits=9, decimal_places=6)
    longitude = models.DecimalField("Долгота", max_digits=9, decimal_places=6)
    confidence = models.CharField(
        "Точность локализации", max_length=20,
        choices=Confidence.choices, default=Confidence.MEDIUM,
    )

    # ─ Текст ─────────────────────────────────────────────────────
    etymology = RichTextField("Этимология", blank=True)
    narrative = StreamField(
        NarrativeStreamBlock(), blank=True, use_json_field=True,
        verbose_name="Нарратив/история",
    )

    # ─ Связи ─────────────────────────────────────────────────────
    source_maps = models.ManyToManyField(
        HistoricalMap, through="ToponymOnMap",
        related_name="toponyms",
        verbose_name="Связанные рукописные карты",
    )
    related_toponyms = models.ManyToManyField(
        "self", symmetrical=False, blank=True,
        verbose_name="Связанные топонимы",
    )
    related_media = models.ManyToManyField(
        MediaItem, blank=True, related_name="toponyms",
        verbose_name="Медиа",
    )

    # ─ Метаданные ────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "auth.User", on_delete=models.PROTECT, related_name="+", null=True, blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    # Поле для PostgreSQL full-text search — заполняется триггером или save()
    search_vector = SearchVectorField(null=True, blank=True)

    # Wagtail search (используется в Wagtail UI; для публичного API — DRF + PG FTS)
    search_fields = [
        index.SearchField("name_ru", boost=2),
        index.SearchField("name_evn_cyrillic", boost=2),
        index.SearchField("name_evn_latin"),
        index.SearchField("name_en"),
        index.AutocompleteField("name_ru"),
        index.AutocompleteField("name_evn_cyrillic"),
        index.FilterField("feature_type_id"),
        index.FilterField("region_id"),
        index.FilterField("confidence"),
    ]

    panels = [
        MultiFieldPanel(
            [
                FieldPanel("name_ru"),
                FieldPanel("name_ru_variants"),
                FieldPanel("name_evn_cyrillic"),
                FieldPanel("name_evn_latin"),
                FieldPanel("name_evn_ipa"),
                FieldPanel("name_evn_variants"),
                FieldPanel("name_en"),
            ],
            heading="Названия",
        ),
        MultiFieldPanel(
            [FieldPanel("feature_type"), FieldPanel("region")],
            heading="Классификация",
        ),
        MultiFieldPanel(
            [FieldPanel("latitude"), FieldPanel("longitude"), FieldPanel("confidence")],
            heading="География",
        ),
        FieldPanel("etymology"),
        FieldPanel("narrative"),
        MultiFieldPanel(
            [
                FieldPanel("related_toponyms"),
                FieldPanel("related_media"),
            ],
            heading="Связи",
        ),
    ]

    class Meta:
        verbose_name = "Топоним"
        verbose_name_plural = "Топонимы"
        ordering = ["name_ru"]
        indexes = [
            GinIndex(fields=["search_vector"]),
            models.Index(fields=["latitude", "longitude"]),
            models.Index(fields=["feature_type", "region"]),
        ]

    def __str__(self) -> str:
        return self.name_ru or self.name_evn_cyrillic or f"Toponym #{self.pk}"

    def save(self, *args, **kwargs):
        # Автогенерация латиницы из кириллицы, если пусто
        if self.name_evn_cyrillic and not self.name_evn_latin:
            self.name_evn_latin = transliterate_evn_cyrillic_to_latin(self.name_evn_cyrillic)
        super().save(*args, **kwargs)


class ToponymOnMap(models.Model):
    """Связь "топоним на конкретной рукописной карте".

    Один топоним может встречаться на нескольких картах под разными именами,
    в разных пиксельных координатах.
    """

    toponym = models.ForeignKey(
        Toponym, on_delete=models.CASCADE, related_name="map_positions",
    )
    historical_map = models.ForeignKey(
        HistoricalMap, on_delete=models.CASCADE, related_name="toponym_positions",
    )

    # Позиция на скане рукописной карты (пиксели)
    pixel_x = models.IntegerField("X на скане (пиксели)", null=True, blank=True)
    pixel_y = models.IntegerField("Y на скане (пиксели)", null=True, blank=True)

    # Как именно подписан на этой карте (может отличаться от canonical)
    label_as_written = models.CharField(
        "Подпись на карте", max_length=300, blank=True,
        help_text="Как именно записан этот топоним на этой конкретной карте",
    )
    note = models.TextField("Заметка", blank=True)

    class Meta:
        verbose_name = "Топоним на карте"
        verbose_name_plural = "Топонимы на картах"
        unique_together = [("toponym", "historical_map")]

    def __str__(self) -> str:
        return f"{self.toponym} на {self.historical_map}"


# ─── Утилита транслитерации ──────────────────────────────────────────────

# Минимальная таблица. Расширишь по своим конвенциям.
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


def transliterate_evn_cyrillic_to_latin(text: str) -> str:
    """Простая посимвольная транслитерация эвенкийского из кириллицы в латиницу.

    Это стартовая версия — не претендует на полную правильность всех случаев.
    Коллега всегда может поправить вручную.
    """
    return "".join(_EVN_CYR_TO_LAT.get(ch, ch) for ch in text)
