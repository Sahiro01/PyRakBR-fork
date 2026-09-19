class InterfaceParser:

    @staticmethod
    def spawn_select(data: dict | list | str | int | float | bool | None) -> dict | None:
        if not isinstance(data, dict):
            return None
        return {'type': 'interface_sync', 'state': 'spawn_select', 'spawn_available': list(data.get('m')) if isinstance(data.get('m'), list) else [], 'json': data}

    @staticmethod
    def donat_menu(data: dict | list | str | int | float | bool | None) -> dict | None:
        if not isinstance(data, dict):
            return None
        if 't' in data:
            return {'type': 'interface_sync', 'state': 'donat_menu_update', 'json': data}
        required_startup_keys = {'nm', 'sv', 'r', 'd', 'i', 's'}
        if not required_startup_keys.issubset(data):
            return {'type': 'interface_sync', 'state': 'donat_menu_unknown', 'json': data}

        def optional_int(key: str) -> int | None:
            value = data.get(key)
            if isinstance(value, bool):
                return None
            if isinstance(value, int):
                return value
            return None

        def optional_flag(key: str) -> bool | None:
            value = optional_int(key)
            return value == 1 if value is not None else None
        sale_prizes = []
        raw_sales = data.get('s')
        if isinstance(raw_sales, list):
            for index in range(0, len(raw_sales) - 2, 3):
                item_id, sale_time, sale_percent = raw_sales[index:index + 3]
                if any((isinstance(value, bool) or not isinstance(value, int) for value in (item_id, sale_time, sale_percent))):
                    continue
                sale_prizes.append({'item_id': item_id, 'seconds_remaining': sale_time})
        return {'type': 'interface_sync', 'state': 'donat_menu_open', 'showcase_id': optional_int('lc'), 'donate_rubles': optional_int('r'), 'double_donate_value': optional_flag('ds'), 'sale_prizes': sale_prizes, 'free_prize_seconds': optional_int('p'), 'json': data}

    @staticmethod
    def cases(data: dict | list | str | int | float | bool | None) -> dict | None:
        if not isinstance(data, dict):
            return None
        packet_type = data.get('t')
        if packet_type == 1 and isinstance(data.get('cc'), list):
            available_cases = []
            for item in data['cc']:
                if not isinstance(item, dict):
                    continue
                case_id = item.get('id')
                count = item.get('cot')
                if isinstance(case_id, bool) or not isinstance(case_id, int) or isinstance(count, bool) or (not isinstance(count, int)) or (case_id <= 0) or (count <= 0):
                    continue
                available_cases.append({'case_id': case_id, 'count': count})
            return {'type': 'interface_sync', 'state': 'case_menu_open', 'available_cases': available_cases, 'json': data}
        if packet_type == 2 and isinstance(data.get('pr'), list):
            prize_ids = []
            for value in data['pr']:
                if isinstance(value, bool) or not isinstance(value, int):
                    continue
                prize_ids.append(value)
            return {'type': 'interface_sync', 'state': 'case_reward_open', 'prize_ids': prize_ids, 'json': data}
        return {'type': 'interface_sync', 'state': 'cases_update', 'json': data}

    @staticmethod
    def quest_task(data: dict | list | str | int | float | bool | None) -> dict | None:
        if not isinstance(data, dict):
            return None
        if data.get('c') == 1 and 'mq' not in data:
            return {'type': 'interface_sync', 'state': 'quest_task_update', 'quest_update_c': data.get('c'), 'json': data}
        if data.get('o') != 1:
            return {'type': 'interface_sync', 'state': 'quest_task_unknown', 'json': data}
        quest_text = str(data.get('mq', ''))
        return {'type': 'interface_sync', 'state': 'quest_task', 'quest_text': quest_text, 'quest_m': data.get('m'), 'quest_t': data.get('t'), 'quest_mt': data.get('mt'), 'quest_ma': data.get('ma'), 'quest_mc': data.get('mc'), 'quest_aq': data.get('aq') if isinstance(data.get('aq'), list) else [], 'quest_at': data.get('at') if isinstance(data.get('at'), list) else [], 'quest_aa': data.get('aa') if isinstance(data.get('aa'), list) else [], 'quest_ac': data.get('ac') if isinstance(data.get('ac'), list) else [], 'quest_f': data.get('f'), 'json': data}

    @staticmethod
    def notification(data: dict | list | str | int | float | bool | None) -> dict | None:
        if not isinstance(data, dict):
            return None
        if data.get('o') != 1:
            return {'type': 'interface_sync', 'state': 'notification_unknown', 'json': data}
        button_text = str(data.get('k', '')) if 'k' in data else ''
        has_button = bool(button_text)
        return {'type': 'interface_sync', 'state': 'notification', 'notification_text': str(data.get('i', '')), 'notification_o': data.get('o'), 'notification_t': data.get('t'), 'notification_d': data.get('d'), 'notification_s': data.get('s'), 'notification_b': data.get('b'), 'notification_k': data.get('k'), 'notification_button_text': button_text, 'notification_button_value': data.get('b'), 'notification_has_button': has_button, 'notification_has_confirm_button': has_button, 'json': data}

    @staticmethod
    def npc_dialog(data: dict | list | str | int | float | bool | None) -> dict | None:
        if not isinstance(data, dict):
            return None
        if data.get('o') != 1 and data.get('t') != 1:
            return {'type': 'interface_sync', 'state': 'npc_dialog_unknown', 'json': data}
        buttons = []
        raw_buttons = data.get('b')
        if isinstance(raw_buttons, list):
            for index, button in enumerate(raw_buttons):
                if not isinstance(button, dict):
                    continue
                button_text = str(button.get('bn', ''))
                buttons.append({'index': index, 'text': button_text, 'name': button_text, 'type': button.get('bt'), 'key': button.get('bk'), 'raw': button})
        return {'type': 'interface_sync', 'state': 'npc_dialog', 'npc_name': str(data.get('n', '')), 'npc_text': str(data.get('d', '')), 'npc_model': data.get('m'), 'npc_ts': data.get('ts'), 'npc_st': data.get('st'), 'npc_buttons': buttons, 'json': data}

    @staticmethod
    def dialog_npc(data: dict | list | str | int | float | bool | None) -> dict | None:
        if not isinstance(data, dict):
            return None
        if data.get('o') != 1 or 'd' not in data or 't' not in data:
            return {'type': 'interface_sync', 'state': 'dialog_npc_unknown', 'dialog_npc_o': data.get('o'), 'dialog_npc_duration': data.get('d'), 'dialog_npc_text': str(data.get('t', '')), 'json': data}
        return {'type': 'interface_sync', 'state': 'dialog_npc', 'dialog_npc_o': data.get('o'), 'dialog_npc_duration': data.get('d'), 'dialog_npc_text': str(data.get('t', '')), 'json': data}

    @staticmethod
    def call_notification(data: dict | list | str | int | float | bool | None) -> dict | None:
        if not isinstance(data, dict):
            return None
        if data.get('o') != 1:
            return {'type': 'interface_sync', 'state': 'call_notification_unknown', 'json': data}
        return {'type': 'interface_sync', 'state': 'call_notification', 'call_notification_o': data.get('o'), 'call_notification_t': data.get('t'), 'call_notification_header': str(data.get('h', '')), 'call_notification_text': str(data.get('s', '')), 'call_notification_button': str(data.get('b', '')), 'json': data}

    @staticmethod
    def reward(data: dict | list | str | int | float | bool | None) -> dict | None:
        if not isinstance(data, dict):
            return None
        raw_rewards = data.get('pr')
        if not isinstance(raw_rewards, list):
            return None
        rewards = []
        for item in raw_rewards:
            if not isinstance(item, dict):
                continue
            if 'id' not in item:
                continue
            try:
                reward_id = int(item.get('id'))
            except Exception:
                continue
            name = str(item.get('n') or '')
            can_spray = False
            spray_price = None
            try:
                can_spray = int(item.get('el') or 0) == 1
            except Exception:
                can_spray = bool(item.get('el'))
            if 'sp' in item:
                try:
                    spray_price = int(item.get('sp'))
                except Exception:
                    spray_price = item.get('sp')
            rewards.append({'id': reward_id, 'name': name, 'can_spray': can_spray, 'spray_price': spray_price, 'raw': item})
        return {'type': 'interface_sync', 'state': 'reward', 'rewards': rewards}

    @staticmethod
    def cinematic(data: dict | list | str | int | float | bool | None) -> dict | None:
        if not isinstance(data, dict):
            return None
        if data.get('o') == 1:
            return {'type': 'interface_sync', 'state': 'cinematic_started', 'cinematic_name': str(data.get('ur', '')), 'json': data}
        return {'type': 'interface_sync', 'state': 'cinematic_unknown', 'json': data}
