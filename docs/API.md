# API

## Connection

- `is_connected()` - Возвращает `True`, если бот подключен.
- `connect()` - Подключает бота. Возвращает результат подключения.
- `disconnect()` - Отключает бота.
- `reconnect(delay=30.0)` - Переподключает бота через указанную задержку. Запускается в отдельном потоке.
- `SetConnectionProfile(nickname, server=None, server_ip=None, server_port=None, metadata=None)` - Устанавливает ник и адрес сервера. Возвращает `{"nickname": ..., "server": ...}`.
- `getservername()` - Возвращает имя сервера из `server_info`.
- `getserveraddress()` - Возвращает адрес в формате `ip:port`.
- `setserveraddress(ip, port)` - Устанавливает адрес сервера.
- `getbotid()` - Возвращает ID бота.
- `getbotnick()` - Возвращает ник бота.
- `setbotname(nickname)` - Устанавливает ник бота.

## Chat / Dialogs

- `sendchat(message)` - Отправляет сообщение в чат. Строки с `/` отправляются как server command.
- `SendDialogResponse(selected_item, next_items_count=0, r=1)` - Отправляет ответ JSON-меню интерфейса 10.
- `sendClickTextdraw(textdraw_id)` - Нажимает textdraw.
- `SetKey(keys=None, lr=None, ud=None)` - Устанавливает состояние клавиш (`keys` 0..65535) и осей управления `lr`/`ud` (-32768..32767) бота. Любые `None` параметры не изменяют текущее значение. Возвращает `True` при успешной установке.

## Pickups / Death

- `SendPickup(pickup_id)` - Отправляет сообщение о подборе pickup.
- `Autopickup(enabled=1)` - Включает или выключает автоматический подбор pickup. Возвращает новое состояние.
- `SendDeathNotification(reason, killer_id=65535)` - Отправляет уведомление о смерти.

## Score / Ping

- `getbotscore()` - Возвращает score бота.
- `getbotping()` - Возвращает ping бота.
- `getplayerscore(player_id)` - Возвращает score игрока.
- `getplayerping(player_id)` - Возвращает ping игрока.
- `sendscoresandpings()` - Запрашивает обновление score и ping.

## Vehicle

- `setbotvehicle(vehicle_id, seat_id=0, switch_state_after=3.0)` - Посаживает бота в транспорт. `vehicle_id=0` выводит бота из транспорта.
- `getbotvehicle()` - Возвращает состояние текущего транспорта бота.
- `setbotvehiclehealth(health)` - Устанавливает здоровье транспорта.

## Players / Stream

- `getallplayers()` - Возвращает список ников всех известных игроков.
- `getplayers()` - Возвращает `Dict[int, PlayerInfo]` игроков в зоне стрима.
- `getplayer(player_id)` - Возвращает `PlayerInfo` стрим-игрока или `None`.
- `GetDialog()` - Возвращает dict последнего показанного сервером диалога (`dialog_id`, `dialog_style`, `dialog_title`, `dialog_info`, `dialog_button1`, `dialog_button2`, `updated_at`) или `None`.
- `getaudio()` - Возвращает URL аудиопотока, который сервер проигрывает боту (PLAY_AUDIO_STREAM), или `None`, если ничего не проигрывается.
- `gettextdraw(textdraw_id)` - Возвращает dict textdraw (`textdraw_id`, `text`, `x`, `y`, `style`, `selectable`, `model_id`, цвета, `updated_at`) или `None`.
- `getalltextdraws()` - Возвращает `Dict[int, dict]` всех известных textdraw.
- `getallvehicles()` - Возвращает все известные транспортные средства.
- `getvehicle(vehicle_id)` - Возвращает данные транспорта или `None`.
- `getallpickups()` - Возвращает все известные pickup.
- `getpickup(pickup_id)` - Возвращает pickup или `None`.
- `getall3dtextlabels()` - Возвращает все 3D text labels.
- `get3dtextlabel(label_id)` - Возвращает label или `None`.

## Bot state

- `getbothealth()` - Возвращает здоровье бота.
- `setbothealth(health)` - Устанавливает здоровье бота и возвращает новое значение.
- `getbotarmour()` - Возвращает броню бота.
- `setbotarmour(armour)` - Устанавливает броню бота и возвращает новое значение.
- `GetAnimation()` - Возвращает `(animation_id, animation_flags)`.
- `SetAnimation(animation, animation_flags)` - Устанавливает анимацию и её флаги.
- `getbotweapons()` - Возвращает `Dict[int, int]` арсенала бота: `{weapon_id: патроны}`. Заполняется из `GivePlayerWeapon` / `ResetPlayerWeapons` / `SetWeaponAmmo` / `SetSpawnInfo`.
- `getbotmoney()` - Возвращает деньги бота.
- `getbotskin()` - Возвращает skin бота.
- `getbotposition()` - Возвращает `(x, y, z)`.
- `setbotposition(x, y, z)` - Телепортирует бота в указанную позицию и отменяет активное движение.
- `getbotrotation()` - Возвращает угол поворота бота.
- `setbotrotation(rotation)` - Устанавливает угол поворота бота.
- `getbotinterior()` - Возвращает interior бота.
- `getbottargetposition()` - Возвращает текущую цель движения.
- `getbotsyncstate()` - Возвращает текущее состояние синхронизации.

## Movement

- `MoveToCoord(x, y, z, ...)` - Запускает движение к координатам. Возвращает `movement_id`.
- `StopMoveToCoord(movement_id=None, reason="cancelled", reset_velocity=True)` - Останавливает активное движение. Возвращает `True`, если движение было остановлено.

Параметры `MoveToCoord` описаны в [`MOVEMENT.md`](MOVEMENT.md).

## Proxy

- `ProxyConnect(proxy_address, timeout=5.0, reconnect=False)` - Подключает proxy.
- `ProxyDisconnect(reconnect=False)` - Отключает proxy.
- `ProxyChange(proxy_address, timeout=5.0, reconnect=True)` - Меняет proxy.
- `ProxyIsConnected()` - Возвращает состояние proxy-соединения.
- `ProxyIsConfigured()` - Возвращает `True`, если proxy настроен.
- `ProxyInfo()` - Возвращает информацию о proxy.
- `ProxyTCPRequest(target_host, target_port, payload, timeout=5.0, recv_size=4096)` - Выполняет TCP-запрос через proxy и возвращает `bytes`.

## Packets

- `SendPacket(packet_id, payload=b"", reliability=..., ordering_channel=0, priority=...)` - Отправляет произвольный RakNet packet. Байт `packet_id` подставляется автоматически.
- `SendRPC(rpc_id, payload=b"", reliability=..., ordering_channel=0, priority=...)` - Отправляет RPC с указанным id. `payload` - чистые данные RPC (без rpc_id, флагов и bitlen), обёртка `[ID_RPC][rpc_id][bitlen][данные]` строится автоматически. По умолчанию RELIABLE / MEDIUM_PRIORITY.

## Events

События регистрируются через `emitter.on(...)`. Callback получает `bot` первым аргументом. События не возвращают значение.

- `onBotCreated(bot)` - создан объект бота.
- `onBotStopping(bot)` - бот останавливается (вызывается в `close()` перед отключением).
- `onRequestConnect(bot)` - запрошено подключение.
- `onOpenConnectionReplyTimeout(bot, attempts, old_ip, old_port)` - истёк таймаут ответа на OpenConnection.
- `onHandshakeFailed(bot, stage, reason, server_ip, server_port)` - handshake завершился ошибкой.
- `onStateReset(bot, reason, counter)` - сообщает о сбросе состояния
- `onconnect(bot)` - пришел rpc initgame, подключение завершено
- `disconnect(bot)` - соединение разорвано.
- `onSpawn(bot)` - сервер сообщил о спавне бота.
- `onKick(bot, reason_code)` - получен rpc CONNECTION_REJECTED с причиной (1 - incorrect version, 2 - nick already logged in, 3 - bad mod version, 4 - no free slots).
- `onServerTimeout(bot, elapsed, timeout)` - сервер не присылал пакеты дольше `timeout` секунд (`elapsed` - сколько не было пакетов); бот переподключается.
- `onSendPacket(bot, packet_id, body)` - перед отправкой packet.
- `onSendRPC(bot, rpc_id, payload)` - перед отправкой RPC. `payload` - чистые данные RPC (без rpc_id, флагов и bitlen).
- `onReceivePacket(bot, packet_id, payload)` - получен SAMP packet.
- `onReceiveRPC(bot, rpc_id, payload)` - получен RPC. `payload` - чистые данные RPC (без rpc_id и bitlen).
- `onShowDialog(bot, dialog_id, dialog_style, title, info, button1, button2)` - сервер показал диалог.
- `OnShowTextDraw(bot, textdraw_id, info)` - сервер показал textdraw; `info` - dict со всеми полями (`text`, `x`, `y`, `style`, `selectable`, `model_id`, `letter_color`, `box_color`, `background_color`, ...).
- `OnTextDrawSetString(bot, textdraw_id, text)` - сервер обновил текст textdraw (SCR_TEXT_DRAW_SET_STRING).
- `onHideTextDraw(bot, textdraw_id)` - сервер скрыл textdraw (HideTextDraw).
- `onShowChat(bot, message)` - получено сообщение чата.
- `onVehicleStreamIn(bot, model_id, vehicle_id, x, y, z)` - транспорт добавлен в stream.
- `onPlayerStreamIn(bot, player_id, skin_id, x, y, z)` - игрок добавлен в stream.
- `onPlayerStreamOut(bot, player_id)` - игрок покинул stream (WORLD_PLAYER_REMOVE).
- `onVehicleStreamOut(bot, vehicle_id)` - транспорт покинул stream (WORLD_VEHICLE_REMOVE).
- `onPlayerDeath(bot, player_id)` - игрок умер (WORLD_PLAYER_DEATH); убирается из stream, но остаётся в списке игроков сервера.
- `OnPlayerAnimation(bot, player_id, anim_lib, anim_name, delta, loop, lock_x, lock_y, freeze, duration_ms)` - сервер применил анимацию игроку (SCR_APPLY_ANIMATION).
- `OnPlayerClearAnimation(bot, player_id)` - сервер сбросил анимацию игрока (SCR_CLEAR_ANIMATIONS).
- `OnSetInterior(bot, interior_id)` - сервер установил интерьер боту (SCR_SET_INTERIOR).
- `OnSetMoney(bot, money)` - изменены деньги бота: GivePlayerMoney (дельта) или ResetPlayerMoney (0).
- `OnSetPosition(bot, x, y, z)` - сервер установил позицию боту (SCR_SET_PLAYER_POS / SCR_SET_PLAYER_POS_FIND_Z).
- `OnSetSkin(bot, player_id, skin_id)` - сервер установил скин игроку (SCR_SET_PLAYER_SKIN).
- `OnGameText(bot, style, time, text)` - сервер показал gametext (ShowGameText); текст также выводится в консоль `[GAMETEXT] ...`.
- `OnSetCheckpoint(bot, x, y, z, radius)` - установлен обычный checkpoint (SET_CHECKPOINT).
- `OnDisableCheckpoint(bot)` - отключён обычный checkpoint (DISABLE_CHECKPOINT).
- `OnGameModeRestart(bot)` - сервер перезапускается (GAME_MODE_RESTART); в консоль пишется "The Server Is restarting...".
- `OnSetRaceCheckpoint(bot, checkpoint_type, position, next_position, radius)` - установлен race checkpoint (SET_RACE_CHECKPOINT); `position`/`next_position` - кортежи (x, y, z).
- `OnDisableRaceCheckpoint(bot)` - отключён race checkpoint (DISABLE_RACE_CHECKPOINT).
- `OnFreeze(bot, frozen)` - TogglePlayerControllable: `frozen=True` если бот заморожен.
- `onSetMapIcon(bot, icon_id, xyz, marker_type, style)` - сервер установил map icon.
- `onRemoveMapIcon(bot, icon_id)` - сервер удалил map icon (RemoveMapIcon).
- `onCreate3DTextLabel(bot, label_id, text, color, x, y, z, draw_distance, use_los, attached_player_id, attached_vehicle_id)` - создан 3D text label.
- `onDelete3DTextLabel(bot, label_id)` - удалён 3D text label (Delete3DTextLabel).
- `onPutPlayerInVehicle(bot, vehicle_id, seat_id)` - бот помещён в транспорт.
- `onRemoveFromVehicle(bot)` - сервер высадил бота из транспорта (RemovePlayerFromVehicle); `sync_state` бота меняется на `onfoot`.
- `onPlayerEnterVehicle(bot, player_id, vehicle_id, is_passenger)` - игрок вошёл в транспорт.
- `onProxyConnect(bot, info)` - proxy-соединение установлено; `info` - dict состояния proxy.
- `onProxyDisconnect(bot, info)` - proxy отключён (в `info` - состояние до отключения).
- `onProxyError(bot, info, error)` - ошибка proxy (`error` - текст ошибки).
- `onProxyChange(bot, old_info, new_info)` - proxy изменён через `ProxyChange`.
- `OnCoordMoveStart(bot, movement)` - создано движение `MoveToCoord`.
- `OnCoordMovePhaseChange(bot, movement, old_phase, new_phase)` - изменилась фаза движения.
- `OnCoordMoveEnd(bot, movement, status)` - завершилось движение `MoveToCoord`.
- `OnSetPlayerHealth(bot, health)` - сервер установил здоровье боту.
- `OnSetPlayerArmour(bot, armour)` - сервер установил броню боту.
- `OnGivePlayerWeapon(bot, weapon_id, ammo)` - сервер выдал боту оружие (GivePlayerWeapon).
- `OnResetPlayerWeapons(bot)` - сервер забрал всё оружие бота (ResetPlayerWeapons).
- `OnSetWeaponAmmo(bot, weapon_id, ammo)` - сервер изменил количество патронов (SetWeaponAmmo).
- `OnPlayAudioStream(bot, url)` - сервер запустил аудиопоток (PLAY_AUDIO_STREAM).
- `OnStopAudioStream(bot)` - сервер остановил аудиопоток (STOP_AUDIO_STREAM).
