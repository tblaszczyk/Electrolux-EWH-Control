FROM python:3.11-slim

WORKDIR /app

# Zależności systemowe
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kod aplikacji
COPY . .

# Katalogi danych (nadpisywane przez volumes)
RUN mkdir -p /var/lib/boiler /var/log/boiler

EXPOSE 8888

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8888/api/ping || exit 1

CMD ["python", "main.py"]
