FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.production.txt ./
RUN pip install --no-cache-dir -r requirements.production.txt && useradd --create-home appuser && mkdir /state && chown appuser:appuser /state
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts/seed_demo.py scripts/manage_users.py scripts/manage_api_tokens.py ./scripts/
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/ready', timeout=3)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-proxy-headers", "--limit-concurrency", "16", "--timeout-keep-alive", "5"]
