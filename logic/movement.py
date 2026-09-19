
from __future__ import annotations

import math
import random
import threading
import time
from copy import deepcopy

from core import logger


MAX_STEP_DT = 0.25

MOVE_LOG_INTERVAL = 0.0

DEFAULT_MOVEMENT_CONFIG = {
    "completion_distance": 0.01,
    "coord_delay": 0.0,
    "coord_fluctuation_max": 0.0,
    "movement_direction_control": None,
    "movement_keys_mode": None,
    "stop_on_dialog": None,
}

_RANDOM_FIELDS = (
    "coord_delay",
    "accel_time",
    "brake_time",
    "coord_fluctuation_max",
    "accel_inertia_time",
    "accel_inertia_strength",
)

_MODE_MOVEMENT_DEFAULTS = {
    "vehicle": {
        "coord_delay": 5.0,
        "accel_time": 3.0,
        "accel_inertia_time": 0.7,
        "accel_inertia_strength": 0.55,
        "brake_time": 0.5,
        "coord_fluctuation_max": 0.001,
    },
    "walk": {
        "coord_delay": 0.5,
        "accel_time": 1.5,
        "accel_inertia_time": 0.25,
        "accel_inertia_strength": 0.25,
        "brake_time": 0.5,
        "coord_fluctuation_max": 0.001,
    },
}
_RANDOM_SAMPLE_ATTEMPTS = 6


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(float(minimum), min(float(maximum), float(value)))


def _finite_number(value, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def _normalize_percent_or_range(value, field: str, *, allow_zero: bool = True):
    minimum = 0.0 if allow_zero else 0.000001
    if isinstance(value, (tuple, list)):
        if len(value) != 2:
            raise ValueError(f"{field} range must contain exactly two numbers")
        low = _finite_number(value[0], f"{field} minimum")
        high = _finite_number(value[1], f"{field} maximum")
        if low > high:
            raise ValueError(f"{field} minimum must not exceed maximum")
        if low < minimum or high > 100.0:
            raise ValueError(f"{field} must be between {minimum:g} and 100")
        return (low, high)
    number = _finite_number(value, field)
    if number < minimum or number > 100.0:
        raise ValueError(f"{field} must be between {minimum:g} and 100")
    return number


def _sample_percent_or_range(value) -> float:
    if isinstance(value, tuple):
        return random.uniform(float(value[0]), float(value[1]))
    return float(value)


def normalize_movement_keys_mode(value) -> str:
    if not isinstance(value, str):
        raise ValueError("movement_keys_mode must be a string like 'off', 'always', 'always:8', 'throttle', 'throttle:16'")
    parts = value.strip().lower().split(":")
    mode = parts[0]
    if mode not in ("off", "always", "throttle"):
        raise ValueError("movement_keys_mode mode must be 'off', 'always' or 'throttle'")
    if len(parts) > 1:
        try:
            key_value = int(parts[1])
            if not 0 <= key_value <= 65535:
                raise ValueError
        except ValueError:
            raise ValueError("movement_keys_mode key_value must be an integer 0..65535")
        return f"{mode}:{key_value}"
    if mode == "off":
        return "off:0"
    return f"{mode}:8"


def _parse_movement_keys_mode(mode_str: str) -> tuple[str, int]:
    parts = mode_str.split(":")
    mode = parts[0]
    key_value = int(parts[1]) if len(parts) > 1 else (0 if mode == "off" else 8)
    return mode, key_value


def normalize_movement_direction_control(value) -> tuple | None:
    if value is None:
        return None
    if not isinstance(value, (tuple, list)) or len(value) not in (3, 4):
        raise ValueError(
            "movement_direction_control must be "
            "(face_movement, update_lr_ud, nonlinearity_percent[, turn_speed_percent])"
        )
    face_movement, update_lr_ud, deviation_chance = value[:3]
    if not isinstance(face_movement, bool) or not isinstance(update_lr_ud, bool):
        raise ValueError(
            "movement_direction_control first two values must be bool"
        )
    if isinstance(deviation_chance, bool) or not isinstance(deviation_chance, int):
        raise ValueError(
            "movement_direction_control nonlinearity percent must be an int"
        )
    if not 0 <= deviation_chance <= 100:
        raise ValueError(
            "movement_direction_control nonlinearity percent must be between 0 and 100"
        )
    turn_speed = 100.0
    if len(value) == 4:
        turn_speed = _normalize_percent_or_range(
            value[3], "movement_direction_control turn speed percent",
            allow_zero=False,
        )
    return face_movement, update_lr_ud, deviation_chance, turn_speed


def _inertia_number(value, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return max(0.0, result)


def _normalize_inertia_time(value) -> tuple[float, float, bool | None]:
    fade = None
    accel_seconds = value
    brake_seconds = 0.0
    if isinstance(value, (tuple, list)):
        if len(value) == 2 and isinstance(value[1], bool):
            accel_seconds, fade = value
        elif len(value) == 3:
            accel_seconds, brake_seconds, fade = value
        else:
            raise ValueError(
                "accel_inertia_time must be a number, (accel_seconds, "
                "fade_bool), or (accel_seconds, brake_seconds, fade_bool)"
            )
        if not isinstance(fade, bool):
            raise ValueError("accel_inertia_time fade flag must be bool")
    return (
        _inertia_number(accel_seconds, "acceleration inertia seconds"),
        _inertia_number(brake_seconds, "braking inertia seconds"),
        fade,
    )


def _normalize_inertia_strength(value) -> tuple[float, float]:
    if isinstance(value, (tuple, list)):
        if len(value) != 2:
            raise ValueError(
                "accel_inertia_strength must be a number or "
                "(accel_strength, brake_strength)"
            )
        accel_strength, brake_strength = value
    else:
        accel_strength, brake_strength = value, 0.0
    return (
        _clamp(_inertia_number(accel_strength, "acceleration inertia strength"), 0.0, 1.0),
        _clamp(_inertia_number(brake_strength, "braking inertia strength"), 0.0, 1.0),
    )


def _finite_inertia_area(value: float, inertia: float, fade: bool) -> float:
    active = min(max(0.0, float(value)), float(inertia))
    if fade:
        return active - (active ** 4) / (4.0 * inertia ** 3)
    return active


def _finite_inertia_progress(
    elapsed: float,
    duration: float,
    inertia: float,
    strength: float,
    fade: bool,
) -> float:
    if inertia <= 0.001 or strength <= 0.0:
        return elapsed / duration
    numerator = elapsed - strength * _finite_inertia_area(elapsed, inertia, fade)
    denominator = duration - strength * _finite_inertia_area(duration, inertia, fade)
    return numerator / denominator if denominator > 1e-12 else elapsed / duration


def normalize_movement_randomization(value) -> dict | None:
    if value is None or value == 0:
        return None
    if isinstance(value, bool):
        raise ValueError("randomization must not be bool")
    if isinstance(value, dict) and {
        "percent_range", "fields"
    }.issubset(value):
        return deepcopy(value)
    if isinstance(value, str):
        name = value.strip().lower()
        if name in ("", "off", "none"):
            return None
        raise ValueError(
            "randomization must be a percentage, a two-value range, "
            "'off' or a normalized dict"
        )

    if isinstance(value, (int, float)):
        maximum = float(value)
        minimum = 0.0
    elif isinstance(value, (tuple, list)) and len(value) == 2:
        try:
            minimum = float(value[0])
            maximum = float(value[1])
        except (TypeError, ValueError) as exc:
            raise ValueError("randomization range values must be numbers") from exc
    else:
        raise ValueError(
            "randomization must be a percentage, a two-value range or off"
        )

    if (
        not math.isfinite(minimum)
        or not math.isfinite(maximum)
        or minimum < 0.0
        or maximum < minimum
        or maximum >= 100.0
    ):
        raise ValueError("randomization range must satisfy 0 <= min <= max < 100")
    if maximum == 0.0:
        return None
    return {
        "percent_range": (minimum, maximum),
        "min_percent_gap": min(2.0, max(0.0, (maximum - minimum) * 0.25)),
        "fields": _RANDOM_FIELDS,
        "stop_on_dialog": True,
    }


def _sample_percent_value(
    base: float,
    field: str,
    config: dict,
    last_percent: dict,
) -> float:
    if field not in config["fields"]:
        return max(0.0, float(base))
    minimum, maximum = config["percent_range"]
    min_gap = float(config.get("min_percent_gap", 0.0))
    previous = last_percent.get(field)
    signed_percent = 0.0
    for _ in range(_RANDOM_SAMPLE_ATTEMPTS):
        magnitude = random.uniform(float(minimum), float(maximum))
        signed_percent = magnitude if random.getrandbits(1) else -magnitude
        if previous is None or abs(signed_percent - float(previous)) >= min_gap:
            break
    last_percent[field] = signed_percent
    return max(0.0, float(base) * (1.0 + signed_percent / 100.0))


def _sample_motion_value(
    base: float,
    field: str,
    config: dict | None,
    last_percent: dict,
    minimum: float = 0.0,
) -> float:
    if config:
        return max(
            float(minimum),
            _sample_percent_value(base, field, config, last_percent),
        )
    return max(float(minimum), float(base))


class CoordMovementController:

    def __init__(self, player, config: dict | None = None):
        self.player = player
        self._lock = threading.RLock()
        self._sequence = 0
        self._active: dict | None = None
        self._results: dict[int, dict] = {}
        self.config = deepcopy(DEFAULT_MOVEMENT_CONFIG)
        self.configure(config)

    def configure(self, config: dict | None) -> None:
        if not config:
            return
        with self._lock:
            self.config.update(config)

    @staticmethod
    def _public(state: dict) -> dict:
        keys = (
            "movement_id", "mode", "status", "phase",
            "start_position", "base_target", "target_position",
            "started_at", "coord_delay", "current_coord_delay",
            "accel_time", "accel_inertia_time", "accel_inertia_strength",
            "accel_inertia_fade", "brake_inertia_time",
            "brake_inertia_strength",
            "brake_time", "nominal_interval",
            "stop_on_dialog", "stop_dialog_type",
            "movement_direction_control",
            "turn_speed_percent",
            "movement_keys_mode",
        )
        return {key: state.get(key) for key in keys}

    def _finish_locked(self, state: dict, status: str) -> dict:
        state["status"] = str(status)
        state["finished_at"] = time.monotonic()
        state["elapsed"] = max(0.0, state["finished_at"] - state["started_at"])
        state["final_position"] = self.player.get_position()
        state["current_coord_delay"] = 0.0
        self.player.set_coord_delay(0.0)

        if state.get("movement_keys_mode") != "off":
            self.player.keys = int(state.get("original_keys", 0))
        if state.get("update_lr_ud"):
            self.player.set_control_axes(
                state.get("original_lr", 0),
                state.get("original_ud", 0),
            )

        if self._active is state:
            self._active = None

        result = self._public(state)
        result.update(
            status=state["status"],
            final_position=state["final_position"],
            elapsed=state["elapsed"],
        )
        self._results[int(state["movement_id"])] = result
        while len(self._results) > 64:
            self._results.pop(next(iter(self._results)))
        return result

    def cancel(self, movement_id: int | None = None, reason: str = "cancelled") -> dict | None:
        with self._lock:
            state = self._active
            if state is None:
                return None
            if movement_id is not None and int(movement_id) != int(state["movement_id"]):
                return None
            self.player.clear_position_target()
            self.player.reset_velocity()
            return self._finish_locked(state, reason)

    def handle_dialog(self, dialog_type: str = "dialog") -> dict | None:
        with self._lock:
            state = self._active
            if state is None or not state.get("stop_on_dialog"):
                return None
            state["stop_dialog_type"] = str(dialog_type or "dialog")
            self.player.clear_position_target()
            self.player.reset_velocity()
            return self._finish_locked(state, "dialog")

    @staticmethod
    def _resample_motion_parameters(state: dict) -> None:
        config = state.get("randomization")
        if not config:
            return
        last_percent = state["randomization_last_percent"]
        state["coord_delay"] = _sample_motion_value(
            state["base_coord_delay"], "coord_delay", config, last_percent,
            0.000001,
        )
        state["accel_time"] = _sample_motion_value(
            state["base_accel_time"], "accel_time", config, last_percent,
        )
        state["brake_time"] = _sample_motion_value(
            state["base_brake_time"], "brake_time", config, last_percent,
        )
        state["accel_inertia_time"] = _sample_percent_value(
            state["base_accel_inertia_time"],
            "accel_inertia_time",
            config,
            last_percent,
        )
        state["accel_inertia_strength"] = _clamp(
            _sample_percent_value(
                state["base_accel_inertia_strength"],
                "accel_inertia_strength",
                config,
                last_percent,
            ),
            0.0,
            1.0,
        )
        state["coord_fluctuation_max"] = _sample_percent_value(
            state["base_coord_fluctuation_max"],
            "coord_fluctuation_max",
            config,
            last_percent,
        )

    def _apply_movement_keys(self, state: dict) -> None:
        mode_str = state.get("movement_keys_mode", "off:0")
        mode, key_value = _parse_movement_keys_mode(mode_str)
        if mode == "off":
            return
        if mode == "always":
            self.player.keys = key_value
            return
        if state.get("phase") == "braking":
            self.player.keys = 0
        else:
            self.player.keys = key_value

    def start(
        self,
        target_position,
        *,
        mode: str = "auto",
        nominal_interval: float = 0.05,
        overrides: dict | None = None,
    ) -> tuple[dict, dict | None]:
        with self._lock:
            replaced = self.cancel(reason="replaced")
            resolved_mode = str(mode or "auto").lower()
            if resolved_mode == "auto":
                resolved_mode = "vehicle" if self.player.is_in_vehicle() else "walk"
            if resolved_mode in ("onfoot", "foot", "player"):
                resolved_mode = "walk"
            if resolved_mode not in ("walk", "vehicle"):
                raise ValueError("mode must be 'auto', 'walk' or 'vehicle'")

            supplied = dict(overrides or {})
            settings = dict(self.config)
            settings.update(_MODE_MOVEMENT_DEFAULTS[resolved_mode])
            settings.update({key: value for key, value in supplied.items() if value is not None})

            base_coord_delay = float(settings["coord_delay"])
            base_accel_time = max(0.0, float(settings.get("accel_time", 0.0)))
            base_brake_time = max(0.0, float(settings.get("brake_time", 0.0)))
            (
                base_accel_inertia_time,
                base_brake_inertia_time,
                base_accel_inertia_fade,
            ) = _normalize_inertia_time(
                settings.get("accel_inertia_time", 0.0)
            )
            (
                base_accel_inertia_strength,
                base_brake_inertia_strength,
            ) = _normalize_inertia_strength(
                settings.get("accel_inertia_strength", 0.0)
            )
            base_coord_fluctuation_max = max(
                0.0, float(settings.get("coord_fluctuation_max", 0.0))
            )
            randomization = normalize_movement_randomization(
                settings.get("randomization")
            )
            last_percent = {}
            target_delay = _sample_motion_value(
                base_coord_delay, "coord_delay", randomization, last_percent,
                0.000001,
            )
            accel_time = _sample_motion_value(
                base_accel_time, "accel_time", randomization, last_percent,
            )
            brake_time = _sample_motion_value(
                base_brake_time, "brake_time", randomization, last_percent,
            )

            direction_control = normalize_movement_direction_control(
                supplied.get(
                    "movement_direction_control",
                    settings.get("movement_direction_control"),
                )
            )
            if direction_control is None:
                face_movement = False
                update_lr_ud = False
                direction_deviation_chance = 0
            else:
                (
                    face_movement,
                    update_lr_ud,
                    direction_deviation_chance,
                    turn_speed_setting,
                ) = direction_control
                face_movement = face_movement

            if direction_control is None:
                turn_speed_setting = 100.0
            turn_speed_percent = _sample_percent_or_range(turn_speed_setting)

            explicit_keys_mode = settings.get("movement_keys_mode")
            if explicit_keys_mode is None:
                movement_keys_mode = "off:0"
            else:
                movement_keys_mode = normalize_movement_keys_mode(explicit_keys_mode)

            base_target = tuple(float(value) for value in target_position)

            self._sequence += 1
            started = time.monotonic()
            state = {
                "movement_id": self._sequence,
                "mode": resolved_mode,
                "status": "moving",
                "phase": "acceleration" if accel_time > 0.0 else "cruise",
                "start_position": self.player.get_position(),
                "base_target": base_target,
                "target_position": base_target,
                "started_at": started,
                "last_step_at": None,
                "phase_started_at": started,
                "base_coord_delay": base_coord_delay,
                "base_accel_time": base_accel_time,
                "base_brake_time": base_brake_time,
                "base_accel_inertia_time": base_accel_inertia_time,
                "base_accel_inertia_fade": base_accel_inertia_fade,
                "base_accel_inertia_strength": base_accel_inertia_strength,
                "base_brake_inertia_time": base_brake_inertia_time,
                "base_brake_inertia_strength": base_brake_inertia_strength,
                "base_coord_fluctuation_max": base_coord_fluctuation_max,
                "randomization": dict(randomization or {}),
                "randomization_last_percent": last_percent,
                "coord_delay": target_delay,
                "current_coord_delay": 0.0 if accel_time > 0.0 else target_delay,
                "accel_start_coord_delay": 0.0,
                "accel_time": accel_time,
                "accel_inertia_time": _sample_percent_value(
                    base_accel_inertia_time,
                    "accel_inertia_time",
                    randomization,
                    last_percent,
                ) if randomization else base_accel_inertia_time,
                "accel_inertia_strength": _clamp(
                    _sample_percent_value(
                        base_accel_inertia_strength,
                        "accel_inertia_strength",
                        randomization,
                        last_percent,
                    ) if randomization else base_accel_inertia_strength,
                    0.0,
                    1.0,
                ),
                "accel_inertia_fade": base_accel_inertia_fade,
                "brake_inertia_time": base_brake_inertia_time,
                "brake_inertia_strength": base_brake_inertia_strength,
                "brake_time": brake_time,
                "brake_start_coord_delay": None,
                "brake_target_coord_delay": 0.0,
                "nominal_interval": max(0.001, float(nominal_interval)),
                "completion_distance": max(0.0, float(settings.get("completion_distance", 0.01))),
                "last_log_at": started,
                "coord_fluctuation_max": _sample_percent_value(
                    base_coord_fluctuation_max,
                    "coord_fluctuation_max",
                    randomization,
                    last_percent,
                ) if randomization else base_coord_fluctuation_max,
                "movement_direction_control": (
                    face_movement,
                    update_lr_ud,
                    direction_deviation_chance,
                    turn_speed_percent,
                ),
                "turn_speed_percent": turn_speed_percent,
                "update_lr_ud": update_lr_ud,
                "direction_deviation_chance": direction_deviation_chance,
                "direction_deviation_offset": 0.0,
                "direction_deviation_target": 0.0,
                "direction_touch_magnitude": 0.0,
                "direction_deviation_until": started,
                "direction_deviation_next_check": started + 1.0,
                "direction_deviation_updated_at": started,
                "movement_keys_mode": movement_keys_mode,
                "stop_on_dialog": bool(
                    (randomization or {}).get("stop_on_dialog", False)
                    if settings.get("stop_on_dialog") is None
                    else settings.get("stop_on_dialog")
                ),
                "stop_dialog_type": None,
                "original_keys": int(self.player.keys),
                "original_lr": int(self.player.lr),
                "original_ud": int(self.player.ud),
                "last_move_direction": None,
            }
            self._active = state
            self.player.set_coord_delay(state["current_coord_delay"])
            self.player._target_x, self.player._target_y, self.player._target_z = base_target
            self._apply_movement_keys(state)
            if state["update_lr_ud"]:
                self.player.set_control_axes(0, 0)
            return self._public(state), replaced

    @staticmethod
    def _heading_axes(
        current_rotation: float,
        target_rotation: float,
        magnitude: float = 127.0,
    ) -> tuple[int, int]:
        error = (
            float(target_rotation) - float(current_rotation) + 180.0
        ) % 360.0 - 180.0
        radians = math.radians(error)
        magnitude = _clamp(magnitude, 0.0, 127.0)
        lr = int(round(magnitude * math.sin(radians)))
        ud = int(round(magnitude * math.cos(radians)))
        return (
            int(_clamp(lr, -127, 127)),
            int(_clamp(ud, -127, 127)),
        )

    @staticmethod
    def _update_direction_deviation(state: dict, now: float) -> float:
        chance = int(state.get("direction_deviation_chance", 0))
        previous = float(state.get("direction_deviation_updated_at", now))
        dt = _clamp(now - previous, 0.0, 0.25)
        state["direction_deviation_updated_at"] = now

        if now >= float(state.get("direction_deviation_until", now)):
            state["direction_deviation_target"] = 0.0

        if now >= float(state.get("direction_deviation_next_check", now + 1.0)):
            state["direction_deviation_next_check"] = now + 1.0
            inactive = (
                abs(float(state.get("direction_deviation_target", 0.0))) < 1e-6
                and abs(float(state.get("direction_deviation_offset", 0.0))) < 0.35
            )
            if chance > 0 and inactive and random.randrange(100) < chance:
                nonlinearity = chance / 100.0
                magnitude = random.uniform(
                    1.5 + 0.5 * nonlinearity,
                    4.5 + 1.5 * nonlinearity,
                )
                state["direction_deviation_target"] = (
                    magnitude if random.getrandbits(1) else -magnitude
                )
                state["direction_touch_magnitude"] = random.uniform(
                    8.0 + 4.0 * nonlinearity,
                    24.0 + 8.0 * nonlinearity,
                )
                state["direction_deviation_until"] = now + random.uniform(
                    0.35,
                    0.70 + 0.20 * nonlinearity,
                )

        current = float(state.get("direction_deviation_offset", 0.0))
        target = float(state.get("direction_deviation_target", 0.0))
        max_change = 18.0 * dt
        current += _clamp(target - current, -max_change, max_change)
        if target == 0.0 and abs(current) < 0.01:
            current = 0.0
            state["direction_touch_magnitude"] = 0.0
        state["direction_deviation_offset"] = current
        return current

    def _update_direction_controls(
        self,
        state: dict,
        target_rotation: float,
    ) -> None:
        if not state.get("update_lr_ud"):
            return

        error = (
            float(target_rotation) - float(self.player.rotation) + 180.0
        ) % 360.0 - 180.0
        face_movement = state["movement_direction_control"][0]
        if face_movement:
            if abs(error) > 0.75:
                magnitude = max(24.0, 127.0 * min(1.0, abs(error) / 45.0))
            else:
                magnitude = float(state.get("direction_touch_magnitude", 0.0))
            if magnitude <= 0.0 or abs(error) <= 0.10:
                self.player.set_control_axes(0, 0)
                return
        else:
            if abs(error) <= 1.5:
                self.player.set_control_axes(0, 0)
                return
            magnitude = 127.0

        lr, ud = self._heading_axes(
            self.player.rotation,
            target_rotation,
            magnitude=magnitude,
        )
        if state["phase"] == "braking":
            if state["mode"] == "vehicle":
                ud = -abs(ud)
            else:
                lr = 0
                ud = 0
        self.player.set_control_axes(lr, ud)

    @staticmethod
    def _smooth_rotation(current: float, target: float, dt: float, percent: float) -> float:
        percent = _clamp(percent, 0.000001, 100.0)
        target %= 360.0
        if percent >= 100.0:
            return target
        error = (target - float(current) + 180.0) % 360.0 - 180.0
        max_change = 360.0 * (percent / 100.0) * max(0.0, float(dt))
        return (float(current) + _clamp(error, -max_change, max_change)) % 360.0

    def _arrive_at_target_locked(self, state: dict, now: float) -> dict:
        target = state["target_position"]
        self.player._set_position_internal(*target, update_velocity=False)
        self.player.clear_position_target()
        self.player.reset_velocity()
        return {"completed": self._finish_locked(state, "arrived")}

    @staticmethod
    def _accelerated_delay(state: dict, now: float) -> float:
        start = float(state["accel_start_coord_delay"])
        maximum = float(state["coord_delay"])
        duration = float(state["accel_time"])
        if duration <= 0.001 or maximum <= start:
            return maximum
        elapsed = _clamp(now - float(state["phase_started_at"]), 0.0, duration)
        inertia = _clamp(state["accel_inertia_time"], 0.0, duration)
        strength = _clamp(state["accel_inertia_strength"], 0.0, 1.0)
        if inertia <= 0.001 or strength <= 0.0:
            progress = elapsed / duration
        elif state.get("accel_inertia_fade") is not None:
            progress = _finite_inertia_progress(
                elapsed,
                duration,
                inertia,
                strength,
                bool(state["accel_inertia_fade"]),
            )
        else:
            numerator = elapsed - strength * inertia * (-math.expm1(-elapsed / inertia))
            denominator = duration - strength * inertia * (-math.expm1(-duration / inertia))
            progress = numerator / denominator if denominator > 1e-12 else elapsed / duration
        return start + (maximum - start) * _clamp(progress, 0.0, 1.0)

    @staticmethod
    def _braking_delay(state: dict, now: float) -> float:
        start = float(state["brake_start_coord_delay"])
        target = _clamp(
            float(state.get("brake_target_coord_delay", 0.0)),
            0.0,
            start,
        )
        duration = max(0.001, float(state["brake_time"]))
        elapsed = _clamp(now - float(state["phase_started_at"]), 0.0, duration)
        inertia = _clamp(state.get("brake_inertia_time", 0.0), 0.0, duration)
        strength = _clamp(state.get("brake_inertia_strength", 0.0), 0.0, 1.0)
        fade = state.get("accel_inertia_fade")
        if fade is None:
            progress = elapsed / duration
        else:
            progress = _finite_inertia_progress(
                elapsed, duration, inertia, strength, bool(fade)
            )
        return target + (start - target) * (1.0 - progress)

    @staticmethod
    def _braking_distance_time(state: dict) -> float:
        duration = max(0.001, float(state["brake_time"]))
        inertia = _clamp(state.get("brake_inertia_time", 0.0), 0.0, duration)
        strength = _clamp(state.get("brake_inertia_strength", 0.0), 0.0, 1.0)
        fade = state.get("accel_inertia_fade")
        if fade is None or inertia <= 0.001 or strength <= 0.0:
            return duration * 0.5

        if fade:
            integrated_area = (
                inertia * duration * 0.75
                - inertia * inertia * 0.30
            )
        else:
            integrated_area = inertia * duration - inertia * inertia * 0.5
        denominator = duration - strength * _finite_inertia_area(
            duration, inertia, bool(fade)
        )
        if denominator <= 1e-12:
            return duration * 0.5
        integrated_progress = (
            duration * duration * 0.5 - strength * integrated_area
        ) / denominator
        return _clamp(duration - integrated_progress, 0.0, duration)

    def handle_server_velocity_reset(self) -> bool:
        with self._lock:
            state = self._active
            if state is None:
                return False
            now = time.monotonic()
            state["phase"] = "acceleration" if state["accel_time"] > 0.0 else "cruise"
            state["phase_started_at"] = now
            state["accel_start_coord_delay"] = 0.0
            state["current_coord_delay"] = 0.0
            self.player.set_coord_delay(0.0)
            self._apply_movement_keys(state)
            return True

    def step(self, now: float | None = None) -> dict | None:
        with self._lock:
            state = self._active
            if state is None:
                return None
            now = time.monotonic() if now is None else float(now)

            target = state["target_position"]
            dx = target[0] - self.player.x
            dy = target[1] - self.player.y
            dz = target[2] - self.player.z
            distance = math.sqrt(dx * dx + dy * dy + dz * dz)
            if distance <= state["completion_distance"]:
                return self._arrive_at_target_locked(state, now)

            old_phase = state["phase"]
            if old_phase == "acceleration":
                delay = self._accelerated_delay(state, now)
                if now - state["phase_started_at"] >= state["accel_time"]:
                    state["phase"] = "cruise"
                    state["phase_started_at"] = now
                    delay = state["coord_delay"]
            elif old_phase == "braking":
                delay = self._braking_delay(state, now)
            else:
                delay = state["coord_delay"]

            nominal = float(state["nominal_interval"])
            current_delay = max(0.0, float(delay))
            brake_curve_time = self._braking_distance_time(state)

            brake_distance = (
                current_delay * brake_curve_time
            ) / nominal
            if (
                state["brake_time"] > 0.0
                and state["phase"] != "braking"
                and distance <= max(state["completion_distance"], brake_distance)
            ):
                state["phase"] = "braking"
                state["phase_started_at"] = now
                state["brake_start_coord_delay"] = current_delay
                state["brake_target_coord_delay"] = 0.0

            if state["phase"] == "braking":
                delay = self._braking_delay(state, now)
                if now - state["phase_started_at"] >= state["brake_time"]:
                    self.player._set_position_internal(*target, update_velocity=False)
                    self.player.clear_position_target()
                    self.player.reset_velocity()
                    return {"completed": self._finish_locked(state, "arrived")}

            self._apply_movement_keys(state)

            fluctuation = float(state["coord_fluctuation_max"])
            sent_delay = max(0.0, delay + random.uniform(-fluctuation, fluctuation))

            if (
                MOVE_LOG_INTERVAL > 0.0
                and now - float(state["last_log_at"]) >= MOVE_LOG_INTERVAL
            ):
                logger.debug(
                    f"id={int(state['movement_id'])} | "
                    f"mode={state['mode']} | "
                    f"phase={state['phase']} | distance={distance:.2f} | "
                    f"coord_delay={sent_delay:.6f} | "
                    f"elapsed={now - float(state['started_at']):.2f}s"
                )
                state["last_log_at"] = now

            last_step = state["last_step_at"]
            dt = nominal if last_step is None else max(0.001, now - last_step)
            dt = min(dt, MAX_STEP_DT)
            step_distance = sent_delay * (dt / nominal)
            reached = step_distance >= distance
            if reached:
                new_position = target
            else:
                scale = step_distance / distance
                new_position = (
                    self.player.x + dx * scale,
                    self.player.y + dy * scale,
                    self.player.z + dz * scale,
                )
            if distance > 0.0:
                state["last_move_direction"] = (
                    dx / distance,
                    dy / distance,
                    dz / distance,
                )

            target_rotation = None
            if dx != 0.0 or dy != 0.0:
                target_rotation = (
                    math.degrees(math.atan2(dy, dx)) + 90.0
                ) % 360.0

            face_movement = state["movement_direction_control"][0]
            update_lr_ud = state["update_lr_ud"]
            
            if target_rotation is not None and (face_movement or update_lr_ud):
                direction_offset = self._update_direction_deviation(state, now)
            else:
                direction_offset = 0.0

            if face_movement and target_rotation is not None:
                rotation = target_rotation + direction_offset
                self.player.set_rotation(
                    self._smooth_rotation(
                        self.player.rotation,
                        rotation,
                        dt,
                        state.get("turn_speed_percent", 100.0),
                    )
                )
            if target_rotation is not None:
                control_rotation = target_rotation
                if not face_movement:
                    control_rotation += direction_offset
                self._update_direction_controls(state, control_rotation)
            self.player._set_position_internal(
                *new_position,
                update_velocity=False,
                now=time.time(),
            )
            if reached:
                self.player.reset_velocity()
            else:
                self.player.update_movement_velocity(
                    dx,
                    dy,
                    dz,
                    coord_delay=sent_delay,
                    nominal_interval=nominal,
                )
            self.player.set_coord_delay(sent_delay)
            state["current_coord_delay"] = delay
            state["last_step_at"] = now

            response = None
            if old_phase != state["phase"]:
                response = {
                    "phase_change": {
                        "movement": self._public(state),
                        "old_phase": old_phase,
                        "new_phase": state["phase"],
                    }
                }
            if reached:
                arrival_response = self._arrive_at_target_locked(state, now)
                response = response or {}
                response.update(arrival_response)
            return response

    def get_active(self, movement_id: int | None = None) -> dict | None:
        with self._lock:
            if self._active is None:
                return None
            if movement_id is not None and int(movement_id) != int(self._active["movement_id"]):
                return None
            return self._public(self._active)

    def get_result(self, movement_id: int) -> dict | None:
        with self._lock:
            result = self._results.get(int(movement_id))
            return dict(result) if result else None
