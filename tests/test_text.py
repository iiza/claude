import unittest

import numpy as np

from dictado.audio import SAMPLE_RATE, resample
from dictado.transcriber import clean_text, has_speech, to_wav_bytes


class TextTests(unittest.TestCase):
    def test_clean_keeps_normal_text(self):
        self.assertEqual(clean_text("  Hola,   ¿qué tal? "), "Hola, ¿qué tal?")

    def test_removes_amara_hallucination(self):
        self.assertEqual(clean_text("Subtítulos realizados por la comunidad de Amara.org"), "")
        self.assertEqual(clean_text("Nos vemos mañana. Subtítulos por la comunidad de Amara.org"),
                         "Nos vemos mañana.")

    def test_removes_exact_hallucinations(self):
        self.assertEqual(clean_text("¡Gracias por ver el vídeo!"), "")
        self.assertEqual(clean_text("Suscríbete."), "")
        self.assertEqual(clean_text("Gracias."), "Gracias.")


class PromptEchoTests(unittest.TestCase):
    def test_drops_echo_of_context(self):
        prompt = "Hola, ¿qué tal? Te escribo para confirmar la reunión de mañana a las diez."
        self.assertEqual(clean_text("Hola, ¿qué tal?", prompt), "")
        self.assertEqual(clean_text("Iñaki, Kubernetes", "Iñaki, Kubernetes, Osakidetza"), "")

    def test_keeps_real_text_with_context(self):
        self.assertEqual(clean_text("Mañana hablo con Iñaki.", "Iñaki, Kubernetes"), "Mañana hablo con Iñaki.")


class VadTests(unittest.TestCase):
    def test_no_voice_in_silence_or_noise(self):
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            self.skipTest("faster-whisper no instalado")
        from dictado.transcriber import speech_seconds

        rng = np.random.default_rng(0)
        self.assertLess(speech_seconds(np.zeros(SAMPLE_RATE * 2, np.float32)), 0.3)
        noise = (0.02 * rng.standard_normal(SAMPLE_RATE * 2)).astype(np.float32)
        self.assertLess(speech_seconds(noise), 0.3)


class AudioTests(unittest.TestCase):
    def test_has_speech(self):
        self.assertFalse(has_speech(np.zeros(SAMPLE_RATE, np.float32)))
        self.assertFalse(has_speech(np.full(100, 0.5, np.float32)))
        self.assertTrue(has_speech(np.full(SAMPLE_RATE, 0.1, np.float32)))

    def test_resample(self):
        audio = np.ones(48000, np.float32)
        out = resample(audio, 48000)
        self.assertEqual(out.size, SAMPLE_RATE)
        self.assertEqual(out.dtype, np.float32)

    def test_wav(self):
        data = to_wav_bytes(np.zeros(1600, np.float32))
        self.assertTrue(data.startswith(b"RIFF"))
        self.assertEqual(len(data), 44 + 3200)


if __name__ == "__main__":
    unittest.main()
