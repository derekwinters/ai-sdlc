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
    return FakeGitHub(
        issues=[{"number": 7, "labels": [{"name": STATES["triage_queued"]}]}],
        actor=BOT)


class FailingFire:
    """A routine that could not be reached. Nothing started."""

    def send(self, issue, repository):
        from downstream import FireResult

        return FireResult(True, failed=True, detail="502")


def event(label="ai-triage-queued", issue=7):
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
        labels = dict(STATES, triage_queued="needs-triage")
        fire = RecordingFire()
        on_label_added(api(), event(label="needs-triage"),
                       settings(labels=labels, fire=fire))
        self.assertEqual(fire.sent, [(7, "owner/repo")])

    def test_it_records_that_a_session_started(self):  # GK-138
        """The widening in `GK-005`: the handler writes a pipeline state.

        It writes exactly the one it is the only component able to know is
        true — only the thing that fired can say a session began. Before this,
        a started session and a lost poke left the issue looking identical.
        """
        github = api()
        on_label_added(github, event(), settings(fire=RecordingFire()))
        after = {l["name"] for l in github.issue(7).get("labels") or []}
        self.assertIn(STATES["triage_running"], after)
        self.assertNotIn(STATES["triage_queued"], after)

    def test_a_fire_that_started_nothing_records_nothing(self):  # GK-138
        """It stays queued, so the next sweep still sees work waiting rather
        than a session that does not exist — which the sweep would otherwise
        stall, blaming the routine for a failure that was ours."""
        github = api()
        on_label_added(github, event(), settings(fire=FailingFire()))
        after = {l["name"] for l in github.issue(7).get("labels") or []}
        self.assertIn(STATES["triage_queued"], after)
        self.assertNotIn(STATES["triage_running"], after)

    def test_it_writes_no_state_but_that_one(self):  # GK-122
        """A component that could write any state would be a second
        gatekeeper. This one writes queued -> running and nothing else."""
        github = api()
        on_label_added(github, event(), settings(fire=RecordingFire()))
        forbidden = [n for n, _ in github.calls
                     if n in ("comment", "set_milestone", "set_body")]
        self.assertEqual(forbidden, [])


if __name__ == "__main__":
    unittest.main()
