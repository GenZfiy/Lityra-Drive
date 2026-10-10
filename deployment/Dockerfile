FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PORT=10000 WEB_THREADS=1 APP_ENV=production SKIP_INIT=1
RUN apt-get update && apt-get install -y --no-install-recommends supervisor curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
COPY backend/requirements-base.txt /app/backend/requirements-base.txt
RUN pip install -r /app/backend/requirements.txt
COPY backend/libs /app/backend/libs
RUN pip install /app/backend/libs
COPY backend/services /app/backend/services
COPY backend/services.txt /app/backend/services.txt
COPY deployment/entrypoint.sh /app/deployment/entrypoint.sh
RUN chmod +x /app/deployment/entrypoint.sh
EXPOSE 10000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 CMD curl -fsS http://127.0.0.1:${PORT:-10000}/health || exit 1
ENTRYPOINT ["/app/deployment/entrypoint.sh"]
