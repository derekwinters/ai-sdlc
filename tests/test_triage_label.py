"""GK-122 — firing the analysis routine from the label event.

Adding `ai-triage` by hand used to fire nothing: the gatekeeper listens on
`issue_comment`, so the routine was reachable only through `/admit`, and only
at the instant of transition. The label event is now the single trigger, so
"the label was added" fires exactly once however it got there (#123).
"""

import unittest

import _gatekeeper  # noqa: F401
from lib.config import STATES
from lib.fake_github import FakeGitHub
from on_labeled import on_label_added
from run_comment_event import Settings

BOT = "sdlc-bot[bot]"


class RecordingFire:
    def __init__(self, result=None):
        from downstream import FireResult

        self.sent = []
        self._result = result or FireResult(attempted=True)

    def send(self, issue, repository):
        self.sent.append((issue, repository))
        return self._result


def settings(**kwargs):
    kwargs.setdefault("fire", RecordingFire())
    kwargs.setdefault("labels", dict(STATES))
    return Settings(owners=["derekwinters"], bot_login=BOT,
                    dashboard_issue=193, **kwargs)


def api():
    return FakeGitHub(issues=[{"number": 7, "labels": []}], actor=BOT)


def event(label="ai-triage", issue=7):
    return {"issue": {"number": issue}, "label": {"name": label}}


class TestFiringOnTheLabel(unittest.TestCase):
    def test_the_triage_label_fires(self):  # GK-122
        fire = RecordingFire()
        on_label_added(api(), event(), settings(fire=fire))
        self.assertEqual(fire.sent, [(7, "owner/repo")])

    def test_another_label_does_not(self):  # GK-122
        fire = RecordingFire()
        on_label_added(api(), event(label="ready-for-work"), settings(fire=fire))
        self.assertEqual(fire.sent, [])

    def test_it_reports_the_outcome(self):  # GK-122, GK-121
        result = on_label_added(api(), event(), settings())
        self.assertTrue(result.attempted)

    def test_a_non_triage_label_reports_why(self):  # GK-122, GK-121
        result = on_label_added(api(), event(label="parked"), settings())
        self.assertFalse(result.attempted)
        self.assertTrue(result.detail)

    def test_it_honours_a_remapped_triage_label(self):  # GK-122
        """A repository may call the state something else.

        The workflow's `if:` cannot read configuration, so `adopt` writes the
        configured name into the caller — and this is the check that the two
        agree.
        """
        labels = dict(STATES, triage="needs-triage")
        fire = RecordingFire()
        on_label_added(api(), event(label="needs-triage"),
                       settings(labels=labels, fire=fire))
        self.assertEqual(fire.sent, [(7, "owner/repo")])

    def test_it_writes_nothing(self):  # GK-122
        """Firing is a poke, not a state change. The routine decides."""
        github = api()
        on_label_added(github, event(), settings())
        writes = [n for n, _ in github.calls
                  if n in ("set_labels", "comment", "set_milestone", "set_body")]
        self.assertEqual(writes, [])


if __name__ == "__main__":
    unittest.main()
