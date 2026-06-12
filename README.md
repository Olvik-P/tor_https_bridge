# Tor HTTPS Bridge Proxy

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Tor HTTPS Bridge Proxy** — это прокси-сервер, который прозрачно перенаправляет HTTPS-трафик через SOCKS5-прокси Tor. Он принимает стандартные HTTP CONNECT-запросы (от браузеров, curl, системных настроек Windows) и туннелирует их через Tor, обеспечивая анонимность для любого приложения, поддерживающего HTTP(S)-прокси.

## Возможности

- 🔒 **Прозрачная маршрутизация через Tor** — не требует настройки Tor на уровне приложений
- ⚡ **Асинхронный I/O** — построен на `asyncio` для высокой производительности
- 🛡️ **Graceful shutdown** — дожидается завершения активных соединений перед остановкой
- ⚙️ **Гибкая конфигурация** — переменные окружения, `.env`-файлы, JSON/YAML-конфиги, аргументы CLI
- 🪟 **Поддержка Windows** — работает с системными прокси-настройками Windows
- 📦 **Готов к production** — валидация Pydantic v2, структурированное логирование, полные аннотации типов
- 🔁 **Автоматические повторные попытки** — настраиваемые retry-механизмы для SOCKS5-соединений
- 🌐 **Поддержка обычных HTTP-запросов** — туннелирование GET/POST и других методов через Tor

## Установка

### Из исходного кода

```bash
git clone git@github.com:Olvik-P/tor_https_bridge.git
cd tor-https-bridge
pip install .
```

### Для разработки

```bash
pip install -e ".[dev]"
```

### Через pip из GitHub

```bash
pip install git+https://github.com/Olvik-P/tor_https_bridge.git
```

## Быстрый старт

1. **Убедитесь, что Tor запущен** на `127.0.0.1:9050` (по умолчанию).

2. **Запустите bridge**:

```bash
tor-https-bridge
```

3. **Настройте ваше приложение** на использование HTTP-прокси `127.0.0.1:3128`.

4. **Проверьте**:

```bash
curl -x http://127.0.0.1:3128 https://check.torproject.org/api/ip
```

## Конфигурация

### Переменные окружения (префикс `TOR_BRIDGE_`)

| Переменная | По умолчанию | Описание |
|---|---|---|
| `TOR_BRIDGE_TOR_SOCKS_HOST` | `127.0.0.1` | Адрес SOCKS5-прокси Tor |
| `TOR_BRIDGE_TOR_SOCKS_PORT` | `9050` | Порт SOCKS5-прокси Tor |
| `TOR_BRIDGE_HTTPS_PROXY_HOST` | `127.0.0.1` | Адрес для прослушивания HTTPS-прокси |
| `TOR_BRIDGE_HTTPS_PROXY_PORT` | `3128` | Порт для прослушивания HTTPS-прокси |
| `TOR_BRIDGE_BUFFER_SIZE` | `8192` | Размер буфера (байт) |
| `TOR_BRIDGE_BACKLOG` | `100` | Максимальное количество ожидающих соединений |
| `TOR_BRIDGE_MAX_REQUEST_SIZE` | `65535` | Максимальный размер HTTP-запроса (байт) |
| `TOR_BRIDGE_CONNECT_TIMEOUT` | `60` | Таймаут подключения (сек) |
| `TOR_BRIDGE_READ_TIMEOUT` | `120` | Таймаут чтения (сек) |
| `TOR_BRIDGE_SOCKS_RETRY_COUNT` | `2` | Количество повторных попыток SOCKS5 |
| `TOR_BRIDGE_SOCKS_RETRY_DELAY` | `2.0` | Задержка между попытками SOCKS5 (сек) |
| `TOR_BRIDGE_LOG_LEVEL` | `INFO` | Уровень логирования |

### `.env` файл

Скопируйте `.env.example` в `.env` и отредактируйте:

```bash
cp .env.example .env
```

### Аргументы CLI

```bash
tor-https-bridge --proxy-port 8080 --tor-port 9150 --log-level DEBUG
```

Полный список аргументов:

| Аргумент | Описание |
|---|---|
| `--proxy-host` | Адрес для прослушивания HTTPS-прокси |
| `--proxy-port` | Порт для прослушивания HTTPS-прокси |
| `--tor-host` | Адрес SOCKS5-прокси Tor |
| `--tor-port` | Порт SOCKS5-прокси Tor |
| `--buffer-size` | Размер буфера (байт) |
| `--backlog` | Максимальное количество ожидающих соединений |
| `--connect-timeout` | Таймаут подключения (сек) |
| `--read-timeout` | Таймаут чтения (сек) |
| `--log-level` | Уровень логирования (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |
| `--config` | Путь к JSON/YAML файлу конфигурации |
| `--version` | Показать версию и выйти |

### Файл конфигурации (JSON/YAML)

```bash
tor-https-bridge --config config.json
```

**config.json**:

```json
{
  "tor_socks_host": "127.0.0.1",
  "tor_socks_port": 9050,
  "https_proxy_port": 3128,
  "log_level": "INFO"
}
```

**Приоритет** (от высшего к низшему): аргументы CLI → переменные окружения → `.env` файл → файл конфигурации → значения по умолчанию

## Примеры использования

### Программное использование

```python
import asyncio
from tor_https_bridge import TorHTTPSProxy
from tor_https_bridge.config.settings import Settings

async def main():
    settings = Settings(https_proxy_port=8080, tor_socks_port=9150)
    proxy = TorHTTPSProxy(settings)
    await proxy.start()

asyncio.run(main())
```

### Запуск как Python-модуль

```bash
python -m tor_https_bridge --proxy-port 8080
```

### Настройка прокси в Windows

1. Запустите bridge: `tor-https-bridge`
2. Перейдите в **Параметры → Сеть и Интернет → Прокси**
3. Включите **"Использовать прокси-сервер"**
4. Адрес: `127.0.0.1`, Порт: `3128`
5. Нажмите **Сохранить**

## Systemd-сервис (Linux)

Создайте `/etc/systemd/system/tor-https-bridge.service`:

```ini
[Unit]
Description=Tor HTTPS Bridge Proxy
After=network.target tor.service
Wants=tor.service

[Service]
Type=simple
User=tor-bridge
ExecStart=/usr/local/bin/tor-https-bridge
Restart=on-failure
RestartSec=5
Environment=TOR_BRIDGE_LOG_LEVEL=INFO

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable tor-https-bridge
sudo systemctl start tor-https-bridge
```

## Запланированная задача Windows

Создайте задачу для автоматического запуска bridge при загрузке системы:

```powershell
# Создание задачи
$action = New-ScheduledTaskAction -Execute "tor-https-bridge"
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount
Register-ScheduledTask -TaskName "TorHTTPSBridge" -Action $action -Trigger $trigger -Principal $principal

# Запуск задачи
Start-ScheduledTask -TaskName "TorHTTPSBridge"
```

## Поиск и устранение неисправностей

### "Connection refused" при запуске

- Убедитесь, что Tor запущен: `systemctl status tor` (Linux) или проверьте, что Tor Browser открыт (Windows)
- Проверьте, не занят ли порт: `netstat -ano | find ":3128"` (Windows) или `ss -tlnp | grep 3128` (Linux)

### "SOCKS5 connection failed"

- Проверьте SOCKS5-порт Tor: `curl --socks5 127.0.0.1:9050 https://check.torproject.org/api/ip`
- Проверьте логи Tor: `journalctl -u tor -f` (Linux)

### Браузер показывает "Proxy connection failed"

- Убедитесь, что bridge запущен
- Проверьте, что настройки прокси указывают на `127.0.0.1:3128`
- Попробуйте: `curl -x http://127.0.0.1:3128 https://httpbin.org/ip`

### Windows: "Unable to connect to the proxy server"

- Запустите bridge от имени администратора, если используется привилегированный порт (< 1024)
- Проверьте, не блокирует ли брандмауэр Windows соединение

## Архитектура

```
┌─────────────┐     CONNECT     ┌──────────────────┐     SOCKS5     ┌─────────┐
│   Browser   │ ──────────────> │  Tor HTTPS Bridge │ ────────────> │   Tor   │
│  App/curl   │ <────────────── │  (127.0.0.1:3128) │ <──────────── │ :9050   │
└─────────────┘   200 OK/Tunnel └──────────────────┘               └─────────┘
```

Пакет имеет модульную архитектуру:

- **`config/`** — Константы и настройки на Pydantic v2
- **`core/`** — Сервер, обработчик клиентов, форвардер данных, исключения
- **`protocol/`** — Парсер HTTP CONNECT, адаптер SOCKS5
- **`utils/`** — Настройка логирования, системные утилиты
- **`cli/`** — Интерфейс командной строки

## Разработка

```bash
# Установка зависимостей для разработки
pip install -e ".[dev]"

# Форматирование кода
black tor_https_bridge/

# Линтинг
ruff check tor_https_bridge/

# Проверка типов
mypy tor_https_bridge/

# Запуск тестов
pytest
```

## Лицензия

MIT License — подробнее в файле [LICENSE](LICENSE).