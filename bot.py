

import os
import importlib.util
import ctypes
import threading
import time

from core.network import Network
from core import security
from core import logger
from logic.registration import RegistrationConfig
from logic.json_ui import JsonUIConfig
from core.protocol import RakNetProtocol

from samp.api import BotAPI
from samp.session import SampSession
from logic.events import emitter


MAX_NICKNAME_LEN = 20
BAD_NICKNAME_LEN_ERROR = "Bad NickName Len (MAX 20 CHARS)"


def validate_nickname_length(nickname: str) -> None:
    nickname = str(nickname or "")

    if len(nickname) > int(MAX_NICKNAME_LEN):
        raise ValueError(BAD_NICKNAME_LEN_ERROR)


class Bot:
    def __init__(
        self,
        host: str,
        port: int = 7777,
        nickname: str = "Bot",
        sync_scheduler=None,
        fps: float = 100.0,
        pings_ips_continuous: bool = False,
        proxy_address: str | None = None,
        server_password: str | None = None,
        registration: RegistrationConfig | None = None,
        json_ui: JsonUIConfig | None = None,
    ):
        validate_nickname_length(nickname)

        self.host = host
        self.port = port

        self.network = Network(host, port)
        self.protocol = RakNetProtocol(self.network, security)

        self.session = SampSession(
            self.protocol,
            self.host,
            self.port,
            nickname,
            sync_scheduler=sync_scheduler,
            fps=fps,
            pings_ips_continuous=pings_ips_continuous,
            server_password=server_password,
            registration=registration,
            json_ui=json_ui,
        )

        self.api = BotAPI(self.session)

        self.network.set_proxy_manager(self.session.proxy)

        if proxy_address:
            try:
                configured = bool(self.session.proxy.connect(str(proxy_address)))
            except Exception as exc:
                raise ValueError(f"failed to configure --proxy: {exc}") from exc
            if not configured:
                raise ValueError("failed to configure --proxy")
            self.session._proxy_required = True

        self._window_title_running = True
        self._window_title_thread = None
        self._start_window_title_updater()

        self._load_scripts()

        emitter.emit("onBotCreated", self.api)

    @staticmethod
    def _safe_window_title_value(value, fallback: str = "?") -> str:
        try:
            value = str(value)
        except Exception:
            return fallback

        value = " ".join(value.replace("\r", " ").replace("\n", " ").split())
        return value if value else fallback

    @staticmethod
    def _set_process_window_title(title: str) -> None:
        title = Bot._safe_window_title_value(title, "Bot")

        if os.name == "nt":
            try:
                ctypes.windll.kernel32.SetConsoleTitleW(title)
                return
            except Exception:
                return

        try:
            logger.raw(f"\033]0;{title}\007")
        except Exception:
            pass

    def _build_window_title(self) -> str:
        nick = self._safe_window_title_value(
            getattr(self.session, "nickname", None),
            self._safe_window_title_value(getattr(self, "host", "Bot"), "Bot"),
        )

        try:
            player_id = int(self.api.getbotid())
        except Exception:
            player_id = -1

        try:
            hostname = self.api.getservername()
        except Exception:
            hostname = ""

        hostname = self._safe_window_title_value(
            hostname,
            f"{self.host}:{self.port}",
        )

        try:
            x, y, z = self.api.getbotposition()
            xyz = f"{float(x):.2f}, {float(y):.2f}, {float(z):.2f}"
        except Exception:
            xyz = "0.00, 0.00, 0.00"

        try:
            ping = int(self.session.players.get_bot_ping())
        except Exception:
            ping = 0

        try:
            lvl = int(self.session.players.get_bot_score())
        except Exception:
            lvl = 0

        try:
            money = int(self.api.getbotmoney())
        except Exception:
            money = 0

        try:
            hp = float(self.api.getbothealth())
        except Exception:
            hp = 0.0

        return (
            f"{nick} ({player_id}), "
            f"ping: {ping}, "
            f"{hostname}, "
            f"XYZ: {xyz}, "
            f"lvl: {lvl}, "
            f"money: {money}, "
            f"hp: {hp:.0f}"
        )

    def _window_title_worker(self) -> None:
        last_title = None

        while getattr(self, "_window_title_running", False):
            try:
                title = self._build_window_title()

                if title != last_title:
                    self._set_process_window_title(title)
                    last_title = title

            except Exception:
                pass

            time.sleep(0.5)

    def _start_window_title_updater(self) -> None:
        if self._window_title_thread is not None:
            return

        self._window_title_thread = threading.Thread(
            target=self._window_title_worker,
            name="bot-window-title",
            daemon=True,
        )
        self._window_title_thread.start()

    def _load_scripts(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        scripts_dir = os.path.join(base_dir, "scripts")

        if not os.path.exists(scripts_dir):
            os.makedirs(scripts_dir)
            return

        for file in sorted(os.listdir(scripts_dir)):
            if not file.endswith(".py"):
                continue

            path = os.path.join(scripts_dir, file)
            spec = importlib.util.spec_from_file_location(file[:-3], path)

            if spec is None or spec.loader is None:
                continue

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            logger.info(f"Script Loaded: {file}")

    def connect(self) -> bool:
        logger.raw("""
        
        ██████╗ ██╗   ██╗██████╗  █████╗ ██╗  ██╗██████╗ ██████╗
        ██╔══██╗╚██╗ ██╔╝██╔══██╗██╔══██╗██║ ██╔╝██╔══██╗██╔══██╗
        ██████╔╝ ╚████╔╝ ██████╔╝███████║█████╔╝ ██████╔╝██████╔╝
        ██╔═══╝   ╚██╔╝  ██╔══██╗██╔══██║██╔═██╗ ██╔══██╗██╔══██╗
        ██║        ██║   ██║  ██║██║  ██║██║  ██╗██████╔╝██║  ██║
        ╚═╝        ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝


        """)

        return self.api.connect()

    def close(self) -> None:
        self._window_title_running = False

        try:
            emitter.emit("onBotStopping", self.api)
            self.api.disconnect()
        finally:
            if (
                self._window_title_thread is not None
                and self._window_title_thread.is_alive()
                and threading.current_thread() is not self._window_title_thread
            ):
                self._window_title_thread.join(timeout=1.0)

            emitter.shutdown(wait=True)