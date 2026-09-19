
import socket
from typing import Optional

from core import logger


class DirectUDPTransport:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None

    def connect(self) -> bool:
        self.close()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)
        self.sock.connect((self.host, self.port))

        return True

    def send(self, data: bytes) -> None:
        if self.sock is None:
            return

        self.sock.send(data)

    def recv(self, buffer_size: int = 4096) -> bytes | None:
        if self.sock is None:
            return None

        try:
            return self.sock.recv(buffer_size)

        except socket.timeout:
            return None

        except BlockingIOError:
            return None

        except OSError:
            return None

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            except Exception:
                pass

        self.sock = None


class Network:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

        self.transport = None
        self.proxy_manager = None

        self.last_error: str | None = None

    def set_proxy_manager(self, proxy_manager) -> None:
        self.proxy_manager = proxy_manager

    def connect(self) -> bool:
        self.close()
        self.last_error = None

        try:
            transport = None

            proxy_configured = False

            if self.proxy_manager is not None:
                try:
                    proxy_configured = bool(self.proxy_manager.is_configured())
                except Exception:
                    proxy_configured = False

                if proxy_configured:
                    proxy_info = self.proxy_manager.info()
                    transport = self.proxy_manager.create_transport(
                        self.host,
                        self.port,
                    )

                    if transport is None:
                        raise RuntimeError("Proxy is configured, but proxy transport was not created")

                    logger.info(
                        f"Using {str(proxy_info.get('type') or 'proxy').upper()} "
                        f"UDP transport for {self.host}:{self.port}; "
                        "no direct UDP socket will be opened"
                    )

                elif bool(
                    getattr(
                        self.proxy_manager.session,
                        "_proxy_required",
                        False,
                    )
                ):
                    raise RuntimeError(
                        "Direct UDP blocked: proxy is required but not configured"
                    )

            if transport is None:
                transport = DirectUDPTransport(
                    self.host,
                    self.port,
                )

            self.transport = transport
            self.transport.connect()

            return True

        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Connect failed: {e}")
            self.close()
            return False

    def send(self, data: bytes) -> None:
        if self.transport is None:
            return

        self.transport.send(data)

    def recv(self, buffer_size: int = 4096) -> bytes | None:
        if self.transport is None:
            return None

        return self.transport.recv(buffer_size)

    def close(self) -> None:
        if self.transport is not None:
            try:
                self.transport.close()
            except Exception:
                pass

        self.transport = None
