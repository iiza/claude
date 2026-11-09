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
