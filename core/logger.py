
import threading
import queue
import sys
import time

_log_lock = threading.Lock()
_log_queue = queue.Queue(maxsize=10000)
_writer_thread = None
_dropped_count = 0

INFO_MODE = True
DEBUG_MODE = False
PACKET_LOG_MODE = False
EVENT_LOG_MODE = False
CHAT_LOG_MODE = True
DIALOG_LOG_MODE = True
GAMETEXT_LOG_MODE = True


def _writer_loop():
    while True:
        try:
            message = _log_queue.get(timeout=0.5)
            if message is None:
                break
            with _log_lock:
                sys.__stdout__.write(message + "\n")
                sys.__stdout__.flush()
        except queue.Empty:
            continue
        except Exception:
            pass


def _ensure_writer():
    global _writer_thread
    if _writer_thread is None or not _writer_thread.is_alive():
        _writer_thread = threading.Thread(target=_writer_loop, daemon=True)
        _writer_thread.start()


def _timestamp() -> str:
    return time.strftime("[%H:%M:%S]")


def _add_timestamps(message: str) -> str:
    prefixed = []
    for line in str(message).split("\n"):
        if line.strip():
            prefixed.append(f"{_timestamp()} {line}")
        else:
            prefixed.append(line)
    return "\n".join(prefixed)


def _safe_print(message: str, add_timestamp: bool = True) -> None:
    _ensure_writer()
    global _dropped_count
    try:
        text = _add_timestamps(message) if add_timestamp else str(message)
        _log_queue.put_nowait(text)
    except queue.Full:
        _dropped_count += 1


def configure(
    *,
    info: bool | None = None,
    debug: bool | None = None,
    packet: bool | None = None,
    event: bool | None = None,
    chat: bool | None = None,
    dialog: bool | None = None,
    gametext: bool | None = None,
) -> None:
    global INFO_MODE
    global DEBUG_MODE
    global PACKET_LOG_MODE
    global EVENT_LOG_MODE
    global CHAT_LOG_MODE
    global DIALOG_LOG_MODE
    global GAMETEXT_LOG_MODE

    if info is not None:
        INFO_MODE = bool(info)

    if debug is not None:
        DEBUG_MODE = bool(debug)

    if packet is not None:
        PACKET_LOG_MODE = bool(packet)

    if event is not None:
        EVENT_LOG_MODE = bool(event)

    if chat is not None:
        CHAT_LOG_MODE = bool(chat)

    if dialog is not None:
        DIALOG_LOG_MODE = bool(dialog)

    if gametext is not None:
        GAMETEXT_LOG_MODE = bool(gametext)


def raw(message: str, *, add_timestamp: bool = False) -> None:
    _safe_print(str(message), add_timestamp=add_timestamp)


def info(message: str) -> None:
    if INFO_MODE:
        _safe_print(f"[*] {message}")


def debug(message: str) -> None:
    if DEBUG_MODE:
        _safe_print(f"[DEBUG] {message}")


def packet(message: str) -> None:
    if PACKET_LOG_MODE:
        _safe_print(f"[PACKET] {message}")


def event(message: str) -> None:
    if EVENT_LOG_MODE:
        _safe_print(f"[EVENT] {message}")

def audio(message: str) -> None:
    if INFO_MODE:
        _safe_print(f"[AUDIO] Playing stream: {message}")

def chat(message: str) -> None:
    if CHAT_LOG_MODE:
        _safe_print(f"[CHAT] {message}")


def dialog(message: str) -> None:
    if DIALOG_LOG_MODE:
        _safe_print(message)


def gametext(message: str) -> None:
    if GAMETEXT_LOG_MODE:
        _safe_print(f"[GAMETEXT] {message}")


def warn(message: str) -> None:
    _safe_print(f"[WARN] {message}")


def error(message: str) -> None:
    _safe_print(f"[ERROR] {message}")

def rpc_parse_error(message: str) -> None:
    _safe_print(f"[RPC PARSE ERROR] {message}")

def auth(message: str) -> None:
    if INFO_MODE:
        _safe_print(f"[AUTH] {message}")


def proxy(message: str) -> None:
    if INFO_MODE:
        _safe_print(f"[PROXY] {message}")


def get_dropped_count() -> int:
    return _dropped_count


def shutdown():
    _log_queue.put(None)
    if _writer_thread and _writer_thread.is_alive():
        _writer_thread.join(timeout=2.0)


class TimestampStdout:

    def __init__(self, raw=None):
        self._raw = raw if raw is not None else sys.__stdout__
        self._buf = ""

    def write(self, s) -> None:
        if not s:
            return

        parts = (self._buf + str(s)).split("\n")
        self._buf = parts.pop()

        for line in parts:
            if line.strip():
                self._raw.write(f"{_timestamp()} {line}\n")
            else:
                self._raw.write(line + "\n")

    def flush(self) -> None:
        if self._buf.strip():
            self._raw.write(f"{_timestamp()} {self._buf}\n")
            self._buf = ""
        self._raw.flush()

    def writelines(self, lines) -> None:
        for line in lines:
            self.write(line)

    def isatty(self) -> bool:
        try:
            return self._raw.isatty()
        except Exception:
            return False

    @property
    def encoding(self):
        try:
            return self._raw.encoding
        except Exception:
            return "utf-8"

    def __getattr__(self, name):
        return getattr(self._raw, name)


def install_stdout_timestamps() -> None:
    if isinstance(sys.stdout, TimestampStdout):
        return
    sys.stdout = TimestampStdout(sys.__stdout__)
