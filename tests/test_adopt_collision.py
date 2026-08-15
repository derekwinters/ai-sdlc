"""ADOPT-030 to ADOPT-034 — two handlers on one event is worse than none."""

import unittest

from _adopt import repository
import _adopt  # noqa: F401
from adopt import CLAIMED_EVENTS, collisions

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
