FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Системные зависимости для Pillow, psycopg, и .т.д.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    libwebp-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install -e ".[dev]"

# Код монтируется через volume в dev; в prod скопируется на build
COPY . /app

# Папка для media (volume в compose)
RUN mkdir -p /app/media /app/static_collected

EXPOSE 8000

CMD ["gunicorn", "toponymics.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
