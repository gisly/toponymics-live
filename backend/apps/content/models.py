"""
Типы страниц Wagtail.

Стартовый набор:
- HomePage — главная (только одна, корень)
- ProjectPage — раздел проекта (О проекте, Картография и топонимика, ...)
- PlatformPage — страница с встроенной интерактивной картой (одна на сайт)
- ArticlePage — статья, событие, новость
- TeamMemberPage — карточка участника команды
- EventPage — событие
"""
from django.db import models
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page
from wagtail.search import index

from apps.toponyms.blocks import NarrativeStreamBlock


class HomePage(Page):
    """Главная страница. Только одна, в корне сайта."""

    intro = RichTextField("Вводный текст", blank=True)
    body = StreamField(NarrativeStreamBlock(), blank=True, use_json_field=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("body"),
    ]

    # Тип позволяемых детей — другие наши страницы
    subpage_types = [
        "content.ProjectPage",
        "content.PlatformPage",
        "content.ArticlePage",
        "content.EventPage",
    ]
    parent_page_types = ["wagtailcore.Page"]  # только в корне сайта

    class Meta:
        verbose_name = "Главная страница"


class ProjectPage(Page):
    """Раздел проекта: 'О проекте', 'Картография и топонимика', и т.д."""

    intro = RichTextField("Вводный текст", blank=True)
    body = StreamField(NarrativeStreamBlock(), blank=True, use_json_field=True)
    icon = models.CharField(
        "Иконка", max_length=50, blank=True,
        help_text="Имя иконки lucide-react, например 'book', 'map', 'users'",
    )
    sort_order = models.IntegerField("Порядок в меню", default=100)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("body"),
        MultiFieldPanel(
            [FieldPanel("icon"), FieldPanel("sort_order")],
            heading="Отображение",
        ),
    ]

    subpage_types = ["content.ArticlePage", "content.ProjectPage"]

    class Meta:
        verbose_name = "Раздел"


class PlatformPage(Page):
    """
    Страница с встроенной интерактивной картой топонимов.

    Карта монтируется как UMD-бандл (см. Этап 1 — frontend/dist-lib/),
    раздаётся как статика Django из backend/static/map/.

    На странице одна — но Wagtail-localize создаёт по копии на каждый язык.
    """

    intro = RichTextField(
        "Вступительный текст (над картой)", blank=True,
        help_text="Короткое описание платформы. Покажется над картой.",
    )

    # Начальные параметры карты — редактируемые из админки
    initial_lng = models.FloatField(
        "Начальная долгота", default=110.0,
        help_text="Долгота центра карты при открытии",
    )
    initial_lat = models.FloatField(
        "Начальная широта", default=62.0,
        help_text="Широта центра карты при открытии",
    )
    initial_zoom = models.FloatField(
        "Начальный зум", default=4.0,
        help_text="Чем больше, тем сильнее приближено (0 = весь мир, 18 = улица)",
    )

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        MultiFieldPanel(
            [
                FieldPanel("initial_lng"),
                FieldPanel("initial_lat"),
                FieldPanel("initial_zoom"),
            ],
            heading="Начальный вид карты",
        ),
    ]

    # Карта в одном экземпляре, поэтому subpage_types пуст.
    subpage_types = []
    parent_page_types = ["content.HomePage"]

    class Meta:
        verbose_name = "Платформа (карта)"


class ArticlePage(Page):
    """Статья. Универсальная страница с текстом."""

    intro = models.CharField("Подзаголовок", max_length=500, blank=True)
    body = StreamField(NarrativeStreamBlock(), blank=True, use_json_field=True)
    cover_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        verbose_name="Обложка",
    )
    publish_date = models.DateField("Дата публикации", null=True, blank=True)

    search_fields = Page.search_fields + [
        index.SearchField("intro"),
        index.SearchField("body"),
    ]

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("cover_image"),
        FieldPanel("publish_date"),
        FieldPanel("body"),
    ]

    class Meta:
        verbose_name = "Статья"


class TeamMemberPage(Page):
    """Карточка участника команды."""

    role = models.CharField("Роль в проекте", max_length=200, blank=True)
    affiliation = models.CharField("Аффилиация", max_length=300, blank=True)
    photo = models.ForeignKey(
        "wagtailimages.Image",
        null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        verbose_name="Фото",
    )
    bio = StreamField(NarrativeStreamBlock(), blank=True, use_json_field=True)
    email = models.EmailField("Email", blank=True)
    website = models.URLField("Сайт", blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("role"),
        FieldPanel("affiliation"),
        FieldPanel("photo"),
        FieldPanel("bio"),
        MultiFieldPanel(
            [FieldPanel("email"), FieldPanel("website")],
            heading="Контакты",
        ),
    ]

    class Meta:
        verbose_name = "Участник команды"


class EventPage(Page):
    """Событие: конференция, экспедиция, презентация."""

    event_date = models.DateField("Дата события", null=True, blank=True)
    location = models.CharField("Место", max_length=300, blank=True)
    intro = RichTextField("Краткое описание", blank=True)
    body = StreamField(NarrativeStreamBlock(), blank=True, use_json_field=True)

    content_panels = Page.content_panels + [
        FieldPanel("event_date"),
        FieldPanel("location"),
        FieldPanel("intro"),
        FieldPanel("body"),
    ]

    class Meta:
        verbose_name = "Событие"
