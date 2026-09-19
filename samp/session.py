
import time
import threading
import queue
from collections import deque
from functools import partial

from .packets import PacketBuilder
from .constants import PacketPriority
from .sender import PacketSender
from .packet_handler import SampPacketHandler
from .proxy import ProxyManager
from core import logger
from core.http_ping import HttpPrePing
from logic.managers import ServerInfo, AllPlayersInfo, ChatInfo, StreamInfo
from logic.events import emitter
from logic.registration import AutoRegistration, RegistrationConfig
from logic.json_ui import JsonUI, JsonUIConfig
from .interfaces import build_json_packet

ENTER_VEHICLE_SYNC_STATE_DELAY = 3.0

CONNECTED_HANDSHAKE_STAGE_TIMEOUT = 15.0
INIT_GAME_HANDSHAKE_TIMEOUT = 15.0
OPEN_CONNECTION_REQUEST_MAX_ATTEMPTS = 5
OPEN_CONNECTION_REQUEST_RETRY_INTERVAL = 3.0
POST_ACCEPT_INTERNAL_PING_COUNT = 2

HANDSHAKE_PACKET_TYPES = frozenset(
    {
        "open_connection_reply",
        "auth_key",
        "connection_request_accepted",
        "invalid_password",
    }
)

TRANSPORT_CONNECT_MAX_ATTEMPTS = 3
TRANSPORT_CONNECT_RETRY_DELAY = 0.75

class SampSession:

    def __init__(
        self,
        protocol,
        server_ip: str,
        server_port: int,
        nickname: str,
        sync_scheduler,
        fps: float = 100.0,
        pings_ips_continuous: bool = False,
        server_password: str | None = None,
        http_pre_ping: bool = True,
        http_pre_ping_port: int = 80,
        http_pre_ping_timeout: float = 5.0,
        http_pre_ping_host_suffix: str = "blackrussia.online",
        http_server_names: dict[str, str] | None = None,
        registration: RegistrationConfig | None = None,
        json_ui: JsonUIConfig | None = None,
    ):
        self.api = None
        self._emit_callback = lambda event, *args, **kwargs: None

        self.protocol = protocol
        self.server_ip = server_ip
        self.server_port = server_port
        self.nickname = nickname
        self.server_password = str(server_password) if server_password else None
        self.pings_ips_continuous = bool(pings_ips_continuous)
        self._first_connect = True
        self.http_pre_ping = HttpPrePing(
            self, enabled=http_pre_ping, port=http_pre_ping_port,
            timeout=http_pre_ping_timeout, host_suffix=http_pre_ping_host_suffix,
            server_names=http_server_names,
        )

        self.connected = False
        self._incoming_queue = deque()
        self._proxy_required = False

        self.server_info = ServerInfo()
        self.players = AllPlayersInfo()
        self.chat = ChatInfo()
        self.stream = StreamInfo()

        self.players.bot.rate_player = max(0.0, float(sync_scheduler.rate_player_min))

        self.sync = sync_scheduler
        self.sync.session = self

        self._server_challenge = None

        self.handler = SampPacketHandler(self)

        self._runtime_reset_counter = 0

        self.fps = max(1.0, min(1000.0, float(fps)))
        self._network_tick_interval = 1.0 / self.fps
        self.connection_start_time = None

        self._network_thread = None
        self._network_running = False

        self._background_recv_enabled = False

        self._reconnect_lock = threading.Lock()
        self._reconnect_state_lock = threading.Lock()
        self._reconnecting = False
        self._reconnect_thread = None
        self._init_game_received = threading.Event()
        self._handshake_packets = queue.Queue()
        self._handshake_recovery_pending = False
        self._handshake_state_lock = threading.Lock()

        self._connection_request_sent = False

        self._handshake_stage = "open_connection_reply"

        self._spawn_lock = threading.Lock()
        self._rpc_spawn_queued = False

        self._update_scores_pings_continuous = bool(
            pings_ips_continuous
        )
        self._update_scores_pings_interval = 15.0
        self._next_update_scores_pings_time = 0.0
        self._scores_pings_request_lock = threading.Lock()
        self._last_scores_pings_on_demand_time = 0.0
        self._scores_pings_on_demand_min_interval = 0.5

        if hasattr(self, "players") and hasattr(self.players, "bot"):
            if hasattr(self.players.bot, "set_onfoot"):
                self.players.bot.set_onfoot()

        self._last_server_packet_time = time.time()
        self._server_silence_timeout = 20.0

        self.proxy = ProxyManager(self)
        self._sender = PacketSender(self)
        self.registration = AutoRegistration(self, registration)
        self.json_ui = JsonUI(self, json_ui)

    def send_json(self, interface_id: int, data: dict, *, packet_name: str = "interface_sync") -> bool:
        packet = build_json_packet(interface_id, data)
        if not self.connected:
            return False
        self._sender.send(packet, packet_name=packet_name)
        self._emit_callback("onSendJSON", interface_id, data, key=interface_id)
        return True

    def attach_api(self, api) -> None:

        self.api = api
        self._emit_callback = lambda event, *args, **kwargs: emitter.emit(event, api, *args, **kwargs)


    def _api_autopickup_tick(self) -> None:
        if self.api is None:
            return

        self.api.autopickup_tick()

    def _api_reset_caches(self) -> None:
        if self.api is None:
            return

        self.api.reset_api_caches()

    def _api_emit_coord_move_end(self, result: dict) -> None:
        if self.api is None:
            return

        self.api._emit_coord_move_end(result)

    def _network_loop(self):
        normal_packets_per_tick = 32
        normal_recv_time_per_tick = 0.005
        burst_packets_per_tick = 128
        burst_recv_time_per_tick = 0.015
        burst_ticks_remaining = 0

        while self._network_running:
            loop_started = time.monotonic()

            if self.connected:
                tick_start = time.monotonic()

                try:
                    t0 = time.monotonic()

                    received_datagrams = 0

                    if self._background_recv_enabled:
                        received_datagrams = self.protocol.pump_network()

                        if received_datagrams:
                            self._mark_server_packet_received()

                    pump_finished = time.monotonic()
                    pump_elapsed = pump_finished - t0

                    self.registration.tick()
                    self.protocol.update()

                    recv_elapsed = 0.0
                    sync_elapsed = 0.0

                    if self._background_recv_enabled:
                        recv_start = time.monotonic()
                        processed = 0
                        burst_mode = burst_ticks_remaining > 0
                        packet_limit = burst_packets_per_tick if burst_mode else normal_packets_per_tick
                        receive_budget = (
                            burst_recv_time_per_tick
                            if burst_mode
                            else normal_recv_time_per_tick
                        )
                        recv_time_limit = max(
                            0.0,
                            receive_budget - pump_elapsed,
                        )

                        while processed < packet_limit:
                            if time.monotonic() - recv_start >= recv_time_limit:
                                break

                            pkt = self._recv_one()

                            if pkt is None:
                                break

                            self._mark_server_packet_received()

                            if (
                                not self._init_game_received.is_set()
                                and pkt.get("type") in HANDSHAKE_PACKET_TYPES
                            ):
                                self._handshake_packets.put(pkt)

                            processed += 1

                            if pkt.get("type") == "disconnection_notification":
                                self._handle_disconnection_notification()
                                break

                        recv_elapsed = time.monotonic() - recv_start
                        receive_work_elapsed = pump_elapsed + recv_elapsed
                        if (
                            processed >= normal_packets_per_tick
                            or receive_work_elapsed >= normal_recv_time_per_tick
                        ):
                            burst_ticks_remaining = 5
                        elif burst_ticks_remaining > 0:
                            burst_ticks_remaining -= 1

                        sync_start = time.monotonic()
                        self._maybe_queue_rpc_spawn()
                        self.sync.tick()
                        self._api_autopickup_tick()
                        self._maybe_send_update_scores_and_pings()
                        sync_elapsed = time.monotonic() - sync_start

                        if not self._network_running:
                            break

                    self._check_server_silence_timeout()

                    if not self._network_running:
                        break

                    self.registration.tick()
                    self.protocol.update()

                    elapsed = time.monotonic() - tick_start

                    if elapsed > 0.250:
                        logger.warn(
                            f"tick took {elapsed:.3f}s | "
                            f"pump={pump_elapsed:.3f}s | "
                            f"recv={recv_elapsed:.3f}s | "
                            f"sync={sync_elapsed:.3f}s"
                        )

                except Exception as e:
                    logger.warn(f"{e}")

            sleep_for = self._network_tick_interval - (
                time.monotonic() - loop_started
            )
            if sleep_for > 0.0:
                time.sleep(sleep_for)

    def _start_network_loop(self):
        if self._network_thread and self._network_thread.is_alive():
            if self._network_running:
                return

            if threading.current_thread() is not self._network_thread:
                self._network_thread.join(timeout=1.0)

        self._network_running = True

        self._network_thread = threading.Thread(
            target=self._network_loop,
            daemon=True
        )

        self._network_thread.start()

    def _stop_network_loop(self):
        self._network_running = False

        if self._network_thread is None:
            return

        if threading.current_thread() is self._network_thread:
            return

        if self._network_thread.is_alive():
            self._network_thread.join(timeout=1.0)

    def reset_runtime_state(
        self,
        reason: str = "connect",
        emit_event: bool = True,
    ) -> None:

        old_coord_delay = self.players.bot.coord_delay

        try:
            self._incoming_queue.clear()
        except Exception:
            self._incoming_queue = deque()

        self.server_info = ServerInfo()
        self.players = AllPlayersInfo()
        self.chat = ChatInfo()
        self.stream = StreamInfo()

        self._api_reset_caches()

        try:
            self.players.bot.set_coord_delay(old_coord_delay)
        except Exception:
            pass

        try:
            if hasattr(self.players.bot, "set_onfoot"):
                self.players.bot.set_onfoot()
        except Exception:
            pass

        self.handler = SampPacketHandler(self)

        self._runtime_reset_counter += 1

        logger.info(
            "Runtime state reset | "
            f"reason={reason} | counter={self._runtime_reset_counter}"
        )

        if emit_event:
            self._emit_callback(
                "onStateReset",
                reason,
                self._runtime_reset_counter,
            )

    def recv_samp_packet(self, process_all: bool = False) -> dict | None:
        if not self.connected:
            return None

        self.registration.tick()
        self.protocol.update()

        if process_all:
            first_packet = None
            all_packets = self.recv_all_packets()

            for pkt in all_packets:
                if first_packet is None:
                    first_packet = pkt

                if pkt.get("type") == "disconnection_notification":
                    self.connected = False
                    return pkt

            return first_packet

        return self._recv_one()

    def _recv_one(self) -> dict | None:
        if not self.connected:
            return None

        if self._incoming_queue:
            pkt = self._incoming_queue.popleft()

            if pkt.get("type") == "disconnection_notification":
                self.connected = False

            return pkt

        raknet_packet = self.protocol.recv_and_parse()

        if raknet_packet is None:
            return None

        if isinstance(raknet_packet, list):
            for pkt in raknet_packet:
                processed = self.handler.process_packet(pkt)

                if processed:
                    self._incoming_queue.append(processed)

            if self._incoming_queue:
                pkt = self._incoming_queue.popleft()

                if pkt.get("type") == "disconnection_notification":
                    self.connected = False

                return pkt

            return None

        return self.handler.process_packet(raknet_packet)

    def recv_all_packets(self) -> list[dict]:
        if not self.connected:
            return []

        packets = []
        self.registration.tick()
        self.protocol.update()

        while self._incoming_queue:
            pkt = self._incoming_queue.popleft()

            if pkt.get("type") == "disconnection_notification":
                self.connected = False

            packets.append(pkt)

        while True:
            pkt = self.protocol.recv_and_parse()

            if pkt is None:
                break

            if isinstance(pkt, list):
                for p in pkt:
                    processed = self.handler.process_packet(p)

                    if processed:
                        packets.append(processed)
            else:
                processed = self.handler.process_packet(pkt)

                if processed:
                    packets.append(processed)

        return packets

    def is_connected(self) -> bool:
        return self.connected

    def setserveraddress(self, ip: str, port: int) -> None:
        ip = str(ip).strip()
        port = int(port)

        self.server_ip = ip
        self.server_port = port

        network = getattr(self.protocol, "network", None)
        if network is not None:
            network.host = ip
            network.port = port

    def session_ms(self) -> int:
        if self.connection_start_time is None:
            return 0

        return int((time.time() - self.connection_start_time) * 1000)

    def is_reconnecting(self) -> bool:
        return self._reconnecting

    def is_handshake_recovery_pending(self) -> bool:
        with self._handshake_state_lock:
            return bool(self._handshake_recovery_pending)

    def mark_init_game_received(self) -> None:
        self._init_game_received.set()
        with self._handshake_state_lock:
            self._handshake_recovery_pending = False

    def report_handshake_failure(self, stage: str, reason: str) -> None:
        stage = str(stage or "unknown")
        reason = str(reason or "unknown handshake failure")

        with self._handshake_state_lock:
            self._handshake_recovery_pending = True

        self.connected = False
        self._background_recv_enabled = False
        self.sync.stop()
        self._stop_network_loop()

        try:
            self.protocol.network.close()
        except Exception:
            pass

        self._mark_proxy_transport_disconnected()
        self._reset_protocol_runtime_state()

        self._emit_callback(
            "onHandshakeFailed",
            stage,
            reason,
            str(self.server_ip),
            int(self.server_port),
        )

    def _mark_server_packet_received(self) -> None:
        self._last_server_packet_time = time.time()

    def _handle_disconnection_notification(self) -> None:
        logger.info("Server sent disconnection_notification. Connection closed.")

        self._background_recv_enabled = False
        self.sync.stop()
        self._stop_network_loop()

    def _check_server_silence_timeout(self) -> None:
        if not self.connected:
            return

        if self._reconnecting:
            return

        if not self._background_recv_enabled:
            return

        elapsed = time.time() - self._last_server_packet_time

        if elapsed < self._server_silence_timeout:
            return

        logger.warn(
            f"No packets from server for {elapsed:.1f}s. Reconnecting..."
        )

        try:
            self._emit_callback(
                "onServerTimeout",
                elapsed,
                self._server_silence_timeout,
            )
        except Exception as e:
            logger.warn(f"onServerTimeout emit failed: {e}")

        self.reconnect(delay=1.0, threaded=True)

    def _reset_session_runtime_flags(self) -> None:
        self.registration.reset()
        self.json_ui.reset()

        self._background_recv_enabled = False
        self._init_game_received.clear()
        self._handshake_packets = queue.Queue()
        self._connection_request_sent = False
        self._handshake_stage = "open_connection_reply"

        self._rpc_spawn_queued = False

        self.sync.reset()

        self._next_update_scores_pings_time = 0.0
        with self._scores_pings_request_lock:
            self._last_scores_pings_on_demand_time = 0.0

        self._last_server_packet_time = time.time()

    def _reset_for_connect(self):
        self.http_pre_ping.reset_session()

        self.connection_start_time = time.time()
        self.connected = True

        self._reset_session_runtime_flags()

        if not getattr(self, "_first_connect", True):
            self.reset_runtime_state(
                reason="reconnect",
                emit_event=True,
            )

        self._first_connect = False

    def _reset_after_disconnect(self, reason: str) -> None:

        self._reset_session_runtime_flags()

        self.reset_runtime_state(
            reason=str(reason or "disconnect"),
            emit_event=True,
        )

        self.connected = False

    def _maybe_queue_rpc_spawn(self) -> None:
        if not self.connected:
            return

        if self._rpc_spawn_queued:
            return

        spawn_response = getattr(
            self.server_info,
            "spawn_response",
            None
        )

        if spawn_response is not True:
            return

        with self._spawn_lock:
            if self._rpc_spawn_queued:
                return

            spawn_response = getattr(
                self.server_info,
                "spawn_response",
                None
            )

            if spawn_response is not True:
                return

            self._rpc_spawn_queued = True
            self.send_rpc_spawn()

    def _reset_protocol_runtime_state(self) -> None:
        protocol = self.protocol

        if hasattr(protocol, "message_number"):
            protocol.message_number = 0

        if hasattr(protocol, "pending_acks"):
            protocol.pending_acks.clear()

        if hasattr(protocol, "resend_queue"):
            protocol.resend_queue.clear()

        if hasattr(protocol, "ordering_indices"):
            protocol.ordering_indices = [0] * 16

        if hasattr(protocol, "reset_ack_state"):
            protocol.reset_ack_state()
        else:
            if hasattr(protocol, "_ack_pending"):
                protocol._ack_pending.clear()

            if hasattr(protocol, "_ping_ms"):
                protocol._ping_ms = 100

            if hasattr(protocol, "_next_ack_time"):
                protocol._next_ack_time = time.monotonic()

        if hasattr(protocol, "_recv_buffer"):
            protocol._recv_buffer.clear()

        if hasattr(protocol, "_send_queues"):
            protocol._send_queues = [
                deque()
                for _ in range(PacketPriority.NUMBER_OF_PRIORITIES)
            ]

        if hasattr(protocol, "_split_packets"):
            protocol._split_packets.clear()

    def _mark_proxy_transport_connected(self) -> None:
        proxy = getattr(self, "proxy", None)

        if proxy is None:
            return

        if not proxy.is_configured():
            return

        proxy.mark_connected()

    def _mark_proxy_transport_error(self, error: str) -> None:
        proxy = getattr(self, "proxy", None)

        if proxy is None:
            return

        if not proxy.is_configured():
            return

        proxy.mark_error(error)

    def _mark_proxy_transport_disconnected(self) -> None:
        proxy = getattr(self, "proxy", None)

        if proxy is None:
            return

        if not proxy.is_configured():
            return

        proxy.mark_disconnected(emit_event=True)

    def _send_raw(self, payload: bytes, event_name: str | None = None) -> None:
        if not self.connected:
            return

        self.protocol.send_raw(payload)

        if event_name:
            self._emit_callback(event_name)

    def _choose_wclass(self, preferred: int = 0) -> int:
        d_spawns_available = self.server_info.d_spawns_available

        preferred = int(preferred)

        if d_spawns_available <= 0:
            return 0

        if 0 <= preferred < d_spawns_available:
            return preferred

        return 0

    def send_rpc_request_class(
        self,
        preferred_wclass: int = 0,
    ) -> None:
        wclass = self._choose_wclass(preferred_wclass)

        self._sender.send(
            PacketBuilder.rpc_build("request_class", wclass),
            rpc_name="request_class",
        )


    def send_rpc_spawn(
        self,
    ) -> None:
        logger.info("Queueing RPC_SPAWN")

        self._sender.send(
            PacketBuilder.rpc_build("spawn"),
            rpc_name="spawn",
        )

        self.sync.start()
        if self._update_scores_pings_continuous:
            self._next_update_scores_pings_time = (
                time.time() + float(self._update_scores_pings_interval)
            )
        else:
            self._next_update_scores_pings_time = 0.0

        logger.info("Player sync started")

        try:
            self._emit_callback("onSpawn")
        except Exception as e:
            logger.warn(f"onSpawn emit failed: {e}")

    def _maybe_send_update_scores_and_pings(self) -> None:
        if not self.connected:
            return

        if not self._background_recv_enabled:
            return

        if not bool(
            getattr(
                self,
                "_update_scores_pings_continuous",
                False,
            )
        ):
            return

        interval = float(getattr(self, "_update_scores_pings_interval", 15.0))

        if interval <= 0.0:
            return

        now = time.time()

        if self._next_update_scores_pings_time <= 0.0:
            self._next_update_scores_pings_time = now + interval
            return

        if now < self._next_update_scores_pings_time:
            return

        self._next_update_scores_pings_time = now + interval
        self.send_rpc_update_scores_and_pings()

    def request_scores_and_pings_on_demand(self) -> bool:

        if not self.connected or not self._background_recv_enabled:
            return False

        now = time.monotonic()
        min_interval = max(
            0.0,
            float(
                getattr(
                    self,
                    "_scores_pings_on_demand_min_interval",
                    0.5,
                )
            ),
        )

        with self._scores_pings_request_lock:
            elapsed = now - float(
                self._last_scores_pings_on_demand_time
            )
            if elapsed < min_interval:
                return False

            self._last_scores_pings_on_demand_time = now

        self.send_rpc_update_scores_and_pings()
        return True

    def send_rpc_update_scores_and_pings(self) -> None:
        if not self.connected:
            return

        self._sender.send(
            PacketBuilder.rpc_build("update_scores_and_pings"),
            rpc_name="update_scores_and_pings",
        )

    def send_open_connection_request(
        self,
        attempt: int | None = None,
        max_attempts: int | None = None,
        cookie: int = 0x6969,
    ) -> None:
        reason = "before OPEN_CONNECTION_REQUEST"
        if attempt is not None and max_attempts is not None:
            reason += f" {attempt}/{max_attempts}"
        self.http_pre_ping.ping(reason=reason)
        self._send_raw(
            PacketBuilder.open_connection_request(cookie),
            event_name="onRequestConnect"
        )

    def send_connection_request(self) -> None:
        self._sender.send(
            PacketBuilder.connection_request(self.server_password),
            packet_name="connection_request",
        )

    def send_auth_key_response(
        self,
        server_key_24: str,
    ) -> None:
        self._sender.send(
            PacketBuilder.auth_key_response(server_key_24),
            packet_name="auth_key_response",
        )

    def send_new_incoming_connection(self) -> None:
        self._sender.send(
            PacketBuilder.new_incoming_connection(
                self.server_ip,
                self.server_port
            ),
            packet_name="new_incoming_connection",
        )

    def send_internal_ping(
        self,
        session_ms: int = 0,
    ) -> None:
        self._sender.send(
            PacketBuilder.internal_ping(session_ms),
            packet_name="internal_ping",
        )

    def send_connected_pong(
        self,
        receiver_ms: int,
        sender_ms: int,
    ) -> None:
        self._sender.send(
            PacketBuilder.connected_pong(
                receiver_ms,
                sender_ms
            ),
            packet_name="connected_pong",
        )

    def send_received_static_data(self) -> None:
        self._sender.send(
            PacketBuilder.received_static_data(),
            packet_name="received_static_data",
        )

    def send_detect_lost_connections(self) -> None:
        raise NotImplementedError("PyRakBR defines no DETECT_LOST_CONNECTIONS packet ID")

    def send_disconnection_notification(self) -> None:

        if not self.connected:
            return

        logger.info("Sending DISCONNECTION_NOTIFICATION")

        self._sender.send(
            PacketBuilder.disconnection_notification(),
            packet_name="disconnection_notification",
        )

    def send_rpc_client_join(
        self,
    ) -> None:
        logger.info(f"Sending RPC_CLIENT_JOIN ({self.nickname})")

        self._sender.send(
            PacketBuilder.rpc_build(
                "client_join",
                self.nickname,
                self._server_challenge,
            ),
            rpc_name="client_join",
        )

    def _send_post_handshake_packets(self) -> None:
        self.send_new_incoming_connection()

        for _ in range(POST_ACCEPT_INTERNAL_PING_COUNT):
            self.send_internal_ping(self.session_ms())

        self.send_received_static_data()
        self.send_rpc_client_join()
        self._mark_server_packet_received()

    def _fail_open_connection(self, attempts: int) -> bool:
        server_ip = str(self.server_ip)
        server_port = int(self.server_port)
        reason = f"no reply after {attempts} requests"

        logger.warn(
            f"No OPEN_CONNECTION_REPLY after {attempts} requests | "
            f"server={server_ip}:{server_port}"
        )
        self._emit_callback(
            "onOpenConnectionReplyTimeout",
            attempts,
            server_ip,
            server_port,
        )
        self.report_handshake_failure("open_connection_reply", reason)
        return False

    def _fail_handshake_stage(self, stage: str, reason: str) -> bool:
        logger.warn(f"{reason}")
        self.report_handshake_failure(stage, reason)
        return False

    def _open_transport(self) -> bool:
        proxy = getattr(self, "proxy", None)

        if (
            getattr(self, "_proxy_required", False)
            and (proxy is None or not proxy.is_configured())
        ):
            error = "Direct UDP blocked: proxy is required but not configured"
            logger.error(f"{error}")
            self.report_handshake_failure("transport", error)
            return False

        if proxy is not None and proxy.is_configured():
            info = proxy.info()
            logger.info(
                "SOCKS5 UDP proxy required/enabled; "
                f"direct UDP to {self.server_ip}:{self.server_port} "
                "is disabled | "
                f"proxy={info.get('host')}:{info.get('port')}"
            )

        network = self.protocol.network
        last_error = "network connect failed"

        for attempt in range(1, TRANSPORT_CONNECT_MAX_ATTEMPTS + 1):


            if network.connect():
                self._mark_proxy_transport_connected()
                return True

            last_error = network.last_error or last_error

            if attempt < TRANSPORT_CONNECT_MAX_ATTEMPTS:
                logger.warn(
                    "Transport connect failed | "
                    f"error={last_error}; retrying in "
                    f"{TRANSPORT_CONNECT_RETRY_DELAY:.2f}s"
                )
                time.sleep(TRANSPORT_CONNECT_RETRY_DELAY)

        self._mark_proxy_transport_error(last_error)
        self.report_handshake_failure("transport", last_error)
        return False

    def connect(self) -> bool:
        self.connected = False
        self._background_recv_enabled = False
        self.sync.stop()
        self._stop_network_loop()
        self._reset_protocol_runtime_state()

        if not self._open_transport():
            return False

        self._reset_for_connect()
        self._background_recv_enabled = True
        self._start_network_loop()

        attempts = 0
        next_open_request_at = 0.0
        stage_deadline = 0.0

        logger.info(f"Connecting to {self.server_ip}:{self.server_port}")

        while self.connected:
            if self._init_game_received.is_set():

                return True

            now = time.monotonic()

            if not self._connection_request_sent and now >= next_open_request_at:
                if attempts >= OPEN_CONNECTION_REQUEST_MAX_ATTEMPTS:
                    return self._fail_open_connection(attempts)

                attempts += 1

                self.send_open_connection_request(
                    attempt=attempts,
                    max_attempts=OPEN_CONNECTION_REQUEST_MAX_ATTEMPTS,
                )
                next_open_request_at = (
                    now + OPEN_CONNECTION_REQUEST_RETRY_INTERVAL
                )

            if self._connection_request_sent and now >= stage_deadline:
                return self._fail_handshake_stage(
                    self._handshake_stage,
                    self._handshake_timeout_reason(self._handshake_stage),
                )

            try:
                packet = self._handshake_packets.get(timeout=0.05)
            except queue.Empty:
                continue

            reaction = self._HANDSHAKE_REACTIONS.get(packet.get("type"))

            if reaction is None:
                continue

            if reaction(self, packet) is False:
                return False

            stage_deadline = time.monotonic() + self._handshake_stage_timeout(
                self._handshake_stage
            )

        return False


    @staticmethod
    def _handshake_stage_timeout(stage: str) -> float:
        if stage == "init_game":
            return float(INIT_GAME_HANDSHAKE_TIMEOUT)

        return float(CONNECTED_HANDSHAKE_STAGE_TIMEOUT)

    @staticmethod
    def _handshake_timeout_reason(stage: str) -> str:
        if stage == "init_game":
            return (
                "no INIT_GAME after CLIENT_JOIN within "
                f"{INIT_GAME_HANDSHAKE_TIMEOUT:.1f}s"
            )

        return (
            f"no {stage.upper()} after "
            f"{CONNECTED_HANDSHAKE_STAGE_TIMEOUT:.1f}s"
        )

    def _on_open_connection_reply(self, packet: dict) -> bool | None:
        if self._connection_request_sent:
            return None

        self._connection_request_sent = True

        logger.info("Received OPEN_CONNECTION_REPLY")
        self.send_connection_request()
        self._handshake_stage = "auth_key"
        return None

    def _on_auth_key(self, packet: dict) -> bool | None:
        server_key = packet.get("key")

        if not server_key:
            self._fail_handshake_stage(
                "auth_key",
                "received empty AUTH_KEY",
            )
            return False

        logger.info(f"AUTH_KEY: {server_key}")

        self.send_auth_key_response(server_key)
        self._handshake_stage = "connection_request_accepted"
        return None

    def _on_connection_request_accepted(self, packet: dict) -> bool | None:
        logger.info("CONNECTION_REQUEST_ACCEPTED")
        self._server_challenge = packet.get("server_challenge")
        self._send_post_handshake_packets()
        self._handshake_stage = "init_game"
        return None

    def _on_invalid_password(self, packet: dict) -> bool:
        logger.error("Invalid server password.")
        self.report_handshake_failure(
            "invalid_password",
            "Invalid server password.",
        )
        return False

    _HANDSHAKE_REACTIONS = {
        "open_connection_reply": _on_open_connection_reply,
        "auth_key": _on_auth_key,
        "connection_request_accepted": _on_connection_request_accepted,
        "invalid_password": _on_invalid_password,
    }

    def disconnect(self, reason: str = "user request") -> None:
        if self.connected:
            try:
                self.send_disconnection_notification()
            except Exception as e:
                logger.warn(
                    "Failed to send DISCONNECTION_NOTIFICATION: "
                    f"{e}"
                )

        self.connected = False
        self._background_recv_enabled = False
        self.sync.stop()
        self._stop_network_loop()

        try:
            self.protocol.network.close()
        except Exception:
            pass

        self._mark_proxy_transport_disconnected()
        self._reset_protocol_runtime_state()
        self._reset_after_disconnect(reason)

        logger.info(f"Disconnected | reason={reason}")

    def _run_reconnect(self, delay: float) -> bool:
        try:
            with self._reconnect_lock:
                logger.info("Reconnecting...")
                self.disconnect(reason="reconnect")

                if delay:
                    logger.info(
                        f"Waiting {delay:.1f} seconds before reconnect..."
                    )
                    time.sleep(delay)

                connected = self.connect()
                logger.info(
                    "Reconnect complete"
                    if connected
                    else "Reconnect failed"
                )
                return connected
        finally:
            with self._reconnect_state_lock:
                self._reconnecting = False
                self._reconnect_thread = None

    def reconnect(self, delay: float = 30.0, threaded: bool = True):
        try:
            requested_delay = max(0.0, float(delay))
        except (TypeError, ValueError):
            requested_delay = 30.0

        with self._reconnect_state_lock:
            if self._reconnecting:
                logger.info("Reconnect already in progress; request ignored")
                return self._reconnect_thread if threaded else False

            self._reconnecting = True

            if threaded:
                self._reconnect_thread = threading.Thread(
                    target=self._run_reconnect,
                    args=(requested_delay,),
                    name="bot-reconnect",
                    daemon=True,
                )

        if threaded:
            thread = self._reconnect_thread
            thread.start()
            return thread

        return self._run_reconnect(requested_delay)
