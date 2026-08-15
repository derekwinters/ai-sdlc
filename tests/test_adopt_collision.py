"""ADOPT-030 to ADOPT-034 — two handlers on one event is worse than none."""

import unittest

from _adopt import NEWER_PIN, PIN, repository
import _adopt  # noqa: F401
from adopt import CLAIMED_EVENTS, AdoptRefused, apply, collisions

EXISTING = """
name: their-gatekeeper
on:
  issue_comment:
    types: [created]
jobs:
  run:
    runs-on: ubuntu-latest
"""

UNRELATED = """
name: their-tests
on:
  push:
    branches: [main]
jobs:
  run:
    runs-on: ubuntu-latest
"""


def found(files, claims=("issue_comment",), acknowledged=()):
    return collisions(repository(files), claims=list(claims),
                      acknowledged=list(acknowledged))


class TestDetection(unittest.TestCase):
    def test_an_existing_handler_on_a_claimed_event_collides(self):  # ADOPT-030
        result = found({".github/workflows/theirs.yml": EXISTING})
        self.assertEqual([c.workflow for c in result], ["theirs.yml"])

    def test_an_unrelated_workflow_does_not(self):  # ADOPT-030
        self.assertEqual(found({".github/workflows/theirs.yml": UNRELATED}), [])

    def test_the_event_is_named(self):  # ADOPT-030
        result = found({".github/workflows/theirs.yml": EXISTING})
        self.assertEqual(result[0].event, "issue_comment")

    def test_no_workflows_at_all_is_no_collision(self):  # ADOPT-030
        self.assertEqual(found({}), [])


class TestItComparesTriggersNotNames(unittest.TestCase):
    """ADOPT-031 — the collision a file comparison misses."""

    def test_a_differently_named_workflow_still_collides(self):
        result = found({".github/workflows/something-else-entirely.yml": EXISTING})
        self.assertEqual(len(result), 1)

    def test_a_same_named_workflow_on_another_event_does_not(self):
        result = found({".github/workflows/gatekeeper-comment.yml": UNRELATED})
        self.assertEqual(result, [])


class TestAcknowledgement(unittest.TestCase):
    def test_an_acknowledged_collision_is_not_reported(self):  # ADOPT-033
        result = found({".github/workflows/theirs.yml": EXISTING},
                       acknowledged=["theirs.yml"])
        self.assertEqual(result, [])

    def test_acknowledging_one_does_not_silence_another(self):  # ADOPT-033
        files = {".github/workflows/a.yml": EXISTING, ".github/workflows/b.yml": EXISTING}
        result = found(files, acknowledged=["a.yml"])
        self.assertEqual([c.workflow for c in result], ["b.yml"])


class TestTheClaimedEvents(unittest.TestCase):
    def test_only_sole_writer_events_are_claimed(self):  # ADOPT-034
        self.assertEqual(set(CLAIMED_EVENTS), {"issue_comment", "issues"})

    def test_pull_request_is_deliberately_excluded(self):  # ADOPT-034
        """Every repository has a test workflow on it; flagging them all would
        train the owner to acknowledge without reading."""
        self.assertNotIn("pull_request", CLAIMED_EVENTS)

    def test_an_issues_handler_collides(self):  # ADOPT-034
        workflow = EXISTING.replace("issue_comment", "issues")
        self.assertEqual(len(found({".github/workflows/t.yml": workflow},
                                   claims=["issues"])), 1)

    def test_a_pull_request_handler_does_not_collide_by_default(self):  # ADOPT-034
        workflow = EXISTING.replace("issue_comment", "pull_request")
        self.assertEqual(found({".github/workflows/t.yml": workflow},
                               claims=list(CLAIMED_EVENTS)), [])


if __name__ == "__main__":
    unittest.main()


class TestOurOwnCallersAreNotCollisions(unittest.TestCase):
    """ADOPT-036 — a file adoption manages is never a collision with itself.

    The collision check reads workflow triggers, and adoption's own callers
    listen on the events it claims — so once `pipeline` was installed, the next
    `apply` refused:

        refused: these workflows already handle events this adoption claims:
        dashboard.yml (on issues), gatekeeper-close.yml (on issues),
        gatekeeper-comment.yml (on issue_comment)

    Which makes ADOPT-046 — "upgrading is the same operation" — false for any
    repository that took the pipeline. Found upgrading
    `connor-multiplying-frogs` from v0.4.6 to v0.4.7.
    """

    def _adopted(self):
        root = repository({
            ".claude/repo-config.yml":
                "capabilities:\n  - hygiene\n  - consistency\n  - labels\n"
                "  - release\n  - pipeline\nowners:\n  - x\ndashboard_issue: 1\n",
        })
        apply(root, pin=PIN)
        return root

    def test_a_second_apply_is_not_refused(self):  # ADOPT-036
        root = self._adopted()
        apply(root, pin=PIN)  # must not raise

    def test_an_upgrade_is_not_refused(self):  # ADOPT-036
        root = self._adopted()
        apply(root, pin=NEWER_PIN)  # must not raise

    def test_an_upgrade_actually_rewrites_the_callers(self):  # ADOPT-036
        root = self._adopted()
        apply(root, pin=NEWER_PIN)
        text = (root / ".github/workflows/gatekeeper-comment.yml").read_text()
        self.assertIn(NEWER_PIN[1], text)

    def test_a_foreign_workflow_on_a_claimed_event_still_collides(self):  # ADOPT-036
        # The exemption is for files carrying our provenance, not for the
        # event: somebody else's issue_comment handler is still the race the
        # check exists to prevent.
        root = self._adopted()
        (root / ".github/workflows/theirs.yml").write_text(
            "name: theirs\non:\n  issue_comment:\n    types: [created]\n")
        with self.assertRaises(AdoptRefused):
            apply(root, pin=PIN)
