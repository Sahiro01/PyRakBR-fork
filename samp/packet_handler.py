from .parsers import parse_packet as samp_parse_packet
from core import logger


class SampPacketHandler:

    def _emit_connection_rejected_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        try:
            reason_code = int(parsed.get("reason_kick", -1))
        except Exception:
            reason_code = -1

        self.session._emit_callback(
            "onKick",
            reason_code,
        )

    def _emit_show_dialog_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "onShowDialog",
            parsed.get("dialog_id"),
            parsed.get("dialog_style"),
            parsed.get("dialog_title", ""),
            parsed.get("dialog_info", ""),
            parsed.get("dialog_button1", ""),
            parsed.get("dialog_button2", ""),
        )

    def _stop_coord_movement_on_dialog(self, result: dict) -> None:
        self.api._handle_coord_movement_dialog("show_dialog")

    def _emit_show_text_draw_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        info = dict(parsed)
        info.pop("state", None)

        self.session._emit_callback(
            "OnShowTextDraw",
            parsed.get("textdraw_id"),
            info,
        )

    def _emit_text_draw_set_string_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "OnTextDrawSetString",
            parsed.get("textdraw_id"),
            parsed.get("text", ""),
        )

    def _emit_hide_text_draw_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "onHideTextDraw",
            parsed.get("textdraw_id"),
        )

    def _emit_show_chat_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "onShowChat",
            parsed.get("message", ""),
        )


    def _emit_vehicle_stream_in_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "onVehicleStreamIn",
            parsed.get("model_id"),
            parsed.get("vehicle_id"),
            parsed.get("x"),
            parsed.get("y"),
            parsed.get("z"),
        )


    def _emit_player_stream_in_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        for event_name in ("OnPlayerStreamIn", "onPlayerStreamIn"):
            self.session._emit_callback(
                event_name,
                parsed.get("player_id"),
                parsed.get("skin_id"),
                parsed.get("x"),
                parsed.get("y"),
                parsed.get("z"),
            )

    def _emit_player_stream_out_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        for event_name in ("OnPlayerStreamOut", "onPlayerStreamOut"):
            self.session._emit_callback(
                event_name,
                parsed.get("player_id"),
            )

    def _emit_player_death_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "onPlayerDeath",
            parsed.get("player_id"),
        )

    def _emit_apply_player_animation_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "OnPlayerAnimation",
            parsed.get("player_id"),
            parsed.get("anim_lib", ""),
            parsed.get("anim_name", ""),
            parsed.get("delta"),
            parsed.get("loop"),
            parsed.get("lock_x"),
            parsed.get("lock_y"),
            parsed.get("freeze"),
            parsed.get("duration_ms"),
        )

    def _emit_clear_player_animation_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "OnPlayerClearAnimation",
            parsed.get("player_id"),
        )

    def _emit_vehicle_stream_out_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        for event_name in ("OnVehicleStreamOut", "onVehicleStreamOut"):
            self.session._emit_callback(
                event_name,
                parsed.get("vehicle_id"),
            )


    def _emit_set_map_icon_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "onSetMapIcon",
            parsed.get("icon_id"),
            (parsed.get("x"), parsed.get("y"), parsed.get("z")),
            parsed.get("marker_type"),
            parsed.get("style"),
        )

    def _emit_remove_map_icon_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "onRemoveMapIcon",
            parsed.get("icon_id"),
        )

    def _emit_create_3d_text_label_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "onCreate3DTextLabel",
            parsed.get("label_id"),
            parsed.get("text"),
            parsed.get("color"),
            parsed.get("x"),
            parsed.get("y"),
            parsed.get("z"),
            parsed.get("draw_distance"),
            parsed.get("use_los"),
            parsed.get("attached_player_id"),
            parsed.get("attached_vehicle_id"),
        )

    def _emit_delete_3d_text_label_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "onDelete3DTextLabel",
            parsed.get("label_id"),
        )


    def _emit_enter_vehicle_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "onPlayerEnterVehicle",
            parsed.get("player_id"),
            parsed.get("vehicle_id"),
            parsed.get("is_passenger"),
        )

    def _emit_put_player_in_vehicle_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "onPutPlayerInVehicle",
            parsed.get("vehicle_id"),
            parsed.get("seat_id"),
        )

    def _emit_remove_player_from_vehicle_event(self, result: dict) -> None:
        self.session._emit_callback("onRemoveFromVehicle")

    def _emit_give_player_weapon_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "OnGivePlayerWeapon",
            parsed.get("weapon_id"),
            parsed.get("ammo"),
        )

    def _emit_reset_player_weapons_event(self, result: dict) -> None:
        self.session._emit_callback("OnResetPlayerWeapons")

    def _emit_set_weapon_ammo_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "OnSetWeaponAmmo",
            parsed.get("weapon_id"),
            parsed.get("ammo"),
        )

    def _emit_play_audio_stream_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "OnPlayAudioStream",
            parsed.get("url"),
        )

    def _emit_stop_audio_stream_event(self, result: dict) -> None:
        self.session._emit_callback("OnStopAudioStream")

    def _emit_set_player_health_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "OnSetPlayerHealth",
            parsed.get("health"),
        )

    def _emit_set_player_armour_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "OnSetPlayerArmour",
            parsed.get("armour"),
        )

    def _emit_set_interior_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "OnSetInterior",
            parsed.get("interior_id"),
        )

    def _emit_give_money_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "OnSetMoney",
            parsed.get("amount"),
        )

    def _emit_reset_money_event(self, result: dict) -> None:
        self.session._emit_callback(
            "OnSetMoney",
            0,
        )

    def _emit_set_position_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "OnSetPosition",
            parsed.get("x"),
            parsed.get("y"),
            parsed.get("z"),
        )

    def _emit_set_skin_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "OnSetSkin",
            parsed.get("player_id"),
            parsed.get("skin"),
        )

    def _emit_game_text_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "OnGameText",
            parsed.get("style"),
            parsed.get("time"),
            parsed.get("text"),
        )

    def _emit_set_checkpoint_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "OnSetCheckpoint",
            parsed.get("xCP"),
            parsed.get("yCP"),
            parsed.get("zCP"),
            parsed.get("fRadius"),
        )

    def _emit_disable_checkpoint_event(self, result: dict) -> None:
        self.session._emit_callback("OnDisableCheckpoint")

    def _emit_game_mode_restart_event(self, result: dict) -> None:
        logger.info("The Server Is restarting...")
        self.session._emit_callback("OnGameModeRestart")

    def _emit_set_race_checkpoint_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        self.session._emit_callback(
            "OnSetRaceCheckpoint",
            parsed.get("type"),
            (
                parsed.get("xCP"),
                parsed.get("yCP"),
                parsed.get("zCP"),
            ),
            (
                parsed.get("xNextCP"),
                parsed.get("yNextCP"),
                parsed.get("zNextCP"),
            ),
            parsed.get("fRadius"),
        )

    def _emit_disable_race_checkpoint_event(self, result: dict) -> None:
        self.session._emit_callback("OnDisableRaceCheckpoint")

    def _emit_freeze_event(self, result: dict) -> None:
        parsed = result.get("parsed_payload") or {}

        frozen = bool(parsed.get("frozen"))

        self.session.players.bot.frozen = frozen

        self.session._emit_callback(
            "OnFreeze",
            frozen,
        )


    def __init__(self, session):
        self.session = session

        self._rpc_router = {
            "connection_rejected": self._emit_connection_rejected_event,
            "enter_vehicle": self._emit_enter_vehicle_event,
            "put_player_in_vehicle": self._emit_put_player_in_vehicle_event,
            "remove_player_from_vehicle": self._emit_remove_player_from_vehicle_event,
            "give_player_weapon": self._emit_give_player_weapon_event,
            "reset_player_weapons": self._emit_reset_player_weapons_event,
            "set_weapon_ammo": self._emit_set_weapon_ammo_event,
            "play_audio_stream": self._emit_play_audio_stream_event,
            "stop_audio_stream": self._emit_stop_audio_stream_event,
            "set_player_health": self._emit_set_player_health_event,
            "set_player_armour": self._emit_set_player_armour_event,
            "set_interior": self._emit_set_interior_event,
            "give_player_money": self._emit_give_money_event,
            "reset_player_money": self._emit_reset_money_event,
            "set_player_pos": self._emit_set_position_event,
            "set_player_pos_find_z": self._emit_set_position_event,
            "set_player_skin": self._emit_set_skin_event,
            "show_game_text": self._emit_game_text_event,
            "set_checkpoint": self._emit_set_checkpoint_event,
            "disable_checkpoint": self._emit_disable_checkpoint_event,
            "game_mode_restart": self._emit_game_mode_restart_event,
            "set_race_checkpoint": self._emit_set_race_checkpoint_event,
            "disable_race_checkpoint": self._emit_disable_race_checkpoint_event,
            "toggle_player_controllable": self._emit_freeze_event,
            "world_player_add": self._emit_player_stream_in_event,
            "world_player_remove": self._emit_player_stream_out_event,
            "world_player_death": self._emit_player_death_event,
            "apply_player_animation": self._emit_apply_player_animation_event,
            "clear_player_animation": self._emit_clear_player_animation_event,
            "world_vehicle_add": self._emit_vehicle_stream_in_event,
            "world_vehicle_remove": self._emit_vehicle_stream_out_event,
            "set_map_icon": self._emit_set_map_icon_event,
            "remove_map_icon": self._emit_remove_map_icon_event,
            "create_3d_text_label": self._emit_create_3d_text_label_event,
            "delete_3d_text_label": self._emit_delete_3d_text_label_event,
            "show_dialog": self._emit_dialog_handlers,
            "show_text_draw": self._emit_show_text_draw_event,
            "text_draw_set_string": self._emit_text_draw_set_string_event,
            "hide_text_draw": self._emit_hide_text_draw_event,
            "client_message": self._emit_show_chat_event,
            "init_game": self._handle_init_game,
        }

    @property
    def api(self):
        return self.session.api

    def _check_disconnection(self, result: dict) -> bool:
        if result and result.get("type") == "disconnection_notification":
            reason = result.get("reason", "Unknown reason")

            self.session.connected = False
            self.session._emit_callback("disconnect")
            return True

        return False

    def _attach_raknet_metadata(self, result: dict, raknet_packet: dict) -> None:
        result["_msg_num"] = raknet_packet.get("message_number")
        result["_reliability"] = raknet_packet.get("reliability")
        result["_ordering_channel"] = raknet_packet.get("ordering_channel")
        result["_ordering_index"] = raknet_packet.get("ordering_index")

    def _emit_receive_event(self, body: bytes) -> None:
        packet_id = body[0] if body else None
        payload = body[1:] if body else b""

        self.session._emit_callback(
            "onReceivePacket",
            packet_id,
            payload,
            key=packet_id,
        )

    def _emit_receive_rpc_event(self, result: dict) -> None:
        if result.get("type") != "rpc":
            return

        rpc_id = result.get("rpc_id")

        self.session._emit_callback(
            "onReceiveRPC",
            rpc_id,
            result.get("payload", b""),
            key=rpc_id,
        )

    def _update_managers(self, result: dict) -> None:
        self.session.server_info.process_packet(result)
        self.session.stream.process_packet(result)
        self.session.players.process_packet(result, stream_info=self.session.stream)
        self.session.chat.process_packet(result)

    def _handle_init_game(self, result: dict) -> None:
        self.session.mark_init_game_received()
        self.session._emit_callback("onconnect")

        self.session.send_rpc_request_class(0)

    def _handle_open_connection_cookie(self, result: dict) -> None:
        if result.get("type") != "open_connection_cookie":
            return

        cookie = result.get("cookie", 0x6969)
        self.session.send_open_connection_request(cookie=cookie)

    def _handle_internal_ping(self, result: dict) -> None:
        if result.get("type") != "internal_ping":
            return

        sender_ms = result.get("sender_ms", 0)
        receiver_ms = self.session.session_ms()

        if self.session.connected:

            self.session.send_connected_pong(
                receiver_ms,
                sender_ms
            )

    def _emit_dialog_handlers(self, result: dict) -> None:
        self._stop_coord_movement_on_dialog(result)
        self._emit_show_dialog_event(result)

    def _dispatch_rpc_handlers(self, result: dict) -> None:
        parsed = result.get("parsed_payload")

        if not parsed:
            return

        handler = self._rpc_router.get(parsed.get("state"))
        if handler is not None:
            handler(result)

    def _handle_by_type(self, result: dict) -> None:
        ptype = result.get("type")

        if ptype == "interface_sync":
            self.session.registration.handle(result)
            self.session.json_ui.handle(result)
            self.session._emit_callback(
                "onReceiveJSON", result["interface_id"], result["json"],
                key=result["interface_id"],
            )
            return

        if ptype == "rpc":
            self._emit_receive_rpc_event(result)
            self._update_managers(result)
            self._dispatch_rpc_handlers(result)
            return

        if ptype == "internal_ping":
            self._handle_internal_ping(result)
            return

        if ptype == "open_connection_cookie":
            self._handle_open_connection_cookie(result)
            return

        self._update_managers(result)

    def process_packet(self, raknet_packet: dict) -> dict | None:
        if raknet_packet.get("type") == "ack":
            return raknet_packet

        body = raknet_packet.get("data", b"")

        if not body:
            return None

        self._emit_receive_event(body)

        result = samp_parse_packet(body)
        if body[0] == 0x1B and result.get("type") != "interface_sync":
            interface_id = int.from_bytes(body[1:3], "little") if len(body) >= 3 else None
            logger.warn(f"[JSON] Invalid interface packet: interface={interface_id}, bytes={len(body)}")


        if not result:
            return None

        if self._check_disconnection(result):
            return result

        self._attach_raknet_metadata(result, raknet_packet)

        self._handle_by_type(result)

        return result
