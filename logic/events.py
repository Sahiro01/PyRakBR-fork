
from typing import Callable, Hashable
from concurrent.futures import ThreadPoolExecutor
import threading
from core import logger

class EventEmitter:

    def __init__(self, max_workers: int = 8):
        self._listeners: dict[str, list[Callable]] = {}
        self._keyed_listeners: dict[str, dict[Hashable, list[Callable]]] = {}
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="evt-worker",
        )
        self._shutdown = False
        self._shutdown_lock = threading.Lock()

    def on(self, event: str, key: Hashable = None, sync: bool = False):
        def decorator(func: Callable) -> Callable:
            func._event_sync = sync

            if key is None:
                self._listeners.setdefault(event, []).append(func)
            else:
                self._keyed_listeners.setdefault(event, {}).setdefault(key, []).append(func)

            return func
        return decorator

    def off(self, event: str, func: Callable, key: Hashable = None) -> None:
        if key is None:
            listeners = self._listeners.get(event, [])
            if func in listeners:
                listeners.remove(func)
            return

        listeners = self._keyed_listeners.get(event, {}).get(key, [])
        if func in listeners:
            listeners.remove(func)

    def has_listeners(self, event: str, key: Hashable = None) -> bool:
        if self._listeners.get(event):
            return True

        keyed_map = self._keyed_listeners.get(event)
        if not keyed_map:
            return False

        if key is None:
            return bool(keyed_map)

        return bool(keyed_map.get(key))

    @staticmethod
    def _is_default_handler(func: Callable) -> bool:
        return getattr(func, "__name__", "").startswith("_default_")

    @staticmethod
    def _run_handler(event: str, func: Callable, *args, **kwargs) -> None:
        try:
            func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Events Error in '{event}' handler '{func.__name__}': {e}")

    def _dispatch(self, event: str, func: Callable, args: tuple, kwargs: dict) -> None:
        if self._shutdown:
            return

        if self._is_default_handler(func) or getattr(func, "_event_sync", False):
            self._run_handler(event, func, *args, **kwargs)
            return

        try:
            self._pool.submit(self._run_handler, event, func, *args, **kwargs)
        except RuntimeError as e:
            if self._shutdown or "shutdown" in str(e).lower():
                return

            raise

    def shutdown(self, wait: bool = True) -> None:
        with self._shutdown_lock:
            if self._shutdown:
                return
            self._shutdown = True

        self._pool.shutdown(wait=bool(wait), cancel_futures=True)

    def emit(self, event: str, *args, key: Hashable = None, **kwargs) -> None:
        if self._shutdown:
            return

        generic = self._listeners.get(event)

        specific = None
        if key is not None:
            keyed_map = self._keyed_listeners.get(event)
            if keyed_map:
                specific = keyed_map.get(key)

        if not generic and not specific:
            return

        if generic:
            for func in list(generic):
                self._dispatch(event, func, args, kwargs)

        if specific:
            for func in list(specific):
                self._dispatch(event, func, args, kwargs)


emitter = EventEmitter()


@emitter.on("onReceiveJSON")
def _default_on_receive_json(bot, interface_id, data):
    pass


@emitter.on("onSendJSON")
def _default_on_send_json(bot, interface_id, data):
    pass


@emitter.on("onNotification")
def _default_on_notification(bot, text, button, has_button):
    pass


@emitter.on("onCallNotification")
def _default_on_call_notification(bot, header, text, button, notification_type):
    pass


@emitter.on("onNpcDialog")
def _default_on_npc_dialog(bot, name, text, model, buttons):
    pass


@emitter.on("onDialogNPC")
def _default_on_dialog_npc(bot, duration, text, origin):
    pass


@emitter.on("onQuestTask")
def _default_on_quest_task(bot, text):
    pass


@emitter.on("onRewardList")
def _default_on_reward_list(bot, rewards):
    pass


@emitter.on("DonatMenuOpen")
def _default_donat_menu_open(bot, showcase_id, donate_rubles, double_donate_value, sale_prizes, free_prize_seconds):
    pass


@emitter.on("CaseMenuOpen")
def _default_case_menu_open(bot, cases):
    pass


@emitter.on("CaseRewardOpen")
def _default_case_reward_open(bot, prize_ids):
    pass


@emitter.on("onCinematic")
def _default_on_cinematic(bot, name):
    pass


@emitter.on("onRegistrationState")
def _default_on_registration_state(bot, state):
    pass



@emitter.on("onBotCreated")
def _default_on_bot_created(bot):
    pass

@emitter.on("onRequestConnect")
def _default_on_request_connect(bot):
    pass

@emitter.on("onOpenConnectionReplyTimeout")
def _default_on_open_connection_reply_timeout(
    bot,
    attempts,
    old_ip,
    old_port,
):
    pass


@emitter.on("onHandshakeFailed")
def _default_on_handshake_failed(
    bot,
    stage,
    reason,
    server_ip,
    server_port,
):
    logger.info(
        f"Handshake failed | stage={stage} | reason={reason} | "
        f"server={server_ip}:{server_port}"
    )

@emitter.on("onStateReset")
def _default_on_state_reset(bot, reason="unknown", counter=0):
    logger.info(f"EVENT State reset: reason={reason}, counter={counter}")

@emitter.on("onconnect")
def _default_on_connect(bot):
    pass
    
@emitter.on("disconnect")
def _default_on_disconnect(bot):
    pass

@emitter.on("onSpawn")
def _default_on_spawn(bot):
    pass


@emitter.on("onKick")
def _default_on_kick(bot, reason_code):
    pass

@emitter.on("onSendPacket")
def _default_on_send_packet(bot, packet_id, body):
    pass

@emitter.on("onSendRPC")
def _default_on_send_rpc(bot, rpc_id, payload):
    pass

@emitter.on("onReceivePacket")
def _default_on_receive_packet(bot, packet_id, body):
    pass

@emitter.on("onReceiveRPC")
def _default_on_receive_rpc(bot, rpc_id, payload):
    pass

@emitter.on("onShowDialog")
def _default_on_show_dialog(
    bot,
    dialog_id,
    dialog_style,
    title,
    info,
    button1,
    button2,
):
    pass


@emitter.on("OnShowTextDraw")
def _default_on_show_text_draw(bot, textdraw_id, info):
    pass


@emitter.on("OnTextDrawSetString")
def _default_on_text_draw_set_string(bot, textdraw_id, text):
    pass


@emitter.on("onHideTextDraw")
def _default_on_hide_text_draw(bot, textdraw_id):
    pass


@emitter.on("onShowChat")
def _default_on_show_chat(bot, message):
    pass

@emitter.on("onVehicleStreamIn")
def _default_on_vehicle_stream_in(
    bot,
    model_id,
    vehicle_id,
    x,
    y,
    z,
):
    pass



@emitter.on("onPlayerStreamIn")
def _default_on_player_stream_in(
    bot,
    player_id,
    skin_id,
    x,
    y,
    z,
):
    pass


@emitter.on("onPlayerStreamOut")
def _default_on_player_stream_out(
    bot,
    player_id,
):
    pass


@emitter.on("onVehicleStreamOut")
def _default_on_vehicle_stream_out(
    bot,
    vehicle_id,
):
    pass



@emitter.on("onSetMapIcon")
def _default_on_set_map_icon(
    bot,
    icon_id,
    xyz,
    marker_type,
    style,
):
    pass


@emitter.on("onRemoveMapIcon")
def _default_on_remove_map_icon(bot, icon_id):
    pass


@emitter.on("onCreate3DTextLabel")
def _default_on_create_3d_text_label(
    bot,
    label_id,
    text,
    color,
    x,
    y,
    z,
    draw_distance,
    use_los,
    attached_player_id,
    attached_vehicle_id,
):
    pass


@emitter.on("onDelete3DTextLabel")
def _default_on_delete_3d_text_label(bot, label_id):
    pass


@emitter.on("onPutPlayerInVehicle")
def _default_on_put_player_in_vehicle(
    bot,
    vehicle_id,
    seat_id,
):
    pass


@emitter.on("onRemoveFromVehicle")
def _default_on_remove_from_vehicle(bot):
    pass



@emitter.on("onPlayerEnterVehicle")
def _default_on_player_enter_vehicle(
    bot,
    player_id,
    vehicle_id,
    is_passenger,
):
    pass

@emitter.on("OnCoordMoveStart")
def _default_on_coord_move_start(bot, movement):
    pass


@emitter.on("OnCoordMovePhaseChange")
def _default_on_coord_move_phase_change(
    bot,
    movement,
    old_phase,
    new_phase,
):
    pass


@emitter.on("OnCoordMoveEnd")
def _default_on_coord_move_end(bot, movement, status):
    pass


@emitter.on("OnSetPlayerHealth")
def _default_on_set_player_health(bot, health):
    pass


@emitter.on("OnSetPlayerArmour")
def _default_on_set_player_armour(bot, armour):
    pass


@emitter.on("OnSetInterior")
def _default_on_set_interior(bot, interior_id):
    pass


@emitter.on("OnSetMoney")
def _default_on_set_money(bot, money):
    pass


@emitter.on("OnSetPosition")
def _default_on_set_position(bot, x, y, z):
    pass


@emitter.on("OnSetSkin")
def _default_on_set_skin(bot, player_id, skin_id):
    pass


@emitter.on("OnGivePlayerWeapon")
def _default_on_give_player_weapon(bot, weapon_id, ammo):
    pass


@emitter.on("OnResetPlayerWeapons")
def _default_on_reset_player_weapons(bot):
    pass


@emitter.on("OnSetWeaponAmmo")
def _default_on_set_weapon_ammo(bot, weapon_id, ammo):
    pass


@emitter.on("OnPlayAudioStream")
def _default_on_play_audio_stream(bot, url):
    pass


@emitter.on("OnStopAudioStream")
def _default_on_stop_audio_stream(bot):
    pass


@emitter.on("OnGameText")
def _default_on_game_text(bot, style, time, text):
    pass


@emitter.on("OnSetCheckpoint")
def _default_on_set_checkpoint(bot, x, y, z, radius):
    pass


@emitter.on("OnDisableCheckpoint")
def _default_on_disable_checkpoint(bot):
    pass


@emitter.on("OnGameModeRestart")
def _default_on_game_mode_restart(bot):
    pass


@emitter.on("OnSetRaceCheckpoint")
def _default_on_set_race_checkpoint(
    bot,
    checkpoint_type,
    position,
    next_position,
    radius,
):
    pass


@emitter.on("OnDisableRaceCheckpoint")
def _default_on_disable_race_checkpoint(bot):
    pass


@emitter.on("OnFreeze")
def _default_on_freeze(bot, frozen):
    pass


@emitter.on("onBotStopping")
def _default_on_bot_stopping(bot):
    pass


@emitter.on("onProxyConnect")
def _default_on_proxy_connect(bot, info):
    pass


@emitter.on("onProxyDisconnect")
def _default_on_proxy_disconnect(bot, info):
    pass


@emitter.on("onProxyError")
def _default_on_proxy_error(bot, info, error):
    pass


@emitter.on("onProxyChange")
def _default_on_proxy_change(bot, old_info, new_info):
    pass


@emitter.on("onServerTimeout")
def _default_on_server_timeout(bot, elapsed, timeout):
    pass


@emitter.on("onPlayerDeath")
def _default_on_player_death(bot, player_id):
    pass


@emitter.on("OnPlayerAnimation")
def _default_on_player_animation(
    bot,
    player_id,
    anim_lib,
    anim_name,
    delta,
    loop,
    lock_x,
    lock_y,
    freeze,
    duration_ms,
):
    pass


@emitter.on("OnPlayerClearAnimation")
def _default_on_player_clear_animation(bot, player_id):
    pass
