from typing import Dict, Optional
import math
import time

from .movement import CoordMovementController
from core import logger
class ServerInfo:
    def __init__(self):
        self.hostname: str = ""

        self.d_spawns_available: int = 0

        self.spawn_response: bool | None = None

    _RPC_HANDLERS = {
        "init_game": "_handle_init_game",
        "request_spawn": "_handle_request_spawn",
    }

    def _handle_init_game(self, parsed: dict) -> None:
        self.hostname = parsed.get("hostname", self.hostname)

        if "d_spawns_available" in parsed:
            self.d_spawns_available = parsed["d_spawns_available"]

    def _handle_request_spawn(self, parsed: dict) -> None:
        self.spawn_response = bool(parsed.get("spawn_response"))

    def process_packet(self, packet: dict) -> None:
        if packet.get("type") != "rpc":
            return

        parsed = packet.get("parsed_payload")

        if not parsed:
            return

        handler = self._RPC_HANDLERS.get(parsed.get("state"))
        if handler is not None:
            getattr(self, handler)(parsed)


class ChatInfo:

    def __init__(self):
        self.last_dialog: dict | None = None
        self.audio_url: str | None = None

    def get_last_dialog(self) -> dict | None:
        if self.last_dialog is None:
            return None

        return dict(self.last_dialog)

    def get_audio(self) -> str | None:
        return self.audio_url

    def _handle_client_message(self, parsed: dict) -> None:
        logger.chat(f"{parsed.get('message', '')}")

    def _handle_show_game_text(self, parsed: dict) -> None:
        logger.gametext(
            f"{parsed.get('text', '')} "
            f"(style={parsed.get('style')}, "
            f"time={parsed.get('time')}ms)"
        )

    def _handle_play_audio_stream(self, parsed: dict) -> None:
        self.audio_url = parsed.get("url")
        logger.audio(f"{parsed.get('url', '')}")

    def _handle_stop_audio_stream(self, parsed: dict) -> None:
        self.audio_url = None

    def _handle_connection_rejected(self, parsed: dict) -> None:
        reason_code = parsed.get("reason_kick")

        reasons = {
            1: "Incorrect client version",
            2: "This account is already logged in",
            3: "Bad mod version",
            4: "No free player slots available"
        }

        reason_text = reasons.get(
            reason_code,
            f"Unknown reason ({reason_code})"
        )

        logger.error(f"CONNECTION REJECTED!")
        logger.error(f"Reason: {reason_text}")
        logger.error(f"The server has kicked the bot.\n")

    def _handle_show_dialog(self, parsed: dict) -> None:
        dialog_id = parsed.get("dialog_id")
        style = parsed.get("dialog_style")
        title = parsed.get("dialog_title", "")
        button1 = parsed.get("dialog_button1", "")
        button2 = parsed.get("dialog_button2", "")
        info = parsed.get("dialog_info", "")

        self.last_dialog = {
            "dialog_id": dialog_id,
            "dialog_style": style,
            "dialog_title": title,
            "dialog_info": info,
            "dialog_button1": button1,
            "dialog_button2": button2,
            "updated_at": time.time(),
        }

        lines = [
            "=" * 60,
            f"ID: {dialog_id}",
            f"Style: {style}",
        ]

        if title:
            lines.append(f"Title: {title}")

        lines.append("-" * 60)
        lines.append(info if info else "[empty dialog text]")
        lines.append("-" * 60)
        lines.append(f"Button1: {button1}")
        lines.append(f"Button2: {button2}")
        lines.append("=" * 60)

        logger.dialog("\n" + "\n".join(lines) + "\n")

    _RPC_HANDLERS = {
        "client_message": "_handle_client_message",
        "show_game_text": "_handle_show_game_text",
        "play_audio_stream": "_handle_play_audio_stream",
        "stop_audio_stream": "_handle_stop_audio_stream",
        "connection_rejected": "_handle_connection_rejected",
        "show_dialog": "_handle_show_dialog",
    }

    def process_packet(self, packet: dict) -> None:
        if packet.get("type") != "rpc":
            return

        parsed = packet.get("parsed_payload")

        if not parsed:
            return

        handler = self._RPC_HANDLERS.get(parsed.get("state"))
        if handler is not None:
            getattr(self, handler)(parsed)



class StreamVehicleInfo:

    def __init__(
        self,
        vehicle_id: int,
        model_id: int,
        x: float,
        y: float,
        z: float,
        rotation: float,
        *,
        health: float = 1000.0,
        interior: int = 0,
        color1: int = 0,
        color2: int = 0,
        raw_extra: str = "",
    ):
        self.vehicle_id: int = int(vehicle_id)
        self.model_id: int = int(model_id)

        self.x: float = float(x)
        self.y: float = float(y)
        self.z: float = float(z)
        self.rotation: float = float(rotation)

        self.health: float = float(health)
        self.interior: int = int(interior)

        self.color1: int = int(color1)
        self.color2: int = int(color2)

        self.raw_extra: str = str(raw_extra or "")
        self.updated_at: float = time.time()

    def update_from_packet(self, packet: dict) -> None:
        self.model_id = int(packet.get("model_id", self.model_id))

        self.x = float(packet.get("x", self.x))
        self.y = float(packet.get("y", self.y))
        self.z = float(packet.get("z", self.z))
        self.rotation = float(packet.get("rotation", self.rotation))

        self.health = float(packet.get("health", self.health))
        self.interior = int(packet.get("interior", self.interior))

        self.color1 = int(packet.get("color1", self.color1))
        self.color2 = int(packet.get("color2", self.color2))

        self.raw_extra = str(packet.get("raw_extra", self.raw_extra) or "")
        self.updated_at = time.time()

    def update_position(self, x: float, y: float, z: float) -> None:
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.updated_at = time.time()

    def update_rotation(self, rotation: float) -> None:
        self.rotation = float(rotation)
        self.updated_at = time.time()

    def to_dict(self) -> dict:
        return {
            "vehicle_id": self.vehicle_id,
            "model_id": self.model_id,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "rotation": self.rotation,
            "health": self.health,
            "interior": self.interior,
            "color1": self.color1,
            "color2": self.color2,
            "updated_at": self.updated_at,
            "raw_extra": self.raw_extra,
        }


class Stream3DTextLabelInfo:

    def __init__(
        self,
        label_id: int,
        text: str,
        color: int,
        x: float,
        y: float,
        z: float,
        draw_distance: float,
        *,
        use_los: bool = False,
        attached_player_id: int = 0xFFFF,
        attached_vehicle_id: int = 0xFFFF,
    ):
        self.label_id: int = int(label_id)
        self.text: str = str(text or "")

        self.color: int = int(color) & 0xFFFFFFFF
        self.color_hex: str = f"0x{self.color:08X}"

        self.x: float = float(x)
        self.y: float = float(y)
        self.z: float = float(z)

        self.draw_distance: float = float(draw_distance)
        self.use_los: bool = bool(use_los)

        self.attached_player_id: int = int(attached_player_id)
        self.attached_vehicle_id: int = int(attached_vehicle_id)

        self.updated_at: float = time.time()

    def update_from_packet(self, packet: dict) -> None:
        self.text = str(packet.get("text", self.text) or "")

        self.color = int(packet.get("color", self.color)) & 0xFFFFFFFF
        self.color_hex = f"0x{self.color:08X}"

        self.x = float(packet.get("x", self.x))
        self.y = float(packet.get("y", self.y))
        self.z = float(packet.get("z", self.z))

        self.draw_distance = float(packet.get("draw_distance", self.draw_distance))
        self.use_los = bool(packet.get("use_los", self.use_los))

        self.attached_player_id = int(packet.get("attached_player_id", self.attached_player_id))
        self.attached_vehicle_id = int(packet.get("attached_vehicle_id", self.attached_vehicle_id))
        self.updated_at = time.time()

    def to_dict(self) -> dict:
        return {
            "label_id": self.label_id,
            "text": self.text,
            "color": self.color,
            "color_hex": self.color_hex,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "draw_distance": self.draw_distance,
            "use_los": self.use_los,
            "attached_player_id": self.attached_player_id,
            "attached_vehicle_id": self.attached_vehicle_id,
            "updated_at": self.updated_at,
        }


class StreamPickupInfo:

    def __init__(
        self,
        pickup_id: int,
        model_id: int,
        spawn_type: int,
        x: float,
        y: float,
        z: float,
    ):
        self.pickup_id: int = int(pickup_id)
        self.model_id: int = int(model_id)
        self.spawn_type: int = int(spawn_type)
        self.x: float = float(x)
        self.y: float = float(y)
        self.z: float = float(z)
        self.updated_at: float = time.time()

    def update_from_packet(self, packet: dict) -> None:
        self.model_id = int(packet.get("model_id", self.model_id))
        self.spawn_type = int(packet.get("spawn_type", self.spawn_type))
        self.x = float(packet.get("x", self.x))
        self.y = float(packet.get("y", self.y))
        self.z = float(packet.get("z", self.z))
        self.updated_at = time.time()

    def distance_to(self, x: float, y: float, z: float) -> float:
        dx = float(x) - self.x
        dy = float(y) - self.y
        dz = float(z) - self.z
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def to_dict(self) -> dict:
        return {
            "pickup_id": self.pickup_id,
            "model_id": self.model_id,
            "spawn_type": self.spawn_type,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "updated_at": self.updated_at,
        }


class TextDrawInfo:

    def __init__(self, textdraw_id: int):
        self.textdraw_id: int = int(textdraw_id)
        self.text: str = ""
        self.x: float = 0.0
        self.y: float = 0.0
        self.style: int = 0
        self.selectable: bool = False
        self.model_id: int = 0
        self.letter_color: int = 0
        self.box_color: int = 0
        self.background_color: int = 0
        self.flags: int = 0
        self.letter_width: float = 0.0
        self.letter_height: float = 0.0
        self.zoom: float = 0.0
        self.updated_at: float = time.time()

    def update_from_packet(self, packet: dict) -> None:
        self.text = str(packet.get("text", self.text) or "")
        self.x = float(packet.get("x", self.x))
        self.y = float(packet.get("y", self.y))
        self.style = int(packet.get("style", self.style))
        self.selectable = bool(packet.get("selectable", self.selectable))
        self.model_id = int(packet.get("model_id", self.model_id))
        self.letter_color = int(packet.get("letter_color", self.letter_color))
        self.box_color = int(packet.get("box_color", self.box_color))
        self.background_color = int(packet.get("background_color", self.background_color))
        self.flags = int(packet.get("flags", self.flags))
        self.letter_width = float(packet.get("letter_width", self.letter_width))
        self.letter_height = float(packet.get("letter_height", self.letter_height))
        self.zoom = float(packet.get("zoom", self.zoom))
        self.updated_at = time.time()

    def update_text(self, text: str) -> None:
        self.text = str(text or "")
        self.updated_at = time.time()

    def to_dict(self) -> dict:
        return {
            "textdraw_id": self.textdraw_id,
            "text": self.text,
            "x": self.x,
            "y": self.y,
            "style": self.style,
            "selectable": self.selectable,
            "model_id": self.model_id,
            "letter_color": self.letter_color,
            "box_color": self.box_color,
            "background_color": self.background_color,
            "flags": self.flags,
            "letter_width": self.letter_width,
            "letter_height": self.letter_height,
            "zoom": self.zoom,
            "updated_at": self.updated_at,
        }


class StreamInfo:

    def __init__(self):
        self.vehicles: Dict[int, StreamVehicleInfo] = {}
        self.text_labels_3d: Dict[int, Stream3DTextLabelInfo] = {}
        self.pickups: Dict[int, StreamPickupInfo] = {}
        self.textdraws: Dict[int, TextDrawInfo] = {}

    _STATE_HANDLERS = {
        "world_vehicle_add": "_handle_vehicle_add",
        "world_vehicle_remove": "_handle_vehicle_remove",
        "set_vehicle_pos": "_handle_vehicle_pos",
        "set_vehicle_z_angle": "_handle_vehicle_z_angle",
        "create_pickup": "_handle_pickup_create",
        "destroy_pickup": "_handle_pickup_remove",
        "create_3d_text_label": "_handle_label_create",
        "delete_3d_text_label": "_handle_label_remove",
        "show_text_draw": "_handle_textdraw_add",
        "text_draw_set_string": "_handle_textdraw_text",
        "hide_text_draw": "_handle_textdraw_remove",
    }

    def process_packet(self, packet: dict) -> None:
        if packet.get("type") == "vehicle_sync":
            self._handle_vehicle_sync(packet)
            return

        if packet.get("type") != "rpc":
            return

        parsed = packet.get("parsed_payload")

        if not parsed:
            return

        handler = self._STATE_HANDLERS.get(parsed.get("state"))
        if handler is not None:
            getattr(self, handler)(parsed)

    def _handle_vehicle_sync(self, packet: dict) -> None:
        vehicle_id = int(packet.get("vehicle_id", 0))
        if vehicle_id <= 0:
            return

        vehicle = self.vehicles.get(vehicle_id)
        if vehicle is not None:
            vehicle.x = float(packet.get("x", 0.0))
            vehicle.y = float(packet.get("y", 0.0))
            vehicle.z = float(packet.get("z", 0.0))
            vehicle.health = float(packet.get("vehicle_health", vehicle.health))
            vehicle.updated_at = time.time()

    def _handle_vehicle_add(self, parsed: dict) -> None:
        vehicle_id = int(parsed.get("vehicle_id", 0))
        if vehicle_id <= 0:
            return

        if vehicle_id in self.vehicles:
            self.vehicles[vehicle_id].update_from_packet(parsed)
        else:
            self.vehicles[vehicle_id] = StreamVehicleInfo(
                vehicle_id,
                int(parsed.get("model_id", 0)),
                float(parsed.get("x", 0.0)),
                float(parsed.get("y", 0.0)),
                float(parsed.get("z", 0.0)),
                float(parsed.get("rotation", 0.0)),
                health=float(parsed.get("health", 1000.0)),
                interior=int(parsed.get("interior", 0)),
                color1=int(parsed.get("color1", 0)),
                color2=int(parsed.get("color2", 0)),
                raw_extra=str(parsed.get("raw_extra", "") or ""),
            )

    def _handle_vehicle_remove(self, parsed: dict) -> None:
        vehicle_id = int(parsed.get("vehicle_id", 0))
        if vehicle_id in self.vehicles:
            del self.vehicles[vehicle_id]

    def _handle_vehicle_pos(self, parsed: dict) -> None:
        vehicle_id = int(parsed.get("vehicle_id", 0))
        if vehicle_id <= 0:
            return

        vehicle = self.vehicles.get(vehicle_id)
        if vehicle is not None:
            vehicle.update_position(
                float(parsed.get("x", 0.0)),
                float(parsed.get("y", 0.0)),
                float(parsed.get("z", 0.0)),
            )

    def _handle_vehicle_z_angle(self, parsed: dict) -> None:
        vehicle_id = int(parsed.get("vehicle_id", 0))
        if vehicle_id <= 0:
            return

        vehicle = self.vehicles.get(vehicle_id)
        if vehicle is not None:
            vehicle.update_rotation(
                float(parsed.get("rotation", vehicle.rotation)),
            )

    def _handle_pickup_create(self, parsed: dict) -> None:
        pickup_id = int(parsed.get("pickup_id", 0))
        if pickup_id < 0:
            return

        if pickup_id in self.pickups:
            self.pickups[pickup_id].update_from_packet(parsed)
        else:
            self.pickups[pickup_id] = StreamPickupInfo(
                pickup_id,
                int(parsed.get("model_id", 0)),
                int(parsed.get("spawn_type", 0)),
                float(parsed.get("x", 0.0)),
                float(parsed.get("y", 0.0)),
                float(parsed.get("z", 0.0)),
            )

    def _handle_pickup_remove(self, parsed: dict) -> None:
        pickup_id = int(parsed.get("pickup_id", -1))
        if pickup_id in self.pickups:
            del self.pickups[pickup_id]

    def _handle_label_create(self, parsed: dict) -> None:
        label_id = int(parsed.get("label_id", 0))
        if label_id < 0:
            return

        if label_id in self.text_labels_3d:
            self.text_labels_3d[label_id].update_from_packet(parsed)
        else:
            self.text_labels_3d[label_id] = Stream3DTextLabelInfo(
                label_id,
                str(parsed.get("text", "") or ""),
                int(parsed.get("color", 0)),
                float(parsed.get("x", 0.0)),
                float(parsed.get("y", 0.0)),
                float(parsed.get("z", 0.0)),
                float(parsed.get("draw_distance", 0.0)),
                use_los=bool(parsed.get("use_los", False)),
                attached_player_id=int(parsed.get("attached_player_id", 0xFFFF)),
                attached_vehicle_id=int(parsed.get("attached_vehicle_id", 0xFFFF)),
            )

    def _handle_label_remove(self, parsed: dict) -> None:
        label_id = int(parsed.get("label_id", -1))
        if label_id in self.text_labels_3d:
            del self.text_labels_3d[label_id]

    def _handle_textdraw_add(self, parsed: dict) -> None:
        textdraw_id = int(parsed.get("textdraw_id", -1))
        if textdraw_id < 0:
            return

        textdraw = self.textdraws.get(textdraw_id)
        if textdraw is None:
            textdraw = TextDrawInfo(textdraw_id)
            self.textdraws[textdraw_id] = textdraw

        textdraw.update_from_packet(parsed)

    def _handle_textdraw_text(self, parsed: dict) -> None:
        textdraw_id = int(parsed.get("textdraw_id", -1))
        if textdraw_id < 0:
            return

        textdraw = self.textdraws.get(textdraw_id)
        if textdraw is None:
            textdraw = TextDrawInfo(textdraw_id)
            self.textdraws[textdraw_id] = textdraw

        textdraw.update_text(str(parsed.get("text", "") or ""))

    def _handle_textdraw_remove(self, parsed: dict) -> None:
        textdraw_id = int(parsed.get("textdraw_id", -1))
        if textdraw_id in self.textdraws:
            del self.textdraws[textdraw_id]

    def get_vehicle(self, vehicle_id: int) -> StreamVehicleInfo | None:
        return self.vehicles.get(int(vehicle_id))

    def get_all_vehicles(self) -> Dict[int, dict]:
        return {
            vehicle_id: vehicle.to_dict()
            for vehicle_id, vehicle in self.vehicles.items()
        }

    def get_pickup(self, pickup_id: int) -> StreamPickupInfo | None:
        return self.pickups.get(int(pickup_id))

    def get_all_pickups(self) -> Dict[int, dict]:
        return {
            pickup_id: pickup.to_dict()
            for pickup_id, pickup in self.pickups.items()
        }

    def get_3d_text_label(self, label_id: int) -> Stream3DTextLabelInfo | None:
        return self.text_labels_3d.get(int(label_id))

    def get_all_3d_text_labels(self) -> Dict[int, dict]:
        return {
            label_id: label.to_dict()
            for label_id, label in self.text_labels_3d.items()
        }

    def get_textdraw(self, textdraw_id: int) -> TextDrawInfo | None:
        return self.textdraws.get(int(textdraw_id))

    def get_all_textdraws(self) -> Dict[int, dict]:
        return {
            textdraw_id: textdraw.to_dict()
            for textdraw_id, textdraw in self.textdraws.items()
        }

    def clear(self) -> None:
        self.vehicles.clear()
        self.text_labels_3d.clear()
        self.pickups.clear()
        self.textdraws.clear()



class PlayerInfo:

    def __init__(self, player_id: int, name: str = ""):
        self.player_id: int = player_id
        self.name: str = name

        self.skin: int = 0
        self.team: int = 0
        self.color: int = 0

        self._x: float = 0.0
        self._y: float = 0.0
        self._z: float = 0.0

        self.rotation: float = 0.0

        self.quat_w: float = 1.0
        self.quat_x: float = 0.0
        self.quat_y: float = 0.0
        self.quat_z: float = 0.0

        self.health: float = 0.0
        self.armour: float = 0.0

        self.money: int = 0

        self.score: int = 0
        self.ping: int = 0

        self.lr: int = 0
        self.ud: int = 0
        self.keys: int = 0

        self.additional_key: int = 0
        self.weapon_id: int = 0
        self.special_action: int = 0

        self.extra_1: int = 0
        self.extra_2: int = 0

        self.velocity_x: float = 0.0
        self.velocity_y: float = 0.0
        self.velocity_z: float = 0.0

        self.surfing_x: float = 0.0
        self.surfing_y: float = 0.0
        self.surfing_z: float = 0.0

        self.surfing_vehicle_id: int = 0

        self.animation_id: int = 0
        self.animation_flags: int = 255

        self.anim_lib: str = ""
        self.anim_name: str = ""
        self.anim_delta: float = 4.1
        self.anim_loop: bool = False
        self.anim_lock_x: bool = False
        self.anim_lock_y: bool = False
        self.anim_freeze: bool = False
        self.anim_duration_ms: int = 0
        self.anim_active: bool = False

        self.weapons: Dict[int, int] = {}

        self.rate_player: float = 0.200

        self.interior: int = 0

        self.frozen: bool = False

        self.is_npc: bool = False

        self.sync_state: str = "onfoot"

        self.current_vehicle_id: int = 0
        self.current_vehicle_seat_id: int = 0

        self.vehicle_id: int = 0
        self.seat_id: int = 0
        self.vehicle_health: float = 1000.0
        self.siren_state: int = 0
        self.landing_gear_state: int = 0
        self.trailer_id: int = 0
        self.train_speed: float = 0.0
        self.extra: int = 0

        self.vehicle = self

        self._target_x: float | None = None
        self._target_y: float | None = None
        self._target_z: float | None = None

        self._last_velocity_time: float | None = None

        self.max_sync_velocity: float = 1.0

        self.coord_movement = CoordMovementController(self)


    @property
    def x(self) -> float:
        return self._x

    @x.setter
    def x(self, value: float) -> None:
        self._x = float(value)

    @property
    def y(self) -> float:
        return self._y

    @y.setter
    def y(self, value: float) -> None:
        self._y = float(value)

    @property
    def z(self) -> float:
        return self._z

    @z.setter
    def z(self, value: float) -> None:
        return setattr(self, "_z", float(value))


    @staticmethod
    def rotation_to_quaternion(
        rotation: float
    ) -> tuple[float, float, float, float]:
        yaw = math.radians(rotation)
        half_yaw = yaw * 0.5

        quat_w = math.cos(half_yaw)
        quat_x = 0.0
        quat_y = 0.0
        quat_z = math.sin(half_yaw)

        return quat_w, quat_x, quat_y, quat_z

    def set_rotation(self, rotation: float) -> None:
        self.rotation = rotation

        (
            self.quat_w,
            self.quat_x,
            self.quat_y,
            self.quat_z
        ) = self.rotation_to_quaternion(rotation)

    def get_quaternion(self) -> tuple[float, float, float, float]:
        return (
            self.quat_w,
            self.quat_x,
            self.quat_y,
            self.quat_z
        )

    def apply_animation(
        self,
        anim_lib: str,
        anim_name: str,
        delta: float = 4.1,
        loop: bool = False,
        lock_x: bool = False,
        lock_y: bool = False,
        freeze: bool = False,
        duration_ms: int = 0,
    ) -> None:
        self.anim_lib = str(anim_lib or "")
        self.anim_name = str(anim_name or "")
        self.anim_delta = float(delta)
        self.anim_loop = bool(loop)
        self.anim_lock_x = bool(lock_x)
        self.anim_lock_y = bool(lock_y)
        self.anim_freeze = bool(freeze)
        self.anim_duration_ms = int(duration_ms)
        self.anim_active = True

    def clear_animation(self) -> None:
        self.anim_lib = ""
        self.anim_name = ""
        self.anim_delta = 4.1
        self.anim_loop = False
        self.anim_lock_x = False
        self.anim_lock_y = False
        self.anim_freeze = False
        self.anim_duration_ms = 0
        self.anim_active = False


    @property
    def coord_delay(self) -> float:
        return float(self.coord_movement.config.get("coord_delay", 0.0))

    @coord_delay.setter
    def coord_delay(self, value: float) -> None:
        self.coord_movement.config["coord_delay"] = max(0.0, float(value))

    def set_coord_delay(self, coord_delay: float) -> None:
        self.coord_movement.config["coord_delay"] = max(0.0, float(coord_delay))

    def start_coord_movement(self, target_position, **kwargs):
        return self.coord_movement.start(target_position, **kwargs)

    def cancel_coord_movement(
        self,
        movement_id: int | None = None,
        reason: str = "cancelled",
    ):
        return self.coord_movement.cancel(movement_id, reason)

    def has_position_target(self) -> bool:
        controller = getattr(self, "coord_movement", None)
        if controller is not None and controller.get_active() is not None:
            return True
        return (
            self._target_x is not None
            and self._target_y is not None
            and self._target_z is not None
        )

    def get_target_position(self):
        controller = getattr(self, "coord_movement", None)
        if controller is not None:
            movement = controller.get_active()
            if movement is not None:
                return movement.get("target_position")
        if not self.has_position_target():
            return None

        return (
            self._target_x,
            self._target_y,
            self._target_z,
        )

    def clear_position_target(self) -> None:
        self._target_x = None
        self._target_y = None
        self._target_z = None

    def reset_velocity(self) -> None:
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.velocity_z = 0.0
        self._last_velocity_time = time.time()

    def update_velocity(self, vx: float, vy: float, vz: float) -> None:
        self.velocity_x = float(vx)
        self.velocity_y = float(vy)
        self.velocity_z = float(vz)
        self._last_velocity_time = time.time()

    def update_movement_velocity(
        self,
        direction_x: float,
        direction_y: float,
        direction_z: float,
        *,
        coord_delay: float,
        nominal_interval: float,
    ) -> None:
        direction_x = float(direction_x)
        direction_y = float(direction_y)
        direction_z = float(direction_z)
        length = math.sqrt(
            direction_x * direction_x
            + direction_y * direction_y
            + direction_z * direction_z
        )
        if length <= 1e-12 or float(coord_delay) <= 0.0:
            self.reset_velocity()
            return

        interval = max(0.001, float(nominal_interval))
        sync_speed = max(0.0, float(coord_delay)) * ((1.0 / 50.0) / interval)
        scale = sync_speed / length
        self.update_velocity(
            direction_x * scale,
            direction_y * scale,
            direction_z * scale,
        )
        self._clamp_velocity()

    def _clamp_velocity(self) -> None:
        max_v = float(self.max_sync_velocity)

        if max_v <= 0:
            return

        self.velocity_x = max(-max_v, min(max_v, self.velocity_x))
        self.velocity_y = max(-max_v, min(max_v, self.velocity_y))
        self.velocity_z = max(-max_v, min(max_v, self.velocity_z))

    def _set_position_internal(
        self,
        x: float,
        y: float,
        z: float,
        *,
        update_velocity: bool = True,
        now: float | None = None,
    ) -> None:
        x = float(x)
        y = float(y)
        z = float(z)

        if now is None:
            now = time.time()

        old_x = self._x
        old_y = self._y
        old_z = self._z

        if update_velocity:
            if self._last_velocity_time is None:
                dt = self.rate_player if self.rate_player > 0 else 0.200
            else:
                dt = now - self._last_velocity_time

                if dt <= 0.0:
                    dt = self.rate_player if self.rate_player > 0 else 0.200

            frame_time = 1.0 / 50.0

            self.velocity_x = ((x - old_x) / dt) * frame_time
            self.velocity_y = ((y - old_y) / dt) * frame_time
            self.velocity_z = ((z - old_z) / dt) * frame_time
            self._clamp_velocity()
        else:
            self.velocity_x = 0.0
            self.velocity_y = 0.0
            self.velocity_z = 0.0

        self._x = x
        self._y = y
        self._z = z

        self._last_velocity_time = now

    def update_position(self, x: float, y: float, z: float) -> None:

        self.clear_position_target()
        self._set_position_internal(
            x,
            y,
            z,
            update_velocity=False,
        )

    def advance_movement_step(self) -> dict | None:

        if self.coord_movement.get_active() is not None:
            return self.coord_movement.step()

        if not self.has_position_target():
            return None

        target_position = (
            float(self._target_x),
            float(self._target_y),
            float(self._target_z),
        )

        delay = float(self.coord_delay)

        if delay <= 0.0:
            self._set_position_internal(
                target_position[0],
                target_position[1],
                target_position[2],
                update_velocity=False,
            )
            self.clear_position_target()
            self.reset_velocity()

            return {
                "final_position": self.get_position(),
                "target_position": target_position,
                "reason": "coord_delay_zero",
            }

        dx = target_position[0] - self._x
        dy = target_position[1] - self._y
        dz = target_position[2] - self._z

        dist = math.sqrt((dx * dx) + (dy * dy) + (dz * dz))

        if dist <= 0.000001:
            self.clear_position_target()
            self.reset_velocity()

            return {
                "final_position": self.get_position(),
                "target_position": target_position,
                "reason": "already_at_target",
            }

        now = time.time()

        if dist <= delay:
            new_x = target_position[0]
            new_y = target_position[1]
            new_z = target_position[2]
            reached = True
        else:
            scale = delay / dist
            new_x = self._x + (dx * scale)
            new_y = self._y + (dy * scale)
            new_z = self._z + (dz * scale)
            reached = False

        self._set_position_internal(
            new_x,
            new_y,
            new_z,
            update_velocity=True,
            now=now,
        )

        if not reached:
            return None

        self.clear_position_target()
        self.reset_velocity()

        return {
            "final_position": self.get_position(),
            "target_position": target_position,
            "reason": "reached",
        }

    def get_position(self):
        return (self._x, self._y, self._z)

    def get_velocity(self):
        return (
            self.velocity_x,
            self.velocity_y,
            self.velocity_z,
        )

    def set_keys(self, keys: int) -> None:
        self.keys = int(keys) & 0xFFFF

    def set_control_axes(self, lr: int, ud: int) -> None:
        self.lr = max(-32768, min(32767, int(round(lr))))
        self.ud = max(-32768, min(32767, int(round(ud))))

    def give_weapon(self, weapon_id: int, ammo: int) -> None:
        weapon_id = int(weapon_id) & 0xFF
        ammo = int(ammo)

        if ammo > 0:
            self.weapons[weapon_id] = ammo
        else:
            self.weapons.pop(weapon_id, None)

    def reset_weapons(self) -> None:
        self.weapons.clear()

    def set_weapon_ammo(self, weapon_id: int, ammo: int) -> None:
        weapon_id = int(weapon_id) & 0xFF
        ammo = int(ammo)

        if ammo > 0:
            self.weapons[weapon_id] = ammo
        else:
            self.weapons.pop(weapon_id, None)

    def set_spawn_weapons(
        self,
        weapon1: int,
        ammo1: int,
        weapon2: int,
        ammo2: int,
        weapon3: int,
        ammo3: int,
    ) -> None:
        self.weapons.clear()

        for weapon_id, ammo in (
            (weapon1, ammo1),
            (weapon2, ammo2),
            (weapon3, ammo3),
        ):
            if int(weapon_id) > 0 and int(ammo) > 0:
                self.weapons[int(weapon_id) & 0xFF] = int(ammo)

    def get_weapon_ammo(self, weapon_id: int) -> int:
        return int(self.weapons.get(int(weapon_id) & 0xFF, 0))

    def is_onfoot(self) -> bool:
        return self.sync_state == "onfoot"

    def is_in_vehicle(self) -> bool:
        return self.sync_state in ("vehicle", "passenger")

    def update_passenger_coords_from_vehicle(self, stream_info) -> bool:
        if self.sync_state != "passenger":
            return False

        vehicle_id = self.get_current_vehicle_id()
        if vehicle_id <= 0:
            return False

        if stream_info is None:
            return False

        vehicle = stream_info.get_vehicle(vehicle_id)
        if vehicle is None:
            return False

        self.x = float(vehicle.x)
        self.y = float(vehicle.y)
        self.z = float(vehicle.z)
        return True

    def set_onfoot(self) -> None:
        self.sync_state = "onfoot"
        self.clear_current_vehicle()

    def set_vehicle(
        self,
        vehicle_id: int,
        *,
        seat_id: int = 0,
    ) -> None:
        self.vehicle_id = int(vehicle_id) & 0xFFFF
        self.seat_id = int(seat_id) & 0xFF

    def set_current_vehicle(
        self,
        vehicle_id: int,
        *,
        seat_id: int = 0,
    ) -> None:
        self.current_vehicle_id = int(vehicle_id) & 0xFFFF
        self.current_vehicle_seat_id = int(seat_id) & 0xFF
        self.set_vehicle(
            self.current_vehicle_id,
            seat_id=self.current_vehicle_seat_id,
        )

    def clear_current_vehicle(self) -> None:
        self.current_vehicle_id = 0
        self.current_vehicle_seat_id = 0
        self.set_vehicle(0, seat_id=0)

    def get_current_vehicle_id(self) -> int:
        if self.current_vehicle_id:
            return int(self.current_vehicle_id)

        return int(self.vehicle_id)

    def set_vehicle_state(
        self,
        vehicle_id: int,
        *,
        seat_id: int = 0,
        copy_player_position: bool = False,
    ) -> None:
        self.current_vehicle_seat_id = seat_id
        if seat_id == 0:
            self.sync_state = "vehicle"
        else:
            self.sync_state = "passenger"
        self.set_current_vehicle(vehicle_id, seat_id=seat_id)


    def update_vehicle_position(
        self,
        x: float,
        y: float,
        z: float,
    ) -> None:
        self.update_position(x, y, z)

    def update_vehicle_velocity(
        self,
        vx: float,
        vy: float,
        vz: float,
    ) -> None:
        self.update_velocity(vx, vy, vz)

    @property
    def velocity_x_car(self) -> float:
        return self.velocity_x

    @velocity_x_car.setter
    def velocity_x_car(self, value: float) -> None:
        self.velocity_x = float(value)

    @property
    def velocity_y_car(self) -> float:
        return self.velocity_y

    @velocity_y_car.setter
    def velocity_y_car(self, value: float) -> None:
        self.velocity_y = float(value)

    @property
    def velocity_z_car(self) -> float:
        return self.velocity_z

    @velocity_z_car.setter
    def velocity_z_car(self, value: float) -> None:
        self.velocity_z = float(value)

    def update_quaternion(
        self,
        quat_w: float,
        quat_x: float,
        quat_y: float,
        quat_z: float,
    ) -> None:
        self.quat_w = float(quat_w)
        self.quat_x = float(quat_x)
        self.quat_y = float(quat_y)
        self.quat_z = float(quat_z)

    def vehicle_to_dict(self) -> dict:
        return {
            "vehicle_id": self.vehicle_id,
            "seat_id": self.seat_id,
            "keys": {
                "lr": self.lr,
                "ud": self.ud,
                "keys": self.keys,
            },
            "position": self.get_position(),
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "velocity_car": (
                self.velocity_x,
                self.velocity_y,
                self.velocity_z,
            ),
            "velocity_x_car": self.velocity_x,
            "velocity_y_car": self.velocity_y,
            "velocity_z_car": self.velocity_z,
            "quaternion": (
                self.quat_w,
                self.quat_x,
                self.quat_y,
                self.quat_z,
            ),
            "vehicle_health": self.vehicle_health,
            "health": self.vehicle_health,
            "player_health": int(float(self.health)),
            "player_armour": int(float(self.armour)),
            "weapon_id": self.weapon_id,
            "additional_key": self.additional_key,
            "siren_state": self.siren_state,
            "landing_gear_state": self.landing_gear_state,
            "trailer_id": self.trailer_id,
            "train_speed": self.train_speed,
            "extra": self.extra,
        }

class AllPlayersInfo:

    def __init__(self):
        self._players: Dict[int, PlayerInfo] = {}
        self._streamed_players: Dict[int, PlayerInfo] = {}
        self._scores_pings: Dict[int, dict] = {}

        self.bot = PlayerInfo(-1, "Bot")

        self.log_player_join: bool = False
        self.log_player_quit: bool = False
        self.log_player_stream: bool = False
        self.log_player_skin: bool = False

    def _reset_coord_movement_acceleration(self, rpc_name: str) -> None:
        if self.bot.coord_movement.handle_server_velocity_reset():
            logger.debug(
                f"{rpc_name} reset acceleration | "
                "restart from zero with same accel/inertia"
            )

    def _handle_player_sync(self, packet: dict) -> None:
        try:
            player_id = int(packet.get("player_id", -1))
        except Exception:
            return
        if player_id < 0:
            return
        player = self._streamed_players.get(player_id)
        if player is None:
            player = self._players.get(player_id)
            if player is None:
                return
        try:
            if "x" in packet:
                player._x = float(packet["x"])
            if "y" in packet:
                player._y = float(packet["y"])
            if "z" in packet:
                player._z = float(packet["z"])
            if "quat_w" in packet:
                player.quat_w = float(packet.get("quat_w", player.quat_w))
                player.quat_x = float(packet.get("quat_x", player.quat_x))
                player.quat_y = float(packet.get("quat_y", player.quat_y))
                player.quat_z = float(packet.get("quat_z", player.quat_z))
            if "health" in packet:
                player.health = float(packet["health"])
            if "armour" in packet:
                player.armour = float(packet["armour"])
            if "lr" in packet:
                player.lr = int(packet["lr"])
            if "ud" in packet:
                player.ud = int(packet["ud"])
            if "keys" in packet:
                player.keys = int(packet["keys"])
            if "velocity_x" in packet:
                player.velocity_x = float(packet["velocity_x"])
                player.velocity_y = float(packet["velocity_y"])
                player.velocity_z = float(packet["velocity_z"])
                player._last_velocity_time = time.time()
            if "weapon" in packet:
                player.weapon_id = int(packet["weapon"])
            if "special_action" in packet:
                player.special_action = int(packet["special_action"])
            if "anim_id" in packet:
                player.animation_id = int(packet["anim_id"])
            if packet.get("has_surf"):
                player.surfing_vehicle_id = int(packet.get("surf_vehicle_id", player.surfing_vehicle_id))
                player.surfing_x = float(packet.get("surf_x", player.surfing_x))
                player.surfing_y = float(packet.get("surf_y", player.surfing_y))
                player.surfing_z = float(packet.get("surf_z", player.surfing_z))
            try:
                player.set_onfoot()
            except Exception:
                player.sync_state = "onfoot"
                player.clear_current_vehicle()
            other = self._players.get(player_id)
            if other is not None and other is not player:
                other._x = player._x
                other._y = player._y
                other._z = player._z
                other.quat_w = player.quat_w
                other.quat_x = player.quat_x
                other.quat_y = player.quat_y
                other.quat_z = player.quat_z
                other.health = player.health
                other.armour = player.armour
                try:
                    other.set_onfoot()
                except Exception:
                    other.sync_state = "onfoot"
                    other.clear_current_vehicle()
        except Exception as e:
            logger.debug(f"player_sync update failed for {player_id}: {e}")

    def _handle_vehicle_sync(self, packet: dict) -> None:
        try:
            player_id = int(packet.get("player_id", -1))
        except Exception:
            return
        if player_id < 0:
            return
        player = self._streamed_players.get(player_id)
        if player is None:
            player = self._players.get(player_id)
            if player is None:
                return
        try:
            if "x" in packet:
                player._x = float(packet["x"])
                player._y = float(packet["y"])
                player._z = float(packet["z"])
            if "quat_w" in packet:
                player.quat_w = float(packet.get("quat_w", player.quat_w))
                player.quat_x = float(packet.get("quat_x", player.quat_x))
                player.quat_y = float(packet.get("quat_y", player.quat_y))
                player.quat_z = float(packet.get("quat_z", player.quat_z))
            if "health" in packet:
                player.health = float(packet["health"])
            if "armour" in packet:
                player.armour = float(packet["armour"])
            if "lr" in packet:
                player.lr = int(packet["lr"])
            if "ud" in packet:
                player.ud = int(packet["ud"])
            if "keys" in packet:
                player.keys = int(packet["keys"])
            if "velocity_x" in packet:
                player.velocity_x = float(packet["velocity_x"])
                player.velocity_y = float(packet["velocity_y"])
                player.velocity_z = float(packet["velocity_z"])
                player._last_velocity_time = time.time()
            if "vehicle_id" in packet:
                vid = int(packet["vehicle_id"])
                if vid:
                    try:
                        player.set_vehicle_state(vid, seat_id=0)
                    except Exception:
                        player.current_vehicle_id = vid
                        player.vehicle_id = vid
                        player.sync_state = "vehicle"
            other = self._players.get(player_id)
            if other is not None and other is not player:
                other._x = player._x
                other._y = player._y
                other._z = player._z
                other.quat_w = player.quat_w
                other.quat_x = player.quat_x
                other.quat_y = player.quat_y
                other.quat_z = player.quat_z
                try:
                    other.set_vehicle_state(int(packet.get("vehicle_id", other.current_vehicle_id)), seat_id=0)
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"vehicle_sync update failed for {player_id}: {e}")

    def _handle_passenger_sync(self, packet: dict) -> None:
        try:
            player_id = int(packet.get("player_id", -1))
        except Exception:
            return
        if player_id < 0:
            return
        player = self._streamed_players.get(player_id)
        if player is None:
            player = self._players.get(player_id)
            if player is None:
                return
        try:
            if "x" in packet:
                player._x = float(packet["x"])
                player._y = float(packet["y"])
                player._z = float(packet["z"])
            if "health" in packet:
                player.health = float(packet["health"])
            if "armour" in packet:
                player.armour = float(packet["armour"])
            vid = int(packet.get("vehicle_id", 0) or 0)
            seat = int(packet.get("seat_id", 1) or 1)
            if vid:
                try:
                    player.set_vehicle_state(vid, seat_id=seat)
                except Exception:
                    player.current_vehicle_id = vid
                    player.vehicle_id = vid
                    player.sync_state = "passenger"
            other = self._players.get(player_id)
            if other is not None and other is not player:
                other._x = player._x
                other._y = player._y
                other._z = player._z
                if vid:
                    try:
                        other.set_vehicle_state(vid, seat_id=seat)
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"passenger_sync update failed for {player_id}: {e}")

    def process_packet(self, packet: dict, stream_info=None) -> None:
        ptype = packet.get("type")
        if ptype == "player_sync":
            self._handle_player_sync(packet)
            return
        if ptype == "vehicle_sync":
            self._handle_vehicle_sync(packet)
            return
        if ptype == "passenger_sync":
            self._handle_passenger_sync(packet)
            return
        if ptype != "rpc":
            return

        parsed = packet.get("parsed_payload")

        if not parsed:
            return

        if parsed.get("state") == "put_player_in_vehicle":
            try:
                vehicle_id = int(parsed.get("vehicle_id", 0))
            except Exception:
                vehicle_id = 0

            try:
                seat_id = int(parsed.get("seat_id", 0))
            except Exception:
                seat_id = 0

            if vehicle_id <= 0:
                return

            self.bot.set_vehicle_state(
                vehicle_id,
                seat_id=seat_id,
                copy_player_position=False,
            )

            logger.info(
                "PutPlayerInVehicle -> sync_state changed to vehicle | "
                f"vehicle_id={vehicle_id}, seat_id={seat_id}, "
                f"xyz={self.bot.get_position()}"
            )

            if stream_info is not None and hasattr(stream_info, "get_vehicle"):
                try:
                    stream_vehicle = stream_info.get_vehicle(vehicle_id)
                    if stream_vehicle is not None:
                        self.bot.vehicle_health = float(
                            getattr(stream_vehicle, "health", self.bot.vehicle_health)
                        )
                except Exception:
                    pass

            return


        if parsed.get("state") == "remove_player_from_vehicle":
            if self.bot.is_in_vehicle():
                old_vehicle_id = int(self.bot.get_current_vehicle_id())
                old_seat_id = int(getattr(self.bot, "current_vehicle_seat_id", 0))

                self.bot.set_onfoot()
                self.bot.reset_velocity()

                logger.info(
                    "RemovePlayerFromVehicle -> sync_state changed to onfoot | "
                    f"old_vehicle_id={old_vehicle_id}, old_seat_id={old_seat_id}"
                )

            return


        if parsed.get("state") == "world_vehicle_remove":
            try:
                vehicle_id = int(parsed.get("vehicle_id", 0))
            except Exception:
                vehicle_id = 0

            if vehicle_id <= 0:
                return

            current_vehicle_id = int(self.bot.get_current_vehicle_id())

            if self.bot.is_in_vehicle() and current_vehicle_id == vehicle_id:
                old_seat_id = int(getattr(self.bot, "current_vehicle_seat_id", 0))
                self.bot.set_onfoot()
                self.bot.reset_velocity()

                logger.info(
                    "WorldVehicleRemove -> bot vehicle unloaded; "
                    "sync_state changed to onfoot | "
                    f"vehicle_id={vehicle_id}, old_seat_id={old_seat_id}"
                )

            return


        if parsed.get("state") == "set_vehicle_pos":
            try:
                vehicle_id = int(parsed.get("vehicle_id", 0))
            except Exception:
                vehicle_id = 0

            if vehicle_id <= 0:
                return

            x = float(parsed.get("x", 0.0))
            y = float(parsed.get("y", 0.0))
            z = float(parsed.get("z", 0.0))

            current_vehicle_id = int(self.bot.get_current_vehicle_id())

            if self.bot.is_in_vehicle() and current_vehicle_id == vehicle_id:
                self.bot.update_vehicle_position(x, y, z)
                self._reset_coord_movement_acceleration("SCR_SET_VEHICLE_POS")

                logger.info(
                    "SCR_SET_VEHICLE_POS -> bot/vehicle XYZ updated | "
                    f"vehicle_id={vehicle_id}, xyz=({x:.3f}, {y:.3f}, {z:.3f})"
                )

            return


        if parsed.get("state") == "set_player_velocity":
            velocity_x = parsed.get("velocity_x", 0.0)
            velocity_y = parsed.get("velocity_y", 0.0)
            velocity_z = parsed.get("velocity_z", 0.0)
            self.bot.update_velocity(velocity_x, velocity_y, velocity_z)
            self._reset_coord_movement_acceleration("SCR_SET_PLAYER_VELOCITY")
            return

        if parsed.get("state") == "set_vehicle_velocity":
            velocity_x = parsed.get("velocity_x_car", 0.0)
            velocity_y = parsed.get("velocity_y_car", 0.0)
            velocity_z = parsed.get("velocity_z_car", 0.0)
            self.bot.update_vehicle_velocity(velocity_x, velocity_y, velocity_z)
            self._reset_coord_movement_acceleration("SCR_SET_VEHICLE_VELOCITY")
            return

        if parsed.get("state") == "update_scores_and_pings":
            self.update_scores_and_pings(
                parsed.get("scores_and_pings") or []
            )
            return

        if parsed.get("state") == "give_player_weapon":
            weapon_id = int(parsed.get("weapon_id", 0))
            ammo = int(parsed.get("ammo", 0))

            self.bot.give_weapon(weapon_id, ammo)
            return

        if parsed.get("state") == "reset_player_weapons":
            self.bot.reset_weapons()
            return

        if parsed.get("state") == "set_weapon_ammo":
            weapon_id = int(parsed.get("weapon_id", 0))
            ammo = int(parsed.get("ammo", 0))

            self.bot.set_weapon_ammo(weapon_id, ammo)
            return

        if parsed.get("state") == "set_spawn_info":
            self.bot.team = int(parsed.get("team", 0))
            self.bot.skin = int(parsed.get("skin", 0))

            self.bot.set_spawn_weapons(
                int(parsed.get("weapon1", 0)),
                int(parsed.get("ammo1", 0)),
                int(parsed.get("weapon2", 0)),
                int(parsed.get("ammo2", 0)),
                int(parsed.get("weapon3", 0)),
                int(parsed.get("ammo3", 0)),
            )
            return

        if parsed.get("state") == "init_game":
            self.bot.player_id = parsed.get("player_id")

        elif parsed.get("state") == "server_join":
            player_id = parsed.get("player_id")
            name = parsed.get("name")
            is_npc = parsed.get("is_npc", False)

            if player_id not in self._players:
                self._players[player_id] = PlayerInfo(
                    player_id,
                    name
                )

                self._players[player_id].is_npc = is_npc

                if self.log_player_join:
                    logger.info(
                        f"Player joined: "
                        f"{name} (ID: {player_id})"
                    )

        elif parsed.get("state") == "server_quit":
            player_id = parsed["player_id"]

            if player_id in self._players:
                name = self._players[player_id].name

                del self._players[player_id]

                if player_id in self._streamed_players:
                    del self._streamed_players[player_id]

                if self.log_player_quit:
                    logger.info(
                        f"Player quit: "
                        f"{name} (ID: {player_id})"
                    )

        elif parsed.get("state") == "world_player_add":
            try:
                player_id = int(parsed.get("player_id", -1))
            except Exception:
                return

            if player_id < 0:
                return

            skin = int(parsed.get("skin_id", 0))

            x = float(parsed.get("x", 0.0))
            y = float(parsed.get("y", 0.0))
            z = float(parsed.get("z", 0.0))

            angle = float(parsed.get("facing_angle", 0.0))
            color = int(parsed.get("player_color", 0))
            team = int(parsed.get("team", 0))

            if player_id in self._players:
                player = self._players[player_id]
            else:
                player = PlayerInfo(
                    player_id,
                    f"Unknown_{player_id}"
                )

                self._players[player_id] = player

            player.skin = skin
            player.team = team
            player.color = color

            if "health" in parsed:
                player.health = float(parsed.get("health", player.health))

            if "armour" in parsed:
                player.armour = float(parsed.get("armour", player.armour))

            player.update_position(x, y, z)
            player.set_rotation(angle)

            self._streamed_players[player_id] = player

            if self.log_player_stream:
                logger.info(
                    f"Player streamed in: "
                    f"{player.name} (ID: {player_id})"
                )

        elif parsed.get("state") == "world_player_remove":
            try:
                player_id = int(parsed.get("player_id", -1))
            except Exception:
                return

            if player_id in self._streamed_players:
                name = self._streamed_players[player_id].name

                del self._streamed_players[player_id]

                if self.log_player_stream:
                    logger.info(
                        f"Player streamed out: "
                        f"{name} (ID: {player_id})"
                    )

        elif parsed.get("state") == "world_player_death":
            try:
                player_id = int(parsed.get("player_id", -1))
            except Exception:
                return

            if player_id in self._streamed_players:
                name = self._streamed_players[player_id].name

                del self._streamed_players[player_id]

                if self.log_player_stream:
                    logger.info(
                        f"Player death: streamed out: "
                        f"{name} (ID: {player_id})"
                    )

        elif parsed.get("state") == "apply_player_animation":
            try:
                player_id = int(parsed.get("player_id", -1))
            except Exception:
                return

            if player_id == self.bot.player_id:
                self.bot.animation_id = 0
                self.bot.animation_flags = 0
                self.bot.apply_animation(
                    parsed.get("anim_lib", ""),
                    parsed.get("anim_name", ""),
                    parsed.get("delta", 4.1),
                    parsed.get("loop", False),
                    parsed.get("lock_x", False),
                    parsed.get("lock_y", False),
                    parsed.get("freeze", False),
                    parsed.get("duration_ms", 0),
                )
            elif player_id in self._streamed_players:
                self._streamed_players[player_id].apply_animation(
                    parsed.get("anim_lib", ""),
                    parsed.get("anim_name", ""),
                    parsed.get("delta", 4.1),
                    parsed.get("loop", False),
                    parsed.get("lock_x", False),
                    parsed.get("lock_y", False),
                    parsed.get("freeze", False),
                    parsed.get("duration_ms", 0),
                )

        elif parsed.get("state") == "clear_player_animation":
            try:
                player_id = int(parsed.get("player_id", -1))
            except Exception:
                return

            if player_id == self.bot.player_id:
                self.bot.clear_animation()
            elif player_id in self._streamed_players:
                self._streamed_players[player_id].clear_animation()

        elif parsed.get("state") == "set_player_skin":
            player_id = parsed.get("player_id")
            skin = parsed.get("skin")

            if player_id == self.bot.player_id:
                self.bot.skin = skin

            if player_id in self._players:
                self._players[player_id].skin = skin

                if self.log_player_skin:
                    logger.info(
                        f"Player "
                        f"{player_id} skin changed to {skin}"
                    )

        elif parsed.get("state") in ("set_player_pos", "set_player_pos_find_z"):
            was_in_vehicle = self.bot.is_in_vehicle()
            current_vehicle_id = int(self.bot.get_current_vehicle_id())

            self.bot.update_position(
                parsed.get("x"),
                parsed.get("y"),
                parsed.get("z")
            )
            self._reset_coord_movement_acceleration("SCR_SET_PLAYER_POS")

            if was_in_vehicle:
                logger.info(
                    "SetPlayerPos -> XYZ updated; "
                    "vehicle-sync preserved | "
                    f"vehicle_id={current_vehicle_id}, "
                    f"xyz={self.bot.get_position()}"
                )

        elif parsed.get("state") == "set_player_health":
            self.bot.health = parsed.get("health")

        elif parsed.get("state") == "set_player_armour":
            self.bot.armour = parsed.get("armour")

        elif parsed.get("state") == "give_player_money":
            amount = int(parsed.get("amount", 0))
            self.bot.money += amount

        elif parsed.get("state") == "reset_player_money":
            old_money = self.bot.money
            self.bot.money = 0

        elif parsed.get("state") == "set_interior":
            self.bot.interior = parsed.get("interior_id")


    def update_scores_and_pings(self, entries: list[dict]) -> None:

        bot_id = int(getattr(self.bot, "player_id", -1))

        for entry in entries:
            try:
                player_id = int(entry.get("player_id"))
                score = int(entry.get("score", 0))
                ping = int(entry.get("ping", 0))
            except Exception:
                continue

            self._scores_pings[player_id] = {
                "score": score,
                "ping": ping,
            }

            player = self._players.get(player_id)

            if player is not None:
                player.score = score
                player.ping = ping

            if player_id == bot_id:
                self.bot.score = score
                self.bot.ping = ping

    def get_player_score(self, player_id: int, default: int = 0) -> int:
        player_id = int(player_id)

        record = self._scores_pings.get(player_id)
        if record is not None and "score" in record:
            return int(record.get("score", default))

        player = self._players.get(player_id)

        if player is not None:
            return int(player.score)

        if player_id == int(getattr(self.bot, "player_id", -1)):
            return int(self.bot.score)

        return int(default)

    def get_player_ping(self, player_id: int, default: int = 0) -> int:
        player_id = int(player_id)

        record = self._scores_pings.get(player_id)
        if record is not None and "ping" in record:
            return int(record.get("ping", default))

        player = self._players.get(player_id)

        if player is not None:
            return int(player.ping)

        if player_id == int(getattr(self.bot, "player_id", -1)):
            return int(self.bot.ping)

        return int(default)

    def get_bot_score(self) -> int:
        return self.get_player_score(
            int(getattr(self.bot, "player_id", -1))
        )

    def get_bot_ping(self) -> int:
        return self.get_player_ping(
            int(getattr(self.bot, "player_id", -1))
        )

    def get_scores_pings(self) -> dict[int, dict]:
        return dict(self._scores_pings)

    def get_player(self, player_id: int) -> Optional[PlayerInfo]:
        return self._players.get(player_id)

    def get_all_players(self) -> list[str]:
        return [player.name for player in self._players.values()]

    def get_streamed_players(self) -> Dict[int, PlayerInfo]:
        return self._streamed_players.copy()

    def get_player_count(self) -> int:
        return len(self._players)