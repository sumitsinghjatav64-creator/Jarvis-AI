import unittest

from core.vad import EnergyVAD


class EnergyVADTests(unittest.TestCase):
    def test_silence_is_not_speech(self):
        vad = EnergyVAD(sample_rate=16000, threshold=0.03)
        self.assertFalse(vad.is_speech([0] * 320))

    def test_loud_frame_is_speech(self):
        vad = EnergyVAD(sample_rate=16000, threshold=0.03)
        self.assertTrue(vad.is_speech([2000] * 320))

    def test_hangover_keeps_short_gap_in_same_turn(self):
        vad = EnergyVAD(sample_rate=16000, threshold=0.03, hangover_ms=250)
        self.assertTrue(vad.is_speech([3000] * 320))
        self.assertTrue(vad.is_speech([0] * 320))

    def test_reset_clears_hangover(self):
        vad = EnergyVAD(sample_rate=16000, threshold=0.03, hangover_ms=250)
        vad.is_speech([3000] * 320)
        vad.reset()
        self.assertFalse(vad.is_speech([0] * 320))


if __name__ == "__main__":
    unittest.main()
