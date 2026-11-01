import unittest

from core.audio_preprocessor import AudioPreprocessor


class AudioPreprocessorTests(unittest.TestCase):
    def test_passthrough_preserves_shape_and_dtype(self):
        processor = AudioPreprocessor()
        samples = [0, 100, -100, 200]
        result = processor.process(samples, sample_rate=16000)
        self.assertEqual(len(result), len(samples))

    def test_empty_audio_is_safe(self):
        self.assertEqual(AudioPreprocessor().process([], 16000), [])

    def test_backend_status_is_reported(self):
        status = AudioPreprocessor().status()
        self.assertIn("noise_suppression", status)
        self.assertIn("aec", status)


if __name__ == "__main__":
    unittest.main()
