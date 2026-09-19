from dataclasses import dataclass

from core import logger
from .json_console import format_interface


@dataclass(frozen=True)
class JsonUIConfig:
    console_output: bool = True
    auto_close_cinematic: bool = True

    @classmethod
    def from_config(cls, config):
        return cls(
            console_output=config.getboolean('JSON', 'console_output', fallback=True),
            auto_close_cinematic=config.getboolean('JSON', 'auto_close_cinematic', fallback=True),
        )


class JsonUI:
    def __init__(self, session, config=None):
        self.session = session
        self.config = config or JsonUIConfig()
        self.reset()

    def reset(self):
        pass

    @property
    def api(self):
        return self.session.api

    def handle(self, result):
        state = result.get('state')
        emit = self.session._emit_callback
        if state == 'notification':
            has_button = bool(result.get('notification_has_button'))
            button = result.get('notification_button_text') if has_button else None
            emit('onNotification', result['notification_text'], button, has_button)
        elif state == 'call_notification':
            emit('onCallNotification', result['call_notification_header'], result['call_notification_text'],
                 result['call_notification_button'], result['call_notification_t'])
        elif state == 'npc_dialog':
            emit('onNpcDialog', result['npc_name'], result['npc_text'], result['npc_model'],
                 result['npc_buttons'])
        elif state == 'dialog_npc':
            emit('onDialogNPC', result['dialog_npc_duration'], result['dialog_npc_text'],
                 result['dialog_npc_o'])
        elif state == 'quest_task':
            emit('onQuestTask', result['quest_text'])
        elif state == 'reward':
            rewards = result['rewards']
            if self.api is not None:
                self.api._set_reward_cache(rewards)
            emit('onRewardList', rewards)
        elif state == 'donat_menu_open':
            emit('DonatMenuOpen', result['showcase_id'], result['donate_rubles'], result['double_donate_value'],
                 result['sale_prizes'], result['free_prize_seconds'])
        elif state == 'case_menu_open':
            emit('CaseMenuOpen', result['available_cases'])
        elif state == 'case_reward_open':
            if self.api is not None:
                self.api._set_case_reward_cache(result['prize_ids'])
            emit('CaseRewardOpen', result['prize_ids'])
        elif state == 'cinematic_started':
            name = result['cinematic_name']
            emit('onCinematic', name)
            self._cinematic_log(f"Started: {name or '<unnamed>'}")
            if self.config.auto_close_cinematic:
                if self.session.send_json(76, {'t': 1}, packet_name='interface_cinematic_stop'):
                    self._cinematic_log('close queued: interface=76, JSON={"t":1}')
                else:
                    self._cinematic_log('close not queued: disconnected')
            else:
                self._cinematic_log('automatic close disabled')
        elif result['interface_id'] == 76:
            self._cinematic_log(f"update: o={result['json'].get('o')}, c={result['json'].get('c')}, t={result['json'].get('t')}")
        if self.config.console_output:
            self._print(result)

    def _print(self, result):
        message = format_interface(result)
        if message:
            logger.raw(message, add_timestamp=True)

    def _cinematic_log(self, message):
        if self.config.console_output:
            logger.raw(f"[CINEMATIC] {message}", add_timestamp=True)

    def on_cinematic_sent(self):
        self._cinematic_log('close sent to transport: interface=76, JSON={"t":1}')
