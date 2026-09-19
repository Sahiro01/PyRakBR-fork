from .interfaces import build_json_packet, InterfaceID as OutgoingInterfaceSync

class InterfaceSyncPayloadBuilder:

    @staticmethod
    def create(interface_id: int, data: dict) -> bytes:
        return build_json_packet(interface_id, data)[1:]

    @staticmethod
    def auth_password(password: str) -> bytes:
        data = {'t': 6, 's': str(password), 'r': 0}
        return InterfaceSyncPayloadBuilder.create(OutgoingInterfaceSync.AUTH, data)

    @staticmethod
    def register_password(password: str, email: str='') -> bytes:
        data = {'t': 1, 's': str(email or ''), 'p': str(password)}
        return InterfaceSyncPayloadBuilder.create(OutgoingInterfaceSync.AUTH, data)

    @staticmethod
    def register_unknown_after_password() -> bytes:
        data = {'t': 2, 's': '', 'r': 0}
        return InterfaceSyncPayloadBuilder.create(OutgoingInterfaceSync.AUTH, data)

    @staticmethod
    def register_referral(referral: str='') -> bytes:
        data = {'t': 4, 's': str(referral or '')}
        return InterfaceSyncPayloadBuilder.create(OutgoingInterfaceSync.AUTH, data)

    @staticmethod
    def register_gender(gender: int=0) -> bytes:
        gender = int(gender)
        if gender not in (0, 1):
            raise ValueError('gender must be 0 (male) or 1 (female)')
        data = {'t': 3, 'r': gender}
        return InterfaceSyncPayloadBuilder.create(OutgoingInterfaceSync.AUTH, data)

    @staticmethod
    def register_skin(skin_id: int=78) -> bytes:
        data = {'t': 5, 'r': int(skin_id)}
        return InterfaceSyncPayloadBuilder.create(OutgoingInterfaceSync.AUTH, data)

    @staticmethod
    def register_finish() -> bytes:
        data = {'c': 1}
        return InterfaceSyncPayloadBuilder.create(OutgoingInterfaceSync.AUTH, data)

    @staticmethod
    def spawn_select(spawn_id: int) -> bytes:
        return InterfaceSyncPayloadBuilder.create(OutgoingInterfaceSync.SPAWN_SELECT, {'t': int(spawn_id)})

    @staticmethod
    def cinematic_stop() -> bytes:
        data = {'t': 1}
        return InterfaceSyncPayloadBuilder.create(OutgoingInterfaceSync.CINEMATIC, data)

    @staticmethod
    def npc_dialog_response(button_key: int) -> bytes:
        data = {'bk': int(button_key)}
        return InterfaceSyncPayloadBuilder.create(OutgoingInterfaceSync.NPC_DIALOG, data)

    @staticmethod
    def shop_food(item_id: int) -> bytes:
        data = {'t': 1, 'r': int(item_id)}
        return InterfaceSyncPayloadBuilder.create(OutgoingInterfaceSync.SHOP_FOOD, data)

    @staticmethod
    def get_free_reward() -> bytes:
        data = {'t': 2}
        return InterfaceSyncPayloadBuilder.create(OutgoingInterfaceSync.DONATE_MENU, data)

    @staticmethod
    def donat_menu_close() -> bytes:
        return InterfaceSyncPayloadBuilder.create(OutgoingInterfaceSync.DONATE_MENU, {'t': 3})

    @staticmethod
    def case_open(case_id: int, skip_animation: bool=True) -> bytes:
        data = {'t': 2, 'cs': int(case_id), 'type': 1 if bool(skip_animation) else 0}
        return InterfaceSyncPayloadBuilder.create(OutgoingInterfaceSync.CASES, data)

    @staticmethod
    def case_collect_reward(prize_ids: list[int]) -> bytes:
        data = {'t': 3, 'bt1': [int(prize_id) for prize_id in prize_ids]}
        return InterfaceSyncPayloadBuilder.create(OutgoingInterfaceSync.CASES, data)

    @staticmethod
    def case_menu_close() -> bytes:
        return InterfaceSyncPayloadBuilder.create(OutgoingInterfaceSync.CASES, {'t': 4, 'd': 1})

    @staticmethod
    def dialog_menu_select(selected_item: str | int, next_items_count: int=0, r: int=1) -> bytes:
        data = {'r': int(r), 'i': str(selected_item), 'l': int(next_items_count)}
        return InterfaceSyncPayloadBuilder.create(OutgoingInterfaceSync.DIALOG_MENU, data)

    @staticmethod
    def reward_take(reward_id: int) -> bytes:
        data = {'t': 4, 'id': int(reward_id), 's': 1}
        return InterfaceSyncPayloadBuilder.create(OutgoingInterfaceSync.REWARD, data)

    @staticmethod
    def close_reward() -> bytes:
        data = {'c': 1}
        return InterfaceSyncPayloadBuilder.create(OutgoingInterfaceSync.REWARD, data)

    @staticmethod
    def notification_response(c: int=13, notification_type: int=0, notification_s: int=0, button: int=0) -> bytes:
        data = {'c': int(c), 't': int(notification_type), 's': int(notification_s), 'b': int(button)}
        return InterfaceSyncPayloadBuilder.create(OutgoingInterfaceSync.NOTIFICATION, data)

    @staticmethod
    def call_notification_response(notification_type: int=2, button: int=1) -> bytes:
        data = {'t': int(notification_type), 'b': int(button)}
        return InterfaceSyncPayloadBuilder.create(OutgoingInterfaceSync.CALL_NOTIFICATION, data)
