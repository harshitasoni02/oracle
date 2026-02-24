FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    supervisor \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install torch CPU-only first (lighter wheel from PyTorch index)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV HF_HOME=/app/hf_cache

COPY . .

RUN mkdir -p /app/db /app/hf_cache /var/log/supervisor /var/log/django

COPY supervisord.conf /etc/supervisord.conf
COPY docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["supervisord", "-n", "-c", "/etc/supervisord.conf"]
