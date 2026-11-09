import unittest

from dictado.gesture import BLOCKED, HOLD, IDLE, REC_HOLD, REC_TOGGLE, TOGGLE, CtrlGesture

LCTRL, RCTRL, KEY_C, ESC = 0xA2, 0xA3, 0x43, 0x1B


class Recorder:
    def __init__(self):
        self.events = []

    def gesture(self, mode=HOLD, **kw):
        return CtrlGesture(
            mode=mode,
            on_start=lambda: self.events.append("start"),
            on_cancel=lambda: self.events.append("cancel"),
            on_finish=lambda: self.events.append("finish"),
            **kw,
        )


class HoldModeTests(unittest.TestCase):
    def setUp(self):
        self.r = Recorder()
        self.g = self.r.gesture(HOLD, hold_threshold=0.3)

    def test_hold_and_release_dictates(self):
        self.g.ctrl_down(LCTRL, 0.0)
        self.g.tick(0.1)
        self.assertEqual(self.r.events, [])
        self.g.ctrl_down(LCTRL, 0.2)  # autorrepetición
        self.g.tick(0.31)
        self.assertEqual(self.g.state, REC_HOLD)
        self.g.ctrl_up(LCTRL, 2.0)
        self.assertEqual(self.r.events, ["start", "finish"])
        self.assertEqual(self.g.state, IDLE)

    def test_quick_tap_does_nothing(self):
        self.g.ctrl_down(LCTRL, 0.0)
        self.g.tick(0.1)
        self.g.ctrl_up(LCTRL, 0.15)
        self.g.tick(1.0)
        self.assertEqual(self.r.events, [])

    def test_ctrl_c_is_not_dictation(self):
        self.g.ctrl_down(LCTRL, 0.0)
        self.g.other_down(KEY_C, 0.1)
        self.g.tick(0.5)
        self.g.other_up(KEY_C, 0.6)
        self.g.ctrl_up(LCTRL, 0.7)
        self.assertEqual(self.r.events, [])
        self.assertEqual(self.g.state, IDLE)

    def test_slow_shortcut_cancels_recording(self):
        self.g.ctrl_down(LCTRL, 0.0)
        self.g.tick(0.4)
        self.g.other_down(KEY_C, 0.5)
        self.g.ctrl_up(LCTRL, 0.6)
        self.assertEqual(self.r.events, ["start", "cancel"])

    def test_ctrl_click_is_not_dictation(self):
        self.g.ctrl_down(LCTRL, 0.0)
        self.g.other_down(None, 0.05)  # clic de ratón
        self.g.tick(1.0)
        self.g.ctrl_up(LCTRL, 1.1)
        self.assertEqual(self.r.events, [])

    def test_shift_held_then_ctrl_is_shortcut(self):
        self.g.other_down(0x10, 0.0)
        self.g.ctrl_down(LCTRL, 0.1)
        self.g.tick(1.0)
        self.assertEqual(self.g.state, BLOCKED)
        self.g.ctrl_up(LCTRL, 1.1)
        self.assertEqual(self.r.events, [])

    def test_stale_other_key_is_forgotten(self):
        self.g.other_down(0x5B, 0.0)  # Win pulsada y nunca soltada (p. ej. Win+L)
        self.g.ctrl_down(LCTRL, 10.0)
        self.g.tick(10.4)
        self.assertEqual(self.r.events, ["start"])

    def test_altgr_is_not_dictation(self):
        # AltGr en teclados españoles genera Ctrl izquierdo + Alt derecho
        self.g.ctrl_down(LCTRL, 0.0)
        self.g.other_down(0xA5, 0.0)
        self.g.tick(0.5)
        self.g.other_up(0xA5, 0.6)
        self.g.ctrl_up(LCTRL, 0.6)
        self.assertEqual(self.r.events, [])

    def test_max_duration(self):
        g = self.r.gesture(HOLD, hold_threshold=0.3, max_duration=5)
        g.ctrl_down(LCTRL, 0.0)
        g.tick(0.3)
        g.tick(5.4)
        self.assertEqual(self.r.events, ["start", "finish"])
        self.assertEqual(g.state, BLOCKED)
        g.ctrl_up(LCTRL, 6.0)
        self.assertEqual(self.r.events, ["start", "finish"])
        self.assertEqual(g.state, IDLE)

    def test_pause(self):
        self.g.set_enabled(False)
        self.g.ctrl_down(LCTRL, 0.0)
        self.g.tick(1.0)
        self.g.ctrl_up(LCTRL, 1.1)
        self.assertEqual(self.r.events, [])
        self.g.set_enabled(True)
        self.g.ctrl_down(LCTRL, 2.0)
        self.g.tick(2.4)
        self.g.ctrl_up(LCTRL, 3.0)
        self.assertEqual(self.r.events, ["start", "finish"])

    def test_both_ctrls(self):
        self.g.ctrl_down(LCTRL, 0.0)
        self.g.ctrl_down(RCTRL, 0.1)
        self.g.tick(1.0)
        self.g.ctrl_up(LCTRL, 1.1)
        self.g.ctrl_up(RCTRL, 1.2)
        self.assertEqual(self.r.events, [])


class ToggleModeTests(unittest.TestCase):
    def setUp(self):
        self.r = Recorder()
        self.g = self.r.gesture(TOGGLE, tap_max=0.4)

    def tap(self, t):
        self.g.ctrl_down(LCTRL, t)
        self.g.ctrl_up(LCTRL, t + 0.1)

    def test_tap_tap(self):
        self.tap(0.0)
        self.assertEqual(self.g.state, REC_TOGGLE)
        self.g.tick(3.0)
        self.tap(5.0)
        self.assertEqual(self.r.events, ["start", "finish"])
        self.assertEqual(self.g.state, IDLE)

    def test_long_press_does_not_start(self):
        self.g.ctrl_down(LCTRL, 0.0)
        self.g.ctrl_up(LCTRL, 1.0)
        self.assertEqual(self.r.events, [])

    def test_shortcut_while_recording_keeps_recording(self):
        self.tap(0.0)
        self.g.ctrl_down(LCTRL, 1.0)
        self.g.other_down(KEY_C, 1.05)
        self.g.other_up(KEY_C, 1.1)
        self.g.ctrl_up(LCTRL, 1.15)
        self.assertEqual(self.g.state, REC_TOGGLE)
        self.assertEqual(self.r.events, ["start"])
        self.tap(2.0)
        self.assertEqual(self.r.events, ["start", "finish"])

    def test_escape_cancels(self):
        self.tap(0.0)
        self.g.other_down(ESC, 1.0, is_escape=True)
        self.assertEqual(self.r.events, ["start", "cancel"])
        self.assertEqual(self.g.state, IDLE)

    def test_typing_while_recording_does_not_stop(self):
        self.tap(0.0)
        self.g.other_down(0x41, 0.5)
        self.g.other_up(0x41, 0.6)
        self.assertEqual(self.g.state, REC_TOGGLE)


if __name__ == "__main__":
    unittest.main()
