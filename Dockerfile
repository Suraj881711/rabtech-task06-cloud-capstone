# =============================================================================
# Dockerfile — Task 06 Capstone (Flask + gunicorn)
# Slim base image, non-root user, built-in health check.
# Works on Render-style platforms: the app binds to $PORT (default 8000).
# =============================================================================

FROM python:3.12-slim

# Keep Python output unbuffered (logs appear immediately) and skip .pyc files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

WORKDIR /app

# Install dependencies first (better Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY app.py .

# Run as a non-root user
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# Container health check — hits the same /health endpoint used by Render
# and by the uptime monitor. Uses Python (always present) instead of curl,
# which the slim image does not ship.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/health', timeout=4)"

# Production server: gunicorn, bound to the platform-provided $PORT
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 2 --threads 4 --timeout 60 app:app"]
