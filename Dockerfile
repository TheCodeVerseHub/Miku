# Miku - Multi-stage Dockerfile
#
# Build:
#     docker build -t miku .
#
# Run (bot only):
#     docker run -e DISCORD_BOT_TOKEN=... -e DATABASE_URL=... miku
#
# Run (dashboard only):
#     docker run -e DASHBOARD_CLIENT_ID=... -e DASHBOARD_CLIENT_SECRET=... -e DATABASE_URL=... \
#         miku uvicorn dashboard.backend.main:app --host 0.0.0.0 --port 8000
#
# Run (both with docker compose):
#     docker compose up
#
# NOTE: a Dockerfile only supports `#` comments. Do not put a Python docstring
# at the top of this file - the daemon parses the first line as an instruction
# and the build fails with `unknown instruction: """`.

FROM python:3.14-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package installer)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install Python dependencies.
#
# The project must be installed as editable *after* its sources are present.
# setuptools auto-discovers the `src/` layout, so installing with only
# `pyproject.toml` in the build context discovers no packages and silently
# produces an editable install with an empty module mapping. The container then
# starts, but `import cogs/services/shared/utils` fails - which only `main.py`
# hides via its own sys.path manipulation. The assertion below fails the build
# loudly if that ever regresses.
COPY pyproject.toml requirements.txt ./
COPY src/ ./src/
RUN uv pip install --system -e . \
    && python -c "import cogs, services, shared, utils; from shared.formula import calculate_level; calculate_level(1000)"

# Dashboard dependencies
COPY dashboard/requirements.txt dashboard/
RUN uv pip install --system -r dashboard/requirements.txt

# ── Runtime stage ────────────────────────────────────────────────────
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=UTC

WORKDIR /app

# Install runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    fonts-dejavu-core \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Create non-root user
RUN groupadd -r miku && useradd -r -g miku -d /app -s /sbin/nologin miku && \
    chown -R miku:miku /app
USER miku

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Default: run the bot
CMD ["python", "main.py"]

# Expose dashboard port
EXPOSE 8000
