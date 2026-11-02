FROM python:3.13-alpine@sha256:7984cf56ceaddebe4fefeb75d64000b9f45d8b77b11a09b24524da6cdc3af0c8 AS build
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.production.lock.txt ./
RUN pip install --no-cache-dir --only-binary=:all: -r requirements.production.lock.txt \
    && addgroup -S -g 1000 appuser && adduser -S -u 1000 -G appuser -h /home/appuser appuser \
    && mkdir /state && chown appuser:appuser /state
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts/seed_demo.py scripts/manage_users.py scripts/manage_api_tokens.py ./scripts/
USER appuser

FROM build AS runtime
# Package installation belongs to build/test stages, not the immutable runtime.
# Remove the complete unused installers, not vulnerability metadata or scan records.
USER root
RUN python -m pip uninstall -y pip \
    && python -c "import pathlib, shutil, sysconfig; shutil.rmtree(pathlib.Path(sysconfig.get_path('stdlib')) / 'ensurepip')"
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/ready', timeout=3)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-proxy-headers", "--limit-concurrency", "16", "--timeout-keep-alive", "5"]
