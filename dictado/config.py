"""Configuración del usuario en %APPDATA%\\Dictado\\config.json."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from dictado import APP_NAME

log = logging.getLogger(__name__)

DEFAULTS = {
    "modo": "mantener",
    "tiempo_pulsacion": 0.3,
    "duracion_maxima": 300,
    "idioma": "es",
    "motor": "local",
    "modelo_local": "large-v3-turbo",
    "dispositivo": "auto",
    "api_url": "https://api.openai.com/v1",
    "api_modelo": "gpt-4o-transcribe",
    "api_clave": "",
    "metodo_insercion": "pegar",
    "espacio_final": True,
    "sonidos": True,
    "microfono": None,
    "microfono_siempre_abierto": False,
    "texto_contexto": "",
}

# Valor por defecto de la versión 0.1.0: provocaba que, sin voz, se escribiera esa frase.
_OLD_CONTEXT = "Hola, ¿qué tal? Te escribo para confirmar la reunión de mañana a las diez."

HELP = {
    "modo": "'mantener': mantén Ctrl pulsado mientras hablas y suéltalo al terminar. "
    "'alternar': toca Ctrl una vez para empezar y otra para terminar (Esc cancela).",
    "tiempo_pulsacion": "Segundos que hay que mantener Ctrl (solo) para empezar a grabar en modo 'mantener'.",
    "duracion_maxima": "Segundos máximos de una grabación.",
    "idioma": "Código de idioma ('es', 'en', 'ca', 'eu', 'gl', 'fr'...) o '' para detectarlo automáticamente.",
    "motor": "'local': reconocimiento en tu PC con Whisper (gratis, privado, sin internet tras la primera descarga). "
    "'api': servicio en la nube compatible con OpenAI (requiere clave).",
    "modelo_local": "Modelo Whisper: 'large-v3-turbo' (muy bueno, recomendado), 'large-v3' (el mejor, más lento), "
    "'medium', 'small' o 'base' (más rápidos, peores).",
    "dispositivo": "'auto', 'cpu' o 'cuda' (tarjeta NVIDIA).",
    "api_url": "URL base de la API. OpenAI: https://api.openai.com/v1 · Groq: https://api.groq.com/openai/v1",
    "api_modelo": "OpenAI: 'gpt-4o-transcribe' o 'whisper-1' · Groq: 'whisper-large-v3-turbo' o 'whisper-large-v3'.",
    "api_clave": "Tu clave de la API (si está vacía se usa la variable de entorno OPENAI_API_KEY).",
    "metodo_insercion": "'pegar': usa el portapapeles y Ctrl+V (rápido, lo restaura después). "
    "'escribir': simula la escritura letra a letra.",
    "espacio_final": "Añadir un espacio al final para encadenar dictados.",
    "sonidos": "Pitido al empezar y al terminar de grabar.",
    "microfono": "null = micrófono predeterminado de Windows, o parte del nombre del micrófono a usar.",
    "microfono_siempre_abierto": "true = el micrófono queda abierto y no se pierde ni una sílaba al empezar "
    "(Windows mostrará siempre el icono de micrófono en uso; con cascos Bluetooth puede empeorar el sonido).",
    "texto_contexto": "Opcional: nombres propios o términos técnicos que uses a menudo, separados por comas, "
    "para que los escriba bien (p. ej. 'Iñaki, Kubernetes, Osakidetza').",
}


def _base(env: str, fallback: Path) -> Path:
    value = os.environ.get(env)
    return Path(value) if value else fallback


def config_dir() -> Path:
    path = _base("APPDATA", Path.home() / ".config") / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def data_dir() -> Path:
    path = _base("LOCALAPPDATA", Path.home() / ".local" / "share") / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return config_dir() / "config.json"


def load() -> tuple[dict, str | None]:
    """Devuelve (configuración, mensaje_de_error_o_None)."""
    path = config_path()
    cfg = dict(DEFAULTS)
    user: dict = {}
    error = None
    if path.exists():
        try:
            user = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(user, dict):
                raise ValueError("el archivo no contiene un objeto JSON")
        except Exception as exc:  # no sobrescribimos el archivo del usuario si está mal
            log.exception("No se pudo leer %s", path)
            return cfg, f"No se pudo leer la configuración ({exc}). Se usan los valores por defecto."
    if user.get("texto_contexto") == _OLD_CONTEXT:
        user["texto_contexto"] = ""
        user.pop("_ayuda", None)  # fuerza reescribir el archivo con la ayuda nueva
    cfg.update({k: v for k, v in user.items() if k in DEFAULTS})

    if "_ayuda" not in user or any(k not in user for k in DEFAULTS):
        merged = {"_ayuda": HELP}
        merged.update({k: cfg[k] for k in DEFAULTS})
        try:
            path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            log.exception("No se pudo escribir %s", path)
    return cfg, error
