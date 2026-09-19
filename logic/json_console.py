import html
import re


def clean_text(value):
    text = str(value or '')
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = html.unescape(re.sub(r'<[^>]+>', '', text))
    return text.replace('\\r\\n', '\n').replace('\\n', '\n').replace('\r\n', '\n').replace('\r', '\n')


def format_interface(result):
    state = result.get('state', '')
    title = None
    details = ''
    text = ''
    if state == 'notification':
        title = 'NOTIFICATION'
        details = ' | '.join(f'{key}={result.get("notification_" + key)}' for key in ('t', 'd', 's', 'b'))
        details += f" | has_button={bool(result.get('notification_has_button'))} | k={clean_text(result.get('notification_button_text'))!r}"
        text = clean_text(result.get('notification_text'))
    elif state == 'quest_task':
        title = 'QUEST TASK'
        details = ' | '.join(f'{key}={result.get("quest_" + key)}' for key in ('m', 't', 'mt', 'ma', 'mc', 'f'))
        text = clean_text(result.get('quest_text'))
    elif state == 'npc_dialog':
        title = 'NPC DIALOG'
        details = f"Name: {clean_text(result.get('npc_name'))}\n[NPC DIALOG] Model: {result.get('npc_model')} | TS: {result.get('npc_ts')} | ST: {result.get('npc_st')}"
        text = clean_text(result.get('npc_text'))
        buttons = '\n'.join(f"[NPC DIALOG] Button {b['index']}: {clean_text(b['text'])!r} | type={b['type']} | key={b['key']}" for b in result.get('npc_buttons', []))
        text += '\n' + '-' * 60 + '\n' + (buttons or '[NPC DIALOG] Buttons: none')
    elif state == 'call_notification':
        title = 'CALL NOTIFICATION'
        details = f"t={result.get('call_notification_t')} | button={clean_text(result.get('call_notification_button'))!r}"
        text = '\n'.join(filter(None, (clean_text(result.get('call_notification_header')), clean_text(result.get('call_notification_text')))))
    elif state == 'dialog_npc':
        title = 'DIALOG NPC'
        details = f"duration={result.get('dialog_npc_duration')} | origin={result.get('dialog_npc_o')}"
        text = clean_text(result.get('dialog_npc_text'))
    elif state == 'reward':
        title = 'REWARDS'
        text = '\n'.join(f"{r['id']}: {clean_text(r['name'])}" for r in result.get('rewards', []))
    elif state == 'case_menu_open':
        title = 'CASES'
        text = '\n'.join(f"{c['case_id']}: {c['count']}" for c in result.get('available_cases', []))
    elif state == 'case_reward_open':
        title = 'CASE REWARD'
        text = ', '.join(map(str, result.get('prize_ids', [])))
    elif state == 'donat_menu_open':
        title = 'DONATE MENU'
        details = f"balance={result.get('donate_rubles')} | free_reward_seconds={result.get('free_prize_seconds')}"
        text = f"showcase={result.get('showcase_id')} | double_donate={result.get('double_donate_value')}\n{result.get('sale_prizes')}"
    else:
        labels = {13: 'NOTIFICATION', 39: 'QUEST TASK', 63: 'NPC DIALOG',
                  65: 'CALL NOTIFICATION', 114: 'DIALOG NPC', 73: 'CASES',
                  74: 'REWARDS', 22: 'DONATE MENU'}
        label = labels.get(result.get('interface_id'))
        if label:
            action = 'Closed' if result.get('action') == 'close' else 'Update/control payload' if state.endswith('_update') else 'Unknown payload'
            return f"[{label}] {action}: {result.get('json')}"
        return None
    lines = ['', '=' * 60, f'[{title}]']
    if details:
        lines.append(f'[{title}] {details}')
    lines.extend(('-' * 60, text or '[empty]', '=' * 60, ''))
    return '\n'.join(lines)
