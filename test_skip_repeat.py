"""Tests for skip-repeat (frustration) flag in gerald_openai_brain."""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, "/opt/Gerald")

import gerald_openai_brain as brain


class TestIsFrustrationTurn(unittest.TestCase):
    def test_stop_repeating(self):
        self.assertTrue(brain._is_frustration_turn("Stop repeating yourself!"))

    def test_you_keep_repeating(self):
        self.assertTrue(brain._is_frustration_turn("You keep repeating the same thing."))

    def test_move_on(self):
        self.assertTrue(brain._is_frustration_turn("Can you move on already?"))

    def test_i_already_know(self):
        self.assertTrue(brain._is_frustration_turn("I already know all this."))

    def test_you_said_that(self):
        self.assertTrue(brain._is_frustration_turn("You said that already."))

    def test_dont_repeat(self):
        self.assertTrue(brain._is_frustration_turn("Dont repeat yourself."))

    def test_cut_the_recap(self):
        self.assertTrue(brain._is_frustration_turn("Just answer — cut the recap."))

    def test_case_insensitive(self):
        self.assertTrue(brain._is_frustration_turn("STOP REPEATING"))

    def test_normal_turn_not_frustration(self):
        self.assertFalse(brain._is_frustration_turn("What is the current status of the build?"))

    def test_empty_string(self):
        self.assertFalse(brain._is_frustration_turn(""))

    def test_unrelated_message(self):
        self.assertFalse(brain._is_frustration_turn("Fix the button colour on the home screen."))


class TestSkipRepeatFlag(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._orig_dir = brain.CONVERSATION_DIR
        brain.CONVERSATION_DIR = Path(self._tmp)

    def tearDown(self):
        brain.CONVERSATION_DIR = self._orig_dir
        shutil.rmtree(self._tmp, ignore_errors=True)

    _P = "_test_skip_repeat_"

    def test_flag_initially_false(self):
        self.assertFalse(brain.is_skip_repeat_active(self._P))

    def test_frustration_sets_flag(self):
        brain._update_skip_repeat_flag(self._P, "stop repeating please")
        self.assertTrue(brain.is_skip_repeat_active(self._P))

    def test_flag_persists_through_first_normal_turn(self):
        brain._update_skip_repeat_flag(self._P, "stop repeating please")
        brain._update_skip_repeat_flag(self._P, "fix the button colour")
        self.assertTrue(brain.is_skip_repeat_active(self._P))

    def test_flag_clears_after_two_normal_turns(self):
        brain._update_skip_repeat_flag(self._P, "stop repeating please")
        brain._update_skip_repeat_flag(self._P, "fix the button colour")   # turn 1
        brain._update_skip_repeat_flag(self._P, "update the home screen")  # turn 2 → clears
        self.assertFalse(brain.is_skip_repeat_active(self._P))

    def test_flag_stays_clear_after_additional_normal_turns(self):
        brain._update_skip_repeat_flag(self._P, "stop repeating please")
        brain._update_skip_repeat_flag(self._P, "turn 1")
        brain._update_skip_repeat_flag(self._P, "turn 2")  # cleared
        brain._update_skip_repeat_flag(self._P, "turn 3")
        self.assertFalse(brain.is_skip_repeat_active(self._P))

    def test_second_frustration_resets_counter(self):
        brain._update_skip_repeat_flag(self._P, "stop repeating please")
        brain._update_skip_repeat_flag(self._P, "fix the button")          # 1 normal
        brain._update_skip_repeat_flag(self._P, "you keep repeating yourself")  # resets counter
        brain._update_skip_repeat_flag(self._P, "fix the colour")          # 1 normal after reset
        self.assertTrue(brain.is_skip_repeat_active(self._P))              # still active

    def test_non_frustration_does_not_set_flag(self):
        brain._update_skip_repeat_flag(self._P, "fix the colour please")
        self.assertFalse(brain.is_skip_repeat_active(self._P))

    def test_state_persisted_to_disk(self):
        brain._update_skip_repeat_flag(self._P, "stop repeating please")
        # Re-read state from disk
        state = brain._load_convo_state(self._P)
        self.assertTrue(state.get("skip_repeat"))
        self.assertEqual(state.get("turns_since_set"), 0)

    def test_turns_since_set_increments(self):
        brain._update_skip_repeat_flag(self._P, "stop repeating please")
        brain._update_skip_repeat_flag(self._P, "normal turn")
        state = brain._load_convo_state(self._P)
        self.assertEqual(state.get("turns_since_set"), 1)


if __name__ == "__main__":
    unittest.main()
