"""DEV-040 to DEV-046 — the contract the dev agent works under.

The agent is prose, so these tests check that the prose actually states the
rules the pipeline depends on. A rule the agent file forgot is a rule that
quietly stops being followed.
"""

import re
import unittest

from _support import ROOT

AGENT = (ROOT / "agents" / "dev.md").read_text()
BODY = AGENT.lower()


class TestItIsAValidAgent(unittest.TestCase):
    def test_it_has_frontmatter(self):
        self.assertTrue(AGENT.startswith("---"))

    def test_it_declares_a_name(self):
        self.assertRegex(AGENT, re.compile(r"^name:\s*dev\s*$", re.MULTILINE))

    def test_it_declares_a_description(self):
        self.assertIn("description:", AGENT)


class TestTheOrderIsStated(unittest.TestCase):
    def test_the_specification_comes_before_the_code(self):  # DEV-040
        self.assertIn("specification first", BODY)

    def test_a_failing_test_comes_before_the_implementation(self):  # DEV-041
        self.assertIn("failing test", BODY)

    def test_it_requires_watching_the_failure(self):  # DEV-041
        self.assertIn("see red", BODY)

    def test_the_specification_precedes_the_test_in_the_document(self):  # DEV-040
        self.assertLess(BODY.index("specification first"), BODY.index("failing test"))


class TestThePullRequestContract(unittest.TestCase):
    def test_a_plain_english_lead_is_required(self):  # DEV-042
        self.assertIn("plain-english lead", BODY)

    def test_deviations_and_decisions_is_required(self):  # DEV-043
        self.assertIn("deviations and decisions", BODY)

    def test_it_is_required_even_when_empty(self):  # DEV-043
        self.assertIn("none.", BODY)

    def test_documentation_is_reconciled_in_the_same_pull_request(self):  # DEV-044
        self.assertIn("docs:", BODY)

    def test_one_closing_keyword(self):  # DEV-045
        self.assertIn("closing keyword", BODY)

    def test_one_issue_per_pull_request(self):  # DEV-045
        self.assertIn("one issue, one branch, one pull request", BODY)


class TestItIsStackAgnostic(unittest.TestCase):
    def test_it_reads_the_repository_configuration(self):  # DEV-046
        self.assertIn("repo-config.yml", AGENT)

    def test_it_asks_rather_than_guessing_a_test_command(self):  # DEV-046
        self.assertIn("guessed test command", BODY)

    def test_it_names_no_specific_stack(self):  # DEV-046
        """A stack named here is a stack every other consumer has to ignore."""
        for stack in ("unity", "gradle", "pytest", "vitest", "dotnet", "npm "):
            self.assertNotIn(stack, BODY, stack)


class TestItSaysWhatToDoWhenStuck(unittest.TestCase):
    def test_it_says_to_ask_rather_than_decide(self):  # TRI-030
        self.assertIn("stop. ask on the issue", BODY)

    def test_it_forbids_weakening_a_test(self):  # DEV-041
        self.assertIn("do not weaken a test", BODY)

    def test_it_forbids_widening_scope(self):  # DEV-045
        self.assertIn("do not widen the scope", BODY)

    def test_it_forbids_ticking_unverified_checks(self):  # DEV-041
        self.assertIn("have not verified", BODY)


if __name__ == "__main__":
    unittest.main()
