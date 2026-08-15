"""GK-010 to GK-019 — who may command, and who writes.

The gatekeeper is the only thing that moves an issue through the pipeline, so
"who is allowed to tell it to" is the whole security model. There is no clever
part: it is a list of logins, compared case-insensitively, and nothing else
grants authority.
"""

import unittest

import _gatekeeper  # noqa: F401
from authority import Authority, is_bot_login


def owners(*logins, bot="github-actions[bot]"):
    return Authority(owners=list(logins), bot_login=bot)


def comment(login, body="/approve", **extra):
    return dict({"user": {"login": login}, "body": body}, **extra)


class TestTheOwnerList(unittest.TestCase):
    def test_a_login_on_the_list_is_honoured(self):  # GK-010
        self.assertTrue(owners("derekwinters").may_command(comment("derekwinters")))

    def test_a_login_not_on_the_list_is_not(self):  # GK-010
        self.assertFalse(owners("derekwinters").may_command(comment("stranger")))

    def test_one_owner_is_a_list_of_one(self):  # GK-010
        """Not a special case: the same code path as many owners."""
        self.assertTrue(owners("derekwinters").may_command(comment("derekwinters")))

    def test_several_owners_are_all_honoured(self):  # GK-010
        authority = owners("derekwinters", "someone-else")
        self.assertTrue(authority.may_command(comment("someone-else")))

    def test_authority_is_membership_not_position(self):  # GK-010
        """The first owner is not privileged over the others."""
        authority = owners("a", "b", "c")
        self.assertEqual(
            [authority.may_command(comment(login)) for login in ("a", "b", "c")],
            [True, True, True],
        )


class TestCaseInsensitivity(unittest.TestCase):
    def test_a_different_case_still_matches(self):  # GK-011
        self.assertTrue(owners("derekwinters").may_command(comment("DerekWinters")))

    def test_the_configured_case_does_not_matter_either(self):  # GK-011
        self.assertTrue(owners("DerekWinters").may_command(comment("derekwinters")))

    def test_a_different_login_still_does_not_match(self):  # GK-011
        self.assertFalse(owners("derekwinters").may_command(comment("derekwinters2")))


class TestAssociationIsIrrelevant(unittest.TestCase):
    """GK-012 — GitHub's author_association is about repository permissions.

    A collaborator is not an owner. Reading authority from a permission level
    would silently widen who can drive the pipeline whenever the repository's
    access changes, which is not a decision the pipeline should inherit.
    """

    def test_an_owner_association_does_not_grant_authority(self):
        payload = comment("stranger", author_association="OWNER")
        self.assertFalse(owners("derekwinters").may_command(payload))

    def test_a_collaborator_association_does_not_grant_authority(self):
        payload = comment("stranger", author_association="COLLABORATOR")
        self.assertFalse(owners("derekwinters").may_command(payload))

    def test_a_none_association_does_not_remove_it(self):
        payload = comment("derekwinters", author_association="NONE")
        self.assertTrue(owners("derekwinters").may_command(payload))


class TestBots(unittest.TestCase):
    def test_the_configured_bot_is_never_a_commander(self):  # GK-014
        """Otherwise the gatekeeper's own acknowledgements read as commands."""
        self.assertFalse(
            owners("derekwinters", bot="sdlc-bot[bot]").may_command(comment("sdlc-bot[bot]"))
        )

    def test_the_bot_is_refused_even_if_listed_as_an_owner(self):  # GK-014
        authority = Authority(owners=["sdlc-bot[bot]"], bot_login="sdlc-bot[bot]")
        self.assertFalse(authority.may_command(comment("sdlc-bot[bot]")))

    def test_any_bot_login_is_refused(self):  # GK-015
        self.assertFalse(owners("derekwinters").may_command(comment("dependabot[bot]")))

    def test_the_claude_app_is_refused(self):  # GK-015
        self.assertFalse(owners("derekwinters").may_command(comment("claude[bot]")))

    def test_a_human_whose_name_contains_bot_is_not_a_bot(self):  # GK-015
        self.assertTrue(owners("robotham").may_command(comment("robotham")))

    def test_the_bot_suffix_test_is_exact(self):  # GK-015
        self.assertTrue(is_bot_login("x[bot]"))
        self.assertFalse(is_bot_login("x[bot]y"))
        self.assertFalse(is_bot_login("bot"))


class TestPullRequestsAreNotIssues(unittest.TestCase):
    def test_a_comment_on_a_pull_request_is_ignored(self):  # GK-016
        payload = comment("derekwinters")
        payload["issue"] = {"number": 1, "pull_request": {"url": "..."}}
        self.assertFalse(owners("derekwinters").may_command(payload))

    def test_a_comment_on_an_issue_is_not(self):  # GK-016
        payload = comment("derekwinters")
        payload["issue"] = {"number": 1}
        self.assertTrue(owners("derekwinters").may_command(payload))


class TestSilence(unittest.TestCase):
    def test_a_refusal_carries_no_acknowledgement(self):  # GK-013
        """Replying to a stranger would let anyone make the bot post."""
        decision = owners("derekwinters").decide(comment("stranger"))
        self.assertFalse(decision.honoured)
        self.assertIsNone(decision.acknowledgement)

    def test_a_refusal_names_its_reason_internally(self):  # GK-013
        decision = owners("derekwinters").decide(comment("stranger"))
        self.assertEqual(decision.reason, "not-owner")

    def test_a_bot_refusal_is_distinguishable_from_a_stranger(self):  # GK-014
        decision = owners("derekwinters").decide(comment("dependabot[bot]"))
        self.assertEqual(decision.reason, "bot")

    def test_an_honoured_comment_has_no_reason(self):  # GK-013
        self.assertIsNone(owners("derekwinters").decide(comment("derekwinters")).reason)


class TestAnEmptyList(unittest.TestCase):
    """GK-019 — missing configuration must not fall back to something permissive."""

    def test_an_empty_owner_list_honours_nothing(self):
        self.assertFalse(Authority(owners=[], bot_login="x[bot]").may_command(comment("anyone")))

    def test_not_even_a_repository_owner_association(self):
        payload = comment("derekwinters", author_association="OWNER")
        self.assertFalse(Authority(owners=[], bot_login="x[bot]").may_command(payload))

    def test_the_reason_says_there_are_no_owners(self):
        decision = Authority(owners=[], bot_login="x[bot]").decide(comment("derekwinters"))
        self.assertEqual(decision.reason, "no-owners")


class TestWritesAreAuthoredByTheBot(unittest.TestCase):
    def test_the_write_identity_is_the_bot_not_the_owner(self):  # GK-017
        self.assertEqual(owners("derekwinters", bot="sdlc-bot[bot]").write_as, "sdlc-bot[bot]")

    def test_it_defaults_to_github_actions(self):  # GK-018
        from lib.config import parse_config

        config = parse_config("capabilities:\n  - hygiene")
        self.assertEqual(Authority.from_config(config).write_as, "github-actions[bot]")

    def test_it_comes_from_configuration(self):  # GK-018
        from lib.config import parse_config

        config = parse_config(
            "capabilities:\n  - hygiene\nbot:\n  login: sdlc-bot[bot]"
        )
        self.assertEqual(Authority.from_config(config).write_as, "sdlc-bot[bot]")

    def test_owners_come_from_configuration_too(self):  # GK-010
        from lib.config import parse_config

        config = parse_config(
            "capabilities:\n  - hygiene\nowners:\n  - derekwinters\n  - someone"
        )
        self.assertEqual(Authority.from_config(config).owners, ["derekwinters", "someone"])


if __name__ == "__main__":
    unittest.main()
