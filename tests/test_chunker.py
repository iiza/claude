import unittest

from dictado.chunker import find_cut

SR = 16000


def seg(a, b):
    return {"start": int(a * SR), "end": int(b * SR)}


class ChunkerTests(unittest.TestCase):
    def test_no_speech(self):
        self.assertIsNone(find_cut([], 10 * SR))

    def test_waits_while_still_talking(self):
        self.assertIsNone(find_cut([seg(0.2, 3.9)], 4 * SR))

    def test_cuts_after_pause_at_end(self):
        cut = find_cut([seg(0.2, 3.0)], int(3.6 * SR))
        self.assertEqual(cut, int(3.2 * SR))

    def test_cuts_in_middle_gap(self):
        cut = find_cut([seg(0.2, 3.0), seg(3.8, 5.0)], int(5.1 * SR))
        self.assertEqual(cut, int(3.4 * SR))

    def test_ignores_short_gaps(self):
        self.assertIsNone(find_cut([seg(0.2, 3.0), seg(3.2, 5.0)], int(5.1 * SR)))

    def test_too_early_to_cut(self):
        self.assertIsNone(find_cut([seg(0.1, 1.0)], int(1.8 * SR)))

    def test_forced_cut_for_long_speech(self):
        cut = find_cut([seg(0, 10), seg(10.3, 20), seg(20.1, 26)], 26 * SR)
        self.assertEqual(cut, int(10.15 * SR))


if __name__ == "__main__":
    unittest.main()
