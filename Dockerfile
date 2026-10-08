FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ requirements/
ARG REQUIREMENTS=production.txt
RUN pip install -r requirements/${REQUIREMENTS}

COPY . .

RUN useradd -m -u 10001 fomobot && chown -R fomobot /app
USER fomobot

EXPOSE 8000

# Default: ASGI (HTTP + WebSockets). Override for workers/beat.
CMD ["sh", "-c", "uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-2}"]
