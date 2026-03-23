FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/root/.local/bin:${PATH}"

WORKDIR /workspace

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY apps ./apps
COPY packages ./packages

RUN uv sync --frozen --no-dev --package api

ENV VIRTUAL_ENV="/workspace/.venv" \
    PATH="/workspace/.venv/bin:/root/.local/bin:${PATH}"

COPY apps/api/docker/entrypoint.sh docker/entrypoint.sh
RUN chmod +x docker/entrypoint.sh

ENTRYPOINT ["./docker/entrypoint.sh"]
