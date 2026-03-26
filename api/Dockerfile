FROM ghcr.io/astral-sh/uv:0.8 AS uv
FROM python:3.12-slim

WORKDIR /app

COPY --from=uv /uv /bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
