FROM python:3.13-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /uvx /bin/

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock README.md ./
COPY puregym_bot ./puregym_bot

RUN mkdir -p /app/data && uv sync --frozen --no-dev

CMD ["uv", "run", "puregym-bot"]
