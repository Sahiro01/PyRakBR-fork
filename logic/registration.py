import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field

from samp.interfaces import InterfaceID


@dataclass(frozen=True)
class RegistrationConfig:
    enabled: bool = False
    auto_login: bool = True
    password: str = field(default='', repr=False)
    email: str = ''
    referral: str = ''
    gender: int = 0
    skin: int = 78
    step_delay: float = 0.5
    ack_timeout: float = 15.0

    def __post_init__(self):
        if self.enabled and not self.password:
            raise ValueError('Registration.password is required when enabled')
        if self.gender not in (0, 1):
            raise ValueError('Registration.gender must be 0 or 1')
        if self.skin < 0:
            raise ValueError('Registration.skin must be nonnegative')
        if not math.isfinite(self.step_delay) or self.step_delay < 0:
            raise ValueError('Registration.step_delay must be finite and nonnegative')
        if not math.isfinite(self.ack_timeout) or self.ack_timeout <= 0:
            raise ValueError('Registration.ack_timeout must be finite and positive')

    @classmethod
    def from_config(cls, config):
        return cls(
            enabled=config.getboolean('Registration', 'enabled', fallback=False),
            auto_login=config.getboolean('Registration', 'auto_login', fallback=True),
            password=config.get('Registration', 'password', raw=True, fallback=''),
            email=config.get('Registration', 'email', raw=True, fallback=''),
            referral=config.get('Registration', 'referral', raw=True, fallback=''),
            gender=config.getint('Registration', 'gender', fallback=0),
            skin=config.getint('Registration', 'skin', fallback=78),
            step_delay=config.getfloat('Registration', 'step_delay', fallback=0.5),
            ack_timeout=config.getfloat('Registration', 'ack_timeout', fallback=15.0),
        )


class AutoRegistration:
    def __init__(self, session, config=None, clock=time.monotonic):
        self.session = session
        self.config = config or RegistrationConfig()
        self.clock = clock
        self._lock = threading.RLock()
        self.reset()

    def reset(self):
        with self._lock:
            self.state = 'idle'
            self.pending = None
            self.deadline = 0.0
            self.next_send = 0.0
            self._queue = deque()

    def status(self):
        with self._lock:
            return {'enabled': self.config.enabled, 'state': self.state,
                    'pending': self.pending, 'queued': len(self._queue)}

    def _state(self, value):
        self.state = value
        self.session._emit_callback('onRegistrationState', value)

    def _schedule(self, *steps):
        self._queue.extend(steps)
        self.next_send = self.clock() + self.config.step_delay

    def _gender(self):
        self._schedule(({'t': 3, 'r': self.config.gender}, 'gender', True))

    def handle(self, packet):
        with self._lock:
            if not self.config.enabled or not self.session.connected or packet['interface_id'] != InterfaceID.AUTH:
                return
            data = packet['json']
            if data.get('o') == 1:
                if self.state != 'idle' or self._queue or self.pending:
                    return
                if data.get('r') == 0:
                    self._state('registering')
                    self._schedule(({'t': 1, 's': self.config.email, 'p': self.config.password}, 'password', True))
                elif data.get('r') == 1 and self.config.auto_login:
                    self._state('logging_in')
                    self._schedule(({'t': 6, 's': self.config.password, 'r': 0}, 'login', True))
                return
            if data.get('c') == 1:
                if self.pending or self._queue:
                    self.pending = None
                    self._queue.clear()
                    self._state('closed')
                return
            if data.get('t') == 3 and self.pending in ('login', 'password', 'referral'):
                self.pending = None
                self._state('registering')
                self._gender()
                return
            if data.get('t') != 0 or self.pending is None:
                return
            step = self.pending
            self.pending = None
            if step == 'password':
                self._schedule(({'t': 2, 's': '', 'r': 0}, 'intermediate', False),
                               ({'t': 4, 's': self.config.referral}, 'referral', True))
            elif step == 'referral':
                self._gender()
            elif step == 'gender':
                self._schedule(({'t': 5, 'r': self.config.skin}, 'skin', False),
                               ({'c': 1}, 'finish', False))
            elif step == 'login':
                self._state('authenticated')

    def tick(self):
        with self._lock:
            if not self.config.enabled or not self.session.connected:
                return
            now = self.clock()
            if self.pending is not None:
                if now >= self.deadline:
                    self.pending = None
                    self._queue.clear()
                    self._state('timeout')
                return
            if not self._queue or now < self.next_send:
                return
            data, step, wait_ack = self._queue[0]
            packet_name = {
                'login': 'interface_auth_password',
                'password': 'interface_register_password',
                'intermediate': 'interface_register_unknown_after_password',
                'referral': 'interface_register_referral',
                'gender': 'interface_register_gender',
                'skin': 'interface_register_skin',
                'finish': 'interface_register_finish',
            }[step]
            if not self.session.send_json(InterfaceID.AUTH, data, packet_name=packet_name):
                return
            self._queue.popleft()
            self.next_send = now + self.config.step_delay
            if wait_ack:
                self.pending = step
                self.deadline = now + self.config.ack_timeout
            if step == 'finish':
                self._state('submitted')
