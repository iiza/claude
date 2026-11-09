"""Utilidades de Windows que no requieren permisos de administrador."""

from __future__ import annotations

import ctypes
import logging
import sys
import threading
from pathlib import Path

from dictado import APP_NAME

log = logging.getLogger(__name__)

IS_WINDOWS = sys.platform == "win32"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_mutex = None


def single_instance() -> bool:
    """True si somos la única instancia en esta sesión de usuario."""
    global _mutex
    if not IS_WINDOWS:
        return True
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    _mutex = kernel32.CreateMutexW(None, False, f"Local\\{APP_NAME}-dictado-ctrl")
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS


def message_box(text: str, title: str = APP_NAME, error: bool = False):
    if IS_WINDOWS:
        flags = 0x10 if error else 0x40  # MB_ICONERROR / MB_ICONINFORMATION
        ctypes.windll.user32.MessageBoxW(None, text, title, flags | 0x10000)  # MB_SETFOREGROUND
    else:
        print(f"{title}: {text}", file=sys.stderr)


def launch_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    script = Path(__file__).resolve().parent.parent / "dictado_main.py"
    return f'"{pythonw if pythonw.exists() else exe}" "{script}"'


def autostart_enabled() -> bool:
    if not IS_WINDOWS:
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except OSError:
        return False


def set_autostart(enabled: bool):
    """Inicio automático por usuario (HKCU), sin necesidad de administrador."""
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, launch_command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


def beep(freqs: tuple[int, ...], duration_ms: int = 70):
    if not IS_WINDOWS:
        return

    def _play():
        import winsound

        try:
            for f in freqs:
                winsound.Beep(f, duration_ms)
        except Exception:
            pass

    threading.Thread(target=_play, daemon=True).start()
