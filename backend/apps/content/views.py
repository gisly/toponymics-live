"""
Раздача больших ассетов карты:
- /pmtiles/<filename> — pmtiles-файлы тайлов (несколько ГБ), с поддержкой
  HTTP Range и обязательным Content-Length (требование pmtiles-клиента).
- /map-style/<filename> — JSON стилей MapLibre, с подменой плейсхолдера
  {PMTILES_URL} на актуальный URL.

В проде эти пути нужно отдать nginx-у напрямую — он быстрее и без GIL.
В dev (DEBUG=True) и для простой prod-установки этого достаточно.
"""
import json
import re
from pathlib import Path

from django.conf import settings
from django.http import (
    FileResponse,
    Http404,
    HttpResponse,
    HttpResponseNotModified,
    JsonResponse,
)
from django.utils.http import http_date
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_safe


# Корни задаются через settings, чтобы можно было поменять без правки кода
PMTILES_ROOT: Path = Path(getattr(settings, "PMTILES_ROOT", "/app/pmtiles-local"))
MAP_STYLE_ROOT: Path = Path(getattr(settings, "MAP_STYLE_ROOT", "/app/map-style"))


# Парсим Range: bytes=START-END (END может отсутствовать)
_RANGE_RE = re.compile(r"^bytes=(\d+)-(\d*)$")


@require_safe
@cache_control(public=True, max_age=86400)  # 1 день
def serve_pmtiles(request, path: str):
    """
    Отдаёт pmtiles-файл с поддержкой HTTP Range и обязательным Content-Length.

    pmtiles-клиент проверяет Content-Length у первого запроса; если его
    нет (или ответ chunked transfer-encoding) — клиент падает с
    "Server returned no content-length header".

    django.views.static.serve умеет Range, но в зависимости от middleware
    может вернуть streaming-ответ без Content-Length. Поэтому реализуем
    обработку Range вручную и всегда выставляем Content-Length.
    """
    # Безопасность: запрещаем path traversal
    if ".." in path or path.startswith("/") or "\\" in path:
        raise Http404("invalid path")

    full_path = PMTILES_ROOT / path
    try:
        full_path = full_path.resolve(strict=True)
    except (FileNotFoundError, OSError):
        raise Http404(f"pmtiles not found: {path}")
    if not str(full_path).startswith(str(PMTILES_ROOT.resolve())):
        raise Http404("path traversal")
    if not full_path.is_file():
        raise Http404("not a file")

    file_size = full_path.stat().st_size
    mtime = full_path.stat().st_mtime
    etag = f'"{int(mtime)}-{file_size}"'

    # If-None-Match (для условных запросов)
    if request.META.get("HTTP_IF_NONE_MATCH") == etag:
        return HttpResponseNotModified()

    range_header = request.META.get("HTTP_RANGE", "")
    if range_header:
        m = _RANGE_RE.match(range_header)
        if not m:
            resp = HttpResponse(status=416)
            resp["Content-Range"] = f"bytes */{file_size}"
            return resp
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else file_size - 1
        if start >= file_size or end >= file_size or start > end:
            resp = HttpResponse(status=416)
            resp["Content-Range"] = f"bytes */{file_size}"
            return resp

        length = end - start + 1
        f = full_path.open("rb")
        f.seek(start)

        resp = FileResponse(
            _read_chunk(f, length),
            status=206,
            content_type="application/octet-stream",
        )
        resp["Content-Length"] = str(length)
        resp["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    else:
        # Полный файл
        resp = FileResponse(
            full_path.open("rb"),
            content_type="application/octet-stream",
        )
        resp["Content-Length"] = str(file_size)

    resp["Accept-Ranges"] = "bytes"
    resp["ETag"] = etag
    resp["Last-Modified"] = http_date(mtime)
    return resp


def _read_chunk(f, remaining: int, block_size: int = 64 * 1024):
    """Итератор: читает не больше `remaining` байт из открытого файла."""
    try:
        while remaining > 0:
            chunk = f.read(min(block_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
    finally:
        f.close()


@require_safe
@cache_control(public=True, max_age=300)
def serve_map_style(request, filename: str):
    """
    Отдаёт JSON стиля MapLibre, подставляя {PMTILES_URL} на актуальный путь.
    """
    if "/" in filename or "\\" in filename or filename.startswith(".") or not filename.endswith(".json"):
        raise Http404("invalid filename")

    path = MAP_STYLE_ROOT / filename
    if not path.exists():
        raise Http404(f"map style not found: {filename}")

    pmtiles_filename = getattr(settings, "PMTILES_DEFAULT_FILE", "russia-asian.pmtiles")
    pmtiles_url = request.build_absolute_uri(f"/pmtiles/{pmtiles_filename}")

    text = path.read_text(encoding="utf-8")
    text = text.replace("{PMTILES_URL}", pmtiles_url)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return HttpResponse(
            f"Map style {filename} is not valid JSON after substitution: {e}",
            status=500,
            content_type="text/plain; charset=utf-8",
        )

    return JsonResponse(data)
