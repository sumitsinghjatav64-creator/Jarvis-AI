import unittest

from core.gesture_mapper import GestureMapper


class GestureMapperTests(unittest.TestCase):
    def setUp(self):
        self.mapper = GestureMapper()

    def test_safe_gestures_map_to_ui_commands(self):
        self.assertEqual(self.mapper.map("open_palm"), "interrupt")
        self.assertEqual(self.mapper.map("swipe_left"), "previous_panel")
        self.assertEqual(self.mapper.map("swipe_right"), "next_panel")
        self.assertEqual(self.mapper.map("two_fingers"), "toggle_camera")

    def test_approval_gestures_are_not_directly_authorized(self):
        self.assertEqual(self.mapper.map("thumbs_up"), "open_confirmation")
        self.assertNotEqual(self.mapper.map("thumbs_up"), "confirm")

    def test_unknown_gesture_is_ignored(self):
        self.assertIsNone(self.mapper.map("unknown_gesture"))


if __name__ == "__main__":
    unittest.main()
