import random
import socket
import threading
from datetime import datetime, timedelta


DEFAULT_HTTP_PORT = 80
DEFAULT_HTTP_TIMEOUT = 5.0
DEFAULT_HTTP_HOST_SUFFIX = "blackrussia.online"

HTTP_USER_AGENT_ANDROID_VERSIONS = (12, 13, 14, 15)
HTTP_USER_AGENT_LOCALES = ("ru-RU", "en-US", "uk-UA", "kk-KZ")
HTTP_USER_AGENT_LOCALE_CHANCE = 0.85


def _generate_android_device_model() -> str:
    family = random.choices(
        (
            "samsung_a",
            "samsung_s",
            "pixel",
            "xiaomi",
            "redmi",
            "poco",
            "oneplus",
            "realme",
            "oppo",
            "vivo",
        ),
        weights=(24, 15, 10, 10, 10, 8, 7, 6, 5, 5),
        k=1,
    )[0]

    if family == "samsung_a":
        series = random.choice((13, 14, 15, 23, 24, 25, 33, 34, 35, 53, 54, 55))
        generation = random.choice((5, 6))
        region = random.choice(("B", "F", "M", "N"))
        return f"SM-A{series}{generation}{region}"

    if family == "samsung_s":
        generation = random.choice((90, 91, 92, 93))
        tier = random.choice((1, 6, 8))
        region = random.choice(("B", "U", "N"))
        return f"SM-S{generation}{tier}{region}"

    if family == "pixel":
        generation = random.randint(6, 9)
        variant = random.choice(("", "a", " Pro", " Pro XL"))
        if generation == 6 and variant == " Pro XL":
            variant = " Pro"
        return f"Pixel {generation}{variant}"

    if family == "xiaomi":
        return (
            f"{random.randint(2100000, 2509999)}"
            f"{random.choice(('G', 'I', 'C', 'Y'))}"
        )

    if family == "redmi":
        year = random.randint(22, 25)
        month = random.randint(1, 12)
        revision = random.randint(1, 99)
        return (
            f"{year:02d}{month:02d}{random.randint(10, 99):02d}"
            f"RN{revision:02d}{random.choice(('A', 'G', 'I'))}"
        )

    if family == "poco":
        series = random.choice(("M", "X", "F", "C"))
        generation = random.randint(3, 7)
        suffix = random.choice(("", " Pro", " GT"))
        return f"POCO {series}{generation}{suffix}"

    if family in {"oneplus", "oppo"}:
        return f"CPH{random.randint(2300, 2699)}"

    if family == "realme":
        return f"RMX{random.randint(3300, 3999)}"

    return f"V{random.randint(2100, 2399)}"


def _generate_android_build_id(android_version: int) -> str:
    build_profiles = {
        12: (("SP1A", "SQ3A"), datetime(2021, 8, 1), datetime(2023, 3, 31)),
        13: (("TP1A", "TQ3A"), datetime(2022, 6, 1), datetime(2024, 6, 30)),
        14: (("UP1A", "UQ1A"), datetime(2023, 10, 1), datetime(2025, 9, 30)),
        15: (("AP3A", "BP1A"), datetime(2024, 8, 1), datetime(2026, 6, 30)),
    }

    prefixes, date_from, date_to = build_profiles[int(android_version)]
    days = max(0, (date_to - date_from).days)
    build_date = date_from + timedelta(days=random.randint(0, days))
    patch = random.randint(1, 99)

    return f"{random.choice(prefixes)}.{build_date:%y%m%d}.{patch:03d}"


def generate_http_user_agent() -> str:
    android_version = random.choice(HTTP_USER_AGENT_ANDROID_VERSIONS)
    device_model = _generate_android_device_model()
    build_id = _generate_android_build_id(android_version)

    parts = [
        "Linux",
        "U",
        f"Android {android_version}",
    ]

    if random.random() < float(HTTP_USER_AGENT_LOCALE_CHANCE):
        parts.append(random.choice(HTTP_USER_AGENT_LOCALES))

    parts.append(f"{device_model} Build/{build_id}")
    return f"Dalvik/2.1.0 ({'; '.join(parts)})"


class HttpPrePing:
    

    def __init__(
        self,
        session,
        *,
        enabled: bool = True,
        port: int = DEFAULT_HTTP_PORT,
        timeout: float = DEFAULT_HTTP_TIMEOUT,
        host_suffix: str = DEFAULT_HTTP_HOST_SUFFIX,
        server_names: dict[str, str] | None = None,
    ):
        
        self.session = session
        self.enabled = bool(enabled)
        self.port = int(port)
        self.timeout = max(0.1, float(timeout))
        self.host_suffix = str(host_suffix or "").strip().strip(".")
        self.server_names = {
            str(host).strip(): str(name).strip()
            for host, name in dict(server_names or {}).items()
            if str(host).strip() and str(name).strip()
        }
        self._lock = threading.RLock()
        self._session_user_agent: str | None = None

    def reset_session(self) -> None:
        with self._lock:
            self._session_user_agent = None

    def user_agent(self) -> str:
        with self._lock:
            if self._session_user_agent is None:
                self._session_user_agent = generate_http_user_agent()
                print(
                    "[HTTP UA] generated for current session: "
                    f"{self._session_user_agent}",
                    flush=True,
                )

            return self._session_user_agent

    def _http_host_for_server(self, host: str) -> str:
        host = str(host or "").strip()
        server_name = self.server_names.get(host, "").strip()

        if server_name and self.host_suffix:
            return f"{server_name.lower()}.{self.host_suffix}"

        return host

    def _build_request(self, host: str, http_host: str) -> tuple[bytes, str]:
        user_agent = self.user_agent()
        request = (
            "GET / HTTP/1.1\r\n"
            f"User-Agent: {user_agent}\r\n"
            f"Host: {http_host or host}\r\n"
            "Connection: Keep-Alive\r\n"
            "Accept-Encoding: gzip\r\n"
            "\r\n"
        ).encode("ascii", errors="ignore")
        return request, user_agent

    def _request_via_proxy(self, host: str, request: bytes) -> bytes:
        return self.session.proxy.tcp_request(
            host,
            self.port,
            request,
            timeout=self.timeout,
            recv_size=1024,
        )

    def _request_direct(self, host: str, request: bytes) -> bytes:
        with socket.create_connection(
            (host, self.port),
            timeout=self.timeout,
        ) as sock:
            sock.settimeout(self.timeout)
            sock.sendall(request)
            return sock.recv(1024)

    def ping(self, reason: str = "before OPEN_CONNECTION_REQUEST") -> bool:
        if not self.enabled:
            return True

        host = str(getattr(self.session, "server_ip", "") or "").strip()
        if not host:
            print(f"[HTTP] pre-ping skipped: empty server host | reason={reason}")
            return False

        http_host = self._http_host_for_server(host)
        request, user_agent = self._build_request(host, http_host)
        proxy = getattr(self.session, "proxy", None)
        try:
            proxy_configured = bool(
                proxy is not None and proxy.is_configured()
            )
        except Exception:
            proxy_configured = False
        route = "proxy" if proxy_configured else "direct"

        print(
            f"[HTTP] pre-ping start | reason={reason} | "
            f"target={host}:{self.port} | Host={http_host} | "
            f"route={route} | UA={user_agent}",
            flush=True,
        )

        try:
            if proxy_configured:
                response = self._request_via_proxy(host, request)
            else:
                response = self._request_direct(host, request)

            if not response:
                print(
                    f"[HTTP] pre-ping failed: empty response | "
                    f"target={host}:{self.port} | reason={reason}",
                    flush=True,
                )
                return False

            print(
                f"[HTTP] pre-ping done | target={host}:{self.port} | "
                f"Host={http_host} | route={route} | bytes={len(response)}",
                flush=True,
            )
            return True

        except Exception as exc:
            print(
                f"[HTTP] pre-ping failed | target={host}:{self.port} | "
                f"Host={http_host} | route={route} | reason={reason} | {exc}",
                flush=True,
            )
            return False