"""Ganchos globales de teclado y ratón (WH_KEYBOARD_LL / WH_MOUSE_LL).

Funcionan sin permisos de administrador. Solo observan: nunca bloquean teclas,
así que Ctrl+C, Ctrl+V, etc. siguen funcionando con normalidad.
"""

from __future__ import annotations

import logging
import time

from dictado.gesture import CtrlGesture

log = logging.getLogger(__name__)

WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x100, 0x101, 0x104, 0x105
WM_MOUSEMOVE = 0x200
LLKHF_INJECTED = 0x10 | 0x02  # inyectada (incluye LOWER_IL_INJECTED)
LLMHF_INJECTED = 0x01 | 0x02
VK_CONTROL, VK_LCONTROL, VK_RCONTROL = 0x11, 0xA2, 0xA3
VK_ESCAPE = 0x1B
CTRL_KEYS = (VK_CONTROL, VK_LCONTROL, VK_RCONTROL)


class GlobalHooks:
    def __init__(self, gesture: CtrlGesture):
        self.gesture = gesture
        self._kb = None
        self._mouse = None

    # Las funciones *_filter se ejecutan dentro del gancho de Windows: deben ser rápidas.
    # Siempre devuelven False para que pynput no haga trabajo extra (el evento llega igual
    # a las aplicaciones: el filtro de pynput solo decide si se llama a sus callbacks).
    def _kb_filter(self, msg, data):
        try:
            if data.flags & LLKHF_INJECTED:
                return False  # teclas simuladas (incluido nuestro propio Ctrl+V)
            vk = data.vkCode
            t = time.monotonic()
            down = msg in (WM_KEYDOWN, WM_SYSKEYDOWN)
            up = msg in (WM_KEYUP, WM_SYSKEYUP)
            if vk in CTRL_KEYS:
                if down:
                    self.gesture.ctrl_down(vk, t)
                elif up:
                    self.gesture.ctrl_up(vk, t)
            else:
                if down:
                    self.gesture.other_down(vk, t, is_escape=(vk == VK_ESCAPE))
                elif up:
                    self.gesture.other_up(vk, t)
        except Exception:
            log.exception("Error en el gancho de teclado")
        return False

    def _mouse_filter(self, msg, data):
        try:
            if msg != WM_MOUSEMOVE and not (data.flags & LLMHF_INJECTED):
                # Clic o rueda: Ctrl+clic / Ctrl+rueda son atajos, no dictado.
                if msg in (0x201, 0x204, 0x207, 0x20A, 0x20B, 0x20E):  # botones abajo y ruedas
                    self.gesture.other_down(None, time.monotonic())
        except Exception:
            log.exception("Error en el gancho de ratón")
        return False

    def start(self):
        from pynput import keyboard, mouse

        self._kb = keyboard.Listener(win32_event_filter=self._kb_filter)
        self._mouse = mouse.Listener(win32_event_filter=self._mouse_filter)
        self._kb.daemon = True
        self._mouse.daemon = True
        self._kb.start()
        self._mouse.start()

    def stop(self):
        for listener in (self._kb, self._mouse):
            if listener is not None:
                listener.stop()
