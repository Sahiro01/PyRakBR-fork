# Changelog

## 0.2.1

Fixed:

- Исправлен баг с позицией бота при спавне: менеджеры определяли RPC по содержимому словаря (`x/y/z` без `player_id`), из-за чего пикапы, map icons, 3D labels и транспорт перезаписывали позицию бота. Все менеджеры (`ServerInfo`, `ChatInfo`, `AllPlayersInfo`) переведены на роутинг по `state`.

События:

- Новые: `onPlayerDeath`, `OnPlayerAnimation`, `OnPlayerClearAnimation`, `onRemoveFromVehicle`, `OnGivePlayerWeapon`, `OnResetPlayerWeapons`, `OnSetWeaponAmmo`, `OnPlayAudioStream`, `OnStopAudioStream`, `onBotStopping`, `onServerTimeout`, `onProxyConnect`, `onProxyDisconnect`, `onProxyError`, `onProxyChange`.

API:

- Добавлены `getaudio()`, `getbotweapons()`.

Соединение:

- Параметр `server_password` в `config.ini`

Парсеры/менеджеры:

- Новые RPC: `WORLD_PLAYER_DEATH`, `ApplyPlayerAnimation`, `ClearPlayerAnimations`, `StopAudioStream`, `GivePlayerWeapon`, `ResetPlayerWeapons`, `RemovePlayerFromVehicle`, `SetVehicleZAngle`.
- Оружие бота (`PlayerInfo.weapons`) заполняется из GivePlayerWeapon / ResetPlayerWeapons / SetWeaponAmmo / SetSpawnInfo.
- Бот переходит в `onfoot` при RemovePlayerFromVehicle; ротация транспорта обновляется при SetVehicleZAngle.
- `ChatInfo` хранит текущий аудиопоток, `StopAudioStream` сбрасывает его.
- Диалог печатается в консоль одним блоком.

## 0.2.0-beta

Breaking:

- Событиям больше не передаются `parsed` и `packet` — только полезные данные (`onShowChat(bot, message)`, `onShowDialog(bot, id, style, title, info, btn1, btn2)` и т.д.).
- У `parsers.py` убраны поля `state` и дублирующиеся алиасы (`CarX/y/z` -> `x/y/z`, `xPickup` -> `x` и т.п.) — у каждого RPC один словарь с едиными именами полей.
- `SendKey(keys)` заменён на `SetKey(keys=None, lr=None, ud=None)`.
- `SendPacket(payload)` заменён на `SendPacket(packet_id, payload)`.
- Событие `onConnectionRejected` убрано, `onKick(bot, reason_code)` теперь принимает только код причины.

События:

- Новые: `OnTextDrawSetString`, `onHideTextDraw`, `onPlayerStreamOut`, `onVehicleStreamOut`, `onRemoveMapIcon`, `onDelete3DTextLabel`, `OnSetInterior`, `OnSetMoney`, `OnSetPosition`, `OnSetSkin`, `OnSetCheckpoint`, `OnDisableCheckpoint`, `OnSetRaceCheckpoint`, `OnDisableRaceCheckpoint`, `OnFreeze`, `OnGameModeRestart`.

API:

- Добавлены `SendRPC(rpc_id, payload)` — отправка произвольного RPC, `getplayers()`, `getplayer(id)`, `gettextdraw(id)`, `getalltextdraws()`, `GetDialog()`.
- Убрана функция `wait()`.
- Добавлен лог `[GAMETEXT]` для `ShowGameText`.

Парсеры:

- Добавлена обработка новых RPC: gametext, checkpoint'ы, race checkpoint'ы, `TogglePlayerControllable` (freeze), `RemoveMapIcon`, `GameModeRestart`, stream out.
- Добавлен единый реестр парсеров RPC.

Прочее:

- Движение игроков и транспорта теперь обновляется из onfoot/vehicle sync.
- Переписана документация: PROTOCOL.md (структура датаграмм), API.md, добавлен BITSTREAM.md.

## 0.1.0-beta

- Добавлено подключение к SA:MP 0.3.7 серверам.
- Добавлена работа с RakNet-пакетами, RPC и BitStream.
- Добавлено управление ботом через API: чат, диалоги, игроки, транспорт, pickup и textdraw.
- Добавлена система событий и автоматическая загрузка скриптов из `scripts/`.
- Добавлено движение по координатам через `MoveToCoord`.
- Добавлена поддержка SOCKS5-proxy.
- Добавлена документация по API, конфигурации, движению и протоколу.
