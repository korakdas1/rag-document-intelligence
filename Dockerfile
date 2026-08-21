# API image. Ollama stays on the host (or another service) — do not pretend GPU
# local models are fully containerized. Hugging Face weights download on first use
# unless you mount a cache volume.

FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web ./
RUN npm run build

FROM python:3.11-slim-bookworm AS api
WORKDIR /app
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/data/processed /app/data/uploads /app/data/indexes /app/web/dist \
    && chown -R appuser:appuser /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .
COPY --from=web /web/dist /app/web/dist
USER appuser
ENV APP_ENV=production \
    API_HOST=0.0.0.0 \
    API_PORT=8000 \
    RESEARCH_ASSISTANT_DATABASE_PATH=/app/data/processed/research_assistant.db \
    RESEARCH_ASSISTANT_UPLOAD_DIR=/app/data/uploads \
    RESEARCH_ASSISTANT_VECTOR_INDEX_PATH=/app/data/indexes/qdrant \
    PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "-m", "research_assistant", "serve", "--host", "0.0.0.0", "--port", "8000"]
