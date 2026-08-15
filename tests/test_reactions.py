"""GK-070 to GK-080 — the three-state watermark and the replies.

The watermark is what makes "a command is applied at most once" true. Three
states rather than two: 👀 on sight, replaced by 👍 when acted on or 👎 when
refused. A comment still showing a bare 👀 after its run should have finished
is therefore a command that died mid-flight, and nothing else — which is what
lets catch-up (#10) find it without guessing from timestamps.
"""

import unittest

import _gatekeeper  # noqa: F401
from lib.fake_github import FakeGitHub
from reactions import ACTED, REFUSED, SEEN, Watermark

BOT = "sdlc-bot[bot]"


def fake(reactions=None):
    return FakeGitHub(
        issues=[{"number": 7, "labels": []}],
        comments={7: [{"id": 55, "body": "/approve", "user": {"login": "derekwinters"}}]},
        reactions=reactions or {},
        actor=BOT,
    )


def watermark(api=None):
    return Watermark(api or fake(), bot_login=BOT)


def by(login, content):
    return {"id": 1, "content": content, "user": {"login": login}}


class TestTheThreeStates(unittest.TestCase):
    def test_seen_is_eyes(self):  # GK-070
        self.assertEqual(SEEN, "eyes")

    def test_acted_is_thumbs_up(self):  # GK-071
        self.assertEqual(ACTED, "+1")

    def test_refused_is_thumbs_down(self):  # GK-072
        self.assertEqual(REFUSED, "-1")

    def test_they_are_distinct(self):  # GK-070
        self.assertEqual(len({SEEN, ACTED, REFUSED}), 3)


class TestMarkingSeen(unittest.TestCase):
    def test_it_places_eyes(self):  # GK-070
        api = fake()
        watermark(api).seen(55)
        self.assertEqual([r["content"] for r in api.reactions(55)], [SEEN])

    def test_it_happens_before_any_write(self):  # GK-070
        """A run dying after this leaves a bare eyes — the fault signal."""
        api = fake()
        mark = watermark(api)
        mark.seen(55)
        names = [call[0] for call in api.calls]
        self.assertEqual(names[0], "react")


class TestResolving(unittest.TestCase):
    def test_acting_replaces_eyes_with_thumbs_up(self):  # GK-071
        api = fake()
        mark = watermark(api)
        mark.seen(55)
        mark.acted(55)
        self.assertEqual([r["content"] for r in api.reactions(55)], [ACTED])

    def test_refusing_replaces_eyes_with_thumbs_down(self):  # GK-072
        api = fake()
        mark = watermark(api)
        mark.seen(55)
        mark.refused(55)
        self.assertEqual([r["content"] for r in api.reactions(55)], [REFUSED])

    def test_the_eyes_are_actually_removed(self):  # GK-071
        api = fake()
        mark = watermark(api)
        mark.seen(55)
        mark.acted(55)
        self.assertNotIn(SEEN, [r["content"] for r in api.reactions(55)])

    def test_resolving_without_a_prior_eyes_still_marks(self):  # GK-071
        api = fake()
        watermark(api).acted(55)
        self.assertEqual([r["content"] for r in api.reactions(55)], [ACTED])


class TestRecognisingAFinishedComment(unittest.TestCase):
    def test_a_thumbs_up_means_done(self):  # GK-073
        api = fake({55: [by(BOT, ACTED)]})
        self.assertTrue(watermark(api).is_finished(55))

    def test_a_thumbs_down_means_done(self):  # GK-073
        api = fake({55: [by(BOT, REFUSED)]})
        self.assertTrue(watermark(api).is_finished(55))

    def test_a_bare_eyes_does_not(self):  # GK-073
        api = fake({55: [by(BOT, SEEN)]})
        self.assertFalse(watermark(api).is_finished(55))

    def test_no_reaction_does_not(self):  # GK-073
        self.assertFalse(watermark(fake()).is_finished(55))

    def test_a_bare_eyes_is_recognised_as_unfinished(self):  # GK-073
        api = fake({55: [by(BOT, SEEN)]})
        self.assertTrue(watermark(api).is_unfinished(55))

    def test_a_resolved_comment_is_not_unfinished(self):  # GK-073
        api = fake({55: [by(BOT, ACTED)]})
        self.assertFalse(watermark(api).is_unfinished(55))


class TestOnlyTheBotsReactionCounts(unittest.TestCase):
    def test_a_humans_thumbs_up_is_not_a_watermark(self):  # GK-074
        api = fake({55: [by("derekwinters", ACTED)]})
        self.assertFalse(watermark(api).is_finished(55))

    def test_a_humans_eyes_is_not_a_watermark(self):  # GK-074
        api = fake({55: [by("derekwinters", SEEN)]})
        self.assertFalse(watermark(api).is_unfinished(55))

    def test_another_bots_reaction_is_not_a_watermark(self):  # GK-074
        api = fake({55: [by("dependabot[bot]", ACTED)]})
        self.assertFalse(watermark(api).is_finished(55))

    def test_the_bots_own_reaction_alongside_a_humans_counts(self):  # GK-074
        api = fake({55: [by("derekwinters", SEEN), by(BOT, ACTED)]})
        self.assertTrue(watermark(api).is_finished(55))


class TestAmbiguityIsTreatedAsDone(unittest.TestCase):
    """GK-080 — an unreadable lookup must never cause a second application."""

    def test_a_failing_lookup_reads_as_finished(self):
        from lib.fake_github import FakeFailure

        api = FakeGitHub(
            issues=[{"number": 7}],
            fail={"reactions": FakeFailure("upstream is down")},
            actor=BOT,
        )
        self.assertTrue(Watermark(api, bot_login=BOT).is_finished(55))

    def test_a_failing_lookup_does_not_read_as_unfinished(self):
        from lib.fake_github import FakeFailure

        api = FakeGitHub(
            issues=[{"number": 7}],
            fail={"reactions": FakeFailure("upstream is down")},
            actor=BOT,
        )
        self.assertFalse(Watermark(api, bot_login=BOT).is_unfinished(55))

    def test_the_failure_is_not_raised(self):
        from lib.fake_github import FakeFailure

        api = FakeGitHub(issues=[{"number": 7}],
                         fail={"reactions": FakeFailure("down")}, actor=BOT)
        Watermark(api, bot_login=BOT).is_finished(55)  # must not raise


class TestSilence(unittest.TestCase):
    def test_a_non_owner_comment_gets_no_reaction(self):  # GK-075
        api = fake()
        watermark(api).ignore(55)
        self.assertEqual(api.reactions(55), [])

    def test_ignoring_writes_nothing_at_all(self):  # GK-075
        api = fake()
        watermark(api).ignore(55)
        self.assertNotIn("react", [call[0] for call in api.calls])


if __name__ == "__main__":
    unittest.main()
