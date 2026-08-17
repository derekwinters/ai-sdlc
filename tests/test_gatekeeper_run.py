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
        # Firing moved to the label event (#123), so what matters here is
        # that a refused command applies no label — with no transition into
        # triage, there is no `labeled` event and nothing to fire.
        self.assertNotIn("ai-triage", labels_of(api))


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
    """GK-114, GK-116 — a command re-renders the board and persists its value.

    These used to assert only that an override was *returned* on the result,
    plus that `update_issue` was absent from the call log — a method that does
    not exist, so the assertion was vacuously true. Nothing acted on the
    returned value, so `/focus` replied `Done` and changed nothing (#105).

    The board's own body is the store: the renderer writes the marker it read,
    which is what carries a value from this workflow run into the dashboard's
    separate one.
    """

    def _body(self, api):
        return next((args[1] for name, args in api.calls if name == "set_body"), None)

    def test_focus_writes_the_marker_into_the_board(self):  # GK-116
        api = github()
        handle_comment(api, event(body="/focus v0.2", issue=193), settings())
        self.assertIn("<!-- pipeline-focus: v0.2 -->", self._body(api) or "")

    def test_cap_writes_the_marker_into_the_board(self):  # GK-116
        api = github()
        handle_comment(api, event(body="/cap 3", issue=193), settings())
        self.assertIn("<!-- pipeline-cap: 3 -->", self._body(api) or "")

    def test_the_board_is_rewritten_once(self):  # GK-114
        api = github()
        handle_comment(api, event(body="/focus v0.2", issue=193), settings())
        writes = [name for name, _ in api.calls if name == "set_body"]
        self.assertEqual(len(writes), 1)

    def test_only_the_dashboard_is_rewritten(self):  # GK-114
        api = github()
        handle_comment(api, event(body="/focus v0.2", issue=193), settings())
        targets = {args[0] for name, args in api.calls if name == "set_body"}
        self.assertEqual(targets, {193})

    def test_a_label_change_also_re_renders(self):  # GK-114
        api = github()
        handle_comment(api, event(body="/approve", issue=7), settings())
        self.assertIsNotNone(self._body(api))

    def test_a_run_that_changes_nothing_does_not_re_render(self):  # GK-115
        api = github(labels=("ready-for-work",))
        handle_comment(api, event(body="/approve", issue=7), settings())
        self.assertIsNone(self._body(api))

    def test_focus_is_returned_as_an_override(self):  # GK-116
        api = github()
        result = handle_comment(api, event(body="/focus v0.2", issue=193), settings())
        self.assertEqual(result.overrides["focus"], "v0.2")

    def test_cap_is_returned_as_an_override(self):  # GK-116
        api = github()
        result = handle_comment(api, event(body="/cap 3", issue=193), settings())
        self.assertEqual(result.overrides["cap"], 3)

    def test_a_failed_re_render_does_not_fail_the_run(self):  # GK-120
        """The commands are already applied and acknowledged by then.

        Losing the run — and its exit code — because the board could not be
        redrawn would be the worse trade; the next scheduled render fixes it.
        """
        from lib.fake_github import FakeFailure

        api = github(fail={"set_body": FakeFailure("down")})
        result = handle_comment(api, event(body="/focus v0.2", issue=193), settings())
        self.assertEqual(result.overrides["focus"], "v0.2")

    def test_no_label_is_written_for_an_override(self):  # GK-116
        api = github()
        handle_comment(api, event(body="/cap 3", issue=193), settings())
        self.assertNotIn("set_labels", [name for name, _ in api.calls])


class TestTheGatekeeperDoesNotFire(unittest.TestCase):
    """GK-110 — firing belongs to the label event, not to this run.

    `/admit` applies the label; the `issues: labeled` event that follows is
    what pokes the analysis routine. Firing here as well would poke it twice
    for every `/admit`, and deduplicating two independent workflows is harder
    than having one (#123).
    """

    def test_admitting_does_not_fire(self):  # GK-110
        api = github(labels=())
        fire = RecordingFire()
        handle_comment(api, event(body="/admit"), settings(fire=fire))
        self.assertEqual(fire.sent, [])

    def test_admitting_still_applies_the_label(self):  # GK-110
        """The gatekeeper's own job is unchanged; only the poke moved."""
        api = github(labels=())
        handle_comment(api, event(body="/admit"), settings())
        self.assertIn("ai-triage", labels_of(api))

    def test_no_command_fires_anything(self):  # GK-110
        api = github()
        fire = RecordingFire()
        handle_comment(api, event(), settings(fire=fire))
        self.assertEqual(fire.sent, [])


if __name__ == "__main__":
    unittest.main()
