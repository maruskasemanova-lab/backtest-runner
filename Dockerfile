FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

COPY . /app

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /data/config /data/remote_cache /app/reports \
    && chown -R appuser:appuser /app /data

USER appuser

EXPOSE 8080

CMD ["sh", "-lc", "mkdir -p /data/config /data/remote_cache /app/reports && uvicorn api_server:app --host 0.0.0.0 --port ${PORT:-8080}"]
