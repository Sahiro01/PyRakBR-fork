from .constants import PacketReliability, PacketPriority

UNREL = PacketReliability.UNRELIABLE
UNREL_SEQ = PacketReliability.UNRELIABLE_SEQUENCED
REL = PacketReliability.RELIABLE
REL_ORD = PacketReliability.RELIABLE_ORDERED
REL_SEQ = PacketReliability.RELIABLE_SEQUENCED

PRI_SYS = PacketPriority.SYSTEM_PRIORITY
PRI_HIGH = PacketPriority.HIGH_PRIORITY
PRI_MED = PacketPriority.MEDIUM_PRIORITY
PRI_LOW = PacketPriority.LOW_PRIORITY

PACKET_DELIVERY = {
    "interface_spawn_select": (REL, PRI_SYS, 0),
    "interface_npc_dialog_response": (REL, PRI_SYS, 0),
    "interface_shop_food": (REL, PRI_SYS, 0),
    "interface_get_free_reward": (REL, PRI_SYS, 0),
    "interface_donat_menu_close": (REL, PRI_SYS, 0),
    "interface_case_open": (REL, PRI_SYS, 0),
    "interface_case_collect_reward": (REL, PRI_SYS, 0),
    "interface_case_menu_close": (REL, PRI_SYS, 0),
    "interface_dialog_menu_select": (REL, PRI_SYS, 0),
    "interface_call_notification_response": (REL, PRI_SYS, 0),
    "interface_notification_response": (REL, PRI_SYS, 0),
    "interface_reward_take": (REL, PRI_SYS, 0),
    "interface_close_reward": (REL, PRI_SYS, 0),
    "interface_auth_password": (REL_ORD, PRI_MED, 0),
    "interface_register_password": (REL_ORD, PRI_MED, 0),
    "interface_register_unknown_after_password": (REL_ORD, PRI_MED, 0),
    "interface_register_referral": (REL_ORD, PRI_MED, 0),
    "interface_register_gender": (REL_ORD, PRI_MED, 0),
    "interface_register_skin": (REL_ORD, PRI_MED, 0),
    "interface_register_finish": (REL_ORD, PRI_MED, 0),
    "interface_cinematic_stop": (REL, PRI_HIGH, 0),
    "interface_sync": (REL_ORD, PRI_MED, 0),
    "player_sync": (UNREL_SEQ, PRI_HIGH, 0),
    "vehicle_sync": (UNREL_SEQ, PRI_HIGH, 0),
    "passenger_sync": (UNREL_SEQ, PRI_HIGH, 0),
    "connection_request": (REL, PRI_SYS, 0),
    "auth_key_response": (REL, PRI_SYS, 0),
    "new_incoming_connection": (REL, PRI_HIGH, 0),
    "internal_ping": (UNREL, PRI_HIGH, 0),
    "connected_pong": (UNREL, PRI_SYS, 0),
    "received_static_data": (REL, PRI_HIGH, 0),
    "detect_lost_connections": (REL, PRI_HIGH, 0),
    "disconnection_notification": (REL, PRI_SYS, 0),
}

RPC_DELIVERY = {
    "spawn": (REL_ORD, PRI_MED, 0),
    "client_join": (REL, PRI_MED, 0),
    "enter_vehicle": (REL_SEQ, PRI_SYS, 0),
    "exit_vehicle": (REL_SEQ, PRI_SYS, 0),
    "request_class": (REL, PRI_MED, 0),
    "send_chat": (REL, PRI_MED, 0),
    "server_command": (REL, PRI_MED, 0),
    "update_scores_and_pings": (REL, PRI_MED, 0),
    "picked_up_pickup": (REL, PRI_MED, 0),
    "picked_up_interact": (REL, PRI_MED, 0),
    "death_notification": (REL, PRI_MED, 0),
    "dialog_response": (REL, PRI_MED, 0),
}

_RPC_DELIVERY_DEFAULT = (REL, PRI_MED, 0)


def get_delivery_params(
    packet_name: str | None = None,
    rpc_name: str | None = None,
):
    if rpc_name:
        reliability, priority, ordering_channel = RPC_DELIVERY.get(
            rpc_name, _RPC_DELIVERY_DEFAULT
        )
        return reliability, priority, ordering_channel

    if packet_name is None:
        return REL, PRI_HIGH, 0

    return PACKET_DELIVERY.get(packet_name, (REL, PRI_HIGH, 0))


class PacketSender:

    __slots__ = ("_session",)

    def __init__(self, session) -> None:
        self._session = session

    def resolve_delivery(
        self,
        packet_name: str | None = None,
        rpc_name: str | None = None,
    ) -> tuple[int, int, int]:
        return get_delivery_params(packet_name=packet_name, rpc_name=rpc_name)

    def send(
        self,
        payload: bytes,
        *,
        packet_name: str | None = None,
        rpc_name: str | None = None,
        event_name: str | None = None,
    ) -> None:
        if not self._session.connected:
            return

        reliability, priority, ordering_channel = get_delivery_params(
            packet_name=packet_name,
            rpc_name=rpc_name,
        )

        self._session.protocol.send_with_header(
            payload,
            reliability,
            ordering_channel=ordering_channel,
            priority=priority,
        )

        if event_name:
            self._session._emit_callback(event_name)
