import json
import struct

from .constants import PacketID
from .interface_parsers import InterfaceParser


class InterfaceID:
    AUTH = 38
    SPAWN_SELECT = 50
    NOTIFICATION = 13
    DONATE_MENU = 22
    CASES = 73
    QUEST_TASK = 39
    CINEMATIC = 76
    NPC_DIALOG = 63
    DIALOG_NPC = 114
    CALL_NOTIFICATION = 65
    REWARD = 74
    SHOP_FOOD = 3
    DIALOG_MENU = 10
    PASSWORD = 50


INTERFACE_PARSERS = {
    InterfaceID.SPAWN_SELECT: InterfaceParser.spawn_select,
    InterfaceID.NOTIFICATION: InterfaceParser.notification,
    InterfaceID.DONATE_MENU: InterfaceParser.donat_menu,
    InterfaceID.CASES: InterfaceParser.cases,
    InterfaceID.QUEST_TASK: InterfaceParser.quest_task,
    InterfaceID.CINEMATIC: InterfaceParser.cinematic,
    InterfaceID.NPC_DIALOG: InterfaceParser.npc_dialog,
    InterfaceID.DIALOG_NPC: InterfaceParser.dialog_npc,
    InterfaceID.CALL_NOTIFICATION: InterfaceParser.call_notification,
    InterfaceID.REWARD: InterfaceParser.reward,
}


def build_json_packet(interface_id: int, data: dict) -> bytes:
    if isinstance(interface_id, bool) or not isinstance(interface_id, int) or not 0 <= interface_id <= 65535:
        raise ValueError("interface_id must be an integer in 0..65535")
    if not isinstance(data, dict):
        raise TypeError("interface JSON must be an object")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode('utf-8')
    return bytes([PacketID.USER_INTERFACE_SYNC]) + struct.pack('<HI', interface_id, len(payload)) + payload


def _reject_constant(value):
    raise ValueError('Invalid JSON constant')


def parse_json_payload(data: bytes) -> dict | None:
    if len(data) < 6:
        return None
    interface_id, size = struct.unpack_from('<HI', data)
    if size > len(data) - 6:
        return None
    try:
        value = json.loads(data[6:6 + size].decode('utf-8'), parse_constant=_reject_constant)
    except (UnicodeError, ValueError, RecursionError):
        return None
    if not isinstance(value, dict):
        return None
    action = 'open' if value.get('o') == 1 else 'close' if value.get('c') == 1 else 'update'
    result = {'type': 'interface_sync', 'interface_id': interface_id,
              'json': value, 'action': action, 'raw': data}
    parser = INTERFACE_PARSERS.get(interface_id)
    if parser is not None:
        result.update(parser(value) or {})
    elif interface_id == InterfaceID.AUTH:
        if value.get('o') == 1 and value.get('r') in (0, 1):
            result['state'] = 'auth_allowed' if value['r'] else 'registration_allowed'
        elif value.get('t') == 0:
            result['state'] = 'ack_auth'
        elif value.get('t') == 3:
            result['state'] = 'registration_continue_required'
    return result
