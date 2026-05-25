FROM python:3.11-slim-bookworm AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install --prefix=/install \
      "openai>=1.40,<2.0" \
      "tiktoken>=0.7" \
      "tenacity>=8.2" \
      "pypdf>=4.3" \
      "python-pptx>=1.0" \
      "chromadb>=0.5" \
      "chainlit>=1.1,<2.0" \
      "slowapi>=0.1.9" \
      "azure-storage-blob>=12.20" \
      "azure-monitor-opentelemetry>=1.6" \
      "rich>=13.7" \
      "python-dotenv>=1.0" \
      "pydantic>=2.7,<2.10"

FROM python:3.11-slim-bookworm
WORKDIR /app

# Variant: 'public' (7 cleared docs) or 'full' (all 51).
ARG VARIANT=public
ENV CORPUS_VARIANT=${VARIANT}

# Copy installed deps from the builder.
COPY --from=builder /install /usr/local

# Copy application code (no PDFs — those are processed at build time on the host).
COPY app/ ./app/
COPY ingest/ ./ingest/
COPY rag/ ./rag/
COPY chainlit.md ./
COPY .chainlit/config.toml ./.chainlit/config.toml
COPY public/ ./public/

# Wiki + chroma — variant-specific. Build context must contain wiki-<variant>/ and chroma-<variant>/.
COPY wiki-${VARIANT}/ ./wiki/
COPY chroma-${VARIANT}/ ./chroma/

ENV WIKI_PATH=/app/wiki \
    CHROMA_PATH=/app/chroma \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BUDGET_STATE_PATH=/app/state/budget.json \
    LOCAL_LOG_DIR=/app/state/logs

RUN mkdir -p /app/state/logs

EXPOSE 8000
CMD ["chainlit", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8000", "--headless"]
