FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy locustfile, instrumentation, and entrypoint scripts
COPY locustfile.py .
COPY instrumentation.py .
COPY run-headless.sh .
COPY entrypoint.sh .
RUN chmod +x run-headless.sh entrypoint.sh

# Expose Locust web UI port
EXPOSE 8089

# Default command - uses entrypoint.sh to read TARGET_HOST from environment
CMD ["/app/entrypoint.sh"]

