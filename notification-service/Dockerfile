# AI Assistance Disclosure:
# Tool: Claude Code (model: claude-opus-5-5), date: 2026-11-03
# Scope: Boilerplate generation — package the API, worker, and Alembic files in one image with a non-root user, readiness health check, and uvicorn entrypoint, following credit-service conventions.
# Author review: Keith confirmed review of all affected changes.
# Details: notification-service/ai/usage-log.md; ai-20261103-001

FROM python:3.12-slim

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/ready', timeout=3)"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
