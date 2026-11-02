FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first so code changes don't bust the layer cache. The project itself
# (src/chicago_transit) isn't needed at runtime, so it isn't installed.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY main.py ./
COPY backend ./backend
COPY scripts ./scripts

RUN useradd --create-home app
USER app

CMD ["python", "main.py"]
