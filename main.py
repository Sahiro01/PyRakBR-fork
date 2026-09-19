
import argparse
import configparser
import json
import sys
import time
import os
import ctypes
import random
import re
from pathlib import Path

from bot import Bot, MAX_NICKNAME_LEN
from samp.sync import PlayerSyncScheduler
from logic.registration import RegistrationConfig
from logic.json_ui import JsonUIConfig
from core import logger
from core.logger import install_stdout_timestamps


NAMES_FILE = "names.txt"
SURNAMES_FILE = "surnames.txt"
SERVER_IPS_FILE = "server_ips.txt"
SCRIPTS_DIR = "scripts"

DISCONNECTED_RECONNECT_POLL = 0.05

_POSITIVE_FLOAT_PATTERN = (
    r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
)
_RATE_PLAYER_PATTERN = re.compile(
    rf"^\s*({_POSITIVE_FLOAT_PATTERN})"
    rf"(?:\s*-\s*({_POSITIVE_FLOAT_PATTERN}))?\s*$"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SA-MP Bot launcher",
    )

    parser.add_argument(
        "--config",
        default="config.ini",
        help="Путь к config.ini. По умолчанию: config.ini",
    )

    parser.add_argument(
        "--ip",
        "--host",
        dest="host",
        default=None,
        help="IP/host сервера. Можно указать ip:port.",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Порт сервера.",
    )

    parser.add_argument(
        "--nick",
        "--Nick",
        "--nickname",
        dest="nick",
        default=None,
        help="Ник бота.",
    )

    parser.add_argument(
        "--proxy",
        dest="proxy",
        default=None,
        help="SOCKS5 proxy: ip:port или ip:port:login:password.",
    )

    parser.add_argument(
        "--rate-player",
        "--rate_player",
        dest="rate_player",
        default=None,
        help="RATE_PLAYER для player sync: число или диапазон 0.05-0.06.",
    )

    parser.add_argument(
        "--coord-delay",
        "--coord_delay",
        dest="coord_delay",
        type=float,
        default=None,
        help="coord_delay для движения.",
    )

    parser.add_argument("--random-ip", dest="random_ip", action="store_true", default=None)
    parser.add_argument("--no-random-ip", dest="random_ip", action="store_false")

    parser.add_argument("--random-nick", dest="random_nick", action="store_true", default=None)
    parser.add_argument("--no-random-nick", dest="random_nick", action="store_false")

    return parser.parse_args(argv)


def _override(value, fallback):
    return fallback if value is None else value


def _parse_rate_player(value) -> tuple[float, float]:

    minimum, maximum = _parse_float_range(value, "RATE_PLAYER")

    if minimum == 0.0 and maximum > 0.0:
        raise ValueError(
            "RATE_PLAYER range cannot start at zero; use 0 to disable sync"
        )

    return minimum, maximum


def _parse_float_range(
    value,
    option: str,
    *,
    minimum_allowed: float = 0.0,
) -> tuple[float, float]:

    raw = "" if value is None else str(value).strip()
    match = _RATE_PLAYER_PATTERN.fullmatch(raw)

    if match is None:
        raise ValueError(
            f"{option} must be a number or a range, for example "
            "0.05 or 0.05-0.06"
        )

    minimum = float(match.group(1))
    maximum = float(match.group(2) or match.group(1))

    if minimum < minimum_allowed or maximum < minimum_allowed:
        raise ValueError(
            f"{option} cannot be less than {minimum_allowed:g}"
        )

    if minimum > maximum:
        raise ValueError(f"{option} range minimum cannot exceed maximum")

    return minimum, maximum


def _config_nonnegative_float(
    config: configparser.ConfigParser,
    section: str,
    option: str,
    fallback: float,
) -> float:
    value = config.getfloat(section, option, fallback=fallback)

    if value < 0.0:
        raise ValueError(f"{option} cannot be negative")

    return float(value)


def _split_host_port(value: str) -> tuple[str, int | None]:
    raw = str(value or "").strip()

    if not raw:
        return "", None

    if raw.count(":") == 1:
        host, port_text = raw.rsplit(":", 1)
        host = host.strip()
        port_text = port_text.strip()

        if host and port_text.isdigit():
            return host, int(port_text)

    return raw, None


def disable_windows_quick_edit() -> None:
    if os.name != "nt":
        return

    try:
        kernel32 = ctypes.windll.kernel32

        STD_INPUT_HANDLE = -10

        ENABLE_QUICK_EDIT_MODE = 0x0040
        ENABLE_EXTENDED_FLAGS = 0x0080
        ENABLE_INSERT_MODE = 0x0020

        handle = kernel32.GetStdHandle(STD_INPUT_HANDLE)

        mode = ctypes.c_uint()

        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return

        new_mode = mode.value
        new_mode |= ENABLE_EXTENDED_FLAGS
        new_mode &= ~ENABLE_QUICK_EDIT_MODE
        new_mode &= ~ENABLE_INSERT_MODE

        kernel32.SetConsoleMode(handle, new_mode)

        logger.info("Windows QuickEdit disabled")

    except Exception as e:
        logger.warn(f"Failed to disable QuickEdit: {e}")


def _base_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _file_candidates(filename: str) -> list[str]:

    base_dir = _base_dir()

    return [
        os.path.join(base_dir, filename),
        os.path.join(base_dir, SCRIPTS_DIR, filename),
    ]


def _resolve_existing_file(filename: str) -> str | None:
    for path in _file_candidates(filename):
        if os.path.exists(path):
            return path

    return None


def _read_non_empty_lines(path: str) -> list[str]:
    if not os.path.exists(path):
        logger.warn(f"File not found: {path}")
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            return [
                row.strip()
                for row in f
                if row.strip()
            ]

    except Exception as e:
        logger.warn(f"Failed to read {path}: {e}")
        return []


def _read_named_file_lines(filename: str) -> list[str]:
    path = _resolve_existing_file(filename)

    if path is None:
        checked = ", ".join(_file_candidates(filename))
        logger.warn(f"{filename} not found. Checked: {checked}")
        return []

    return _read_non_empty_lines(path)


def _normalize_nickname_part(value: str) -> str:
    value = str(value or "").strip()

    cleaned = "".join(
        ch
        for ch in value
        if ch.isalnum()
    )

    return cleaned


def _compose_random_nick(name: str, surname: str) -> str | None:
    name = _normalize_nickname_part(name)
    surname = _normalize_nickname_part(surname)

    if not name or not surname:
        return None

    max_body_len = int(MAX_NICKNAME_LEN) - 1

    if max_body_len < 2:
        return None

    if len(name) + len(surname) > max_body_len:
        if len(name) <= max_body_len // 2:
            name_len = len(name)
            surname_len = max_body_len - name_len
        elif len(surname) <= max_body_len // 2:
            surname_len = len(surname)
            name_len = max_body_len - surname_len
        else:
            name_len = max_body_len // 2
            surname_len = max_body_len - name_len

        name = name[:max(1, name_len)]
        surname = surname[:max(1, surname_len)]

    nick = f"{name}_{surname}"

    if len(nick) > int(MAX_NICKNAME_LEN):
        return None

    return nick


def generate_random_nick(
    names_file: str = NAMES_FILE,
    surnames_file: str = SURNAMES_FILE,
) -> str | None:

    names = _read_named_file_lines(names_file)
    surnames = _read_named_file_lines(surnames_file)

    if not names:
        logger.warn(f"{names_file} is empty or not found")
        return None

    if not surnames:
        logger.warn(f"{surnames_file} is empty or not found")
        return None

    for _ in range(50):
        nick = _compose_random_nick(
            random.choice(names),
            random.choice(surnames),
        )

        if nick and "_" in nick and len(nick) <= int(MAX_NICKNAME_LEN):
            return nick

    logger.warn("Failed to generate valid nickname")
    return None


def _parse_server_ip_row(row: str) -> tuple[str, str | None] | None:

    row = str(row or "").strip()

    if not row:
        return None

    if ":" in row:
        ip, server_name = row.split(":", 1)
        ip = ip.strip()
        server_name = server_name.strip() or None
    else:
        ip = row.strip()
        server_name = None

    if not ip:
        return None

    return ip, server_name


def load_server_ips(
    server_ips_file: str = SERVER_IPS_FILE,
) -> list[tuple[str, str | None]]:

    rows = _read_named_file_lines(server_ips_file)

    servers: list[tuple[str, str | None]] = []

    for row in rows:
        parsed = _parse_server_ip_row(row)

        if parsed is None:
            continue

        servers.append(parsed)

    return servers


def choose_random_server_ip(
    server_ips_file: str = SERVER_IPS_FILE,
) -> tuple[str, str | None] | None:
    servers = load_server_ips(server_ips_file)

    if not servers:
        logger.warn(
            f"{server_ips_file} is empty, missing, or invalid"
        )
        return None

    return random.choice(servers)


def load_config(
    config_path: str = "config.ini",
    args: argparse.Namespace | None = None,
) -> dict:
    config = configparser.ConfigParser()
    config.read(config_path, encoding="utf-8-sig")

    args = args or argparse.Namespace()
    cli_overrides: list[str] = []

    random_nick = config.getboolean(
        "Player",
        "random_nick",
        fallback=False,
    )

    random_ip = config.getboolean(
        "Connection",
        "random_ip",
        fallback=False,
    )

    if getattr(args, "random_nick", None) is not None:
        random_nick = bool(args.random_nick)
        cli_overrides.append("random_nick")

    if getattr(args, "random_ip", None) is not None:
        random_ip = bool(args.random_ip)
        cli_overrides.append("random_ip")

    config_nick = config.get(
        "Player",
        "nick",
        fallback="Bot",
    )

    cli_nick = getattr(args, "nick", None)

    if cli_nick:
        nick = str(cli_nick).strip()
        random_nick = False
        cli_overrides.append("nick")
    else:
        nick = config_nick

        if random_nick:
            generated_nick = generate_random_nick()

            if generated_nick:
                nick = generated_nick
                logger.info(f"Generated nick: {nick}")
            else:
                logger.warn(
                    "Failed to generate nick, "
                    f"using config nick: {config_nick}"
                )

    config_host = config.get(
        "Connection",
        "host",
        fallback="127.0.0.1",
    )

    config_port = config.getint("Connection", "port", fallback=5125)
    try:
        fps = config.getfloat("Connection", "FPS", fallback=100.0)
    except (TypeError, ValueError):
        logger.warn("Invalid FPS in config.ini, using 100")
        fps = 100.0

    fps = max(1.0, min(1000.0, float(fps)))
    pings_ips_continuous = config.getboolean(
        "Connection",
        "PINGS_IPS_CONTINUOUS",
        fallback=False,
    )
    server_password = config.get(
        "Connection",
        "server_password",
        fallback="",
    ).strip() or None
    cli_host = getattr(args, "host", None)
    cli_port = getattr(args, "port", None)

    host = config_host
    port = config_port
    random_ip_server_name = None

    if cli_host:
        parsed_host, parsed_port = _split_host_port(cli_host)

        if parsed_host:
            host = parsed_host
            random_ip = False
            cli_overrides.append("host")

        if parsed_port is not None:
            port = int(parsed_port)
            cli_overrides.append("port")

    if cli_port is not None:
        port = int(cli_port)
        cli_overrides.append("port")

    if random_ip:
        random_server = choose_random_server_ip()

        if random_server is not None:
            host, random_ip_server_name = random_server

            if random_ip_server_name:
                logger.info(
                    f"Selected server: "
                    f"{host} ({random_ip_server_name})"
                )
            else:
                logger.info(f"Selected server: {host}")
        else:
            logger.warn(
                "Failed to choose random IP, "
                f"using config host: {config_host}"
            )

    disable_quick_edit = config.getboolean(
        "Console",
        "disable_quick_edit",
        fallback=True,
    )

    rate_player_raw = _override(
        getattr(args, "rate_player", None),
        config.get("Player", "RATE_PLAYER", fallback="0.200"),
    )
    rate_player_min, rate_player_max = _parse_rate_player(rate_player_raw)
    rate_vehicle_raw = config.get(
        "Player",
        "RATE_VEHICLE",
        fallback=str(rate_player_raw),
    )
    rate_vehicle_min, rate_vehicle_max = _parse_float_range(
        rate_vehicle_raw,
        "RATE_VEHICLE",
    )
    if rate_vehicle_min == 0.0 and rate_vehicle_max > 0.0:
        raise ValueError(
            "RATE_VEHICLE range cannot start at zero; use 0 to disable sync"
        )

    sync_idle_after_min, sync_idle_after_max = _parse_float_range(
        config.get("Player", "SYNC_IDLE_AFTER", fallback="0"),
        "SYNC_IDLE_AFTER",
    )
    (
        sync_idle_backoff_factor_min,
        sync_idle_backoff_factor_max,
    ) = _parse_float_range(
        config.get(
            "Player",
            "SYNC_IDLE_BACKOFF_FACTOR",
            fallback="1",
        ),
        "SYNC_IDLE_BACKOFF_FACTOR",
        minimum_allowed=1.0,
    )
    (
        player_idle_interval_multiplier_min,
        player_idle_interval_multiplier_max,
    ) = _parse_float_range(
        config.get(
            "Player",
            "PLAYER_IDLE_INTERVAL_MULTIPLIER",
            fallback="1",
        ),
        "PLAYER_IDLE_INTERVAL_MULTIPLIER",
        minimum_allowed=1.0,
    )
    (
        vehicle_idle_interval_multiplier_min,
        vehicle_idle_interval_multiplier_max,
    ) = _parse_float_range(
        config.get(
            "Player",
            "VEHICLE_IDLE_INTERVAL_MULTIPLIER",
            fallback="1",
        ),
        "VEHICLE_IDLE_INTERVAL_MULTIPLIER",
        minimum_allowed=1.0,
    )
    rate_player_jitter_max = _config_nonnegative_float(
        config,
        "Player",
        "RATE_PLAYER_JITTER_MAX",
        0.0,
    )
    rate_player_fluctuation_chance = _config_nonnegative_float(
        config,
        "Player",
        "RATE_PLAYER_FLUCTUATION_CHANCE",
        0.0,
    )
    rate_player_fluctuation_max = _config_nonnegative_float(
        config,
        "Player",
        "RATE_PLAYER_FLUCTUATION_MAX",
        0.0,
    )
    if rate_player_fluctuation_chance > 1.0:
        raise ValueError(
            "RATE_PLAYER_FLUCTUATION_CHANCE must be between 0 and 1"
        )
    coord_delay = _override(
        getattr(args, "coord_delay", None),
        config.getfloat("Player", "coord_delay", fallback=0.0),
    )

    for name in ("rate_player", "coord_delay"):
        if getattr(args, name, None) is not None:
            cli_overrides.append(name)

    return {
        "host": host,
        "port": int(port),
        "fps": fps,
        "pings_ips_continuous": bool(pings_ips_continuous),
        "server_password": server_password,
        "registration": RegistrationConfig.from_config(config),
        "json_ui": JsonUIConfig.from_config(config),
        "random_ip": random_ip,
        "random_ip_server_name": random_ip_server_name,
        "nick": nick,
        "random_nick": random_nick,
        "rate_player": (rate_player_min + rate_player_max) / 2.0,
        "rate_player_min": rate_player_min,
        "rate_player_max": rate_player_max,
        "rate_vehicle_min": rate_vehicle_min,
        "rate_vehicle_max": rate_vehicle_max,
        "sync_idle_after_min": sync_idle_after_min,
        "sync_idle_after_max": sync_idle_after_max,
        "sync_idle_backoff_factor_min": sync_idle_backoff_factor_min,
        "sync_idle_backoff_factor_max": sync_idle_backoff_factor_max,
        "player_idle_interval_multiplier_min": (
            player_idle_interval_multiplier_min
        ),
        "player_idle_interval_multiplier_max": (
            player_idle_interval_multiplier_max
        ),
        "vehicle_idle_interval_multiplier_min": (
            vehicle_idle_interval_multiplier_min
        ),
        "vehicle_idle_interval_multiplier_max": (
            vehicle_idle_interval_multiplier_max
        ),
        "rate_player_jitter_max": rate_player_jitter_max,
        "rate_player_fluctuation_chance": rate_player_fluctuation_chance,
        "rate_player_fluctuation_max": rate_player_fluctuation_max,
        "coord_delay": float(coord_delay),
        "disable_quick_edit": bool(disable_quick_edit),
        "config_path": config_path,
        "cli_overrides": sorted(set(cli_overrides)),
        "proxy_address": str(getattr(args, "proxy", None) or "").strip() or None,
    }


def main(argv: list[str] | None = None):
    install_stdout_timestamps()

    args = parse_args(argv)

    try:
        cfg = load_config(args.config, args)
    except (ValueError, configparser.Error) as exc:
        logger.error(f"Invalid config: {exc}")
        sys.exit(2)

    if cfg["disable_quick_edit"]:
        disable_windows_quick_edit()



    if cfg["cli_overrides"]:
        logger.info(f"CLI overrides: {', '.join(cfg['cli_overrides'])}")




    rate_player_display = f"{cfg['rate_player_min']:g}"
    if cfg["rate_player_min"] != cfg["rate_player_max"]:
        rate_player_display = (
            f"{cfg['rate_player_min']:g}-{cfg['rate_player_max']:g}"
        )
    rate_vehicle_display = f"{cfg['rate_vehicle_min']:g}"
    if cfg["rate_vehicle_min"] != cfg["rate_vehicle_max"]:
        rate_vehicle_display = (
            f"{cfg['rate_vehicle_min']:g}-{cfg['rate_vehicle_max']:g}"
        )
    idle_after_display = f"{cfg['sync_idle_after_min']:g}"
    if cfg["sync_idle_after_min"] != cfg["sync_idle_after_max"]:
        idle_after_display = (
            f"{cfg['sync_idle_after_min']:g}-"
            f"{cfg['sync_idle_after_max']:g}"
        )

    sync_scheduler = PlayerSyncScheduler(
        rate_player=cfg["rate_player"],
        rate_player_min=cfg["rate_player_min"],
        rate_player_max=cfg["rate_player_max"],
        rate_vehicle_min=cfg["rate_vehicle_min"],
        rate_vehicle_max=cfg["rate_vehicle_max"],
        sync_idle_after_min=cfg["sync_idle_after_min"],
        sync_idle_after_max=cfg["sync_idle_after_max"],
        sync_idle_backoff_factor_min=cfg["sync_idle_backoff_factor_min"],
        sync_idle_backoff_factor_max=cfg["sync_idle_backoff_factor_max"],
        player_idle_interval_multiplier_min=cfg["player_idle_interval_multiplier_min"],
        player_idle_interval_multiplier_max=cfg["player_idle_interval_multiplier_max"],
        vehicle_idle_interval_multiplier_min=cfg["vehicle_idle_interval_multiplier_min"],
        vehicle_idle_interval_multiplier_max=cfg["vehicle_idle_interval_multiplier_max"],
        rate_player_jitter_max=cfg["rate_player_jitter_max"],
        rate_player_fluctuation_chance=cfg["rate_player_fluctuation_chance"],
        rate_player_fluctuation_max=cfg["rate_player_fluctuation_max"],
    )

    try:
        bot = Bot(
            cfg["host"],
            cfg["port"],
            cfg["nick"],
            sync_scheduler=sync_scheduler,
            fps=cfg["fps"],
            pings_ips_continuous=cfg["pings_ips_continuous"],
            proxy_address=cfg["proxy_address"],
            server_password=cfg["server_password"],
            registration=cfg["registration"],
            json_ui=cfg["json_ui"],
        )
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    bot.session.players.bot.set_coord_delay(cfg["coord_delay"])

    connected = bot.connect()

    if not connected:
        if bot.session.is_reconnecting():
            logger.info("Initial connect was interrupted by reconnect request")
        elif bot.session.is_handshake_recovery_pending():
            logger.info(
                "Initial handshake failed; waiting for script recovery"
            )
        else:
            logger.error("Connection failed")
            sys.exit(1)



    try:
        while True:
            if bot.session.is_reconnecting():
                time.sleep(0.1)
                continue

            if not bot.api.is_connected():
                time.sleep(float(DISCONNECTED_RECONNECT_POLL))
                continue

            time.sleep(0.5)

    except KeyboardInterrupt:
        logger.info("Stopping bot...")

    finally:
        bot.close()


if __name__ == "__main__":
    main()
