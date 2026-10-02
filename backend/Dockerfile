# syntax=docker/dockerfile:1
FROM python:3.12-slim

# `docker compose` builds with INSTALL_DEV=true so pytest runs inside the container.
# Build a lean runtime image with:  docker build -t arad-store-backend backend
ARG INSTALL_DEV=false

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

# The application never runs as root.
RUN groupadd --system --gid 1000 app \
 && useradd --system --uid 1000 --gid app --no-create-home --shell /usr/sbin/nologin app

# Dependencies first: this layer is cached until a requirements file changes.
COPY requirements.txt requirements-dev.txt ./
RUN if [ "$INSTALL_DEV" = "true" ]; then pip install -r requirements-dev.txt; else pip install -r requirements.txt; fi

COPY --chown=app:app . .

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]

# Configuration (DATABASE_URL, SECRET_KEY, ...) comes from environment variables at runtime.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
