"""Inserta el texto reconocido en la ventana que tenga el foco (solo Windows)."""

from __future__ import annotations

import ctypes
import logging
import sys
import time

log = logging.getLogger(__name__)

if sys.platform == "win32":
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
    user32.GetClipboardSequenceNumber.restype = wintypes.DWORD
    user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    user32.RegisterClipboardFormatW.restype = wintypes.UINT
    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = ctypes.c_short
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.restype = wintypes.HGLOBAL

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
# Teclas modificadoras: Shift, Ctrl, Alt, Win izquierda, Win derecha
_MODIFIER_VKS = (0x10, 0x11, 0x12, 0x5B, 0x5C)


class _Clipboard:
    def __enter__(self):
        for _ in range(50):
            if user32.OpenClipboard(None):
                return self
            time.sleep(0.01)
        raise OSError("No se pudo abrir el portapapeles (otra aplicación lo está usando)")

    def __exit__(self, *exc):
        user32.CloseClipboard()


def _global_from_bytes(data: bytes):
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not handle:
        raise MemoryError("GlobalAlloc falló")
    ptr = kernel32.GlobalLock(handle)
    ctypes.memmove(ptr, data, len(data))
    kernel32.GlobalUnlock(handle)
    return handle


def get_clipboard_text() -> str | None:
    if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
        return None
    with _Clipboard():
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        ptr = kernel32.GlobalLock(handle)
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)


def set_clipboard_text(text: str, transient: bool = False):
    with _Clipboard():
        user32.EmptyClipboard()
        handle = _global_from_bytes(text.encode("utf-16-le") + b"\x00\x00")
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            raise OSError("SetClipboardData falló")
        if transient:
            # Que el texto temporal no quede en el historial del portapapeles (Win+V) ni se sincronice.
            for fmt_name, payload in (
                ("CanIncludeInClipboardHistory", b"\x00\x00\x00\x00"),
                ("CanUploadToCloudClipboard", b"\x00\x00\x00\x00"),
            ):
                fmt = user32.RegisterClipboardFormatW(fmt_name)
                if fmt:
                    h = _global_from_bytes(payload)
                    if not user32.SetClipboardData(fmt, h):
                        kernel32.GlobalFree(h)


def modifiers_down() -> bool:
    return any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in _MODIFIER_VKS)


def wait_modifiers_released(timeout: float = 3.0):
    """Evita que el texto se mezcle con un Ctrl/Alt/Shift que el usuario aún tenga pulsado."""
    end = time.monotonic() + timeout
    while modifiers_down() and time.monotonic() < end:
        time.sleep(0.02)


_keyboard = None


def _controller():
    global _keyboard
    if _keyboard is None:
        from pynput.keyboard import Controller

        _keyboard = Controller()
    return _keyboard


def paste_text(text: str):
    from pynput.keyboard import Key, KeyCode

    previous = None
    try:
        previous = get_clipboard_text()
    except Exception:
        log.warning("No se pudo leer el portapapeles actual")
    set_clipboard_text(text, transient=True)
    seq = user32.GetClipboardSequenceNumber()
    kb = _controller()
    with kb.pressed(Key.ctrl):
        kb.tap(KeyCode.from_vk(0x56))  # tecla V, sea cual sea la distribución del teclado
    # Damos tiempo a la aplicación a leer el portapapeles antes de restaurarlo.
    time.sleep(0.35)
    if previous is not None and user32.GetClipboardSequenceNumber() == seq:
        try:
            set_clipboard_text(previous, transient=True)
        except Exception:
            log.warning("No se pudo restaurar el portapapeles")


def type_text(text: str):
    _controller().type(text)


def insert_text(text: str, method: str = "pegar"):
    if not text:
        return
    wait_modifiers_released()
    if method == "escribir":
        type_text(text)
    else:
        paste_text(text)
