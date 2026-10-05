# =============================================================
# Stage 1: Build Frontend SPA Assets (Vite + React)
# =============================================================
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

# Install dependencies (utilizing Docker layer caching)
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Build production assets to /app/frontend/dist
COPY frontend/ ./
RUN npm run build

# =============================================================
# Stage 2: Build Python Dependencies & Wheel
# =============================================================
FROM python:3.12-slim AS backend-builder

WORKDIR /app

# Install build prerequisites
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install application and production dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# =============================================================
# Stage 3: Minimal Production Runtime Container
# =============================================================
FROM python:3.12-slim AS runner

WORKDIR /app

# Copy installed python site-packages and CLI executables
COPY --from=backend-builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=backend-builder /usr/local/bin /usr/local/bin

# Copy built frontend SPA static distribution
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Copy application code, datasets, and migration/seed scripts
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY data/ ./data/
COPY scripts/ ./scripts/

# Create non-root user and initialize persistent directories
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/data /app/storage && \
    chown -R appuser:appuser /app

USER appuser

# Cloud Run defaults to PORT 8080
ENV PORT=8080
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c 'import urllib.request; exit(0 if urllib.request.urlopen("http://localhost:8080/health").getcode() == 200 else 1)'

ENTRYPOINT ["uvicorn", "src.presentation.api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
