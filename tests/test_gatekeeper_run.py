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

    def test_a_refused_command_applies_no_label(self):  # GK-113
        api = github(milestone=None)
        handle_comment(api, event(), settings())
        self.assertNotIn("ai-triage-queued", labels_of(api))


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


class TestTheGatekeeperFires(unittest.TestCase):
    """GK-110, GK-122 — the gatekeeper pokes the routine for its own moves.

    The label event cannot cover them: the gatekeeper labels with
    `GITHUB_TOKEN`, and GitHub starts no workflow run from an event that
    token authored, so `/admit` reaches the label handler never (#126).
    """

    def test_admitting_fires(self):  # GK-110
        api = github(labels=())
        fire = RecordingFire()
        handle_comment(api, event(body="/admit"), settings(fire=fire))
        self.assertEqual(fire.sent, [(7, api.repository)])

    def test_admitting_puts_the_issue_into_triage(self):  # GK-110
        """`/admit` writes queued, and a fire that starts a session immediately
        moves it on to running (`GK-138`). Asserting the end state rather than
        the intermediate one, because the intermediate one exists for as long
        as one HTTP round trip."""
        api = github(labels=())
        handle_comment(api, event(body="/admit"), settings())
        self.assertIn("ai-triage-running", labels_of(api))

    def test_admitting_leaves_it_queued_when_nothing_started(self):  # GK-138
        """A routine that could not be reached started nothing, so the issue
        stays where the sweep will still see work waiting."""
        class FailingFire:
            def send(self, issue, repository):
                from downstream import FireResult
                return FireResult(True, failed=True, detail="502")

        api = github(labels=())
        handle_comment(api, event(body="/admit"), settings(fire=FailingFire()))
        self.assertIn("ai-triage-queued", labels_of(api))

    def test_no_command_fires_anything(self):  # GK-110
        api = github()
        fire = RecordingFire()
        handle_comment(api, event(), settings(fire=fire))
        self.assertEqual(fire.sent, [])

    def test_a_refused_command_fires_nothing(self):  # GK-113
        api = github(labels=(), milestone=None)
        fire = RecordingFire()
        handle_comment(api, event(body="/approve"), settings(fire=fire))
        self.assertEqual(fire.sent, [])

    def test_re_admitting_an_issue_already_in_triage_does_not(self):  # GK-111
        """The transition is what fires, not the destination."""
        api = github(labels=("ai-triage-queued",))
        fire = RecordingFire()
        handle_comment(api, event(body="/admit"), settings(fire=fire))
        self.assertEqual(fire.sent, [])

    def test_the_outcome_is_on_the_result(self):  # GK-121
        """So the entry point can report it — a poke nobody can see is
        indistinguishable from one that never went out."""
        api = github(labels=())
        result = handle_comment(api, event(body="/admit"), settings())
        self.assertTrue(result.fired)

    def test_a_run_that_did_not_fire_says_why(self):  # GK-121
        api = github()
        result = handle_comment(api, event(), settings())
        self.assertFalse(result.fired)
        self.assertIn("triage", result.fired.detail.lower())

    def test_a_failing_fire_does_not_fail_the_run(self):  # GK-117
        """The label move already happened; losing the run over a poke that
        did not land is the worse trade."""
        from downstream import Fire

        api = github(labels=())

        def explode(*_args, **_kwargs):
            raise OSError("no route to host")

        result = handle_comment(
            api,
            event(body="/admit"),
            settings(fire=Fire("https://example.com", "t", transport=explode)),
        )
        self.assertIn("ai-triage-queued", labels_of(api))
        self.assertTrue(result.fired.failed)


if __name__ == "__main__":
    unittest.main()
