FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN sed -i 's/\r$//' start.sh && chmod +x start.sh \
    && mkdir -p downloads transcricoes uploads \
    && useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app

USER appuser
EXPOSE 8000
ENV PORT=8000 WENDEL_MODE=web

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["sh", "start.sh"]
