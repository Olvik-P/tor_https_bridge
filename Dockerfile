# =============================================================================
# Dockerfile for Tor HTTPS Bridge Proxy with Web UI
# =============================================================================
# Runs the proxy with matrix-style web dashboard.
# Tor is expected on the host machine (host.docker.internal:9050).
# =============================================================================

FROM python:3.13-slim

WORKDIR /app

# Install system dependencies (if any needed in the future)
# RUN apt-get update && apt-get install -y --no-install-recommends ... && rm -rf /var/lib/apt/lists/*

# Install Python dependencies globally (into system site-packages)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN groupadd -r torproxy && useradd -r -g torproxy -d /app -s /sbin/nologin torproxy

# Copy application code
COPY tor_https_bridge/ ./tor_https_bridge/
COPY .env.example ./.env.example

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 3128 1080 8080

USER torproxy

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.connect(('127.0.0.1', 8080)); s.close()" || exit 1

ENTRYPOINT ["python", "-m", "tor_https_bridge"]
CMD ["--web", "--web-host", "0.0.0.0", "--web-port", "8080", "--tor-host", "host.docker.internal", "--tor-port", "9050"]
