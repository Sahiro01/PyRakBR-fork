# PyRakBR

Форк [PyRakSAMP](https://github.com/Sahiro01/PyRakSamp), адаптированный для BLACK RUSSIA.
Python-клиент с RakNet, RPC, JSON-интерфейсами и API для скриптов бота.

## Возможности

- Подключение к серверам BLACK RUSSIA без игрового клиента
- JSON-интерфейсы: уведомления, NPC-диалоги, квесты, кейсы и награды
- Автоматическая регистрация, вход и закрытие катсцен
- Работа с RakNet-пакетами и RPC
- Python API для управления ботом
- Система событий и автоматическая загрузка скриптов `scripts/`
- Движение по координатам (`MoveToCoord`)
- Игроки, транспорт, диалоги, TextDraw, пикапы
- Поддержка SOCKS5-прокси
- Логирование с таймстемпами
- Случайные ники и IP

## Требования

- Python 3.10+
- Только стандартная библиотека Python

## Запуск

Windows — запустить `start.bat`:

```bat
start.bat
```

Linux — запустить `start.sh` (при необходимости сначала сделать исполняемым):

```bash
chmod +x start.sh
./start.sh
```

Либо напрямую из корневой папки (работает на любой ОС):

```bash
python main.py
```

Параметры командной строки:

```bash
python main.py --ip 127.0.0.1 --port 7777 --nick MyBot
python main.py --config config.ini
python main.py --proxy 127.0.0.1:1080
python main.py --random-nick --random-ip
```

## Быстрый старт

Скрипты из папки `scripts/` загружаются автоматически при запуске бота. Создайте `.py` файл и подпишитесь на события:

```python
from logic.events import emitter

@emitter.on("onShowChat")
def on_chat(bot, message):
    print(f"[CHAT] {message}")

@emitter.on("onNpcDialog")
def on_npc_dialog(bot, name, text, model, buttons):
    print(name, text, buttons)
```

## Документация

- [API](docs/API.md)
- [JSON API](docs/JSON_API.md)
- [Changelog](docs/CHANGELOG.md)
- [Configuration](docs/CONFIGURATION.md)
- [Movement](docs/MOVEMENT.md)
- [Protocol](docs/PROTOCOL.md)
- [BitStream](docs/BITSTREAM.md)

## Структура проекта

```
PyRakBR/
├── core/      # Низкоуровневый слой: сеть, протокол, bitstream
├── logic/     # Логика бота: события, менеджеры, движение
├── samp/      # SA:MP-слой: API, сессия, пакеты, парсеры
├── scripts/   # Пользовательские скрипты (авто-загрузка)
├── docs/      # Документация
├── bot.py
├── main.py
├── start.bat  # Запуск на Windows
└── start.sh   # Запуск на Linux
```
