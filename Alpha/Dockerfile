# Project Alpha - Sovereign AI Executive Operating System
# Multi-stage production container for FastAPI backend, MCP Server, and local inference orchestration

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ALPHA_OFFLINE=1 \
    ALPHA_PROVIDER=ollama \
    DEFAULT_MODEL=llama3.2:1b \
    ALPHA_EMBEDDINGS=mock \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    sqlite3 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY alpha.py .
COPY .env* ./

RUN mkdir -p Alpha-Vault logs

EXPOSE 8000 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["python", "alpha.py", "start", "--host", "0.0.0.0", "--port", "8000"]
