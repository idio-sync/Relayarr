FROM python:3.12-slim

RUN groupadd -r botuser && useradd -r -g botuser botuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ bot/
COPY main.py .
COPY config/config.example.yaml /app/config.example.yaml

RUN mkdir -p /data && chown -R botuser:botuser /data /app

USER botuser

EXPOSE 9090

CMD ["python", "main.py"]
