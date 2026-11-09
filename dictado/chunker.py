"""Decide dónde cortar el audio mientras se habla para ir transcribiendo por adelantado.

Así, al soltar Ctrl solo queda por transcribir el último trozo y el texto aparece casi al momento.
"""

from __future__ import annotations

SR = 16000


def find_cut(speech: list[dict], n_samples: int, sr: int = SR, min_chunk_s: float = 2.0,
             min_gap_s: float = 0.45, max_chunk_s: float = 25.0) -> int | None:
    """Devuelve la muestra por la que cortar el audio pendiente, o None si aún no conviene.

    ``speech`` son los tramos de voz (``start``/``end`` en muestras) que detecta el VAD en el audio pendiente.
    Solo se corta en una pausa ya completa, para no partir palabras.
    """
    if not speech:
        return None
    min_gap = int(min_gap_s * sr)
    candidates = []
    for a, b in zip(speech, speech[1:]):
        if b["start"] - a["end"] >= min_gap:
            candidates.append((a["end"] + b["start"]) // 2)
    if n_samples - speech[-1]["end"] >= min_gap:
        candidates.append(min(n_samples, speech[-1]["end"] + int(0.2 * sr)))
    good = [c for c in candidates if c >= min_chunk_s * sr]
    if good:
        return max(good)
    if n_samples >= max_chunk_s * sr and len(speech) >= 2:
        # Frase muy larga sin pausas claras: cortamos en el hueco más grande.
        gaps = [((b["start"] - a["end"]), (a["end"] + b["start"]) // 2) for a, b in zip(speech, speech[1:])]
        return max(gaps)[1]
    return None
