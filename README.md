# Tor HTTPS Bridge Proxy

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Tor HTTPS Bridge Proxy** — это асинхронный прокси-сервер, который прозрачно перенаправляет трафик через SOCKS5-прокси Tor. Он поддерживает **HTTPS CONNECT** и **SOCKS5** протоколы, автоматически определяя тип подключения, и обеспечивает анонимность для любого приложения.

---

## Возможности

### 🚀 Двойной прокси-сервер
- **HTTPS CONNECT proxy** — принимает стандартные HTTP CONNECT-запросы от браузеров, curl, системных настроек Windows
- **SOCKS5 proxy (входящий)** — полноценный SOCKS5-сервер (RFC 1928) с поддержкой аутентификации (RFC 1929)
- **Автоопределение протокола** — один порт автоматически определяет SOCKS5 или HTTP по первому байту

### 🔒 Анонимность и безопасность
- **Stealth Mode (санитизация заголовков)** — удаляет идентифицирующие HTTP-заголовки (`X-Forwarded-For`, `X-Real-IP`, `Via` и др.)
- **Замена User-Agent и Accept-Language** — подставляет нейтральные значения (Chrome 125, en-US)
- **Туннелирование через Tor** — весь трафик проходит через SOCKS5 Tor

### ⚡ Производительность
- **Асинхронный I/O** — построен на `asyncio` для высокой производительности
- **Буферизированная пересылка данных** — настраиваемый размер буфера
- **Graceful shutdown** — дожидается завершения активных соединений перед остановкой

### 🛡️ Надёжность
- **Автоматические повторные попытки** — настраиваемые retry-механизмы для SOCKS5-соединений
- **Таймауты** — раздельные таймауты на подключение и чтение
- **Обработка ошибок Windows** — подавление `WinError 10054` и `WinError 6` на `ProactorEventLoop`
- **Поддержка Python 3.13+** — корректная обработка `GeneratorExit` при завершении задач

### 🌐 Поддержка протоколов
- **HTTP CONNECT** — туннелирование HTTPS-трафика
- **Plain HTTP прокси** — туннелирование GET/POST и других HTTP-методов через Tor
- **SOCKS5** — полная поддержка IPv4, IPv6 и доменных имён
- **SOCKS5 Username/Password аутентификация** — RFC 1929

### ⚙️ Конфигурация
- **Многоуровневая система настроек** — переменные окружения, `.env`-файлы, JSON/YAML-конфиги, аргументы CLI
- **Валидация Pydantic v2** — строгая проверка всех параметров
- **Раздельное включение/отключение** — можно запустить только HTTPS, только SOCKS5 или оба сервера

### 🪟 Кроссплатформенность
- **Windows** — полная поддержка, работа с системными прокси-настройками
- **Linux/macOS** — сигналы `SIGTERM`/`SIGINT` для graceful shutdown
- **Systemd-сервис** — готовый unit-файл для Linux
- **Запланированная задача Windows** — автозапуск при загрузке системы

---

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

---

## Быстрый старт

1. **Убедитесь, что Tor запущен** на `127.0.0.1:9050` (по умолчанию).

2. **Запустите bridge**:

```bash
tor-https-bridge
```

3. **Настройте ваше приложение** на использование прокси:
   - HTTP-прокси: `127.0.0.1:3128`
   - SOCKS5-прокси: `127.0.0.1:1080`

4. **Проверьте**:

```bash
# Через HTTP-прокси
curl -x http://127.0.0.1:3128 https://check.torproject.org/api/ip

# Через SOCKS5-прокси
curl --socks5 127.0.0.1:1080 https://check.torproject.org/api/ip
```

---

## Конфигурация

### Переменные окружения (префикс `TOR_BRIDGE_`)

| Переменная | По умолчанию | Описание |
|---|---|---|
| **Tor SOCKS5 (бэкенд)** | | |
| `TOR_BRIDGE_TOR_SOCKS_HOST` | `127.0.0.1` | Адрес SOCKS5-прокси Tor |
| `TOR_BRIDGE_TOR_SOCKS_PORT` | `9050` | Порт SOCKS5-прокси Tor |
| **HTTPS Proxy (входящий)** | | |
| `TOR_BRIDGE_HTTPS_PROXY_HOST` | `0.0.0.0` | Адрес для прослушивания HTTPS-прокси |
| `TOR_BRIDGE_HTTPS_PROXY_PORT` | `3128` | Порт для прослушивания HTTPS-прокси |
| `TOR_BRIDGE_HTTPS_PROXY_ENABLED` | `true` | Включить HTTPS CONNECT proxy |
| **SOCKS5 Proxy (входящий)** | | |
| `TOR_BRIDGE_SOCKS_PROXY_HOST` | `0.0.0.0` | Адрес для прослушивания SOCKS5-прокси |
| `TOR_BRIDGE_SOCKS_PROXY_PORT` | `1080` | Порт для прослушивания SOCKS5-прокси |
| `TOR_BRIDGE_SOCKS_PROXY_ENABLED` | `true` | Включить SOCKS5 proxy |
| `TOR_BRIDGE_SOCKS_PROXY_USERNAME` | — | Имя пользователя для SOCKS5 auth (RFC 1929) |
| `TOR_BRIDGE_SOCKS_PROXY_PASSWORD` | — | Пароль для SOCKS5 auth (RFC 1929) |
| **Производительность** | | |
| `TOR_BRIDGE_BUFFER_SIZE` | `8192` | Размер буфера (байт) |
| `TOR_BRIDGE_BACKLOG` | `100` | Максимальное количество ожидающих соединений |
| `TOR_BRIDGE_MAX_REQUEST_SIZE` | `65535` | Максимальный размер HTTP-запроса (байт) |
| **Таймауты** | | |
| `TOR_BRIDGE_CONNECT_TIMEOUT` | `60` | Таймаут подключения к Tor (сек) |
| `TOR_BRIDGE_READ_TIMEOUT` | `120` | Таймаут чтения данных (сек) |
| **Повторные попытки** | | |
| `TOR_BRIDGE_SOCKS_RETRY_COUNT` | `2` | Количество повторных попыток SOCKS5 |
| `TOR_BRIDGE_SOCKS_RETRY_DELAY` | `2.0` | Задержка между попытками (сек) |
| **Stealth Mode** | | |
| `TOR_BRIDGE_SANITIZE_HEADERS` | `false` | Включить санитизацию HTTP-заголовков |
| `TOR_BRIDGE_OVERRIDE_USER_AGENT` | Chrome 125 en | Кастомный User-Agent |
| `TOR_BRIDGE_OVERRIDE_ACCEPT_LANGUAGE` | `en-US,en;q=0.9` | Кастомный Accept-Language |
| **Логирование** | | |
| `TOR_BRIDGE_LOG_LEVEL` | `INFO` | Уровень логирования |

### `.env` файл

Скопируйте [`.env.example`](.env.example) в `.env` и отредактируйте:

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
| **HTTPS Proxy** | |
| `--proxy-host` | Адрес для прослушивания HTTPS-прокси |
| `--proxy-port` | Порт для прослушивания HTTPS-прокси |
| `--no-https-proxy` | Отключить HTTPS CONNECT proxy |
| **SOCKS5 Proxy (входящий)** | |
| `--socks-host` | Адрес для прослушивания SOCKS5-прокси |
| `--socks-port` | Порт для прослушивания SOCKS5-прокси |
| `--no-socks-proxy` | Отключить SOCKS5 proxy |
| `--socks-username` | Имя пользователя для SOCKS5 auth |
| `--socks-password` | Пароль для SOCKS5 auth |
| **Tor SOCKS5 (бэкенд)** | |
| `--tor-host` | Адрес SOCKS5-прокси Tor |
| `--tor-port` | Порт SOCKS5-прокси Tor |
| **Производительность** | |
| `--buffer-size` | Размер буфера (байт) |
| `--backlog` | Максимальное количество ожидающих соединений |
| **Таймауты** | |
| `--connect-timeout` | Таймаут подключения (сек) |
| `--read-timeout` | Таймаут чтения (сек) |
| **Общие** | |
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
  "socks_proxy_port": 1080,
  "sanitize_headers": true,
  "log_level": "INFO"
}
```

**config.yaml**:

```yaml
tor_socks_host: 127.0.0.1
tor_socks_port: 9050
https_proxy_port: 3128
socks_proxy_port: 1080
sanitize_headers: true
log_level: INFO
```

**Приоритет** (от высшего к низшему): аргументы CLI → переменные окружения → `.env` файл → файл конфигурации → значения по умолчанию

---

## Примеры использования

### Запуск только SOCKS5-прокси

```bash
tor-https-bridge --no-https-proxy --socks-port 2080
```

### Запуск с аутентификацией SOCKS5

```bash
tor-https-bridge --socks-username myuser --socks-password mypass
```

### Включение Stealth Mode

```bash
tor-https-bridge --sanitize-headers
```

Или через переменную окружения:

```bash
TOR_BRIDGE_SANITIZE_HEADERS=true tor-https-bridge
```

### Программное использование

```python
import asyncio
from tor_https_bridge import TorHTTPSProxy
from tor_https_bridge.config.settings import Settings

async def main():
    settings = Settings(
        https_proxy_port=8080,
        tor_socks_port=9150,
        sanitize_headers=True,
    )
    proxy = TorHTTPSProxy(settings)
    await proxy.start()

asyncio.run(main())
```

### Запуск как Python-модуль

```bash
python -m tor_https_bridge --proxy-port 8080 --socks-port 2080
```

### Настройка прокси в Windows

1. Запустите bridge: `tor-https-bridge`
2. Перейдите в **Параметры → Сеть и Интернет → Прокси**
3. Включите **"Использовать прокси-сервер"**
4. Адрес: `127.0.0.1`, Порт: `3128`
5. Нажмите **Сохранить**

### Использование с браузерами

**Firefox**: Настройки → Сеть → Настройки соединения → Ручная настройка прокси:
- HTTP-прокси: `127.0.0.1`, Порт: `3128`
- SOCKS5: `127.0.0.1`, Порт: `1080`

**Chrome/Edge**: Используют системные настройки прокси Windows.

---

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

---

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

---

## Поиск и устранение неисправностей

### "Connection refused" при запуске

- Убедитесь, что Tor запущен: `systemctl status tor` (Linux) или проверьте, что Tor Browser открыт (Windows)
- Проверьте, не занят ли порт: `netstat -ano | find ":3128"` (Windows) или `ss -tlnp | grep 3128` (Linux)

### "SOCKS5 connection failed"

- Проверьте SOCKS5-порт Tor: `curl --socks5 127.0.0.1:9050 https://check.torproject.org/api/ip`
- Проверьте логи Tor: `journalctl -u tor -f` (Linux)
- Увеличьте таймауты: `--connect-timeout 120 --read-timeout 180`

### Браузер показывает "Proxy connection failed"

- Убедитесь, что bridge запущен
- Проверьте, что настройки прокси указывают на `127.0.0.1:3128`
- Попробуйте: `curl -x http://127.0.0.1:3128 https://httpbin.org/ip`

### Windows: "Unable to connect to the proxy server"

- Запустите bridge от имени администратора, если используется привилегированный порт (< 1024)
- Проверьте, не блокирует ли брандмауэр Windows соединение

### SOCKS5 аутентификация не работает

- Убедитесь, что указаны оба параметра: `--socks-username` и `--socks-password`
- Проверьте, что клиент поддерживает RFC 1929 аутентификацию

---

## Архитектура

```
┌─────────────┐     CONNECT     ┌──────────────────┐     SOCKS5     ┌─────────┐
│   Browser   │ ──────────────> │  Tor HTTPS Bridge │ ────────────> │   Tor   │
│  App/curl   │ <────────────── │  (0.0.0.0:3128)  │ <──────────── │ :9050   │
└─────────────┘   200 OK/Tunnel └──────────────────┘               └─────────┘
                                       │
                              SOCKS5   │   SOCKS5
                                       │
                              ┌────────▼────────┐
                              │   SOCKS5 Client  │
                              │  (0.0.0.0:1080)  │
                              └─────────────────┘
```

Пакет имеет модульную архитектуру:

- **[`config/`](tor_https_bridge/config/)** — Константы и настройки на Pydantic v2 с многоуровневой системой конфигурации
  - [`constants.py`](tor_https_bridge/config/constants.py) — Все константы пакета (порты, таймауты, размеры буферов)
  - [`settings.py`](tor_https_bridge/config/settings.py) — Pydantic-модель `Settings` с валидацией
- **[`core/`](tor_https_bridge/core/)** — Ядро прокси-сервера
  - [`server.py`](tor_https_bridge/core/server.py) — Главный сервер `TorHTTPSProxy` с автоопределением протокола
  - [`handler.py`](tor_https_bridge/core/handler.py) — Обработчик HTTPS CONNECT и plain HTTP запросов
  - [`socks_handler.py`](tor_https_bridge/core/socks_handler.py) — Обработчик входящих SOCKS5 соединений
  - [`forwarder.py`](tor_https_bridge/core/forwarder.py) — Асинхронная двунаправленная пересылка данных
  - [`sanitizer.py`](tor_https_bridge/core/sanitizer.py) — Санитизация HTTP-заголовков (Stealth Mode)
  - [`exceptions.py`](tor_https_bridge/core/exceptions.py) — Иерархия исключений
- **[`protocol/`](tor_https_bridge/protocol/)** — Реализации протоколов
  - [`http_parser.py`](tor_https_bridge/protocol/http_parser.py) — Парсер HTTP CONNECT и plain HTTP запросов
  - [`socks_server.py`](tor_https_bridge/protocol/socks_server.py) — Серверная часть SOCKS5 (RFC 1928) + автоопределение протокола
  - [`socks_adapter.py`](tor_https_bridge/protocol/socks_adapter.py) — Адаптер для подключения к Tor через SOCKS5
- **[`utils/`](tor_https_bridge/utils/)** — Утилиты
  - [`logging.py`](tor_https_bridge/utils/logging.py) — Настройка структурированного логирования
  - [`system.py`](tor_https_bridge/utils/system.py) — Системные утилиты (баннер, сигналы, определение платформы)
- **[`cli/`](tor_https_bridge/cli/)** — Интерфейс командной строки
  - [`main.py`](tor_https_bridge/cli/main.py) — CLI entry point с argparse

---

## Разработка

```bash
# Установка зависимостей для разработки
pip install -e ".[dev]"

# Форматирование кода
ruff format tor_https_bridge/

# Линтинг
ruff check tor_https_bridge/

# Проверка типов
mypy tor_https_bridge/

# Запуск тестов
pytest

# Запуск тестов с покрытием
pytest --cov=tor_https_bridge
```

---

## Лицензия

MIT License — подробнее в файле [LICENSE](LICENSE).