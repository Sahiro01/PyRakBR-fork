# Configuration

Основные параметры `config.ini`:

```ini
[Connection]
random_ip = false
host = 127.0.0.1
port = 7777
FPS = 50
PINGS_IPS_CONTINUOUS = false
server_password =

[Player]
random_nick = false
nick = Nick_Name
RATE_PLAYER = 0.05-0.06
RATE_VEHICLE = 0.04-0.06
SYNC_IDLE_AFTER = 0.30-0.50
SYNC_IDLE_BACKOFF_FACTOR = 1.35-1.55
PLAYER_IDLE_INTERVAL_MULTIPLIER = 8-12
VEHICLE_IDLE_INTERVAL_MULTIPLIER = 7-11
RATE_PLAYER_JITTER_MAX = 0.005
RATE_PLAYER_FLUCTUATION_CHANCE = 0.10
RATE_PLAYER_FLUCTUATION_MAX = 0.02
```

- `host`, `port` - адрес сервера.
- `FPS` - частота сетевого цикла.
- `random_ip` - использовать случайный IP из `server_ips.txt`.
- `PINGS_IPS_CONTINUOUS` - периодически отправлять обновление scores/pings.
- `server_password` - пароль сервера. Пустое значение - без пароля. При неверном пароле соединение останавливается
- `random_nick` - генерировать случайный ник.
- `nick` - ник бота.
- `RATE_PLAYER` - интервал player sync. Можно указать число или диапазон.
- `RATE_VEHICLE` - интервал vehicle sync. Можно указать число или диапазон.
- `SYNC_IDLE_AFTER` - через какое время без изменений начинается увеличение интервала sync.
- `SYNC_IDLE_BACKOFF_FACTOR` - множитель увеличения интервала при idle.
- `PLAYER_IDLE_INTERVAL_MULTIPLIER` - максимальный множитель idle-интервала для player sync.
- `VEHICLE_IDLE_INTERVAL_MULTIPLIER` - максимальный множитель idle-интервала для vehicle sync.
- `RATE_PLAYER_JITTER_MAX` - обычное случайное отклонение интервала player sync.
- `RATE_PLAYER_FLUCTUATION_CHANCE` - вероятность сильного случайного отклонения.
- `RATE_PLAYER_FLUCTUATION_MAX` - максимальная дополнительная задержка при сильном отклонении.
