"""GK-020 to GK-028 — recognising commands in a comment.

The parser's job is to be boring and predictable. Every rule here exists
because the alternative is acting on something the author did not mean: a URL
containing a slash-word, an example inside a code fence, a typo silently read
as a different command.
"""

import unittest

import _gatekeeper  # noqa: F401
from parse_commands import COMMANDS, parse


def names(text):
    return [action.command for action in parse(text).actions]


class TestTheVocabulary(unittest.TestCase):
    def test_there_are_eleven_commands(self):  # GK-020
        self.assertEqual(len(COMMANDS), 11)

    def test_every_command_parses(self):  # GK-020
        for command in COMMANDS:
            self.assertEqual(names(f"/{command}"), [command], command)

    def test_retry_is_among_them(self):  # GK-020
        self.assertIn("retry", COMMANDS)


class TestWhereACommandIsRecognised(unittest.TestCase):
    def test_at_the_start_of_a_line(self):  # GK-020
        self.assertEqual(names("/approve"), ["approve"])

    def test_after_up_to_three_spaces(self):  # GK-020
        self.assertEqual(names("   /approve"), ["approve"])

    def test_not_after_four_spaces(self):  # GK-020
        """Four spaces is an indented code block in Markdown."""
        self.assertEqual(names("    /approve"), [])

    def test_not_mid_line(self):  # GK-022
        self.assertEqual(names("please /approve this"), [])

    def test_not_inside_a_url(self):  # GK-022
        self.assertEqual(names("see https://example.com/approve for details"), [])

    def test_not_as_part_of_a_longer_word(self):  # GK-022
        self.assertEqual(names("/approvestuff"), [])

    def test_prose_on_surrounding_lines_does_not_prevent_it(self):  # GK-023
        self.assertEqual(names("Looks good to me.\n/approve\nThanks!"), ["approve"])


class TestCodeFences(unittest.TestCase):
    def test_a_command_inside_backticks_is_ignored(self):  # GK-021
        self.assertEqual(names("```\n/approve\n```"), [])

    def test_a_command_inside_tildes_is_ignored(self):  # GK-021
        self.assertEqual(names("~~~\n/approve\n~~~"), [])

    def test_a_fence_with_a_language_still_fences(self):  # GK-021
        self.assertEqual(names("```bash\n/approve\n```"), [])

    def test_a_command_after_a_closed_fence_is_read(self):  # GK-021
        self.assertEqual(names("```\n/park\n```\n/approve"), ["approve"])

    def test_an_unclosed_fence_swallows_the_rest(self):  # GK-021
        """Safer to read nothing than to guess where the author meant it to end."""
        self.assertEqual(names("```\n/approve"), [])


class TestArguments(unittest.TestCase):
    def test_an_argument_is_the_rest_of_the_line(self):  # GK-024
        self.assertEqual(parse("/milestone v0.4").actions[0].argument, "v0.4")

    def test_an_argument_is_trimmed(self):  # GK-024
        self.assertEqual(parse("/milestone   v0.4   ").actions[0].argument, "v0.4")

    def test_an_argument_may_contain_spaces(self):  # GK-024
        self.assertEqual(parse("/revise use the other approach").actions[0].argument,
                         "use the other approach")

    def test_no_argument_is_an_empty_string_not_none(self):  # GK-024
        self.assertEqual(parse("/approve").actions[0].argument, "")

    def test_an_argument_keeps_its_internal_punctuation(self):  # GK-024
        self.assertEqual(parse("/focus v0.4 — the pilot").actions[0].argument, "v0.4 — the pilot")


class TestSeveralCommands(unittest.TestCase):
    def test_two_commands_are_both_read(self):  # GK-025
        self.assertEqual(names("/milestone v0.4\n/approve"), ["milestone", "approve"])

    def test_they_keep_the_order_written(self):  # GK-025
        self.assertEqual(names("/approve\n/park"), ["approve", "park"])

    def test_blank_lines_between_them_are_fine(self):  # GK-025
        self.assertEqual(names("/milestone v0.4\n\n/approve"), ["milestone", "approve"])

    def test_the_same_command_twice_is_read_twice(self):  # GK-025
        self.assertEqual(names("/park\n/park"), ["park", "park"])


class TestNothingToDo(unittest.TestCase):
    def test_a_comment_with_no_command_yields_nothing(self):  # GK-026
        result = parse("Looks good to me.")
        self.assertEqual(result.actions, [])
        self.assertEqual(result.skips, [])

    def test_an_empty_comment_yields_nothing(self):  # GK-026
        self.assertEqual(parse("").actions, [])

    def test_a_none_body_yields_nothing(self):  # GK-026
        self.assertEqual(parse(None).actions, [])

    def test_a_bare_slash_is_not_a_command(self):  # GK-026
        self.assertEqual(parse("/").actions, [])


class TestUnknownCommands(unittest.TestCase):
    def test_an_unknown_command_is_not_guessed_at(self):  # GK-027
        self.assertEqual(parse("/aprove").actions, [])

    def test_an_unknown_command_is_recorded_as_a_skip(self):  # GK-027
        self.assertEqual(parse("/aprove").skips[0].reason, "unknown-command")

    def test_the_skip_names_what_was_written(self):  # GK-027
        self.assertEqual(parse("/aprove").skips[0].command, "aprove")

    def test_a_near_miss_suggests_the_real_command(self):  # GK-028
        self.assertEqual(parse("/aprove").skips[0].suggestion, "approve")

    def test_another_near_miss(self):  # GK-028
        self.assertEqual(parse("/parc").skips[0].suggestion, "park")

    def test_nonsense_suggests_nothing(self):  # GK-028
        self.assertIsNone(parse("/xyzzy").skips[0].suggestion)

    def test_a_known_command_alongside_an_unknown_one_still_applies(self):  # GK-027
        result = parse("/approve\n/xyzzy")
        self.assertEqual([a.command for a in result.actions], ["approve"])
        self.assertEqual(len(result.skips), 1)


class TestPurity(unittest.TestCase):
    def test_the_module_performs_no_io(self):  # GK-131
        import ast

        from _support import ROOT

        source = (
            ROOT / "skills" / "pipeline" / "pipeline-gatekeeper" / "parse_commands.py"
        ).read_text()
        roots = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                roots.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".")[0])
        self.assertEqual(roots & {"urllib", "http", "socket", "requests", "subprocess"}, set())


if __name__ == "__main__":
    unittest.main()
