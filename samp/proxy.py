
import socket
import struct
import ipaddress
import threading
import ssl
from base64 import b64encode
from urllib.parse import unquote, urlsplit

from core import logger

from dataclasses import dataclass



@dataclass
class ProxyConfig:
    host: str
    port: int
    login: str | None = None
    password: str | None = None
    requested_type: str | None = None

    @property
    def has_auth(self) -> bool:
        return bool(self.login or self.password)

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"

    @property
    def full_address(self) -> str:
        value = self.address
        if self.login is not None or self.password is not None:
            value += f":{self.login or ''}:{self.password or ''}"
        return value


class ProxyProtocolError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        proxy_type: str | None = None,
    ):
        super().__init__(message)
        self.code = str(code)
        self.proxy_type = proxy_type


class UnsupportedProxyTypeError(ProxyProtocolError):
    pass


def parse_proxy_address(proxy_address: str) -> ProxyConfig:
    if not isinstance(proxy_address, str):
        raise TypeError("proxy_address must be str")

    raw = proxy_address.strip()
    if "://" in raw:
        parsed = urlsplit(raw)
        requested_type = str(parsed.scheme or "").strip().lower()
        if requested_type == "socks5h":
            requested_type = "socks5"
        if requested_type not in {"socks5", "socks4", "socks4a", "http", "https"}:
            raise ValueError(f"Unsupported proxy scheme: {parsed.scheme!r}")
        if not parsed.hostname:
            raise ValueError("Proxy host is empty")
        if parsed.port is None:
            raise ValueError("Proxy port is required")
        return ProxyConfig(
            host=str(parsed.hostname),
            port=int(parsed.port),
            login=None if parsed.username is None else unquote(parsed.username),
            password=None if parsed.password is None else unquote(parsed.password),
            requested_type=requested_type,
        )

    parts = raw.split(":")

    if len(parts) not in (2, 4):
        raise ValueError(
            "Invalid proxy format. Use ip:port or ip:port:login:password"
        )

    host = parts[0].strip()
    port_raw = parts[1].strip()

    if not host:
        raise ValueError("Proxy host is empty")

    try:
        port = int(port_raw)
    except ValueError as exc:
        raise ValueError("Proxy port must be integer") from exc

    if not (1 <= port <= 65535):
        raise ValueError("Proxy port must be in range 1..65535")

    if len(parts) == 2:
        return ProxyConfig(
            host=host,
            port=port,
        )

    login = parts[2]
    password = parts[3]

    return ProxyConfig(
        host=host,
        port=port,
        login=login,
        password=password,
    )


def _probe_socks5(config: ProxyConfig, timeout: float) -> bool:
    methods = [0x00]
    if config.has_auth:
        methods.append(0x02)
    with socket.create_connection((config.host, config.port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(b"\x05" + bytes((len(methods),)) + bytes(methods))
        response = sock.recv(2)
        return len(response) == 2 and response[0] == 0x05


def _http_connect_request(config: ProxyConfig, target_host: str, target_port: int) -> bytes:
    lines = [
        f"CONNECT {target_host}:{int(target_port)} HTTP/1.1",
        f"Host: {target_host}:{int(target_port)}",
        "Proxy-Connection: Keep-Alive",
    ]
    if config.has_auth:
        token = b64encode(
            f"{config.login or ''}:{config.password or ''}".encode("utf-8")
        ).decode("ascii")
        lines.append(f"Proxy-Authorization: Basic {token}")
    return ("\r\n".join(lines) + "\r\n\r\n").encode("ascii", errors="ignore")


def _probe_http(
    config: ProxyConfig,
    target_host: str,
    target_port: int,
    timeout: float,
    *,
    use_tls: bool,
) -> bool:
    raw_sock = socket.create_connection((config.host, config.port), timeout=timeout)
    try:
        raw_sock.settimeout(timeout)
        if use_tls:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            sock = context.wrap_socket(raw_sock, server_hostname=config.host)
        else:
            sock = raw_sock
        try:
            sock.sendall(_http_connect_request(config, target_host, target_port))
            response = sock.recv(16)
            return response.upper().startswith(b"HTTP/")
        finally:
            if sock is not raw_sock:
                sock.close()
    finally:
        try:
            raw_sock.close()
        except Exception:
            pass


def _probe_socks4(
    config: ProxyConfig,
    target_host: str,
    target_port: int,
    timeout: float,
) -> bool:
    user = (config.login or "").encode("utf-8", errors="ignore")[:255]
    try:
        packed_host = socket.inet_aton(target_host)
        suffix = b""
    except OSError:
        packed_host = b"\x00\x00\x00\x01"
        suffix = target_host.encode("idna") + b"\x00"
    request = (
        b"\x04\x01"
        + struct.pack(">H", int(target_port))
        + packed_host
        + user
        + b"\x00"
        + suffix
    )
    with socket.create_connection((config.host, config.port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(request)
        response = sock.recv(8)
        return (
            len(response) >= 2
            and response[0] in (0x00, 0x04)
            and response[1] in (0x5A, 0x5B, 0x5C, 0x5D)
        )


def detect_proxy_type(
    config: ProxyConfig,
    target_host: str,
    target_port: int,
    timeout: float = 5.0,
) -> str:
    timeout = max(0.1, float(timeout))
    requested = config.requested_type
    probe_timeout = timeout if requested else min(timeout, 1.5)
    probes = {
        "socks5": lambda: _probe_socks5(config, probe_timeout),
        "socks4": lambda: _probe_socks4(config, target_host, target_port, probe_timeout),
        "socks4a": lambda: _probe_socks4(config, target_host, target_port, probe_timeout),
        "http": lambda: _probe_http(
            config, target_host, target_port, probe_timeout, use_tls=False
        ),
        "https": lambda: _probe_http(
            config, target_host, target_port, probe_timeout, use_tls=True
        ),
    }
    order = (requested,) if requested else ("socks5", "http", "socks4", "https")
    errors = []
    for proxy_type in order:
        try:
            if probes[proxy_type]():
                return proxy_type
        except Exception as exc:
            errors.append(f"{proxy_type}: {exc}")

    detail = "; ".join(errors[-2:]) if errors else "no protocol probe matched"
    raise ProxyProtocolError(
        f"Proxy protocol was not detected ({detail})",
        code="protocol_not_detected",
        proxy_type=requested,
    )


class Socks5UDPTransport:
    def __init__(
        self,
        config: ProxyConfig,
        target_host: str,
        target_port: int,
        timeout: float = 5.0,
    ):
        self.config = config
        self.target_host = target_host
        self.target_port = target_port
        self.timeout = timeout

        self.tcp_sock: socket.socket | None = None
        self.udp_sock: socket.socket | None = None
        self.udp_relay: tuple[str, int] | None = None

    def is_ready(self) -> bool:
        return (
            self.tcp_sock is not None
            and self.udp_sock is not None
            and self.udp_relay is not None
        )

    def connect(self) -> bool:
        if self.is_ready():
            return True

        self.close()

        logger.info(
            f"Connecting to proxy "
            f"{self.config.host}:{self.config.port} "
            f"auth={self.config.has_auth}"
        )

        stage = "TCP connect"

        try:
            tcp = socket.create_connection(
                (self.config.host, self.config.port),
                timeout=self.timeout,
            )
            tcp.settimeout(self.timeout)

            self.tcp_sock = tcp

            stage = "method negotiation/authentication"
            self._negotiate(tcp)

            stage = "UDP ASSOCIATE"
            relay_host, relay_port = self._udp_associate(tcp)

            if relay_host in ("0.0.0.0", "::"):
                relay_host = self.config.host

            stage = "UDP relay socket setup"
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_sock = udp

            udp.setblocking(False)
            udp.connect((relay_host, relay_port))

            self.udp_relay = (relay_host, relay_port)

        except socket.timeout as exc:
            self.close()
            raise TimeoutError(
                f"SOCKS5 {stage} timed out after {float(self.timeout):.1f}s"
            ) from exc
        except Exception:
            self.close()
            raise

        logger.info(
            f"UDP ASSOCIATE ready | "
            f"relay={relay_host}:{relay_port} | "
            f"target={self.target_host}:{self.target_port}"
        )

        return True

    def send(self, data: bytes) -> None:
        if self.udp_sock is None:
            return

        packet = self._build_udp_packet(
            self.target_host,
            self.target_port,
            data,
        )

        self.udp_sock.send(packet)

    def recv(self, buffer_size: int = 4096) -> bytes | None:
        if self.udp_sock is None:
            return None

        try:
            data = self.udp_sock.recv(buffer_size + 512)

        except socket.timeout:
            return None

        except BlockingIOError:
            return None

        except OSError:
            return None

        return self._strip_udp_packet(data)

    def close(self) -> None:
        if self.udp_sock is not None:
            try:
                self.udp_sock.close()
            except Exception:
                pass

        if self.tcp_sock is not None:
            try:
                self.tcp_sock.close()
            except Exception:
                pass

        self.udp_sock = None
        self.tcp_sock = None
        self.udp_relay = None

    def _negotiate(self, tcp: socket.socket) -> None:
        methods = [0x00]

        if self.config.has_auth:
            methods.append(0x02)

        tcp.sendall(
            b"\x05" +
            bytes([len(methods)]) +
            bytes(methods)
        )

        response = self._recv_exact(tcp, 2)

        if response[0] != 0x05:
            raise RuntimeError("Invalid SOCKS5 version in method response")

        method = response[1]

        if method == 0xFF:
            raise RuntimeError("SOCKS5 proxy rejected all auth methods")

        if method == 0x00:
            return

        if method == 0x02:
            self._auth(tcp)
            return

        raise RuntimeError(f"Unsupported SOCKS5 auth method: {method}")

    def _auth(self, tcp: socket.socket) -> None:
        username = (self.config.login or "").encode("utf-8")
        password = (self.config.password or "").encode("utf-8")

        if len(username) > 255:
            raise RuntimeError("SOCKS5 username is too long")

        if len(password) > 255:
            raise RuntimeError("SOCKS5 password is too long")

        tcp.sendall(
            b"\x01" +
            bytes([len(username)]) +
            username +
            bytes([len(password)]) +
            password
        )

        response = self._recv_exact(tcp, 2)

        if response[0] != 0x01:
            raise RuntimeError("Invalid SOCKS5 auth response version")

        if response[1] != 0x00:
            raise RuntimeError("SOCKS5 username/password auth failed")

    def _udp_associate(self, tcp: socket.socket) -> tuple[str, int]:
        request = (
            b"\x05"
            b"\x03"
            b"\x00"
            b"\x01"
            b"\x00\x00\x00\x00"
            b"\x00\x00"
        )

        tcp.sendall(request)

        ver, rep, _rsv, atyp = self._recv_exact(tcp, 4)

        if ver != 0x05:
            raise RuntimeError("Invalid SOCKS5 UDP associate response version")

        if rep != 0x00:
            raise RuntimeError(
                f"SOCKS5 UDP associate failed, REP={rep}"
            )

        relay_host = self._read_addr(tcp, atyp)
        relay_port = struct.unpack(">H", self._recv_exact(tcp, 2))[0]

        return relay_host, relay_port

    def _build_udp_packet(
        self,
        host: str,
        port: int,
        payload: bytes,
    ) -> bytes:
        return (
            b"\x00\x00" +
            b"\x00" +
            self._pack_addr(host) +
            struct.pack(">H", port) +
            payload
        )

    def _strip_udp_packet(self, data: bytes) -> bytes | None:
        if len(data) < 10:
            return None

        if data[0] != 0x00 or data[1] != 0x00:
            return None

        frag = data[2]

        if frag != 0x00:
            return None

        atyp = data[3]
        offset = 4

        if atyp == 0x01:
            offset += 4

        elif atyp == 0x03:
            if offset >= len(data):
                return None

            domain_len = data[offset]
            offset += 1 + domain_len

        elif atyp == 0x04:
            offset += 16

        else:
            return None

        offset += 2

        if offset > len(data):
            return None

        return data[offset:]

    def _pack_addr(self, host: str) -> bytes:
        try:
            ip = ipaddress.ip_address(host)

            if ip.version == 4:
                return b"\x01" + ip.packed

            return b"\x04" + ip.packed

        except ValueError:
            domain = host.encode("idna")

            if len(domain) > 255:
                raise RuntimeError("SOCKS5 domain is too long")

            return b"\x03" + bytes([len(domain)]) + domain

    def _read_addr(self, tcp: socket.socket, atyp: int) -> str:
        if atyp == 0x01:
            raw = self._recv_exact(tcp, 4)
            return socket.inet_ntoa(raw)

        if atyp == 0x03:
            length = self._recv_exact(tcp, 1)[0]
            raw = self._recv_exact(tcp, length)
            return raw.decode("idna", errors="ignore")

        if atyp == 0x04:
            raw = self._recv_exact(tcp, 16)
            return socket.inet_ntop(socket.AF_INET6, raw)

        raise RuntimeError(f"Unsupported SOCKS5 ATYP: {atyp}")

    def _recv_exact(self, sock: socket.socket, size: int) -> bytes:
        data = bytearray()

        while len(data) < size:
            chunk = sock.recv(size - len(data))

            if not chunk:
                raise RuntimeError("Socket closed while reading SOCKS5 data")

            data.extend(chunk)

        return bytes(data)


def open_socks5_tcp_tunnel(
    config: ProxyConfig,
    target_host: str,
    target_port: int,
    timeout: float = 5.0,
) -> socket.socket:
    timeout = max(0.1, float(timeout))
    helper = Socks5UDPTransport(
        config=config,
        target_host=str(target_host),
        target_port=int(target_port),
        timeout=timeout,
    )
    sock = socket.create_connection((config.host, config.port), timeout=timeout)
    sock.settimeout(timeout)
    try:
        helper._negotiate(sock)
        sock.sendall(
            b"\x05\x01\x00"
            + helper._pack_addr(str(target_host))
            + struct.pack(">H", int(target_port))
        )
        ver, rep, _rsv, atyp = helper._recv_exact(sock, 4)
        if ver != 0x05:
            raise ProxyProtocolError(
                "Invalid SOCKS5 version in CONNECT response",
                code="tcp_tunnel_failed",
                proxy_type="socks5",
            )
        bound_host = helper._read_addr(sock, atyp)
        bound_port = struct.unpack(">H", helper._recv_exact(sock, 2))[0]
        if rep != 0x00:
            raise ProxyProtocolError(
                f"SOCKS5 CONNECT failed, REP={rep}",
                code="tcp_tunnel_failed",
                proxy_type="socks5",
            )
    except Exception:
        sock.close()
        raise

    logger.info(
        f"SOCKS5 TCP tunnel ready | proxy={config.address} | "
        f"target={target_host}:{int(target_port)} | bound={bound_host}:{bound_port}"
    )
    return sock


class ProxyManager:
    def __init__(self, session):
        self.session = session
        self.config: ProxyConfig | None = None
        self.connected = False
        self.last_error: str | None = None
        self.last_error_code: str | None = None
        self.detected_type: str | None = None
        self.last_detected_type: str | None = None
        self._lock = threading.RLock()
        self._prepared_transport: Socks5UDPTransport | None = None

    def _prepare(
        self,
        proxy_address: str,
        timeout: float,
    ) -> tuple[ProxyConfig, Socks5UDPTransport, str]:
        config = parse_proxy_address(proxy_address)
        target_host = str(getattr(self.session, "server_ip", "") or "").strip()
        target_port = int(getattr(self.session, "server_port", 5125))
        proxy_type = detect_proxy_type(
            config,
            target_host,
            target_port,
            timeout=timeout,
        )
        if proxy_type in {"http", "https"}:
            raise UnsupportedProxyTypeError(
                f"Proxy type {proxy_type.upper()} detected, but HTTP/HTTPS "
                "proxies do not provide the UDP tunnel required by RakNet",
                code="udp_not_supported",
                proxy_type=proxy_type,
            )
        if proxy_type in {"socks4", "socks4a"}:
            raise UnsupportedProxyTypeError(
                f"Proxy type {proxy_type.upper()} detected, but SOCKS4/SOCKS4a "
                "does not provide UDP ASSOCIATE required by RakNet",
                code="udp_not_supported",
                proxy_type=proxy_type,
            )

        probe = Socks5UDPTransport(
            config=config,
            target_host=target_host,
            target_port=target_port,
            timeout=max(0.1, float(timeout)),
        )

        try:
            probe.connect()
        except Exception:
            probe.close()
            raise
        return config, probe, proxy_type

    def _remember_error(self, exc: Exception) -> None:
        code = getattr(exc, "code", "connect_failed")
        proxy_type = getattr(exc, "proxy_type", None)
        with self._lock:
            self.last_error = str(exc)
            self.last_error_code = str(code)
            if proxy_type:
                self.last_detected_type = str(proxy_type)

    def connect(self, proxy_address: str, timeout: float = 5.0) -> bool:
        try:
            config, probe, proxy_type = self._prepare(proxy_address, timeout)
        except Exception as exc:
            self._remember_error(exc)
            label = str(getattr(exc, "proxy_type", None) or "unknown").upper()
            logger.error(
                f"connect rejected | type={label} | "
                f"address={str(proxy_address)!r} | error={exc}"
            )
            self.session._emit_callback(
                "onProxyError",
                self.info(),
                str(exc),
            )
            return False

        with self._lock:
            old_prepared = self._prepared_transport
            self.config = config
            self.connected = False
            self.last_error = None
            self.last_error_code = None
            self.detected_type = proxy_type
            self.last_detected_type = proxy_type
            self._prepared_transport = probe

        if old_prepared is not None and old_prepared is not probe:
            old_prepared.close()

        logger.info(
            f"configured | type={proxy_type.upper()} | "
            f"address={config.address} | auth={config.has_auth} | "
            "UDP transport prepared"
        )
        return True

    def change(self, proxy_address: str, timeout: float = 5.0) -> bool:
        old_info = self.info()
        try:
            config, probe, proxy_type = self._prepare(proxy_address, timeout)
        except Exception as exc:
            self._remember_error(exc)
            logger.error(
                f"change rejected; current proxy preserved | "
                f"new={str(proxy_address)!r} | error={exc}"
            )
            self.session._emit_callback(
                "onProxyError",
                self.info(),
                str(exc),
            )
            return False

        with self._lock:
            old_prepared = self._prepared_transport
            self.config = config
            self.connected = False
            self.last_error = None
            self.last_error_code = None
            self.detected_type = proxy_type
            self.last_detected_type = proxy_type
            self._prepared_transport = probe

        if old_prepared is not None and old_prepared is not probe:
            old_prepared.close()

        new_info = self.info()
        self.session._emit_callback("onProxyChange", old_info, new_info)
        logger.info(
            f"changed | old={old_info.get('host')}:{old_info.get('port')} | "
            f"new={config.address} | type={proxy_type.upper()}"
        )
        return True

    def disconnect(self, emit_event: bool = True) -> None:
        with self._lock:
            old_info = self.info()
            prepared = self._prepared_transport

            self.config = None
            self.connected = False
            self.last_error = None
            self.last_error_code = None
            self.detected_type = None
            self.last_detected_type = None
            self._prepared_transport = None

        if prepared is not None:
            prepared.close()

        if emit_event:
            self.session._emit_callback(
                "onProxyDisconnect",
                old_info,
            )

        logger.info("Proxy disabled")

    def create_transport(
        self,
        target_host: str,
        target_port: int,
    ) -> Socks5UDPTransport | None:
        with self._lock:
            config = self.config
            prepared = self._prepared_transport
            detected_type = self.detected_type

            if detected_type not in (None, "socks5"):
                raise UnsupportedProxyTypeError(
                    f"Proxy type {detected_type!r} cannot transport RakNet UDP",
                    code="udp_not_supported",
                    proxy_type=detected_type,
                )

            if prepared is not None:
                prepared_matches = (
                    prepared.config == config
                    and str(prepared.target_host) == str(target_host)
                    and int(prepared.target_port) == int(target_port)
                    and prepared.is_ready()
                )

                self._prepared_transport = None
            else:
                prepared_matches = False

        if config is None:
            if prepared is not None:
                prepared.close()
            return None

        if prepared_matches:
            logger.debug(
                f"Reusing prepared SOCKS5 UDP transport | "
                f"proxy={config.address} | target={target_host}:{int(target_port)}"
            )
            return prepared

        if prepared is not None:
            prepared.close()

        return Socks5UDPTransport(
            config=config,
            target_host=target_host,
            target_port=target_port,
        )

    def tcp_request(
        self,
        target_host: str,
        target_port: int,
        payload: bytes,
        timeout: float = 5.0,
        recv_size: int = 4096,
    ) -> bytes:
        with self._lock:
            config = self.config
            proxy_type = self.detected_type

        if config is None:
            raise ProxyProtocolError(
                "Proxy is not configured",
                code="not_configured",
            )
        if proxy_type != "socks5":
            raise UnsupportedProxyTypeError(
                f"Proxy type {proxy_type!r} cannot open a TCP tunnel",
                code="tcp_tunnel_not_supported",
                proxy_type=proxy_type,
            )
        if not isinstance(payload, (bytes, bytearray, memoryview)):
            raise TypeError("payload must be bytes-like")

        with open_socks5_tcp_tunnel(
            config,
            str(target_host),
            int(target_port),
            timeout=timeout,
        ) as sock:
            sock.sendall(bytes(payload))
            return sock.recv(max(1, int(recv_size)))

    def mark_connected(self) -> None:
        with self._lock:
            self.connected = True
            self.last_error = None
            self.last_error_code = None
            info = self.info()

        self.session._emit_callback(
            "onProxyConnect",
            info,
        )

    def mark_disconnected(self, emit_event: bool = True) -> None:
        with self._lock:
            old_info = self.info()
            self.connected = False

        if emit_event:
            self.session._emit_callback(
                "onProxyDisconnect",
                old_info,
            )

    def mark_error(self, error: str) -> None:
        with self._lock:
            self.connected = False
            self.last_error = error
            self.last_error_code = "transport_error"
            info = self.info()

        self.session._emit_callback(
            "onProxyError",
            info,
            error,
        )

    def is_connected(self) -> bool:
        return self.connected

    def is_configured(self) -> bool:
        return self.config is not None

    def info(self) -> dict:
        if self.config is None:
            return {
                "configured": False,
                "connected": self.connected,
                "host": None,
                "port": None,
                "type": self.detected_type or self.last_detected_type,
                "last_detected_type": self.last_detected_type,
                "has_auth": False,
                "last_error": self.last_error,
                "last_error_code": self.last_error_code,
            }

        return {
            "configured": True,
            "connected": self.connected,
            "host": self.config.host,
            "port": self.config.port,
            "type": self.detected_type,
            "last_detected_type": self.last_detected_type,
            "has_auth": self.config.has_auth,
            "last_error": self.last_error,
            "last_error_code": self.last_error_code,
        }
