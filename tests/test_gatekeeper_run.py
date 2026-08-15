"""The runner: one comment event, end to end.

GK-113 and GK-116 live here because they are properties of the whole run
rather than of any one stage.
"""

import unittest

import _gatekeeper  # noqa: F401
from lib.fake_github import FakeGitHub
from reactions import ACTED, REFUSED, SEEN
from run_comment_event import Settings, handle_comment

BOT = "sdlc-bot[bot]"
OWNER = "derekwinters"

MILESTONES = [
    {"number": 1, "title": "v0.1", "state": "open"},
    {"number": 2, "title": "v0.2", "state": "open"},
]


class RecordingFire:
    """Stands in for the analysis routine. Records rather than posting."""

    def __init__(self):
        self.sent = []

    def send(self, issue, repository):
        from downstream import FireResult

        self.sent.append((issue, repository))
        return FireResult(attempted=True)


def settings(**kwargs):
    from lib.config import STATES

    kwargs.setdefault("fire", RecordingFire())
    return Settings(
        owners=[OWNER],
        bot_login=BOT,
        labels=dict(STATES),
        dashboard_issue=193,
        milestone_ordering="semver",
        **kwargs,
    )


def event(body="/approve", login=OWNER, issue=7):
    return {
        "issue": {"number": issue},
        "comment": {"id": 55, "body": body, "user": {"login": login}},
    }


def github(labels=("pending-approval",), milestone="v0.1", **kwargs):
    return FakeGitHub(
        issues=[
            {
                "number": 7,
                "labels": [{"name": name} for name in labels],
                "milestone": {"title": milestone} if milestone else None,
            },
            {"number": 193, "labels": []},
        ],
        comments={7: [{"id": 55, "body": "/approve", "user": {"login": OWNER}}]},
        milestones=MILESTONES,
        actor=BOT,
        **kwargs,
    )


def labels_of(api, number=7):
    return [label["name"] for label in api.issue(number)["labels"]]


class TestAnAppliedCommand(unittest.TestCase):
    def test_the_label_moves(self):
        api = github()
        handle_comment(api, event(), settings())
        self.assertIn("ready-for-work", labels_of(api))

    def test_it_is_watermarked_acted(self):
        api = github()
        handle_comment(api, event(), settings())
        self.assertIn(ACTED, [r["content"] for r in api.reactions(55)])

    def test_it_gets_a_reply(self):
        api = github()
        handle_comment(api, event(), settings())
        self.assertTrue(any(name == "comment" for name, _ in api.calls))

    def test_eyes_are_placed_before_the_label_write(self):
        api = github()
        handle_comment(api, event(), settings())
        names = [name for name, _ in api.calls]
        self.assertLess(names.index("react"), names.index("set_labels"))


class TestARefusal(unittest.TestCase):
    def test_no_label_moves(self):
        api = github(milestone=None)
        handle_comment(api, event(), settings())
        self.assertEqual(labels_of(api), ["pending-approval"])

    def test_it_is_watermarked_refused(self):
        api = github(milestone=None)
        handle_comment(api, event(), settings())
        self.assertIn(REFUSED, [r["content"] for r in api.reactions(55)])

    def test_it_gets_an_explanation(self):
        api = github(milestone=None)
        result = handle_comment(api, event(), settings())
        self.assertIn("milestone", result.reply.lower())

    def test_a_refused_command_fires_nothing(self):  # GK-113
        api = github(milestone=None)
        result = handle_comment(api, event(), settings())
        self.assertFalse(result.fired)


class TestAStranger(unittest.TestCase):
    def test_nothing_is_written(self):
        api = github()
        handle_comment(api, event(login="stranger"), settings())
        self.assertEqual(api.calls, [])

    def test_no_reaction_is_left(self):
        api = github()
        handle_comment(api, event(login="stranger"), settings())
        self.assertEqual(api.reactions(55), [])


class TestIdempotence(unittest.TestCase):
    def test_an_already_resolved_comment_is_not_reapplied(self):
        api = github(reactions={55: [{"id": 1, "content": ACTED,
                                      "user": {"login": BOT}}]})
        handle_comment(api, event(), settings())
        self.assertNotIn("set_labels", [name for name, _ in api.calls])

    def test_running_twice_moves_the_label_once(self):
        api = github()
        handle_comment(api, event(), settings())
        before = list(api.calls)
        handle_comment(api, event(), settings())
        writes = [c for c in api.calls[len(before):] if c[0] == "set_labels"]
        self.assertEqual(writes, [])


class TestDashboardOverrides(unittest.TestCase):
    """GK-116 — focus and cap persist as render overrides, never body patches."""

    def test_focus_does_not_patch_the_issue_body(self):
        api = github()
        handle_comment(api, event(body="/focus v0.2", issue=193), settings())
        self.assertNotIn("update_issue", [name for name, _ in api.calls])

    def test_focus_is_returned_as_an_override(self):
        api = github()
        result = handle_comment(api, event(body="/focus v0.2", issue=193), settings())
        self.assertEqual(result.overrides["focus"], "v0.2")

    def test_cap_is_returned_as_an_override(self):
        api = github()
        result = handle_comment(api, event(body="/cap 3", issue=193), settings())
        self.assertEqual(result.overrides["cap"], 3)

    def test_no_label_is_written_for_an_override(self):
        api = github()
        handle_comment(api, event(body="/cap 3", issue=193), settings())
        self.assertNotIn("set_labels", [name for name, _ in api.calls])


class TestFiring(unittest.TestCase):
    def test_admitting_fires_triage(self):  # GK-110
        api = github(labels=())
        result = handle_comment(api, event(body="/admit"), settings())
        self.assertTrue(result.fired)

    def test_approving_does_not(self):  # GK-110
        api = github()
        self.assertFalse(handle_comment(api, event(), settings()).fired)

    def test_re_admitting_does_not(self):  # GK-111
        api = github(labels=("ai-triage",))
        self.assertFalse(handle_comment(api, event(body="/admit"), settings()).fired)


if __name__ == "__main__":
    unittest.main()
