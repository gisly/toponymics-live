"""Тег для рендеринга StreamField блоков через `{% render_streamfield %}`."""
from django import template

register = template.Library()


@register.inclusion_tag("includes/streamfield.html")
def render_streamfield(stream_value):
    """Рендерит StreamField с нашим оформлением блоков."""
    return {"stream": stream_value}
