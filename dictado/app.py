"""Aplicación de bandeja del sistema: une teclado, micrófono, reconocimiento e inserción de texto."""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import queue
import subprocess
import sys
import threading
import time

# En un .exe sin consola sys.stdout/stderr son None y algunas librerías fallan al escribir en ellos.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

from dictado import APP_NAME, __version__, config, winutil  # noqa: E402

log = logging.getLogger("dictado")


class Session:
    """Un dictado: se va transcribiendo por trozos mientras se habla."""

    def __init__(self):
        self.lock = threading.Lock()
        self.committed = 0  # muestras ya enviadas a transcribir
        self.closed = False
        self.cancelled = False
        self.texts: list[str] = []


def setup_logging():
    path = config.data_dir() / "dictado.log"
    handler = logging.handlers.RotatingFileHandler(path, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    if not getattr(sys, "frozen", False):
        root.addHandler(logging.StreamHandler())
    return path


class DictadoApp:
    def __init__(self, cfg: dict, config_error: str | None = None):
        import pystray

        from dictado import transcriber
        from dictado.audio import Recorder
        from dictado.gesture import HOLD, TOGGLE, CtrlGesture
        from dictado.keyhook import GlobalHooks

        self.cfg = cfg
        self.config_error = config_error
        self.engine = transcriber.create(cfg, config.data_dir() / "modelos")
        self.recorder = Recorder(cfg.get("microfono"), bool(cfg.get("microfono_siempre_abierto")),
                                 preroll_seconds=float(cfg["tiempo_pulsacion"]) + 0.3)
        mode = TOGGLE if str(cfg.get("modo")).lower() == TOGGLE else HOLD
        self.gesture = CtrlGesture(
            mode=mode,
            hold_threshold=float(cfg["tiempo_pulsacion"]),
            max_duration=float(cfg["duracion_maxima"]),
            on_start=lambda: self._audio_cmds.put("start"),
            on_cancel=lambda: self._audio_cmds.put("cancel"),
            on_finish=lambda: self._audio_cmds.put("finish"),
        )
        self.hooks = GlobalHooks(self.gesture)

        self._audio_cmds: queue.Queue = queue.Queue()
        self._jobs: queue.Queue = queue.Queue()
        self._pending = 0
        self._session: Session | None = None
        self._recording = False
        self._loading = True
        self._error: str | None = None
        self._stop = threading.Event()

        menu = pystray.Menu(
            pystray.MenuItem(lambda item: self._status_text(), None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Pausar dictado", self._toggle_pause, checked=lambda item: not self.gesture.enabled),
            pystray.MenuItem("Iniciar con Windows", self._toggle_autostart,
                             checked=lambda item: winutil.autostart_enabled()),
            pystray.MenuItem("Abrir configuración", self._open_config),
            pystray.MenuItem("Ver registro", self._open_log),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", self._quit),
        )
        from dictado.icons import make_icon

        self._make_icon = make_icon
        self.icon = pystray.Icon(APP_NAME, make_icon("loading"), f"{APP_NAME}: cargando…", menu)

    # ------------------------------------------------------------ estado UI
    def _state(self) -> str:
        if self._recording:
            return "recording"
        if self._pending:
            return "busy"
        if self._loading:
            return "loading"
        if self._error:
            return "error"
        if not self.gesture.enabled:
            return "paused"
        return "ready"

    def _status_text(self) -> str:
        return {
            "recording": "Escuchando…",
            "busy": "Transcribiendo…",
            "loading": "Cargando el modelo de voz…",
            "error": f"Error: {self._error}"[:120] if self._error else "Error",
            "paused": "En pausa",
            "ready": "Listo: " + ("mantén Ctrl y habla" if self.gesture.mode == "mantener"
                                   else "toca Ctrl para empezar/terminar"),
        }[self._state()]

    def _refresh(self):
        try:
            state = self._state()
            self.icon.icon = self._make_icon(state)
            self.icon.title = f"{APP_NAME} – {self._status_text()}"[:127]
            self.icon.update_menu()
        except Exception:
            log.exception("No se pudo actualizar el icono")

    def _notify(self, message: str):
        log.info("Aviso: %s", message)
        try:
            self.icon.notify(message, APP_NAME)
        except Exception:
            pass

    # -------------------------------------------------------------- hilos
    def _load_engine(self):
        try:
            if not self.engine.is_downloaded():
                self._notify("Descargando el modelo de reconocimiento de voz (solo la primera vez; "
                             "puede tardar varios minutos)…")
            self.engine.load()
            self._error = None
            mode_hint = ("Mantén pulsada la tecla Ctrl mientras hablas y suéltala al terminar."
                         if self.gesture.mode == "mantener" else
                         "Toca Ctrl para empezar a dictar y otra vez para terminar.")
            self._notify(f"Listo. {mode_hint}")
        except Exception as exc:
            log.exception("Fallo al cargar el motor")
            self._error = str(exc)
            self._notify(str(exc))
        finally:
            self._loading = False
            self._refresh()

    def _ticker(self):
        while not self._stop.is_set():
            self.gesture.tick(time.monotonic())
            time.sleep(0.03)

    def _audio_loop(self):
        sounds = bool(self.cfg.get("sonidos", True))
        while not self._stop.is_set():
            cmd = self._audio_cmds.get()
            try:
                if cmd == "start":
                    if sounds:
                        winutil.beep((880,), 60)
                    self._session = Session()
                    self.recorder.start()
                    self._recording = True
                    self._refresh()
                elif cmd == "cancel":
                    session, self._session = self._session, None
                    if session is not None:
                        with session.lock:
                            session.closed = session.cancelled = True
                    self.recorder.cancel()
                    self._recording = False
                    self._refresh()
                elif cmd == "finish":
                    time.sleep(0.12)  # recoger el final de la última palabra
                    audio = self.recorder.stop()
                    self._recording = False
                    if sounds:
                        winutil.beep((660,), 60)
                    session, self._session = self._session, None
                    if session is None:
                        continue
                    with session.lock:
                        session.closed = True
                        tail = audio[session.committed:]
                    self._pending += 1
                    self._jobs.put((session, tail, True))
                    self._refresh()
                elif cmd == "quit":
                    return
            except Exception as exc:
                log.exception("Error de audio")
                self._recording = False
                self._refresh()
                self._notify(f"No se pudo usar el micrófono: {exc}")

    def _stream_loop(self):
        """Mientras se habla, corta en las pausas y transcribe por adelantado lo ya dicho."""
        from dictado import chunker, transcriber
        from dictado.audio import SAMPLE_RATE

        while not self._stop.is_set():
            time.sleep(0.4)
            session = self._session
            if session is None or session.closed or self._loading:
                continue
            try:
                audio = self.recorder.peek()
                with session.lock:
                    if session.closed:
                        continue
                    pending = audio[session.committed:]
                    if pending.size < 2 * SAMPLE_RATE:
                        continue
                    speech = transcriber.speech_chunks(pending)
                    cut = chunker.find_cut(speech, pending.size)
                    if cut is None:
                        if not speech and pending.size > 5 * SAMPLE_RATE:
                            session.committed += pending.size - SAMPLE_RATE  # descartar silencio largo
                        continue
                    session.committed += cut
                self._jobs.put((session, pending[:cut], False))
            except Exception:
                log.exception("Error al trocear el audio")

    def _transcribe_chunk(self, session: Session, audio) -> str:
        from dictado import transcriber

        if not transcriber.has_speech(audio):
            return ""
        voice = transcriber.speech_seconds(audio)
        if voice < transcriber.MIN_SPEECH_SECONDS:
            log.info("No se detectó voz (%.2fs); se ignora", voice)
            return ""
        t0 = time.time()
        raw = self.engine.transcribe(audio, previous=" ".join(session.texts))
        text = transcriber.clean_text(raw, self.cfg.get("texto_contexto", ""))
        log.info("Trozo de %.1fs reconocido en %.2fs", audio.size / 16000, time.time() - t0)
        return text

    def _transcribe_loop(self):
        from dictado import output

        while not self._stop.is_set():
            job = self._jobs.get()
            if job is None:
                return
            session, audio, final = job
            try:
                if session.cancelled:
                    continue
                if final and self._loading:
                    self._notify("El modelo aún se está cargando; tu dictado se escribirá en cuanto esté listo.")
                text = self._transcribe_chunk(session, audio)
                if text:
                    session.texts.append(text)
                if final:
                    full = " ".join(session.texts)
                    if full:
                        if self.cfg.get("espacio_final", True) and not full.endswith(("\n", " ")):
                            full += " "
                        output.insert_text(full, str(self.cfg.get("metodo_insercion", "pegar")))
            except Exception as exc:
                log.exception("Error al transcribir")
                self._notify(f"Error al reconocer la voz: {exc}")
            finally:
                if final:
                    self._pending = max(0, self._pending - 1)
                    self._refresh()

    # ------------------------------------------------------------- menú
    def _toggle_pause(self, icon, item):
        self.gesture.set_enabled(not self.gesture.enabled)
        self._refresh()

    def _toggle_autostart(self, icon, item):
        try:
            winutil.set_autostart(not winutil.autostart_enabled())
        except Exception as exc:
            self._notify(f"No se pudo cambiar el inicio automático: {exc}")
        self._refresh()

    def _open_config(self, icon, item):
        self._notify("Al guardar los cambios, cierra Dictado (Salir) y vuelve a abrirlo para aplicarlos.")
        subprocess.Popen(["notepad.exe", str(config.config_path())])

    def _open_log(self, icon, item):
        subprocess.Popen(["notepad.exe", str(config.data_dir() / "dictado.log")])

    def _quit(self, icon, item):
        self._stop.set()
        self.hooks.stop()
        self._audio_cmds.put("quit")
        self._jobs.put(None)
        self.recorder.close()
        icon.stop()

    # -------------------------------------------------------------- run
    def _setup(self, icon):
        icon.visible = True
        if self.config_error:
            self._notify(self.config_error)
        for target in (self._load_engine, self._ticker, self._audio_loop, self._stream_loop,
                       self._transcribe_loop):
            threading.Thread(target=target, daemon=True, name=target.__name__).start()
        self.hooks.start()
        self._refresh()

    def run(self):
        self.icon.run(setup=self._setup)


def selftest(out_path: str | None) -> int:
    """Comprueba que el ejecutable empaquetado incluye todo lo necesario (usado en CI)."""
    import tempfile
    import traceback

    import numpy as np

    lines = []
    code = 0
    try:
        import ctranslate2  # noqa: F401
        import onnxruntime  # noqa: F401
        import pynput.keyboard  # noqa: F401
        import pynput.mouse  # noqa: F401
        import pystray  # noqa: F401
        import sounddevice  # noqa: F401
        from faster_whisper import WhisperModel

        from dictado import gesture, icons, keyhook, output, transcriber  # noqa: F401

        icons.make_icon("recording")
        lines.append("imports OK")
        with tempfile.TemporaryDirectory() as tmp:
            model = WhisperModel("tiny", device="cpu", compute_type="int8", download_root=tmp)
            t = np.arange(16000 * 2) / 16000
            audio = (0.1 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
            segments, info = model.transcribe(audio, language="es", vad_filter=True)
            list(segments)
            segments, info = model.transcribe(audio, language="es", vad_filter=False, beam_size=5)
            lines.append(f"whisper OK: {[s.text for s in segments]!r}")
            lines.append(f"vad OK: {transcriber.speech_seconds(audio):.2f}s")
        lines.append("SELFTEST OK")
    except Exception:
        code = 1
        lines.append(traceback.format_exc())
    text = "\n".join(lines)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        print(text)
    return code


def main():
    parser = argparse.ArgumentParser(prog=APP_NAME)
    parser.add_argument("--selftest", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--selftest-out", help=argparse.SUPPRESS)
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    args = parser.parse_args()
    if args.selftest:
        sys.exit(selftest(args.selftest_out))

    log_path = setup_logging()
    log.info("Iniciando %s %s", APP_NAME, __version__)
    if not winutil.single_instance():
        winutil.message_box("Dictado ya se está ejecutando (mira el icono del micrófono junto al reloj).")
        return
    try:
        cfg, error = config.load()
        DictadoApp(cfg, error).run()
    except Exception as exc:
        log.exception("Error fatal")
        winutil.message_box(f"Dictado se ha cerrado por un error:\n\n{exc}\n\nMás detalles en:\n{log_path}",
                            error=True)
        sys.exit(1)
