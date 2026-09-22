FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    RAGTRUST_DATA_DIR=/app/data \
    RAGTRUST_DATABASE_URL=sqlite:////app/data/ragtrust.db \
    PORT=8000

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY demo_data ./demo_data
COPY scripts ./scripts
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir . \
    && chmod +x /app/scripts/start.sh \
    && mkdir -p /app/data

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+('/health' if os.getenv('RAGTRUST_SERVICE','ui') == 'api' else '/_stcore/health'), timeout=3)"

CMD ["/app/scripts/start.sh"]
