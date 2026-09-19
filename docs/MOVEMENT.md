# Movement

`MoveToCoord(x, y, z, ...)` запускает движение к точке.

```python
bot.MoveToCoord(100.0, 200.0, 15.0, mode="vehicle")
```

## Parameters

- `mode` - режим движения: `auto`, `walk`, `vehicle`. Если указать `vehicle`, параметры движения применяются только к vehicle. В режиме `walk` они не используются. `auto` выбирает режим по текущему состоянию бота.
- `coord_delay` - шаг движения между первым и следующим пакетом синхронизации.
- `accel_time` - время разгона.
- `accel_inertia_time` - время действия инерции при разгоне и торможении. Можно передать число, `(accel_time, fade)` или `(accel_time, brake_time, fade)`.
- `accel_inertia_strength` - сила инерции от `0.0` до `1.0`. Чем больше значение, тем сильнее эффект. Можно указать отдельные значения для разгона и торможения: `(accel_strength, brake_strength)`.
- `brake_time` - время торможения.
- `completion_distance` - расстояние до цели, после которого движение считается завершённым.
- `randomization` - случайное изменение параметров в процентах. Можно указать число (`10` = до ±10%) или диапазон `(5, 15)`.
- `movement_direction_control` - управление направлением и поворотом: `(face_movement, update_lr_ud, nonlinearity_percent[, turn_speed_percent])`.
- `movement_keys_mode` - управление кнопками во время движения: `off`, `always`, `always:8`, `throttle`, `throttle:16`.
- `stop_on_dialog` - останавливать движение при появлении диалога.

### Stop

```python
bot.StopMoveToCoord()
```

Возвращаемые состояния движения передаются в событие `OnCoordMoveEnd`. Запуск движения оповещается через `OnCoordMoveStart`. `setbotposition` не вызывает событий движения.
