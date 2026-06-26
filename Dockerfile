# =============================================================================
# Dockerfile for Tor HTTPS Bridge Proxy
# =============================================================================
# Запускает только Python-мост, Tor ожидается на хосте (host.docker.internal:9050)
# =============================================================================

FROM python:3.13-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.13-slim AS runtime

WORKDIR /app

# Создаём не-root пользователя
RUN groupadd -r torproxy && useradd -r -g torproxy -d /app -s /sbin/nologin torproxy

# Копируем зависимости
COPY --from=builder /root/.local /home/torproxy/.local

# Копируем исходники
COPY tor_https_bridge/ ./tor_https_bridge/
COPY .env.example ./.env.example

# Настройка PATH
ENV PATH=/home/torproxy/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 3128 1080

USER torproxy

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.connect(('127.0.0.1', 3128)); s.close()" || exit 1

# Тор на хосте доступен по имени host.docker.internal
ENTRYPOINT ["python", "-m", "tor_https_bridge"]
CMD ["--tor-host", "host.docker.internal", "--tor-port", "9050"]