"""GK-090 to GK-095 — finding commands whose run died mid-flight.

This replaces the removed comment-replay sweep. Replay had to guess a time
window, re-read comments repository-wide, and could act on something you had
since changed your mind about. Catch-up is scoped to the single issue whose
event fired, so it cannot race another issue's handler and needs no window:
"unprocessed" is a fact stored on GitHub, not inferred from timestamps.
"""

import unittest

import _gatekeeper  # noqa: F401
from catchup import unfinished_comments
from lib.fake_github import FakeFailure, FakeGitHub
from reactions import ACTED, REFUSED, SEEN, Watermark

BOT = "sdlc-bot[bot]"
OWNER = "derekwinters"


def comment(cid, body="/approve", login=OWNER):
    return {"id": cid, "body": body, "user": {"login": login}}


def api(comments, reactions=None, **kwargs):
    return FakeGitHub(
        issues=[{"number": 7, "labels": []}, {"number": 8, "labels": []}],
        comments=comments,
        reactions=reactions or {},
        actor=BOT,
        **kwargs,
    )


def mark(content, login=BOT, rid=1):
    return {"id": rid, "content": content, "user": {"login": login}}


def catch_up(github, issue=7, owners=(OWNER,)):
    return unfinished_comments(
        github, issue=issue, watermark=Watermark(github, bot_login=BOT), owners=list(owners)
    )


class TestFindingUnfinishedWork(unittest.TestCase):
    def test_a_bare_eyes_is_caught_up(self):  # GK-090
        github = api({7: [comment(55)]}, {55: [mark(SEEN)]})
        self.assertEqual([c["id"] for c in catch_up(github)], [55])

    def test_a_resolved_comment_is_not(self):  # GK-090
        github = api({7: [comment(55)]}, {55: [mark(ACTED)]})
        self.assertEqual(catch_up(github), [])

    def test_a_refused_comment_is_not(self):  # GK-090
        github = api({7: [comment(55)]}, {55: [mark(REFUSED)]})
        self.assertEqual(catch_up(github), [])

    def test_a_comment_with_no_reaction_is_not_caught_up(self):  # GK-093
        """It was never seen. This event is not evidence about it."""
        github = api({7: [comment(55)]})
        self.assertEqual(catch_up(github), [])

    def test_a_human_eyes_is_not_a_watermark(self):  # GK-074
        github = api({7: [comment(55)]}, {55: [mark(SEEN, login=OWNER)]})
        self.assertEqual(catch_up(github), [])


class TestOnlyOwnerCommands(unittest.TestCase):
    def test_a_strangers_unfinished_comment_is_ignored(self):  # GK-090
        github = api({7: [comment(55, login="stranger")]}, {55: [mark(SEEN)]})
        self.assertEqual(catch_up(github), [])

    def test_a_bots_unfinished_comment_is_ignored(self):  # GK-090
        github = api({7: [comment(55, login="other[bot]")]}, {55: [mark(SEEN)]})
        self.assertEqual(catch_up(github), [])

    def test_a_comment_with_no_command_is_ignored(self):  # GK-090
        github = api({7: [comment(55, body="looks good")]}, {55: [mark(SEEN)]})
        self.assertEqual(catch_up(github), [])


class TestScope(unittest.TestCase):
    def test_it_never_reads_another_issue(self):  # GK-091
        github = api({7: [comment(55)], 8: [comment(66)]},
                     {55: [mark(SEEN)], 66: [mark(SEEN)]})
        catch_up(github, issue=7)
        read = [args[0] for name, args in github.calls if name == "comments"]
        self.assertEqual(read, [7])

    def test_it_never_writes_another_issue(self):  # GK-091
        github = api({7: [comment(55)], 8: [comment(66)]},
                     {55: [mark(SEEN)], 66: [mark(SEEN)]})
        catch_up(github, issue=7)
        writes = [name for name, _ in github.calls if name in ("set_labels", "comment")]
        self.assertEqual(writes, [])

    def test_another_issues_unfinished_work_is_not_returned(self):  # GK-091
        github = api({7: [comment(55)], 8: [comment(66)]},
                     {55: [mark(SEEN)], 66: [mark(SEEN)]})
        self.assertEqual([c["id"] for c in catch_up(github, issue=7)], [55])


class TestOrder(unittest.TestCase):
    def test_comments_come_back_in_ascending_order(self):  # GK-092
        github = api({7: [comment(55), comment(56), comment(57)]},
                     {55: [mark(SEEN)], 56: [mark(SEEN)], 57: [mark(SEEN)]})
        self.assertEqual([c["id"] for c in catch_up(github)], [55, 56, 57])

    def test_a_later_command_is_applied_last(self):  # GK-092
        """So the newest instruction wins, as it would have live."""
        github = api({7: [comment(55, "/park"), comment(56, "/unpark")]},
                     {55: [mark(SEEN)], 56: [mark(SEEN)]})
        self.assertEqual([c["body"] for c in catch_up(github)], ["/park", "/unpark"])

    def test_a_gap_in_the_middle_is_skipped_not_reordered(self):  # GK-092
        github = api({7: [comment(55), comment(56), comment(57)]},
                     {55: [mark(SEEN)], 56: [mark(ACTED)], 57: [mark(SEEN)]})
        self.assertEqual([c["id"] for c in catch_up(github)], [55, 57])


class TestDegradation(unittest.TestCase):
    def test_an_unreadable_reaction_lookup_skips_that_comment(self):  # GK-095
        github = api({7: [comment(55)]}, fail={"reactions": FakeFailure("down")})
        self.assertEqual(catch_up(github), [])

    def test_a_failing_comment_read_yields_nothing_rather_than_raising(self):  # GK-095
        github = api({7: [comment(55)]}, fail={"comments": FakeFailure("down")})
        self.assertEqual(catch_up(github), [])


class TestRetry(unittest.TestCase):
    def test_retry_is_a_command_like_any_other(self):  # GK-094
        from parse_commands import COMMANDS

        self.assertIn("retry", COMMANDS)

    def test_a_retry_comment_is_itself_caught_up_when_unfinished(self):  # GK-094
        github = api({7: [comment(55, "/retry")]}, {55: [mark(SEEN)]})
        self.assertEqual([c["id"] for c in catch_up(github)], [55])


if __name__ == "__main__":
    unittest.main()
