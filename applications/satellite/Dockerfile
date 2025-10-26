FROM python:3.13-slim AS runtime

WORKDIR /app

RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
		build-essential \
		libasound2 \
		libatlas-base-dev \
		libportaudio2 \
		libportaudiocpp0 \
		portaudio19-dev \
	&& rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY applications/satellite/pyproject.toml ./pyproject.toml

COPY applications/satellite/src/ ./src/

ENV PYTHONPATH=/app/src

CMD ["uv", "run", "python", "-m", "satellite.main"]
