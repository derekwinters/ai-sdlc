"""GK-110 to GK-119 — what a successful command sets in motion.

Two effects: analysis is fired when an issue newly enters triage, and the
dashboard is re-rendered once when labels changed. Both are guarded so that a
run which changed nothing costs nothing.
"""

import unittest

import _gatekeeper  # noqa: F401
from downstream import Fire, fires_triage, should_rerender

TRIAGE = "ai-triage"


class TestFiringAnalysis(unittest.TestCase):
    def test_newly_adding_triage_fires(self):  # GK-110
        self.assertTrue(fires_triage([], [TRIAGE], triage_label=TRIAGE))

    def test_an_idempotent_re_add_does_not(self):  # GK-111
        self.assertFalse(fires_triage([TRIAGE], [TRIAGE], triage_label=TRIAGE))

    def test_removing_triage_does_not(self):  # GK-112
        self.assertFalse(fires_triage([TRIAGE], [], triage_label=TRIAGE))

    def test_no_change_does_not(self):  # GK-111
        self.assertFalse(fires_triage(["parked"], ["parked"], triage_label=TRIAGE))

    def test_moving_from_another_state_into_triage_fires(self):  # GK-110
        self.assertTrue(fires_triage(["parked"], [TRIAGE], triage_label=TRIAGE))

    def test_other_labels_changing_alongside_do_not_matter(self):  # GK-110
        self.assertTrue(fires_triage(["area:x"], [TRIAGE, "area:x"], triage_label=TRIAGE))

    def test_the_label_name_comes_from_configuration(self):  # GK-110
        self.assertTrue(fires_triage([], ["queued"], triage_label="queued"))


class TestRerendering(unittest.TestCase):
    def test_a_label_change_rerenders(self):  # GK-114
        self.assertTrue(should_rerender(["a"], ["b"]))

    def test_no_label_change_does_not(self):  # GK-115
        self.assertFalse(should_rerender(["a"], ["a"]))

    def test_order_alone_is_not_a_change(self):  # GK-115
        self.assertFalse(should_rerender(["a", "b"], ["b", "a"]))

    def test_a_removal_is_a_change(self):  # GK-114
        self.assertTrue(should_rerender(["a", "b"], ["a"]))


class TestTheFireIsBestEffort(unittest.TestCase):
    """GK-117 to GK-119 — a routine that cannot be reached must not fail the run.

    The gatekeeper's job is the label move. Analysis running late is an
    inconvenience; a failed workflow run on a label move is a broken pipeline.
    """

    def test_an_unconfigured_endpoint_is_a_notice_not_an_error(self):  # GK-119
        result = Fire(endpoint=None, token=None).send(issue=7, repository="o/r")
        self.assertFalse(result.attempted)
        self.assertFalse(result.failed)

    def test_a_missing_token_is_also_a_notice(self):  # GK-119
        result = Fire(endpoint="https://example.com", token=None).send(7, "o/r")
        self.assertFalse(result.attempted)
        self.assertFalse(result.failed)

    def test_a_transport_failure_is_reported_not_raised(self):  # GK-117
        def explode(*_args, **_kwargs):
            raise OSError("no route to host")

        result = Fire("https://example.com", "t", transport=explode).send(7, "o/r")
        self.assertTrue(result.failed)

    def test_a_failure_carries_a_reason(self):  # GK-117
        def explode(*_args, **_kwargs):
            raise OSError("no route to host")

        result = Fire("https://example.com", "t", transport=explode).send(7, "o/r")
        self.assertIn("no route to host", result.detail)

    def test_a_non_2xx_is_reported_not_raised(self):  # GK-117
        result = Fire("https://example.com", "t",
                      transport=lambda *a, **k: (404, "nope")).send(7, "o/r")
        self.assertTrue(result.failed)

    def test_a_2xx_succeeds(self):  # GK-117
        result = Fire("https://example.com", "t",
                      transport=lambda *a, **k: (202, "{}")).send(7, "o/r")
        self.assertTrue(result.attempted)
        self.assertFalse(result.failed)

    def test_the_body_snippet_is_bounded(self):  # GK-117
        result = Fire("https://example.com", "t",
                      transport=lambda *a, **k: (500, "x" * 10_000)).send(7, "o/r")
        self.assertLess(len(result.detail), 1_000)


class TestNothingSecretIsLogged(unittest.TestCase):
    def test_the_detail_never_contains_the_endpoint(self):  # GK-118
        result = Fire("https://secret.example.com/hook", "t",
                      transport=lambda *a, **k: (500, "boom")).send(7, "o/r")
        self.assertNotIn("secret.example.com", result.detail)

    def test_the_detail_never_contains_the_token(self):  # GK-118
        result = Fire("https://example.com", "s3cret-token",
                      transport=lambda *a, **k: (500, "boom")).send(7, "o/r")
        self.assertNotIn("s3cret-token", result.detail)

    def test_the_repr_contains_neither(self):  # GK-118
        fire = Fire("https://secret.example.com/hook", "s3cret-token")
        self.assertNotIn("secret.example.com", repr(fire))
        self.assertNotIn("s3cret-token", repr(fire))

    def test_a_transport_error_mentioning_the_url_is_still_scrubbed(self):  # GK-118
        def explode(*_args, **_kwargs):
            raise OSError("failed to reach https://secret.example.com/hook")

        result = Fire("https://secret.example.com/hook", "t", transport=explode).send(7, "o/r")
        self.assertNotIn("secret.example.com", result.detail)


class TestTheRequest(unittest.TestCase):
    def test_it_names_the_repository_and_issue(self):  # GK-110
        sent = {}

        def record(url, headers, body):
            sent.update(body=body)
            return (202, "{}")

        Fire("https://example.com", "t", transport=record).send(7, "owner/repo")
        self.assertIn("owner/repo", sent["body"])
        self.assertIn("7", sent["body"])

    def test_the_issue_number_is_an_integer_not_free_text(self):  # GK-110
        import json

        sent = {}

        def record(url, headers, body):
            sent.update(body=body)
            return (202, "{}")

        Fire("https://example.com", "t", transport=record).send(7, "owner/repo")
        self.assertIsInstance(json.loads(sent["body"])["issue"], int)


if __name__ == "__main__":
    unittest.main()


class TestReportingTheOutcome(unittest.TestCase):
    """GK-121 — a run says whether it fired, and why not when it did not.

    A run that fired the routine and one that silently skipped it produced
    byte-identical logs, so "working", "rejected", "unwired" and "no routine
    at all" were indistinguishable. That is why #118 survived from adoption
    until somebody noticed triage had never run.
    """

    def test_a_fired_run_says_so(self):  # GK-121
        from downstream import FireResult, fire_summary

        self.assertIn("fired", fire_summary(FireResult(attempted=True)).lower())

    def test_a_failure_says_why(self):  # GK-121
        from downstream import FireResult, fire_summary

        line = fire_summary(FireResult(True, failed=True, detail="502 from the endpoint"))
        self.assertIn("502 from the endpoint", line)

    def test_an_unconfigured_routine_is_named_as_such(self):  # GK-121
        """GK-119 keeps this a notice rather than an error.

        It must still be *visible*, or a deliberate absence and a broken wire
        read the same.
        """
        from downstream import Fire, fire_summary

        line = fire_summary(Fire(None, None).send(7, "owner/repo"))
        self.assertIn("no analysis routine", line.lower())

    def test_not_a_triage_transition_is_distinguished(self):  # GK-121
        from downstream import NOT_TRIAGE, fire_summary

        self.assertIn("no triage transition", fire_summary(NOT_TRIAGE).lower())

    def test_a_result_is_falsy_when_it_did_not_fire(self):  # GK-121
        """So `result.fired` keeps meaning what four existing tests assert."""
        from downstream import FireResult

        self.assertFalse(FireResult(attempted=False))
        self.assertTrue(FireResult(attempted=True))
