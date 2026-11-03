# ============================================================
# Stage 1: Build the React frontend
# ============================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy dependency manifests first for layer caching.
COPY frontend/package.json frontend/package-lock.json ./

RUN npm ci

# Copy the rest of the source and build.
COPY frontend/ ./

RUN npm run build
# Output: /app/frontend/dist

# ============================================================
# Stage 2: Python runtime
# ============================================================
FROM python:3.12-slim AS runner

# Sensible Python defaults for containers.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_APP=wsgi.py \
    FRONTEND_DIST_DIR=/app/frontend/dist

WORKDIR /app/backend

# Install curl (used by HEALTHCHECK) and clean up in one layer.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies before copying application code so that
# the layer is cached as long as requirements.txt is unchanged.
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code.
COPY backend/ ./

# Copy the built frontend assets from Stage 1.
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Copy and make the entrypoint script executable.
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Create the local storage directory and a non-root user in one layer.
RUN groupadd --system appuser \
    && useradd --system --gid appuser --no-create-home appuser \
    && mkdir -p /app/local_data \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Verify the API is reachable. Start-period gives gunicorn + DB init time.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
