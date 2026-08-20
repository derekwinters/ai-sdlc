"""API-070 to API-078 — the one statement of how anything touches GitHub.

`lib/github.py` encodes a set of constraints in code: a deliberately small
vocabulary, pagination that reports truncation, errors that are bounded, a token
that is never printed. Every one of those constraints applies to an agent too —
and an agent has no method table to be limited by. It can call anything its tools
expose, so a constraint that exists only as an absent method does not exist for
it at all (#158).

So the rules move into a skill, and the module becomes one implementation of
them rather than their only statement. The vocabulary is machine-readable in the
skill and asserted against the client here, because "no delete" being true in
two places for two different reasons is exactly the shape that comes apart
quietly.
"""

import re
import unittest

from _support import ROOT

SKILL = ROOT / "skills" / "substrate" / "github-api" / "SKILL.md"


def _text():
    return SKILL.read_text()


def _frontmatter():
    body = _text()
    _, _, rest = body.partition("---\n")
    front, _, _ = rest.partition("\n---\n")
    return front


def _vocabulary():
    """The machine-readable block, parsed.

    A fenced block after a named marker, rather than prose. The point of
    stating the vocabulary here is that a test can compare it to the client;
    a test that had to read English could not do that without being fragile.
    """
    from lib.yaml_lite import parse

    match = re.search(r"<!-- vocabulary -->\s*```yaml\n(.*?)```", _text(), re.S)
    assert match, "the skill has no `<!-- vocabulary -->` block"
    return parse(match.group(1))


def _client_operations():
    """Every public operation `lib/github.py` exposes."""
    from lib.github import GitHub

    return {
        name
        for name in vars(GitHub)
        if not name.startswith("_") and callable(vars(GitHub)[name])
    }


#: The two the client exposes that are not vocabulary: they are how a request is
#: made, not a thing that may be done.
TRANSPORT = {"request", "paginate"}


class TestTheSkillExists(unittest.TestCase):
    def test_it_is_installed_under_substrate(self):  # API-070
        self.assertTrue(SKILL.is_file())

    def test_its_description_names_what_an_agent_is_about_to_do(self):  # API-077
        """A description offering "GitHub access" in the abstract is one an
        agent loads when it is already too late — after it has decided what to
        do. Naming the acts is what gets it loaded first."""
        description = _frontmatter().lower()
        for act in ("label", "milestone", "comment", "blocker"):
            with self.subTest(act=act):
                self.assertIn(act, description)


class TestTheVocabularyCannotDrift(unittest.TestCase):
    """API-071 — one statement, two implementations, compared.

    This is the answer to #158's open question. The skill governs scripts as
    well as agents: `lib/github.py` is an implementation of the rules rather
    than a second copy of them, and this test is what makes that true rather
    than aspirational.
    """

    def test_every_client_operation_is_stated(self):  # API-071
        stated = set(_vocabulary()["reads"]) | set(_vocabulary()["writes"])
        self.assertEqual(_client_operations() - TRANSPORT - stated, set())

    def test_nothing_is_stated_that_the_client_does_not_have(self):  # API-071
        stated = set(_vocabulary()["reads"]) | set(_vocabulary()["writes"])
        self.assertEqual(stated - _client_operations(), set())

    def test_a_read_is_never_listed_as_a_write(self):  # API-071
        self.assertEqual(set(_vocabulary()["reads"]) & set(_vocabulary()["writes"]), set())

    def test_the_forbidden_list_is_not_empty(self):  # API-072
        self.assertTrue(_vocabulary()["forbidden"])

    def test_nothing_forbidden_is_also_permitted(self):  # API-072
        stated = set(_vocabulary()["reads"]) | set(_vocabulary()["writes"])
        self.assertEqual({f.split()[0] for f in _vocabulary()["forbidden"]} & stated, set())


class TestTheRulesAnAgentWouldOtherwiseNotMeet(unittest.TestCase):
    """API-072 to API-076 — each is a constraint with no code to enforce it
    once the caller is an agent rather than this module."""

    def test_closing_an_issue_is_stated_as_forbidden(self):  # API-072
        """Today this is enforced by the absence of a method. An agent has the
        method."""
        self.assertRegex(_text(), r"(?i)clos(e|ing) an issue")

    def test_the_database_id_rule_is_stated(self):  # API-073
        """Both are integers, so the wrong one silently succeeds (#155)."""
        text = _text()
        self.assertIn("database id", text.lower())
        self.assertIn("add_blocked_by", text)

    def test_truncation_is_stated(self):  # API-074
        self.assertRegex(_text(), r"(?i)truncat")

    def test_a_count_from_a_partial_read_is_refused(self):  # API-074
        self.assertRegex(_text(), r"(?i)never report a (count|total)")

    def test_writing_on_a_schedule_is_stated_as_forbidden(self):  # API-075
        self.assertRegex(_text(), r"(?i)on a schedule")

    def test_redaction_is_stated(self):  # API-076
        """The house rules' "never publish a private link" from the other end:
        an error body quotes the value it was handed."""
        self.assertRegex(_text(), r"(?i)redact")


class TestItIsNotASecondCopyOfThePipeline(unittest.TestCase):
    """API-078 — this says how to touch GitHub, not what the labels mean.

    A skill that also explained the state machine would be a second copy of it,
    and the copy would rot. `GK`, `BLK`, `MS` and `LBL` own that.
    """

    def test_it_names_no_pipeline_state_label(self):  # API-078
        from lib.config import STATES

        text = _text()
        for state, label in STATES.items():
            with self.subTest(state=state):
                self.assertNotIn(label, text)

    def test_it_points_at_the_specifications_that_do(self):  # API-078
        text = _text()
        for area in ("GK", "BLK", "LBL"):
            with self.subTest(area=area):
                self.assertIn(area, text)


class TestARepositoryGetsIt(unittest.TestCase):
    """API-079 — a skill nothing installs is the silence #149 just fixed."""

    def test_it_is_seeded_into_every_repository(self):  # API-079
        import sys

        sys.path.insert(0, str(ROOT / "skills" / "substrate" / "adopt"))
        from adopt import INVOKED_LOCALLY

        self.assertIn("github-api", INVOKED_LOCALLY["substrate"])


if __name__ == "__main__":
    unittest.main()
