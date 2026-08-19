"""ADOPT-060 to ADOPT-066 — a caller is pinned to a commit SHA.

A reusable workflow runs with the *caller's* token, on `issue_comment` and
`issues`, inside the consumer's repository. So what a caller names its workflow
by is a security decision: a tag is a mutable pointer, and publishing it
ourselves narrows who could move it without making the reference immutable.

Callers used to reference `@v0.4.1`. `connor-multiplying-frogs` rejected that
with its own action-pin checker on the first real adoption, and was right to.
"""

import unittest

from _adopt import repository
from adopt import AdoptRefused, _caller, resolve_version

SHA = "5c625bfb5d1ff62eadeeb3772007f7f66fdcf071"
OTHER = "11d5960a326750d5838078e36cf38b85af677262"


def caller(version=("v0.4.1", SHA)):
    return _caller("labels-sync", "reusable-labels-sync.yml", version,
                   trigger="  pull_request:\n")


class TestTheReference(unittest.TestCase):
    def test_uses_names_the_sha(self):  # ADOPT-060
        self.assertIn(f"reusable-labels-sync.yml@{SHA}", caller())

    def test_uses_does_not_name_the_version(self):  # ADOPT-060
        line = [l for l in caller().splitlines() if "uses:" in l][0]
        self.assertNotIn("@v0.4.1", line)

    def test_the_ref_input_is_the_same_sha(self):  # ADOPT-060
        self.assertIn(f"ref: {SHA}", caller())

    def test_the_ref_input_is_not_the_version(self):  # ADOPT-060
        self.assertNotIn("ref: v0.4.1", caller())

    def test_the_sha_carries_a_version_comment(self):  # ADOPT-061
        line = [l for l in caller().splitlines() if "uses:" in l][0]
        self.assertIn("# v0.4.1", line)


class TestResolving(unittest.TestCase):
    def test_a_version_resolves_to_its_commit(self):  # ADOPT-062
        refs = f"{OTHER}\trefs/tags/v0.4.1\n"
        self.assertEqual(resolve_version("v0.4.1", resolver=lambda _: refs), OTHER)

    def test_an_annotated_tag_dereferences_to_the_commit(self):  # ADOPT-064
        # For an annotated tag the bare ref is the *tag object*; only `^{}` is
        # the commit. Pinning the tag object produces a ref that will not
        # resolve — this cost us a whole afternoon in #64.
        refs = f"{OTHER}\trefs/tags/v0.4.1\n{SHA}\trefs/tags/v0.4.1^{{}}\n"
        self.assertEqual(resolve_version("v0.4.1", resolver=lambda _: refs), SHA)

    def test_a_lightweight_tag_needs_no_dereference(self):  # ADOPT-064
        refs = f"{SHA}\trefs/tags/v0.4.1\n"
        self.assertEqual(resolve_version("v0.4.1", resolver=lambda _: refs), SHA)

    def test_a_version_that_resolves_to_nothing_is_an_error(self):  # ADOPT-065
        with self.assertRaises(AdoptRefused):
            resolve_version("v9.9.9", resolver=lambda _: "")

    def test_the_error_names_the_version(self):  # ADOPT-065
        with self.assertRaises(AdoptRefused) as caught:
            resolve_version("v9.9.9", resolver=lambda _: "")
        self.assertIn("v9.9.9", str(caught.exception))

    def test_a_sha_is_accepted_as_itself(self):  # ADOPT-062
        # Passing a SHA directly must not require the network at all.
        def explode(_):
            raise AssertionError("resolution should not have been attempted")

        self.assertEqual(resolve_version(SHA, resolver=explode), SHA)

    def test_an_unrelated_ref_is_not_mistaken_for_the_tag(self):  # ADOPT-065
        # `v0.4.10` contains `v0.4.1` as a prefix.
        refs = f"{OTHER}\trefs/tags/v0.4.10\n"
        with self.assertRaises(AdoptRefused):
            resolve_version("v0.4.1", resolver=lambda _: refs)


class TestTheResolverSeam(unittest.TestCase):
    def test_plan_resolves_through_the_injected_resolver(self):  # ADOPT-063
        # Not merely that resolution works, but that it goes through the seam:
        # a default that quietly opened a socket would make the whole suite
        # network-dependent, and only this asserts it does not.
        root = repository({".ai-sdlc/repo-config.yml": "capabilities:\n  - hygiene\n"})
        seen = []

        def resolver(version):
            seen.append(version)
            return f"{SHA}\trefs/tags/{version}\n"

        from adopt import plan

        plan(root, "v0.4.1", resolver=resolver)
        self.assertEqual(seen, ["v0.4.1"])

    def test_apply_resolves_through_the_injected_resolver(self):  # ADOPT-063
        root = repository({".ai-sdlc/repo-config.yml": "capabilities:\n  - hygiene\n"})

        def resolver(version):
            return f"{SHA}\trefs/tags/{version}\n"

        from adopt import apply

        apply(root, "v0.4.1", resolver=resolver)
        self.assertIn(SHA, (root / ".ai-sdlc" / "ai-sdlc.pin").read_text())


class TestTheRecordedPin(unittest.TestCase):
    def test_the_pin_records_the_version_and_the_sha(self):  # ADOPT-066
        root = repository({".ai-sdlc/repo-config.yml": "capabilities:\n  - hygiene\n"})
        from adopt import apply

        apply(root, ("v0.4.1", SHA))
        recorded = (root / ".ai-sdlc" / "ai-sdlc.pin").read_text()
        self.assertIn("v0.4.1", recorded)
        self.assertIn(SHA, recorded)

    def test_verify_at_the_same_version_needs_no_network(self):  # ADOPT-066
        root = repository({".ai-sdlc/repo-config.yml": "capabilities:\n  - hygiene\n"})
        from adopt import apply, verify

        apply(root, ("v0.4.1", SHA))

        def explode(_):
            raise AssertionError("verify reached the network")

        verify(root, ("v0.4.1", SHA), resolver=explode)


class TestTheRealRepository(unittest.TestCase):
    def test_no_caller_this_repository_ships_names_a_tag(self):  # ADOPT-060
        # ai-sdlc's own consistency gate enforces this for its workflows; this
        # asserts the *generator* cannot reintroduce it.
        self.assertNotIn("@v", [l for l in caller().splitlines() if "uses:" in l][0]
                         .split("@")[1][:1])


if __name__ == "__main__":
    unittest.main()
