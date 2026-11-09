"""Máquina de estados que decide cuándo la tecla Ctrl significa "quiero dictar".

Es puro Python (sin dependencias de Windows) para poder probarla fácilmente.
Todos los métodos reciben el instante actual ``t`` (segundos, reloj monótono).

Modo "mantener" (por defecto, pulsar para hablar):
  * Mantén Ctrl pulsado SOLO (sin otra tecla ni clic) durante ``hold_threshold``
    segundos -> empieza la grabación (suena un pitido).
  * Suelta Ctrl -> termina la grabación y se transcribe.
  * Si mientras Ctrl está pulsado se pulsa otra tecla o se usa el ratón
    (Ctrl+C, Ctrl+clic, Ctrl+rueda...), se considera un atajo normal y no se
    dicta nada (si ya se estaba grabando, se descarta).

Modo "alternar" (manos libres):
  * Toque corto de Ctrl solo -> empieza la grabación.
  * Otro toque corto de Ctrl solo -> termina y se transcribe.
  * Esc mientras se graba -> se cancela.
  * Mientras se graba se pueden usar atajos con Ctrl sin cortar el dictado.
"""

from __future__ import annotations

import threading

HOLD = "mantener"
TOGGLE = "alternar"

# Estados
IDLE = "idle"
ARMED = "armed"  # mantener: Ctrl pulsado solo, esperando el umbral
REC_HOLD = "rec_hold"  # mantener: grabando
BLOCKED = "blocked"  # Ctrl formó parte de un atajo: esperar a que se suelte
TAP = "tap"  # alternar: Ctrl pulsado desde reposo, puede ser un toque
REC_TOGGLE = "rec_toggle"  # alternar: grabando
STOP_TAP = "stop_tap"  # alternar: grabando y Ctrl pulsado, puede ser el toque de parada
REC_TOGGLE_BLOCKED = "rec_toggle_blocked"  # alternar: grabando, Ctrl usado en un atajo

# Una tecla "otra" que lleva este tiempo sin repetirse se considera ya soltada
# (por si se perdió el evento de soltar, p. ej. al bloquear la sesión con Win+L).
STALE_KEY_SECONDS = 1.5


class CtrlGesture:
    def __init__(
        self,
        mode: str = HOLD,
        hold_threshold: float = 0.3,
        tap_max: float = 0.4,
        max_duration: float = 300.0,
        on_start=None,
        on_cancel=None,
        on_finish=None,
    ):
        if mode not in (HOLD, TOGGLE):
            raise ValueError(f"modo desconocido: {mode!r}")
        self.mode = mode
        self.hold_threshold = hold_threshold
        self.tap_max = tap_max
        self.max_duration = max_duration
        self._on_start = on_start or (lambda: None)
        self._on_cancel = on_cancel or (lambda: None)
        self._on_finish = on_finish or (lambda: None)

        self.state = IDLE
        self.enabled = True
        self._lock = threading.Lock()
        self._ctrl_down: set = set()
        self._others_down: dict = {}  # tecla -> último instante visto pulsada
        self._t0 = 0.0  # instante en que se pulsó Ctrl
        self._rec_start = 0.0

    # ------------------------------------------------------------------ util
    @property
    def recording(self) -> bool:
        return self.state in (REC_HOLD, REC_TOGGLE, STOP_TAP, REC_TOGGLE_BLOCKED)

    def _other_keys_held(self, t: float) -> bool:
        for key, seen in list(self._others_down.items()):
            if t - seen > STALE_KEY_SECONDS:
                del self._others_down[key]
        return bool(self._others_down)

    def _run(self, actions):
        for action in actions:
            try:
                action()
            except Exception:  # un fallo en un callback no debe romper el gancho de teclado
                import logging

                logging.getLogger(__name__).exception("Error en callback de gesto")

    # --------------------------------------------------------------- eventos
    def ctrl_down(self, key, t: float):
        actions = []
        with self._lock:
            if key in self._ctrl_down:
                return  # autorrepetición
            first = not self._ctrl_down
            self._ctrl_down.add(key)
            if not first or not self.enabled:
                if self.state in (ARMED, TAP):
                    self.state = BLOCKED
                return
            chord = self._other_keys_held(t)
            if self.state == IDLE:
                if chord:
                    self.state = BLOCKED
                else:
                    self.state = ARMED if self.mode == HOLD else TAP
                    self._t0 = t
            elif self.state == REC_TOGGLE:
                if chord:
                    self.state = REC_TOGGLE_BLOCKED
                else:
                    self.state = STOP_TAP
                    self._t0 = t
        self._run(actions)

    def ctrl_up(self, key, t: float):
        actions = []
        with self._lock:
            self._ctrl_down.discard(key)
            if self._ctrl_down:
                return
            s = self.state
            if s == ARMED or s == BLOCKED:
                self.state = IDLE
            elif s == REC_HOLD:
                self.state = IDLE
                actions.append(self._on_finish)
            elif s == TAP:
                if t - self._t0 <= self.tap_max:
                    self.state = REC_TOGGLE
                    self._rec_start = t
                    actions.append(self._on_start)
                else:
                    self.state = IDLE
            elif s == STOP_TAP:
                if t - self._t0 <= self.tap_max:
                    self.state = IDLE
                    actions.append(self._on_finish)
                else:
                    self.state = REC_TOGGLE
            elif s == REC_TOGGLE_BLOCKED:
                self.state = REC_TOGGLE
        self._run(actions)

    def other_down(self, key, t: float, is_escape: bool = False):
        """Cualquier tecla que no sea Ctrl, o un clic/rueda del ratón."""
        actions = []
        with self._lock:
            if key is not None:
                self._others_down[key] = t
            s = self.state
            if s in (ARMED, TAP):
                self.state = BLOCKED
            elif s == REC_HOLD:
                self.state = BLOCKED
                actions.append(self._on_cancel)
            elif s == STOP_TAP:
                if is_escape:
                    self.state = BLOCKED
                    actions.append(self._on_cancel)
                else:
                    self.state = REC_TOGGLE_BLOCKED
            elif s in (REC_TOGGLE, REC_TOGGLE_BLOCKED) and is_escape:
                self.state = BLOCKED if self._ctrl_down else IDLE
                actions.append(self._on_cancel)
        self._run(actions)

    def other_up(self, key, t: float):
        with self._lock:
            self._others_down.pop(key, None)

    def tick(self, t: float):
        actions = []
        with self._lock:
            if self.state == ARMED and t - self._t0 >= self.hold_threshold:
                self.state = REC_HOLD
                self._rec_start = t
                actions.append(self._on_start)
            elif self.recording and t - self._rec_start >= self.max_duration:
                self.state = BLOCKED if self._ctrl_down else IDLE
                actions.append(self._on_finish)
        self._run(actions)

    def set_enabled(self, enabled: bool):
        actions = []
        with self._lock:
            self.enabled = enabled
            if not enabled and self.state != IDLE:
                if self.recording:
                    actions.append(self._on_cancel)
                self.state = BLOCKED if self._ctrl_down else IDLE
        self._run(actions)
