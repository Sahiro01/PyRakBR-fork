# JSON API

В скриптах методы вызываются через `bot`, как остальные методы API.

```python
bot.setbotfood(8)
bot.pickup_interact(18)
bot.SendDialogResponse("1.", next_items_count=0)
```

## Методы

| Метод | Назначение |
|---|---|
| `Sendpassword(password=None)` | Вход; без аргумента берёт пароль из конфигурации регистрации |
| `send_npc_dialog_response(button_key)` | Ответ NPC по `bk`, не по позиции кнопки |
| `pickup_interact(pickup_id)` | Взаимодействие с пикапом через RPC 413 |
| `setbotfood(item_id)` | Выбор еды |
| `GetFreeReward()` | Получить бесплатную награду донат-меню |
| `DonatMenuClose()` | Закрыть донат-меню |
| `CaseOpen(case_id, skip_animation=True)` | Открыть кейс |
| `CaseCollectReward(prize_ids=None)` | Забрать призы, по умолчанию из последнего CaseRewardOpen |
| `CaseMenuClose()` | Закрыть кейсы и очистить кэш призов |
| `SendDialogResponse(selected_item, next_items_count=0, r=1)` | Ответ меню 10 |
| `send_call_notification_response(notification_type=2, button=1)` | Ответ боковому уведомлению |
| `send_notification_response(c=13, notification_type=0, notification_s=0, button=0)` | Ответ обычному уведомлению |
| `get_rewards()` | Список последних наград |
| `take_reward(reward=None, *, reward_id=None, name=None)` | Забрать награду по ID или имени из кэша |
| `close_reward()` | Закрыть список наград |
| `send_json(interface_id, data)` | Отправить произвольный JSON-словарь |
| `close_interface(interface_id)` | Отправить `{"c":1}`; для кейсов и донат-меню используйте их методы |
| `stop_cinematic()` | Закрыть катсцену |
| `close_npc_dialog()` | Закрыть реплику NPC, интерфейс 114 |
| `select_spawn(spawn_id)` | Выбрать место появления |

## События

Первый аргумент каждого обработчика — `bot`. Ниже указаны остальные аргументы.

| Событие | Аргументы после api |
|---|---|
| `onNotification` | text, button, has_button |
| `onCallNotification` | header, text, button, notification_type |
| `onNpcDialog` | name, text, model, buttons |
| `onDialogNPC` | duration, text, origin |
| `onQuestTask` | text |
| `onRewardList` | rewards |
| `DonatMenuOpen` | showcase_id, donate_rubles, double_donate_value, sale_prizes, free_prize_seconds |
| `CaseMenuOpen` | cases |
| `CaseRewardOpen` | prize_ids |
| `onCinematic` | name |
| `onRegistrationState` | state |

`onReceiveJSON(bot, interface_id, data)` — входящий JSON.
`onSendJSON(bot, interface_id, data)` — передача JSON на отправку.
Оба поддерживают фильтр `key=interface_id`.

```python
from logic.events import emitter

@emitter.on("onNpcDialog")
def npc_dialog(bot, name, text, model, buttons):
    print(name, text, buttons)
```

## Настройки

```ini
[JSON]
console_output = true
auto_close_cinematic = true

[Registration]
enabled = true
auto_login = true
password = your_password
email =
referral =
gender = 0
skin = 78
step_delay = 0.5
ack_timeout = 15
```

- `console_output` — вывод интерфейсов с временем в консоль.
- `auto_close_cinematic` — автоматическое закрытие катсцен.
- `enabled` — включает автоматический модуль регистрации и входа. При `false` оба отключены.
- `auto_login` — разрешает вход в существующий аккаунт, когда `enabled=true`. При `false` остаётся только регистрация нового аккаунта.
- `password` — пароль аккаунта, обязателен при `enabled=true`.
- `email`, `referral`, `gender`, `skin` — данные регистрации; пол: 0 — мужской, 1 — женский.
- `step_delay` — пауза между шагами, `ack_timeout` — ожидание ответа, в секундах.

Ручная регистрация: `register_password`, `register_intermediate`, `register_referral`,
`register_gender`, `register_skin`, `finish_registration`. Ручной вход:
`send_auth_password(password)`. Для ручного управления установите `enabled=false`.
`registration_status()` возвращает состояние автоматического модуля.
