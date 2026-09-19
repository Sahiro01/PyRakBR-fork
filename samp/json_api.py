from core import logger
from .packets import PacketBuilder
from .interfaces import parse_json_payload

class JsonAPI:

    def send_npc_dialog_response(self, button_key: int) -> None:
        if not self.session.connected:
            return
        self._send_interface_packet(PacketBuilder.interface_npc_dialog_response(int(button_key)), packet_name='interface_npc_dialog_response')

    def setbotfood(self, item_id: int) -> None:
        if not self.session.connected:
            return
        self._send_interface_packet(PacketBuilder.interface_shop_food(int(item_id)), packet_name='interface_shop_food')

    def GetFreeReward(self) -> bool:
        if not self.session.connected:
            return False
        self._send_interface_packet(PacketBuilder.interface_get_free_reward(), packet_name='interface_get_free_reward')
        return True

    def DonatMenuClose(self) -> bool:
        if not self.session.connected:
            return False
        self._send_interface_packet(PacketBuilder.interface_donat_menu_close(), packet_name='interface_donat_menu_close')
        return True

    def CaseOpen(self, case_id: int, skip_animation: bool=True) -> bool:
        if not self.session.connected:
            return False
        try:
            case_id = int(case_id)
        except (TypeError, ValueError):
            return False
        if case_id <= 0:
            return False
        self._send_interface_packet(PacketBuilder.interface_case_open(case_id, skip_animation), packet_name='interface_case_open')
        return True

    def _set_case_reward_cache(self, prize_ids) -> None:
        try:
            self._case_reward_cache = [int(value) for value in prize_ids]
        except (TypeError, ValueError):
            self._case_reward_cache = []

    def CaseCollectReward(self, prize_ids=None) -> bool:
        if not self.session.connected:
            return False
        if prize_ids is None:
            normalized_ids = list(self._case_reward_cache)
        elif isinstance(prize_ids, (list, tuple, set)):
            try:
                normalized_ids = [int(value) for value in prize_ids]
            except (TypeError, ValueError):
                return False
        else:
            try:
                normalized_ids = [int(prize_ids)]
            except (TypeError, ValueError):
                return False
        if not normalized_ids:
            return False
        self._send_interface_packet(PacketBuilder.interface_case_collect_reward(normalized_ids), packet_name='interface_case_collect_reward')
        return True

    def CaseMenuClose(self) -> bool:
        if not self.session.connected:
            return False
        self._send_interface_packet(PacketBuilder.interface_case_menu_close(), packet_name='interface_case_menu_close')
        self._case_reward_cache = []
        return True

    def SendDialogResponse(self, selected_item: str | int, next_items_count: int=0, r: int=1) -> None:
        if not self.session.connected:
            return
        self._send_interface_packet(PacketBuilder.interface_dialog_menu_select(selected_item, next_items_count, r), packet_name='interface_dialog_menu_select')

    def send_call_notification_response(self, notification_type: int=2, button: int=1) -> None:
        if not self.session.connected:
            return
        self._send_interface_packet(PacketBuilder.interface_call_notification_response(int(notification_type), int(button)), packet_name='interface_call_notification_response')

    def send_notification_response(self, c: int=13, notification_type: int=0, notification_s: int=0, button: int=0) -> None:
        if not self.session.connected:
            return
        self._send_interface_packet(PacketBuilder.interface_notification_response(int(c), int(notification_type), int(notification_s), int(button)), packet_name='interface_notification_response')

    def _set_reward_cache(self, rewards) -> None:
        try:
            self._reward_cache = list(rewards or [])
        except Exception:
            self._reward_cache = []

    def get_rewards(self) -> list:
        return list(getattr(self, '_reward_cache', []) or [])

    @staticmethod
    def _clean_reward_name(value: str) -> str:
        return ' '.join(str(value or '').strip().lower().split())

    def _resolve_reward_id(self, reward) -> int | None:
        if reward is None:
            return None
        if isinstance(reward, dict):
            reward = reward.get('id') or reward.get('reward_id') or reward.get('name')
        try:
            return int(reward)
        except Exception:
            pass
        wanted = self._clean_reward_name(str(reward))
        if not wanted:
            return None
        rewards = self.get_rewards()
        for item in rewards:
            if not isinstance(item, dict):
                continue
            name = self._clean_reward_name(item.get('name', ''))
            if name == wanted:
                try:
                    return int(item.get('id'))
                except Exception:
                    return None
        for item in rewards:
            if not isinstance(item, dict):
                continue
            name = self._clean_reward_name(item.get('name', ''))
            if wanted in name or name in wanted:
                try:
                    return int(item.get('id'))
                except Exception:
                    return None
        return None

    def take_reward(self, reward=None, *, reward_id: int | None=None, name: str | None=None) -> bool:
        target = reward_id if reward_id is not None else name if name is not None else reward
        resolved_id = self._resolve_reward_id(target)
        if resolved_id is None:
            logger.error(f'take_reward failed: reward not found: {target!r}')
            return False
        if not self.session.connected:
            return False
        self._send_interface_packet(PacketBuilder.interface_reward_take(resolved_id), packet_name='interface_reward_take')
        return True

    def close_reward(self) -> bool:
        if not self.session.connected:
            return False
        self._send_interface_packet(PacketBuilder.interface_close_reward(), packet_name='interface_close_reward')
        return True

    def _send_interface_packet(self, payload, *, packet_name=None):
        parsed = parse_json_payload(payload[1:])
        if parsed is None:
            raise ValueError("Invalid interface packet")
        return self.session.send_json(parsed["interface_id"], parsed["json"], packet_name=packet_name or "interface_sync")

    def Sendpassword(self, password=None):
        if password is None:
            password = self.session.registration.config.password
        return self.send_auth_password(str(password))

    def stop_cinematic(self):
        return self.session.send_json(76, {"t": 1}, packet_name="interface_cinematic_stop")

    def close_npc_dialog(self):
        return self.close_interface(114)


    def pickup_interact(self, pickup_id: int) -> None:
        if not self.session.connected:
            return
        self.session._sender.send(
            PacketBuilder.rpc_build("picked_up_interact", int(pickup_id)),
            rpc_name="picked_up_interact",
        )
