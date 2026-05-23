"""StreamField blocks для нарративов и описаний."""
from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock


class QuoteBlock(blocks.StructBlock):
    text = blocks.TextBlock(label="Текст цитаты")
    attribution = blocks.CharBlock(required=False, label="Автор/источник")

    class Meta:
        icon = "openquote"
        label = "Цитата"


class MapEmbedBlock(blocks.StructBlock):
    """Встраивание мини-карты с подмножеством топонимов в текст статьи."""

    title = blocks.CharBlock(required=False, label="Подпись к карте")
    region_slug = blocks.CharBlock(
        required=False,
        label="Регион (slug)",
        help_text="Фильтр по региону; пусто — без фильтра",
    )
    historical_map_slug = blocks.CharBlock(
        required=False,
        label="Рукописная карта (slug)",
        help_text="Показать только топонимы, связанные с этой рукописной картой",
    )
    height_px = blocks.IntegerBlock(default=400, label="Высота, px")

    class Meta:
        icon = "site"
        label = "Карта (встраиваемая)"


class CollapsibleInnerStreamBlock(blocks.StreamBlock):
    """Подмножество блоков, разрешённых внутри сворачиваемой секции.

    Намеренно НЕ включаем map_embed (карта внутри ката — странно) и
    сам collapsible (чтобы избежать бесконечной вложенности).
    """

    paragraph = blocks.RichTextBlock(
        features=["bold", "italic", "link", "ol", "ul", "blockquote"],
        label="Параграф",
    )
    heading = blocks.CharBlock(form_classname="title", label="Заголовок", icon="title")
    image = ImageChooserBlock(label="Изображение")
    quote = QuoteBlock()


class CollapsibleBlock(blocks.StructBlock):
    """Сворачиваемая секция: заголовок + скрытое содержимое.

    Рендерится как нативный <details><summary>, без JavaScript.
    По умолчанию свёрнут. Содержимое индексируется Google и
    доступно при печати (см. CSS @media print).
    """

    summary = blocks.CharBlock(
        label="Заголовок (видимый текст)",
        help_text="Например: «Подробнее о методологии» или «Список источников»",
    )
    content = CollapsibleInnerStreamBlock(label="Скрытое содержимое")

    class Meta:
        icon = "plus"
        label = "Сворачиваемый блок"


class NarrativeStreamBlock(blocks.StreamBlock):
    """Универсальный набор блоков для нарративов и описаний."""

    paragraph = blocks.RichTextBlock(
        features=["bold", "italic", "link", "ol", "ul", "blockquote"],
        label="Параграф",
    )
    heading = blocks.CharBlock(form_classname="title", label="Заголовок", icon="title")
    image = ImageChooserBlock(label="Изображение")
    quote = QuoteBlock()
    collapsible = CollapsibleBlock()
    map_embed = MapEmbedBlock()
