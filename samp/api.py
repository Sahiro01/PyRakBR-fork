
import math
import time
import threading

from .constants import PacketID, PacketReliability, PacketPriority
from .session import SampSession
from .sender import get_delivery_params
from .packets import PacketBuilder, RPCBuilder
from .parsers import RPC
from core import logger
from .interfaces import InterfaceID, parse_json_payload
from .json_api import JsonAPI

from logic.movement import (
    normalize_movement_direction_control,
    normalize_movement_keys_mode,
    normalize_movement_randomization,
)
from logic.events import emitter


MAX_ENTER_VEHICLE_DISTANCE = 10.0


class BotAPI(JsonAPI):

    def __init__(self, session: SampSession):
        self.session = session
        session.attach_api(self)

        self._reward_cache = []
        self._case_reward_cache = []
        self._autopickup_enabled = False
        self._autopickup_radius = 0.5
        self._autopickup_reset_distance = 5.0
        self._autopickup_blocked_pickups = set()

        self._pending_vehicle_thread = None
        self._pending_vehicle_id = 0

        session.protocol.on_send_packet = self._handle_protocol_send_packet

    def __getattr__(self, name: str):
        lower_name = name.lower()
        for attr_name in dir(self):
            if attr_name.lower() == lower_name and attr_name != name:
                return getattr(self, attr_name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def _handle_protocol_send_packet(self, data: bytes, meta: dict) -> None:
        entries = (meta or {}).get("entries") or []

        for entry in entries:
            payload = entry.get("original_payload")

            if not payload:
                continue

            packet_id = payload[0]
            body = payload[1:]

            emitter.emit(
                "onSendPacket",
                self,
                packet_id,
                body,
                key=packet_id,
            )

            if packet_id == PacketID.USER_INTERFACE_SYNC:
                interface = parse_json_payload(body)
                if interface and interface["interface_id"] == InterfaceID.CINEMATIC and interface["json"].get("t") == 1:
                    self.session.json_ui.on_cinematic_sent()

            if packet_id == PacketID.RPC and body:
                parsed = RPC.read_rpc(body)

                if parsed is None:
                    logger.debug(
                        f"onSendRPC: failed to parse outgoing rpc "
                        f"body_len={len(body)} first_4_bytes={body[:4].hex()}"
                    )
                    continue

                emitter.emit(
                    "onSendRPC",
                    self,
                    parsed["rpc_id"],
                    parsed["payload"],
                    key=parsed["rpc_id"],
                )

    def reset_api_caches(self) -> None:
        self._reward_cache = []
        self._case_reward_cache = []
        self._autopickup_blocked_pickups = set()

    def send_json(self, interface_id: int, data: dict) -> bool:
        return self.session.send_json(interface_id, data)

    def close_interface(self, interface_id: int) -> bool:
        return self.send_json(interface_id, {"c": 1})

    def send_auth_password(self, password: str) -> bool:
        return self.session.send_json(InterfaceID.AUTH, {"t": 6, "s": password, "r": 0}, packet_name="interface_auth_password")

    def register_password(self, password: str, email: str = "") -> bool:
        return self.session.send_json(InterfaceID.AUTH, {"t": 1, "s": email, "p": password}, packet_name="interface_register_password")

    def register_referral(self, referral: str = "") -> bool:
        return self.session.send_json(InterfaceID.AUTH, {"t": 4, "s": referral}, packet_name="interface_register_referral")

    def register_intermediate(self) -> bool:
        return self.session.send_json(InterfaceID.AUTH, {"t": 2, "s": "", "r": 0}, packet_name="interface_register_unknown_after_password")

    def register_gender(self, gender: int = 0) -> bool:
        if gender not in (0, 1):
            raise ValueError("gender must be 0 or 1")
        return self.session.send_json(InterfaceID.AUTH, {"t": 3, "r": gender}, packet_name="interface_register_gender")

    def register_skin(self, skin: int = 78) -> bool:
        if not isinstance(skin, int) or skin < 0:
            raise ValueError("skin must be a nonnegative integer")
        return self.session.send_json(InterfaceID.AUTH, {"t": 5, "r": skin}, packet_name="interface_register_skin")

    def finish_registration(self) -> bool:
        return self.session.send_json(InterfaceID.AUTH, {"c": 1}, packet_name="interface_register_finish")

    def select_spawn(self, spawn_id: int) -> bool:
        return self.session.send_json(InterfaceID.SPAWN_SELECT, {"t": int(spawn_id)}, packet_name="interface_spawn_select")

    def registration_status(self) -> dict:
        return self.session.registration.status()

    def is_connected(self) -> bool:
        return self.session.is_connected()

    def connect(self) -> bool:
        return self.session.connect()

    def disconnect(self) -> None:
        self.session.disconnect()

    def reconnect(self, delay: float = 30.0):
        return self.session.reconnect(
            delay=delay,
            threaded=True,
        )

    def sendchat(self, message: str) -> None:
        if not self.session.connected or not message:
            return

        if message.startswith("/"):
            self.session._sender.send(
                PacketBuilder.rpc_build("server_command", message),
                rpc_name="server_command",
            )
        else:
            self.session._sender.send(
                PacketBuilder.rpc_build("send_chat", message),
                rpc_name="send_chat",
            )


    def SetKey(
        self,
        keys: int | None = None,
        lr: int | None = None,
        ud: int | None = None,
    ) -> bool:
        bot_player = self.session.players.bot
        updated: dict[str, int] = {}

        if keys is not None:
            try:
                value = int(keys) & 0xFFFF
            except Exception:
                logger.error(f"SetKey failed: bad keys={keys!r}")
                return False

            if hasattr(bot_player, "set_keys"):
                bot_player.set_keys(value)
            else:
                bot_player.keys = value

            updated["keys"] = value

        if lr is not None:
            try:
                lr_value = int(round(float(lr)))
            except Exception:
                logger.error(f"SetKey failed: bad lr={lr!r}")
                return False

            lr_value = max(-32768, min(32767, int(lr_value)))
            bot_player.lr = lr_value
            updated["lr"] = lr_value

        if ud is not None:
            try:
                ud_value = int(round(float(ud)))
            except Exception:
                logger.error(f"SetKey failed: bad ud={ud!r}")
                return False

            ud_value = max(-32768, min(32767, int(ud_value)))
            bot_player.ud = ud_value
            updated["ud"] = ud_value

        if not updated:
            logger.info("SetKey -> no changes (all None)")
            return True

        logger.info(
            "SetKey -> " + ", ".join(f"{k}={v}" for k, v in updated.items())
        )
        return True

    def sendClickTextdraw(self, textdraw_id: int) -> None:
        if not self.session.connected:
            return
        
        self.session._sender.send(
            PacketBuilder.rpc_build("select_text_draw", int(textdraw_id)),
            rpc_name="select_text_draw",
        )

    def SendPickup(self, pickup_id: int) -> None:
        if not self.session.connected:
            return
        self.session._sender.send(
            PacketBuilder.rpc_build("picked_up_pickup", int(pickup_id)),
            rpc_name="picked_up_pickup",
        )

    def autopickup_tick(self) -> None:
        if not self.session.connected:
            return

        if not getattr(self, "_autopickup_enabled", False):
            return

        if not self.session.sync.enabled:
            return

        stream = self.session.stream
        players = self.session.players

        if stream is None or players is None:
            return

        try:
            x, y, z = players.bot.get_position()
            x = float(x)
            y = float(y)
            z = float(z)
        except Exception:
            return

        radius = float(getattr(self, "_autopickup_radius", 0.5))
        reset_distance = float(getattr(self, "_autopickup_reset_distance", 5.0))
        blocked = getattr(self, "_autopickup_blocked_pickups", None)

        if blocked is None:
            blocked = set()
            self._autopickup_blocked_pickups = blocked

        pickups = getattr(stream, "pickups", None)
        if not isinstance(pickups, dict):
            return

        active_keys = set()

        for pickup in list(pickups.values()):
            try:
                pickup_id = int(getattr(pickup, "pickup_id", -1))

                if pickup_id < 0:
                    continue

                x_pickup = float(getattr(pickup, "x", 0.0))
                y_pickup = float(getattr(pickup, "y", 0.0))
                z_pickup = float(getattr(pickup, "z", 0.0))

                key = (
                    pickup_id,
                    round(x_pickup, 2),
                    round(y_pickup, 2),
                    round(z_pickup, 2),
                )

                active_keys.add(key)

                dx = x - x_pickup
                dy = y - y_pickup
                dz = z - z_pickup
                distance = (dx * dx + dy * dy + dz * dz) ** 0.5

                if distance >= reset_distance:
                    blocked.discard(key)
                    continue

                if distance > radius:
                    continue

                if key in blocked:
                    continue

                blocked.add(key)
                self.SendPickup(pickup_id)
                logger.info(
                    f"AUTOPICKUP pickup_id={pickup_id} "
                    f"x={x_pickup:.3f} "
                    f"y={y_pickup:.3f} "
                    f"z={z_pickup:.3f}"
                )

            except Exception:
                continue

        blocked.intersection_update(active_keys)

    def SendDeathNotification(
        self,
        reason: int,
        killer_id: int = 65535,
    ) -> None:

        if not self.session.connected:
            return
        self.session._sender.send(
            PacketBuilder.rpc_build(
                "death_notification",
                int(reason) & 0xFF,
                int(killer_id) & 0xFFFF,
            ),
            rpc_name="death_notification",
        )

    def Autopickup(self, enabled: int | bool = 1) -> bool:
        try:
            new_state = bool(int(enabled))
        except Exception:
            new_state = False

        if bool(getattr(self, "_autopickup_enabled", False)) != new_state:
            self._autopickup_blocked_pickups.clear()

        self._autopickup_enabled = new_state
        return self._autopickup_enabled

    def getbotscore(self) -> int:
        self.session.request_scores_and_pings_on_demand()
        return self.session.players.get_bot_score()

    def getbotping(self) -> int:
        self.session.request_scores_and_pings_on_demand()
        return self.session.players.get_bot_ping()

    def getplayerscore(self, player_id: int) -> int:
        self.session.request_scores_and_pings_on_demand()
        return self.session.players.get_player_score(int(player_id))

    def getplayerping(self, player_id: int) -> int:
        self.session.request_scores_and_pings_on_demand()
        return self.session.players.get_player_ping(int(player_id))

    def sendscoresandpings(self) -> None:
        if not self.session.connected:
            return
        self.session._sender.send(
            PacketBuilder.rpc_build("update_scores_and_pings"),
            rpc_name="update_scores_and_pings",
        )

    def setbotvehicle(
        self,
        vehicle_id: int,
        seat_id: int = 0,
        switch_state_after: float = 3.0,
    ) -> bool:

        if not self.session.connected:
            return False

        try:
            vehicle_id = int(vehicle_id)
            seat_id = int(seat_id)
        except Exception:
            logger.error("setbotvehicle failed: bad vehicle_id/seat_id")
            return False

        if vehicle_id <= 0:
            current_vehicle_id = self.session.players.bot.get_current_vehicle_id()
            current_vehicle_id = int(current_vehicle_id)

            if current_vehicle_id <= 0:
                logger.error("setbotvehicle(0) failed: bot is not in vehicle")
                return False

            if self._pending_vehicle_thread is not None:
                self._pending_vehicle_id = 0
                self._pending_vehicle_thread = None

            self.session._sender.send(
                PacketBuilder.rpc_build("exit_vehicle", current_vehicle_id),
                rpc_name="exit_vehicle",
            )

            self.session.players.bot.set_onfoot()

            logger.info(
                "setbotvehicle(0) -> ExitVehicle sent | "
                f"vehicle_id={current_vehicle_id}"
            )
            logger.info(
                "Bot sync_state changed to onfoot | "
                f"position={self.session.players.bot.get_position()}"
            )

            return True

        is_passenger = 1 if seat_id > 0 else 0

        stream_vehicle = self.session.stream.get_vehicle(vehicle_id)

        if stream_vehicle is None:
            logger.error(
                "setbotvehicle failed: "
                f"vehicle_id={vehicle_id} is not in stream"
            )
            return False

        try:
            bot_x, bot_y, bot_z = self.session.players.bot.get_position()
            dx = float(bot_x) - float(stream_vehicle.x)
            dy = float(bot_y) - float(stream_vehicle.y)
            dz = float(bot_z) - float(stream_vehicle.z)
            distance = (dx * dx + dy * dy + dz * dz) ** 0.5
        except Exception as e:
            logger.error(
                "setbotvehicle failed: "
                f"cannot check distance to vehicle_id={vehicle_id} | {e}"
            )
            return False

        if distance > float(MAX_ENTER_VEHICLE_DISTANCE):
            logger.error(
                "setbotvehicle failed: vehicle is too far | "
                f"vehicle_id={vehicle_id}, distance={distance:.2f}m, "
                f"max_distance={float(MAX_ENTER_VEHICLE_DISTANCE):.2f}m"
            )
            return False

        self.session._sender.send(
            PacketBuilder.rpc_build("enter_vehicle", vehicle_id, is_passenger),
            rpc_name="enter_vehicle",
        )

        self.session.players.bot.set_current_vehicle(
            vehicle_id,
            seat_id=seat_id,
        )

        if stream_vehicle is not None:
            self.session.players.bot.vehicle_health = float(stream_vehicle.health)

        logger.info(
            "setbotvehicle -> EnterVehicle sent | "
            f"vehicle_id={vehicle_id}, seat_id={seat_id}, "
            f"is_passenger={is_passenger}"
        )

        def _delayed_set_vehicle_state() -> None:
            try:
                time.sleep(max(0.0, float(switch_state_after)))

                if not self.session.connected:
                    return

                if self._pending_vehicle_id != int(vehicle_id):
                    return

                self._pending_vehicle_thread = None
                self._pending_vehicle_id = 0

                self.session.players.bot.set_vehicle_state(
                    int(vehicle_id),
                    seat_id=int(seat_id),
                    copy_player_position=False,
                )

                if stream_vehicle is not None:
                    self.session.players.bot.vehicle_health = float(stream_vehicle.health)

                sync_state = self.session.players.bot.sync_state
                logger.info(
                    f"Bot sync_state changed to {sync_state} | "
                    f"vehicle_id={int(vehicle_id)}, seat_id={int(seat_id)}"
                )

            except Exception as e:
                logger.info(f"Failed to switch bot to vehicle sync: {e}")

        self._pending_vehicle_thread = threading.Thread(
            target=_delayed_set_vehicle_state,
            daemon=True,
        )
        self._pending_vehicle_id = int(vehicle_id)
        self._pending_vehicle_thread.start()

        return True

    def ProxyConnect(
        self,
        proxy_address: str,
        timeout: float = 5.0,
        reconnect: bool = False,
    ) -> bool:
        result = self.session.proxy.connect(
            proxy_address,
            timeout=timeout,
        )

        if result and reconnect:
            self.reconnect(delay=1.0)

        return result

    def ProxyDisconnect(
        self,
        reconnect: bool = False,
    ) -> bool:
        self.session.proxy.disconnect()

        if reconnect:
            self.reconnect(delay=1.0)
        return True

    def ProxyChange(
        self,
        proxy_address: str,
        timeout: float = 5.0,
        reconnect: bool = True,
    ) -> bool:
        result = self.session.proxy.change(
            proxy_address,
            timeout=timeout,
        )

        if result and reconnect:
            self.reconnect(delay=1.0)

        return result

    def ProxyIsConnected(self) -> bool:
        return self.session.proxy.is_connected()

    def ProxyIsConfigured(self) -> bool:
        return self.session.proxy.is_configured()

    def ProxyInfo(self) -> dict:
        return self.session.proxy.info()

    def ProxyTCPRequest(
        self,
        target_host: str,
        target_port: int,
        payload: bytes,
        timeout: float = 5.0,
        recv_size: int = 4096,
    ) -> bytes:
        return self.session.proxy.tcp_request(
            target_host,
            target_port,
            payload,
            timeout=timeout,
            recv_size=recv_size,
        )

    def SendPacket(
        self,
        packet_id: int,
        payload: bytes = b"",
        reliability: int = PacketReliability.UNRELIABLE,
        ordering_channel: int = 0,
        priority: int = PacketPriority.HIGH_PRIORITY,
    ) -> None:
        if not self.session.connected:
            return

        if payload is None:
            payload = b""

        self.session.protocol.send_with_header(
            PacketBuilder.create(int(packet_id) & 0xFF, bytes(payload)),
            reliability,
            ordering_channel,
            priority,
        )

    def SendRPC(
        self,
        rpc_id: int,
        payload: bytes = b"",
        reliability: int = PacketReliability.RELIABLE,
        ordering_channel: int = 0,
        priority: int = PacketPriority.MEDIUM_PRIORITY,
    ) -> None:
        if not self.session.connected:
            return

        if payload is None:
            payload = b""

        self.session.protocol.send_with_header(
            PacketBuilder.rpc(
                RPCBuilder.create(int(rpc_id) & 0xFF, bytes(payload))
            ),
            reliability,
            ordering_channel,
            priority,
        )

    def getservername(self):
        return self.session.server_info.hostname

    def getserveraddress(self):
        return f"{self.session.server_ip}:{self.session.server_port}"

    def setserveraddress(self, ip: str, port: int):
        return self.session.setserveraddress(ip, port)

    def getbotid(self):
        return self.session.players.bot.player_id

    def getbotnick(self):
        return self.session.nickname

    def setbotname(self, nickname: str):
        self.session.nickname = nickname

    def SetConnectionProfile(
        self,
        *,
        nickname: str,
        server: str | None = None,
        server_ip: str | None = None,
        server_port: int | None = None,
        metadata: dict | None = None,
    ) -> dict:
        nickname = str(nickname or "").strip()
        if not nickname:
            raise ValueError("nickname must not be empty")
        if len(nickname) > 20:
            raise ValueError("Bad NickName Len (MAX 20 CHARS)")

        if server is not None:
            raw_server = str(server or "").strip()
            if raw_server.count(":") == 1:
                parsed_host, parsed_port = raw_server.rsplit(":", 1)
                if parsed_port.isdigit():
                    server_ip = parsed_host.strip()
                    server_port = int(parsed_port)
                else:
                    server_ip = raw_server
            else:
                server_ip = raw_server
        if server_ip is None:
            server_ip = self.session.server_ip
        if server_port is None:
            server_port = self.session.server_port
        server_ip = str(server_ip or "").strip()
        server_port = int(server_port)
        if not server_ip:
            raise ValueError("server_ip must not be empty")
        if not 1 <= server_port <= 65535:
            raise ValueError("server_port must be in range 1..65535")

        self.setserveraddress(server_ip, server_port)
        self.session.nickname = nickname
        return {
            "nickname": self.session.nickname,
            "server": self.getserveraddress(),
        }

    def getallplayers(self):
        return self.session.players.get_all_players()

    def getplayers(self):
        return self.session.players.get_streamed_players()

    def getplayer(self, player_id: int):
        return self.session.players.get_streamed_players().get(int(player_id))

    def getallvehicles(self):
        return self.session.stream.get_all_vehicles()

    def getvehicle(self, vehicle_id: int):
        vehicle = self.session.stream.get_vehicle(int(vehicle_id))

        if vehicle is None:
            return None

        return vehicle.to_dict()

    def getallpickups(self):
        return self.session.stream.get_all_pickups()

    def getpickup(self, pickup_id: int):
        pickup = self.session.stream.get_pickup(int(pickup_id))

        if pickup is None:
            return None

        return pickup.to_dict()

    def getall3dtextlabels(self):
        return self.session.stream.get_all_3d_text_labels()

    def get3dtextlabel(self, label_id: int):
        label = self.session.stream.get_3d_text_label(int(label_id))

        if label is None:
            return None

        return label.to_dict()

    def gettextdraw(self, textdraw_id: int):
        textdraw = self.session.stream.get_textdraw(int(textdraw_id))

        if textdraw is None:
            return None

        return textdraw.to_dict()

    def getalltextdraws(self):
        return self.session.stream.get_all_textdraws()

    def GetDialog(self):
        return self.session.chat.get_last_dialog()

    def getaudio(self):
        return self.session.chat.get_audio()

    def getbotweapons(self):
        return dict(self.session.players.bot.weapons)

    def getbothealth(self):
        return self.session.players.bot.health

    def setbothealth(self, health: float):
        self.session.players.bot.health = float(health)
        return self.session.players.bot.health

    def getbotarmour(self):
        return self.session.players.bot.armour

    def setbotarmour(self, armour: float):
        self.session.players.bot.armour = float(armour)
        return self.session.players.bot.armour

    def GetAnimation(self) -> tuple[int, int]:
        bot_player = self.session.players.bot
        return int(bot_player.animation_id), int(bot_player.animation_flags)

    def SetAnimation(self, animation: int, animation_flags: int) -> None:
        try:
            animation = int(animation)
            animation_flags = int(animation_flags)
        except Exception:
            logger.error(
                f"SetAnimation failed: bad animation={animation!r} "
                f"animation_flags={animation_flags!r}"
            )
            return None

        animation = max(-32768, min(32767, animation))
        animation_flags = max(-32768, min(32767, animation_flags))

        bot_player = self.session.players.bot
        bot_player.animation_id = animation
        bot_player.animation_flags = animation_flags

        logger.info(
            f"SetAnimation -> animation_id={animation}, "
            f"animation_flags={animation_flags}"
        )
        return None

    def getbotmoney(self):
        return int(self.session.players.bot.money)

    def getbotskin(self):
        return self.session.players.bot.skin

    def getbotposition(self):
        return self.session.players.bot.get_position()

    def setbotposition(self, x: float, y: float, z: float):
        bot_player = self.session.players.bot
        target_position = (float(x), float(y), float(z))
        bot_player.cancel_coord_movement(reason="teleported")
        bot_player.update_position(*target_position)
        return bot_player.get_position()

    def _emit_coord_move_end(self, result: dict) -> None:
        emitter.emit("OnCoordMoveEnd", self, dict(result), result.get("status"))

    def _handle_coord_movement_dialog(self, dialog_type: str) -> bool:
        result = self.session.players.bot.coord_movement.handle_dialog(dialog_type)
        if result is None:
            return False
        logger.info(
            f"Move stopped by incoming dialog | "
            f"id={result.get('movement_id')} | type={dialog_type}",
            flush=True,
        )
        self._emit_coord_move_end(result)
        return True

    def MoveToCoord(
        self,
        x: float,
        y: float,
        z: float,
        *,
        mode: str = "auto",
        coord_delay: float | None = None,
        randomization=None,
        accel_time: float | None = None,
        accel_inertia_time: float | None = None,
        accel_inertia_strength: float | None = None,
        brake_time: float | None = None,
        completion_distance: float | None = None,
        movement_direction_control: tuple | None = None,
        movement_keys_mode: str | None = None,
        stop_on_dialog: bool | None = None,
    ) -> int:
        def fail(message: str):
            logger.error(message)
            raise ValueError(message)

        bot_player = self.session.players.bot
        resolved_mode = str(mode or "auto").lower()
        if resolved_mode == "auto":
            resolved_mode = "vehicle" if bot_player.is_in_vehicle() else "walk"
        if resolved_mode in ("onfoot", "foot", "player"):
            resolved_mode = "walk"
        if resolved_mode not in ("walk", "vehicle"):
            fail("mode must be 'auto', 'walk' or 'vehicle'")

        effective_settings = {
            "coord_delay": coord_delay,
            "randomization": randomization,
            "accel_time": accel_time,
            "accel_inertia_time": accel_inertia_time,
            "accel_inertia_strength": accel_inertia_strength,
            "brake_time": brake_time,
            "completion_distance": completion_distance,
            "movement_direction_control": movement_direction_control,
            "movement_keys_mode": movement_keys_mode,
            "stop_on_dialog": stop_on_dialog,
        }
        effective_settings = {
            key: value
            for key, value in effective_settings.items()
            if value is not None
        }

        effective_coord_delay = effective_settings.get("coord_delay")
        if effective_coord_delay is not None:
            try:
                effective_coord_delay = float(effective_coord_delay)
            except (TypeError, ValueError):
                fail(f"coord_delay must be a number, got {effective_coord_delay!r}")
            if not math.isfinite(effective_coord_delay) or effective_coord_delay <= 0.0:
                fail(f"coord_delay must be greater than 0, got {effective_coord_delay!r}")
            effective_settings["coord_delay"] = effective_coord_delay

        randomization_value = effective_settings.get("randomization")
        if randomization_value is not None:
            try:
                normalized_randomization = normalize_movement_randomization(
                    randomization_value
                )
            except ValueError as exc:
                fail(str(exc))
            effective_settings["randomization"] = normalized_randomization

        direction_control_value = effective_settings.get(
            "movement_direction_control"
        )
        if direction_control_value is not None:
            try:
                effective_settings["movement_direction_control"] = (
                    normalize_movement_direction_control(direction_control_value)
                )
            except ValueError as exc:
                fail(str(exc))

        keys_mode_value = effective_settings.get("movement_keys_mode")
        if keys_mode_value is not None:
            try:
                effective_settings["movement_keys_mode"] = (
                    normalize_movement_keys_mode(keys_mode_value)
                )
            except ValueError as exc:
                fail(str(exc))

        if resolved_mode == "vehicle":
            nominal_interval = (
                float(self.session.sync.rate_vehicle_min)
                + float(self.session.sync.rate_vehicle_max)
            ) * 0.5
        else:
            nominal_interval = (
                float(self.session.sync.rate_player_min)
                + float(self.session.sync.rate_player_max)
            ) * 0.5
        nominal_interval = max(0.001, nominal_interval)
        movement, replaced = bot_player.start_coord_movement(
            (float(x), float(y), float(z)),
            mode=resolved_mode,
            nominal_interval=nominal_interval,
            overrides=effective_settings,
        )
        if replaced:
            self._emit_coord_move_end(replaced)
        emitter.emit("OnCoordMoveStart", self, dict(movement))
        return int(movement["movement_id"])

    def StopMoveToCoord(
        self,
        movement_id: int | None = None,
        reason: str = "cancelled",
        reset_velocity: bool = True,
    ) -> bool:
        result = self.session.players.bot.cancel_coord_movement(movement_id, reason)
        if result is None:
            return False
        if reset_velocity:
            self.session.players.bot.reset_velocity()
        self._emit_coord_move_end(result)
        return True

    def getbottargetposition(self):
        return self.session.players.bot.get_target_position()

    def getbotsyncstate(self):
        return self.session.players.bot.sync_state

    def getbotvehicle(self):
        return self.session.players.bot.vehicle_to_dict()

    def setbotvehiclehealth(self, health: float):
        self.session.players.bot.vehicle_health = float(health)

    def getbotrotation(self):
        return self.session.players.bot.rotation

    def setbotrotation(self, rotation: float):
        self.session.players.bot.set_rotation(float(rotation))

    def getbotinterior(self):
        return self.session.players.bot.interior
