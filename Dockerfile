FROM python:3.12-slim

RUN groupadd -r botuser && useradd -r -g botuser botuser \
    && apt-get update && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ bot/
COPY main.py .
COPY config/config.example.yaml /app/config.example.yaml
COPY entrypoint.sh /app/entrypoint.sh

RUN mkdir -p /data && chown -R botuser:botuser /data /app \
    && chmod +x /app/entrypoint.sh

EXPOSE 9090

ENTRYPOINT ["/app/entrypoint.sh"]
