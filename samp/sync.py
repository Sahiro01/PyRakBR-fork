
import random
import time

from .packets import PacketBuilder


class PlayerSyncScheduler:

    def __init__(
        self,
        *,
        rate_player: float = 0.200,
        rate_player_min: float | None = None,
        rate_player_max: float | None = None,
        rate_player_jitter_max: float = 0.0,
        rate_player_fluctuation_chance: float = 0.0,
        rate_player_fluctuation_max: float = 0.0,
        rate_vehicle_min: float | None = None,
        rate_vehicle_max: float | None = None,
        sync_idle_after_min: float = 0.0,
        sync_idle_after_max: float = 0.0,
        sync_idle_backoff_factor_min: float = 1.0,
        sync_idle_backoff_factor_max: float = 1.0,
        player_idle_interval_multiplier_min: float = 1.0,
        player_idle_interval_multiplier_max: float = 1.0,
        vehicle_idle_interval_multiplier_min: float = 1.0,
        vehicle_idle_interval_multiplier_max: float = 1.0,
    ):
        self.session = None

        self.enabled = False
        self._next_player_sync_time = 0.0
        self._player_sync_random = random.Random()
        self._player_sync_last_fingerprint = None
        self._player_sync_last_mode = None
        self._player_sync_idle_since = None
        self._player_sync_idle_after = 0.0
        self._player_sync_idle_factor = 1.0
        self._player_sync_idle_base_interval = 0.0
        self._player_sync_idle_current_interval = 0.0
        self._player_sync_idle_max_interval = 0.0

        nominal_rate_player = max(0.0, float(rate_player))
        self.rate_player_min = max(
            0.0,
            float(
                nominal_rate_player
                if rate_player_min is None
                else rate_player_min
            ),
        )
        self.rate_player_max = max(
            self.rate_player_min,
            float(
                nominal_rate_player
                if rate_player_max is None
                else rate_player_max
            ),
        )
        self.rate_player_jitter_max = max(
            0.0,
            float(rate_player_jitter_max),
        )
        self.rate_player_fluctuation_chance = min(
            1.0,
            max(0.0, float(rate_player_fluctuation_chance)),
        )
        self.rate_player_fluctuation_max = max(
            0.0,
            float(rate_player_fluctuation_max),
        )
        self.rate_vehicle_min = max(
            0.0,
            float(
                self.rate_player_min
                if rate_vehicle_min is None
                else rate_vehicle_min
            ),
        )
        self.rate_vehicle_max = max(
            self.rate_vehicle_min,
            float(
                self.rate_player_max
                if rate_vehicle_max is None
                else rate_vehicle_max
            ),
        )
        self.sync_idle_after_min = max(
            0.0,
            float(sync_idle_after_min),
        )
        self.sync_idle_after_max = max(
            self.sync_idle_after_min,
            float(sync_idle_after_max),
        )
        self.sync_idle_backoff_factor_min = max(
            1.0,
            float(sync_idle_backoff_factor_min),
        )
        self.sync_idle_backoff_factor_max = max(
            self.sync_idle_backoff_factor_min,
            float(sync_idle_backoff_factor_max),
        )
        self.player_idle_interval_multiplier_min = max(
            1.0,
            float(player_idle_interval_multiplier_min),
        )
        self.player_idle_interval_multiplier_max = max(
            self.player_idle_interval_multiplier_min,
            float(player_idle_interval_multiplier_max),
        )
        self.vehicle_idle_interval_multiplier_min = max(
            1.0,
            float(vehicle_idle_interval_multiplier_min),
        )
        self.vehicle_idle_interval_multiplier_max = max(
            self.vehicle_idle_interval_multiplier_min,
            float(vehicle_idle_interval_multiplier_max),
        )


    def start(self) -> None:

        self.enabled = True
        self.reset_idle_state(clear_fingerprint=True)
        self._next_player_sync_time = time.monotonic()

    def stop(self) -> None:
        self.enabled = False

    def reset(self) -> None:

        self.enabled = False
        self._next_player_sync_time = 0.0
        self.reset_idle_state(clear_fingerprint=True)


    def tick(self) -> None:
        if not self.session.connected:
            return

        if not self.enabled:
            return

        bot = self.session.players.bot
        sync_state = getattr(bot, "sync_state", "onfoot")
        if sync_state == "passenger":
            mode = "passenger"
        elif sync_state == "vehicle":
            mode = "vehicle"
        else:
            mode = "onfoot"
        _, rate_maximum = self._sync_rate_bounds(mode)

        if rate_maximum <= 0.0:
            return

        now = time.monotonic()
        fingerprint = self._build_motion_fingerprint(bot, mode)
        state_changed = (
            self._player_sync_last_fingerprint is None
            or fingerprint != self._player_sync_last_fingerprint
        )
        mode_changed = (
            self._player_sync_last_mode is not None
            and mode != self._player_sync_last_mode
        )
        has_motion = self._has_motion(bot)
        was_waiting_idle = self._player_sync_idle_since is not None

        if has_motion or state_changed:
            if was_waiting_idle or mode_changed:
                self._next_player_sync_time = now

            self.reset_idle_state()
            idle_backoff_active = False
        else:
            if not self._idle_enabled(mode):
                self.reset_idle_state()
                idle_backoff_active = False
            else:
                if self._player_sync_idle_since is None:
                    self._start_idle_state(now, mode)

                idle_backoff_active = (
                    now - float(self._player_sync_idle_since)
                    >= float(self._player_sync_idle_after)
                )

        if now < self._next_player_sync_time:
            return

        if mode == "vehicle":
            self.send_vehicle_sync()
        elif mode == "passenger":
            self.send_passenger_sync()
        else:
            self.send_player_sync()

        self._player_sync_last_fingerprint = (
            self._build_motion_fingerprint(bot, mode)
        )
        self._player_sync_last_mode = mode

        if idle_backoff_active:
            interval = self._sample_idle_interval(mode)
        else:
            interval = self._sample_interval(mode)

        next_deadline = self._next_player_sync_time
        if next_deadline <= 0.0:
            next_deadline = now

        next_deadline += interval

        if next_deadline <= now:
            next_deadline = now + interval

        self._next_player_sync_time = next_deadline


    def send_player_sync(self) -> None:
        bot_player = self.session.players.bot

        movement_result = None

        if hasattr(bot_player, "advance_movement_step"):
            movement_result = bot_player.advance_movement_step()

        self.session._sender.send(
            PacketBuilder.player_sync(bot_player),
            packet_name="player_sync",
        )

        self._dispatch_coord_movement_result(movement_result)

    def send_vehicle_sync(self) -> None:
        bot_player = self.session.players.bot

        movement_result = None

        if hasattr(bot_player, "advance_movement_step"):
            movement_result = bot_player.advance_movement_step()

        self.session._sender.send(
            PacketBuilder.vehicle_sync(bot_player),
            packet_name="vehicle_sync",
        )

        self._dispatch_coord_movement_result(movement_result)

    def send_passenger_sync(self) -> None:
        bot_player = self.session.players.bot

        bot_player.update_passenger_coords_from_vehicle(self.session.stream)

        movement_result = None

        if hasattr(bot_player, "advance_movement_step"):
            movement_result = bot_player.advance_movement_step()

        self.session._sender.send(
            PacketBuilder.passenger_sync(bot_player),
            packet_name="passenger_sync",
        )

        self._dispatch_coord_movement_result(movement_result)

    def _dispatch_coord_movement_result(self, movement_result) -> None:
        if not movement_result:
            return

        phase_change = movement_result.get("phase_change")
        if phase_change:
            self.session._emit_callback(
                "OnCoordMovePhaseChange",
                phase_change.get("movement"),
                phase_change.get("old_phase"),
                phase_change.get("new_phase"),
            )

        completed = movement_result.get("completed")
        if completed:
            self.session._api_emit_coord_move_end(completed)
            return


    @staticmethod
    def _build_motion_fingerprint(bot, mode: str) -> tuple:

        return (
            mode,
            getattr(bot, "x", 0.0),
            getattr(bot, "y", 0.0),
            getattr(bot, "z", 0.0),
            getattr(bot, "velocity_x", 0.0),
            getattr(bot, "velocity_y", 0.0),
            getattr(bot, "velocity_z", 0.0),
        )

    @staticmethod
    def _has_motion(bot) -> bool:
        try:
            if bot.has_position_target():
                return True
        except (AttributeError, TypeError):
            pass

        velocity_sq = sum(
            float(getattr(bot, field, 0.0)) ** 2
            for field in ("velocity_x", "velocity_y", "velocity_z")
        )
        return velocity_sq > 1e-12


    def reset_idle_state(self, *, clear_fingerprint: bool = False) -> None:
        self._player_sync_idle_since = None
        self._player_sync_idle_after = 0.0
        self._player_sync_idle_factor = 1.0
        self._player_sync_idle_base_interval = 0.0
        self._player_sync_idle_current_interval = 0.0
        self._player_sync_idle_max_interval = 0.0

        if clear_fingerprint:
            self._player_sync_last_fingerprint = None
            self._player_sync_last_mode = None

    def _idle_enabled(self, mode: str) -> bool:
        _, multiplier_maximum = self._sync_idle_multiplier_bounds(mode)
        factor_maximum = max(
            1.0,
            float(self.sync_idle_backoff_factor_max),
        )
        return multiplier_maximum > 1.0 and factor_maximum > 1.0

    def _start_idle_state(self, now: float, mode: str) -> None:
        rate_minimum, rate_maximum = self._sync_rate_bounds(mode)
        multiplier_minimum, multiplier_maximum = (
            self._sync_idle_multiplier_bounds(mode)
        )

        base_interval = self._player_sync_random.uniform(
            rate_minimum,
            rate_maximum,
        )
        multiplier = self._player_sync_random.uniform(
            multiplier_minimum,
            multiplier_maximum,
        )
        self._player_sync_idle_since = float(now)
        self._player_sync_idle_after = self._player_sync_random.uniform(
            max(0.0, float(self.sync_idle_after_min)),
            max(
                max(0.0, float(self.sync_idle_after_min)),
                float(self.sync_idle_after_max),
            ),
        )
        self._player_sync_idle_factor = self._player_sync_random.uniform(
            max(1.0, float(self.sync_idle_backoff_factor_min)),
            max(
                max(1.0, float(self.sync_idle_backoff_factor_min)),
                float(self.sync_idle_backoff_factor_max),
            ),
        )
        self._player_sync_idle_base_interval = base_interval
        self._player_sync_idle_current_interval = base_interval
        self._player_sync_idle_max_interval = max(
            base_interval,
            base_interval * multiplier,
        )


    def _sync_rate_bounds(self, mode: str) -> tuple[float, float]:
        if mode == "vehicle":
            minimum = max(0.0, float(self.rate_vehicle_min))
            maximum = max(minimum, float(self.rate_vehicle_max))
            return minimum, maximum

        minimum = max(0.0, float(self.rate_player_min))
        maximum = max(minimum, float(self.rate_player_max))
        return minimum, maximum

    def _sync_idle_multiplier_bounds(self, mode: str) -> tuple[float, float]:
        if mode == "vehicle":
            minimum = max(
                1.0,
                float(self.vehicle_idle_interval_multiplier_min),
            )
            maximum = max(
                minimum,
                float(self.vehicle_idle_interval_multiplier_max),
            )
            return minimum, maximum

        minimum = max(
            1.0,
            float(self.player_idle_interval_multiplier_min),
        )
        maximum = max(
            minimum,
            float(self.player_idle_interval_multiplier_max),
        )
        return minimum, maximum

    def _apply_randomization(
        self,
        interval: float,
        minimum: float,
        maximum: float | None = None,
    ) -> float:
        interval = float(interval)

        jitter_max = max(
            0.0,
            float(self.rate_player_jitter_max),
        )
        if jitter_max > 0.0:
            interval += self._player_sync_random.uniform(
                -jitter_max,
                jitter_max,
            )

        fluctuation_chance = min(
            1.0,
            max(0.0, float(self.rate_player_fluctuation_chance)),
        )
        fluctuation_max = max(
            0.0,
            float(self.rate_player_fluctuation_max),
        )

        if (
            fluctuation_max > 0.0
            and self._player_sync_random.random() < fluctuation_chance
        ):
            interval += self._player_sync_random.uniform(
                0.0,
                fluctuation_max,
            )

        interval = max(float(minimum), interval)

        if maximum is not None:
            interval = min(float(maximum), interval)

        return interval

    def _sample_interval(self, mode: str = "onfoot") -> float:
        minimum, maximum = self._sync_rate_bounds(mode)
        interval = self._player_sync_random.uniform(minimum, maximum)
        return self._apply_randomization(interval, minimum)

    def _sample_idle_interval(self, mode: str) -> float:
        minimum, _ = self._sync_rate_bounds(mode)
        current = max(
            self._player_sync_idle_base_interval,
            self._player_sync_idle_current_interval,
        )
        current = min(
            self._player_sync_idle_max_interval,
            current * self._player_sync_idle_factor,
        )
        self._player_sync_idle_current_interval = current

        return self._apply_randomization(
            current,
            minimum,
            self._player_sync_idle_max_interval,
        )
