"""GK-076 to GK-079 — what the gatekeeper says back.

Short replies only. A refusal that says nothing is the behaviour that made the
pipeline feel broken: a command vanishes and the only evidence is a state that
did not change.
"""

import unittest

import _gatekeeper  # noqa: F401
from acknowledge import acknowledge
from parse_commands import Action, Skip


def action(command, argument=""):
    return Action(command, argument)


def skip(command, reason, detail="", suggestion=None):
    made = Skip(command, reason, suggestion=suggestion)
    made.detail = detail
    return made


class TestAnAppliedCommand(unittest.TestCase):
    def test_it_names_what_changed(self):  # GK-077
        text = acknowledge([action("approve")], [], state="ready-for-work")
        self.assertIn("ready-for-work", text)

    def test_it_says_what_happens_next(self):  # GK-077
        text = acknowledge([action("approve")], [], state="ready-for-work")
        self.assertIn("builder", text.lower())

    def test_parking_says_the_pipeline_will_leave_it(self):  # GK-077
        text = acknowledge([action("park")], [], state="parked")
        self.assertIn("leave it alone", text.lower())

    def test_two_commands_are_both_acknowledged(self):  # GK-077
        text = acknowledge([action("milestone", "v0.4"), action("approve")], [],
                           state="ready-for-work")
        self.assertIn("v0.4", text)
        self.assertIn("ready-for-work", text)

    def test_it_is_short(self):  # GK-077
        text = acknowledge([action("approve")], [], state="ready-for-work")
        self.assertLessEqual(len(text.splitlines()), 6)


class TestARefusal(unittest.TestCase):
    def test_it_explains(self):  # GK-078
        text = acknowledge([], [skip("approve", "no-milestone", "This issue has no milestone.")])
        self.assertIn("no milestone", text.lower())

    def test_it_says_nothing_changed(self):  # GK-078
        text = acknowledge([], [skip("approve", "no-milestone", "No milestone.")])
        self.assertIn("nothing changed", text.lower())

    def test_it_carries_the_gates_prose_not_the_reason_code(self):  # GK-079
        text = acknowledge([], [skip("approve", "blocker-inversion", "Blocked by #42 (v0.2).")])
        self.assertIn("#42", text)
        self.assertNotIn("blocker-inversion", text)

    def test_no_reason_code_ever_reaches_the_reply(self):  # GK-079
        for reason in ("no-milestone", "dashboard-only", "epic", "cap-not-positive"):
            text = acknowledge([], [skip("approve", reason, "Something readable.")])
            self.assertNotIn(reason, text, reason)

    def test_an_unknown_command_names_the_closest_match(self):  # GK-028
        text = acknowledge([], [skip("aprove", "unknown-command", suggestion="approve")])
        self.assertIn("approve", text)

    def test_an_unknown_command_with_no_suggestion_lists_the_vocabulary(self):  # GK-028
        text = acknowledge([], [skip("xyzzy", "unknown-command")])
        self.assertIn("/approve", text)
        self.assertIn("/park", text)


class TestBothTogether(unittest.TestCase):
    def test_an_applied_and_a_refused_command_both_appear(self):  # GK-077
        text = acknowledge(
            [action("milestone", "v0.4")],
            [skip("approve", "blocker-inversion", "Blocked by #42.")],
            state=None,
        )
        self.assertIn("v0.4", text)
        self.assertIn("#42", text)


class TestSilence(unittest.TestCase):
    def test_nothing_at_all_produces_no_reply(self):  # GK-076
        self.assertIsNone(acknowledge([], []))

    def test_a_silent_skip_produces_no_reply(self):  # GK-013
        """A stranger's comment must never make the bot post."""
        self.assertIsNone(acknowledge([], [skip("approve", "not-owner")]))

    def test_an_already_applied_skip_produces_no_reply(self):  # GK-073
        """Replying again would post the same acknowledgement twice."""
        self.assertIsNone(acknowledge([], [skip("approve", "already-applied")]))

    def test_a_silent_skip_alongside_a_real_one_still_replies(self):  # GK-078
        text = acknowledge([], [skip("approve", "not-owner"),
                                skip("park", "epic", "This is an epic.")])
        self.assertIn("epic", text.lower())


if __name__ == "__main__":
    unittest.main()
