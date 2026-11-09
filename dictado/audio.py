"""Captura de audio del micrófono a 16 kHz mono (formato que espera Whisper)."""

from __future__ import annotations

import collections
import logging
import threading

import numpy as np

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000


def resample(audio: np.ndarray, src_rate: int, dst_rate: int = SAMPLE_RATE) -> np.ndarray:
    if src_rate == dst_rate or audio.size == 0:
        return audio.astype(np.float32, copy=False)
    duration = audio.size / src_rate
    n_out = int(round(duration * dst_rate))
    x_old = np.linspace(0.0, duration, num=audio.size, endpoint=False)
    x_new = np.linspace(0.0, duration, num=n_out, endpoint=False)
    return np.interp(x_new, x_old, audio).astype(np.float32)


def _find_device(name):
    """Acepta None, un índice o parte del nombre de un dispositivo de entrada."""
    if name is None or name == "":
        return None
    if isinstance(name, int):
        return name
    import sounddevice as sd

    wanted = str(name).lower()
    for idx, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0 and wanted in dev["name"].lower():
            return idx
    log.warning("No se encontró el micrófono %r; se usa el predeterminado", name)
    return None


class Recorder:
    def __init__(self, device=None, always_open: bool = False, preroll_seconds: float = 0.5):
        self.device = _find_device(device)
        self.always_open = always_open
        self._lock = threading.Lock()
        self._stream = None
        self._rate = SAMPLE_RATE
        self._recording = False
        self._chunks: list[np.ndarray] = []
        self._preroll: collections.deque = collections.deque()
        self._preroll_frames = 0
        self._preroll_seconds = preroll_seconds
        if always_open:
            self._open()

    # ------------------------------------------------------------- interno
    def _callback(self, indata, frames, time_info, status):
        data = indata[:, 0].copy()
        with self._lock:
            if self._recording:
                self._chunks.append(data)
            elif self.always_open:
                self._preroll.append(data)
                self._preroll_frames += len(data)
                limit = int(self._preroll_seconds * self._rate)
                while self._preroll and self._preroll_frames - len(self._preroll[0]) >= limit:
                    self._preroll_frames -= len(self._preroll.popleft())

    def _open(self):
        if self._stream is not None:
            return
        import sounddevice as sd

        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                device=self.device, callback=self._callback,
            )
            self._rate = SAMPLE_RATE
        except Exception:
            # Algunos micrófonos no aceptan 16 kHz: grabamos a su frecuencia nativa y remuestreamos.
            info = sd.query_devices(self.device, "input")
            rate = int(info["default_samplerate"])
            log.info("El micrófono no acepta 16 kHz; se graba a %d Hz", rate)
            stream = sd.InputStream(
                samplerate=rate, channels=1, dtype="float32",
                device=self.device, callback=self._callback,
            )
            self._rate = rate
        stream.start()
        self._stream = stream

    def _close(self):
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                log.exception("Error al cerrar el micrófono")

    # ------------------------------------------------------------- público
    def start(self):
        with self._lock:
            self._chunks = list(self._preroll) if self.always_open else []
            self._preroll.clear()
            self._preroll_frames = 0
            self._recording = True
        try:
            self._open()
        except Exception:
            with self._lock:
                self._recording = False
            raise

    def peek(self) -> np.ndarray:
        """Audio grabado hasta ahora (sin detener la grabación)."""
        with self._lock:
            chunks = list(self._chunks)
            rate = self._rate
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return resample(np.concatenate(chunks), rate)

    def stop(self) -> np.ndarray:
        with self._lock:
            self._recording = False
            chunks, self._chunks = self._chunks, []
        rate = self._rate
        if not self.always_open:
            self._close()
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return resample(np.concatenate(chunks), rate)

    def cancel(self):
        self.stop()

    def close(self):
        with self._lock:
            self._recording = False
        self._close()
