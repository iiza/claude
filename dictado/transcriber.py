"""Motores de reconocimiento de voz: Whisper local (faster-whisper) o API compatible con OpenAI."""

from __future__ import annotations

import io
import json
import logging
import os
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.request
import uuid
import wave
from pathlib import Path

import numpy as np

from dictado.audio import SAMPLE_RATE

log = logging.getLogger(__name__)

MIN_SECONDS = 0.3
SILENCE_PEAK = 0.01  # pico máximo por debajo del cual consideramos que no se ha dicho nada
MIN_SPEECH_SECONDS = 0.3  # voz mínima (según el detector de voz) para transcribir

# Frases que Whisper "se inventa" con silencio o ruido (vienen de subtítulos de internet).
_HALLUCINATION_PATTERNS = [
    r"subt[ií]tulos? (realizados? |hechos? )?por la comunidad de amara\.org",
    r"subt[ií]tulos? (creados? )?por la comunidad de amara\.org",
    r"amara\.org",
]
_HALLUCINATION_EXACT = {
    "gracias por ver el video",
    "gracias por ver",
    "gracias por vernos",
    "suscribete",
    "suscribete al canal",
    "thank you for watching",
    "thanks for watching",
    "subtitles by the amaraorg community",
    "you",
    "",
}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())


def clean_text(text: str, prompt: str = "") -> str:
    text = " ".join(text.split())
    # Whisper a veces "repite" el texto de contexto cuando no oye voz: lo descartamos.
    norm, norm_prompt = _normalize(text), _normalize(prompt or "")
    if norm and norm_prompt and norm in norm_prompt:
        return ""
    for pattern in _HALLUCINATION_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    text = " ".join(text.split()).strip()
    if _normalize(text) in _HALLUCINATION_EXACT:
        return ""
    return text


def has_speech(audio: np.ndarray) -> bool:
    if audio.size < MIN_SECONDS * SAMPLE_RATE:
        return False
    return float(np.max(np.abs(audio))) >= SILENCE_PEAK


def speech_seconds(audio: np.ndarray) -> float:
    """Segundos de voz humana según el detector Silero VAD (incluido en faster-whisper)."""
    try:
        from faster_whisper.vad import VadOptions, get_speech_timestamps
    except Exception:
        log.warning("Detector de voz no disponible")
        return audio.size / SAMPLE_RATE
    chunks = get_speech_timestamps(audio, VadOptions(min_speech_duration_ms=150, speech_pad_ms=0))
    return sum(c["end"] - c["start"] for c in chunks) / SAMPLE_RATE


def _language(cfg) -> str | None:
    lang = (cfg.get("idioma") or "").strip().lower()
    return lang or None


# --------------------------------------------------------------------- local
class LocalTranscriber:
    """Whisper ejecutado en el propio PC con faster-whisper (CTranslate2)."""

    def __init__(self, cfg: dict, models_dir: Path):
        self.cfg = cfg
        self.models_dir = Path(models_dir)
        self.model = None
        self.device = None
        self.ready = threading.Event()
        self.error: str | None = None

    def is_downloaded(self) -> bool:
        name = str(self.cfg["modelo_local"])
        if os.path.isdir(name):
            return True
        slug = name.replace("/", "--").lower()
        if self.models_dir.is_dir():
            for entry in self.models_dir.iterdir():
                if entry.name.lower().startswith("models--") and entry.name.lower().endswith(slug):
                    return any(entry.glob("snapshots/*/model.bin"))
        return False

    def _devices(self):
        wanted = str(self.cfg.get("dispositivo") or "auto").lower()
        if wanted == "cpu":
            return [("cpu", "int8")]
        if wanted == "cuda":
            return [("cuda", "float16"), ("cpu", "int8")]
        try:
            import ctranslate2

            if ctranslate2.get_cuda_device_count() > 0:
                return [("cuda", "float16"), ("cpu", "int8")]
        except Exception:
            pass
        return [("cpu", "int8")]

    def load(self):
        from faster_whisper import WhisperModel

        self.models_dir.mkdir(parents=True, exist_ok=True)
        threads = max(4, (os.cpu_count() or 4) // 2)
        last_exc = None
        try:
            for device, compute_type in self._devices():
                try:
                    t0 = time.time()
                    model = WhisperModel(
                        self.cfg["modelo_local"], device=device, compute_type=compute_type,
                        download_root=str(self.models_dir), cpu_threads=threads,
                    )
                    # Calentamiento: también detecta pronto DLLs de CUDA que falten.
                    segments, _ = model.transcribe(
                        np.zeros(SAMPLE_RATE, dtype=np.float32), language=_language(self.cfg) or "es",
                        beam_size=1, vad_filter=False, without_timestamps=True,
                    )
                    list(segments)
                    self.model, self.device = model, device
                    log.info("Modelo %s cargado en %s (%s) en %.1fs", self.cfg["modelo_local"],
                             device, compute_type, time.time() - t0)
                    return
                except Exception as exc:
                    last_exc = exc
                    log.warning("No se pudo cargar el modelo en %s: %s", device, exc)
            self.error = f"No se pudo cargar el modelo de voz: {last_exc}"
            raise RuntimeError(self.error) from last_exc
        finally:
            self.ready.set()

    def transcribe(self, audio: np.ndarray) -> str:
        self.ready.wait()
        if self.model is None:
            raise RuntimeError(self.error or "El modelo de voz no está disponible")
        prompt = (self.cfg.get("texto_contexto") or "").strip() or None
        segments, info = self.model.transcribe(
            audio,
            language=_language(self.cfg),
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 700, "speech_pad_ms": 300},
            initial_prompt=prompt,
            condition_on_previous_text=False,
            without_timestamps=True,
        )
        text = " ".join(seg.text.strip() for seg in segments)
        log.info("Transcrito %.1fs de audio (idioma %s)", audio.size / SAMPLE_RATE, info.language)
        return text


# ----------------------------------------------------------------------- API
def to_wav_bytes(audio: np.ndarray) -> bytes:
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return buf.getvalue()


class ApiTranscriber:
    """Cualquier API compatible con /v1/audio/transcriptions de OpenAI (OpenAI, Groq...)."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.ready = threading.Event()
        self.ready.set()
        self.error = None
        self.device = "api"

    def is_downloaded(self) -> bool:
        return True

    def load(self):
        if not self._key():
            self.error = "Falta la clave de la API ('api_clave' en la configuración)."
            raise RuntimeError(self.error)

    def _key(self) -> str:
        return (self.cfg.get("api_clave") or os.environ.get("OPENAI_API_KEY") or "").strip()

    def transcribe(self, audio: np.ndarray) -> str:
        fields = {"model": self.cfg["api_modelo"], "response_format": "json"}
        if _language(self.cfg):
            fields["language"] = _language(self.cfg)
        if (self.cfg.get("texto_contexto") or "").strip():
            fields["prompt"] = self.cfg["texto_contexto"].strip()

        boundary = uuid.uuid4().hex
        body = io.BytesIO()
        for name, value in fields.items():
            body.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n".encode())
            body.write(str(value).encode("utf-8") + b"\r\n")
        body.write(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"audio.wav\"\r\n"
            "Content-Type: audio/wav\r\n\r\n".encode()
        )
        body.write(to_wav_bytes(audio) + b"\r\n")
        body.write(f"--{boundary}--\r\n".encode())

        url = self.cfg["api_url"].rstrip("/") + "/audio/transcriptions"
        req = urllib.request.Request(
            url, data=body.getvalue(), method="POST",
            headers={
                "Authorization": f"Bearer {self._key()}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": "Dictado",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"La API respondió {exc.code}: {detail}") from exc
        return data.get("text", "")


def create(cfg: dict, models_dir: Path):
    if str(cfg.get("motor", "local")).lower() == "api":
        return ApiTranscriber(cfg)
    return LocalTranscriber(cfg, models_dir)
