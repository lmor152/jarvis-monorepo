FROM python:3.13-slim AS runtime

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY applications/assistant/pyproject.toml ./pyproject.toml

COPY applications/assistant/src/ ./src/

ENV PYTHONPATH=/app/src

EXPOSE 8001

CMD ["uv", "run", "uvicorn", "assistant.main:app", "--host", "0.0.0.0", "--port", "8001"]
