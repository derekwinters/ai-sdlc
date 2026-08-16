"""DASH-002/003/004, DASH-010 to DASH-019 — the rendered page.

Two charts, then five collapsible sections. The assertions here are mostly
about the *shape* of the Markdown rather than its prose, because the shape is
what GitHub either renders or silently mangles — a table without a blank line
around it inside `<details>` comes out as literal text, and a second `bar`
series comes out overlaid rather than stacked.
"""

import unittest

from _dashboard import LABELS, REPO, issue, state
import _dashboard  # noqa: F401
from render_dashboard import render


def _focus_chart(page):
    """The second chart block, or '' when the page has none."""
    blocks = [b for b in page.split("```mermaid") if "xychart" in b]
    return blocks[1] if len(blocks) > 1 else ""


def _milestone_chart(page):
    blocks = [b for b in page.split("```mermaid") if "xychart" in b]
    return blocks[0] if blocks else ""


def _section(page, heading):
    """One `<details>` block, by its summary text."""
    for block in page.split("<details>"):
        if heading in block.split("</summary>")[0]:
            return block
    return ""


class TestDeterminism(unittest.TestCase):
    def test_the_same_state_renders_identically(self):  # DASH-003
        snapshot = state(issues=[issue(7), issue(8)])
        self.assertEqual(render(snapshot), render(snapshot))

    def test_issue_order_does_not_change_the_output(self):  # DASH-004
        forwards = state(issues=[issue(7), issue(8)])
        backwards = state(issues=[issue(8), issue(7)])
        self.assertEqual(render(forwards), render(backwards))

    def test_rendering_touches_no_client(self):  # DASH-002
        import ast

        from _support import ROOT

        source = (ROOT / "skills" / "pipeline" / "pipeline-dashboard"
                  / "render_dashboard.py").read_text()
        imported = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        self.assertNotIn("lib.github", imported)


class TestTheMilestoneChart(unittest.TestCase):
    """DASH-010 — open issues per open milestone."""

    def test_every_open_milestone_appears(self):  # DASH-010
        page = render(state())
        chart = _milestone_chart(page)
        self.assertIn("v0.2", chart)
        self.assertIn("v0.3", chart)

    def test_a_milestone_with_no_issues_still_appears(self):  # DASH-010
        """The whole point of the chart.

        An empty milestone is how you see there is planning runway left, and
        therefore when more milestones need creating. Filtering it out hides
        exactly the thing being looked for.
        """
        page = render(state(milestones=[
            {"title": "v0.2", "number": 2, "open": 2},
            {"title": "v0.9", "number": 9, "open": 0},
        ]))
        chart = _milestone_chart(page)
        self.assertIn("v0.9", chart)
        self.assertIn("bar [2, 0]", chart)


class TestTheFocusChart(unittest.TestCase):
    """DASH-011/012 — the focus milestone by bucket."""

    def _chart_for(self, issues):
        return _focus_chart(render(state(issues=issues)))

    def test_buckets_read_as_a_flow(self):  # DASH-011
        chart = self._chart_for([issue(1)])
        self.assertIn(
            'x-axis ["Unplanned", "In planning", "Ready", "Done"]', chart)

    def test_ready_counts_approved_and_building(self):  # DASH-011
        chart = self._chart_for([
            issue(1, state_label=LABELS["approved"]),
            issue(2, state_label=LABELS["building"]),
        ])
        self.assertIn("bar [0, 0, 2, 0]", chart)

    def test_in_planning_counts_the_three_planning_states(self):  # DASH-011
        chart = self._chart_for([
            issue(1, state_label=LABELS["triage"]),
            issue(2, state_label=LABELS["pending_approval"]),
            issue(3, state_label=LABELS["clarification"]),
        ])
        self.assertIn("bar [0, 3, 0, 0]", chart)

    def test_done_counts_closed_issues(self):  # DASH-011
        chart = self._chart_for([issue(1, closed=True)])
        self.assertIn("bar [0, 0, 0, 1]", chart)

    def test_parked_folds_into_unplanned(self):  # DASH-011
        """Rather than vanishing.

        An issue missing from every bucket makes the chart understate the
        milestone, which is worse than putting it in the roughest bucket.
        """
        chart = self._chart_for([issue(1, state_label=LABELS["parked"])])
        self.assertIn("bar [1, 0, 0, 0]", chart)

    def test_an_untracked_issue_is_unplanned(self):  # DASH-011
        chart = self._chart_for([issue(1, state_label=None)])
        self.assertIn("bar [1, 0, 0, 0]", chart)

    def test_issues_outside_the_focus_are_not_counted(self):  # DASH-011
        chart = self._chart_for([
            issue(1),
            issue(2, milestone="v0.9", milestone_number=9),
        ])
        self.assertIn("bar [0, 0, 1, 0]", chart)

    def test_no_focus_renders_a_sentence_not_a_chart(self):  # DASH-012
        page = render(state(focus=None, issues=[issue(1)]))
        self.assertIn("no milestone set", page)
        self.assertEqual(_focus_chart(page), "")


class TestChartForm(unittest.TestCase):
    """DASH-013/014/015 — how every chart is drawn."""

    def test_charts_are_horizontal(self):  # DASH-013
        page = render(state())
        for chart in (_milestone_chart(page), _focus_chart(page)):
            self.assertIn("xychart-beta horizontal", chart)

    def test_only_one_series_per_chart(self):  # DASH-013
        """Mermaid overlays multiple `bar` series rather than stacking them.

        Verified against mermaid 11.16.1: series of 15 and 12 draw as 15 with
        12 in front of it, not 27, so a taller series hides a shorter one.
        """
        page = render(state(issues=[issue(1), issue(2, closed=True)]))
        for chart in (_milestone_chart(page), _focus_chart(page)):
            self.assertEqual(chart.count("\n    bar "), 1)

    def test_height_grows_with_the_number_of_bars(self):  # DASH-014
        few = _milestone_chart(render(state(milestones=[
            {"title": "v0.2", "number": 2, "open": 1},
        ])))
        many = _milestone_chart(render(state(milestones=[
            {"title": f"v0.{n}", "number": n, "open": 0} for n in range(1, 13)
        ])))
        self.assertLess(_height_of(few), _height_of(many))

    def test_height_has_a_floor(self):  # DASH-014
        """A one-bar chart still needs room for its axis and title."""
        chart = _milestone_chart(render(state(milestones=[
            {"title": "v0.2", "number": 2, "open": 1},
        ])))
        self.assertGreaterEqual(_height_of(chart), 180)

    def test_the_init_directive_keeps_its_doubled_percent_signs(self):  # DASH-014
        """Mermaid needs `%%{init: ...}%%` exactly.

        Built once with Python's `%` operator, which collapses `%%` to `%` —
        producing a directive mermaid ignores, so the chart silently rendered
        at default size. No unit test caught it; a live render did.
        """
        chart = _milestone_chart(render(state()))
        init = [l for l in chart.splitlines() if "init" in l][0]
        self.assertTrue(init.startswith("%%{init:"), init)
        self.assertTrue(init.endswith("}%%"), init)

    def test_milestones_are_ordered_by_version(self):  # DASH-010
        """The API returns creation order, which puts v0.5 after v0.12."""
        page = render(state(milestones=[
            {"title": "v0.12", "number": 12, "open": 1},
            {"title": "Human", "number": 3, "open": 4},
            {"title": "v0.5", "number": 13, "open": 2},
        ]))
        axis = [l for l in _milestone_chart(page).splitlines() if "x-axis" in l][0]
        self.assertLess(axis.index("v0.5"), axis.index("v0.12"))

    def test_a_milestone_naming_no_version_sorts_last(self):  # DASH-010
        page = render(state(milestones=[
            {"title": "Human", "number": 3, "open": 4},
            {"title": "v0.5", "number": 13, "open": 2},
        ]))
        axis = [l for l in _milestone_chart(page).splitlines() if "x-axis" in l][0]
        self.assertLess(axis.index("v0.5"), axis.index("Human"))

    def test_a_quote_in_a_title_cannot_break_the_syntax(self):  # DASH-015
        chart = _milestone_chart(render(state(milestones=[
            {"title": 'the "big" one', "number": 2, "open": 1},
        ])))
        axis = [line for line in chart.splitlines() if "x-axis" in line][0]
        # One quoted label, not three fragments.
        self.assertEqual(axis.count('"'), 2)


def _height_of(chart):
    import re

    found = re.search(r'"height":\s*(\d+)', chart)
    return int(found.group(1)) if found else 0


class TestSections(unittest.TestCase):
    """DASH-016 to DASH-019 — the five collapsible sections."""

    HEADINGS = ("Ready for work", "Pending approval", "Needs clarification",
                "Waiting for triage", "Parked")

    def test_all_five_sections_render(self):  # DASH-016
        page = render(state(issues=[issue(1)]))
        for heading in self.HEADINGS:
            self.assertIn(heading, page)

    def test_each_section_is_collapsible(self):  # DASH-016
        page = render(state(issues=[issue(1)]))
        self.assertEqual(page.count("<details>"), 5)
        self.assertEqual(page.count("</details>"), 5)

    def test_a_section_carries_its_count(self):  # DASH-016
        page = render(state(issues=[issue(1), issue(2)]))
        self.assertIn("Ready for work</b> — 2", _section(page, "Ready for work"))

    def test_an_empty_section_still_renders(self):  # DASH-017
        """So the board's shape is constant.

        A section that disappears when empty makes "missing" ambiguous between
        an empty queue and a defect.
        """
        page = render(state(issues=[]))
        for heading in self.HEADINGS:
            self.assertIn(f"{heading}</b> — 0", _section(page, heading))

    def test_a_table_inside_details_is_surrounded_by_blank_lines(self):  # DASH-016
        """Without them GitHub renders the table as literal text."""
        block = _section(render(state(issues=[issue(1)])), "Ready for work")
        body = block.split("</summary>")[1]
        self.assertTrue(body.startswith("\n\n|"), repr(body[:20]))
        self.assertIn("|\n\n</details>", body)

    def test_ready_for_work_holds_approved_and_building(self):  # DASH-019
        page = render(state(issues=[
            issue(1, state_label=LABELS["approved"]),
            issue(2, state_label=LABELS["building"]),
        ]))
        block = _section(page, "Ready for work")
        self.assertIn("#1", block)
        self.assertIn("#2", block)

    def test_only_ready_for_work_has_a_status_column(self):  # DASH-019
        page = render(state(issues=[
            issue(1, state_label=LABELS["approved"]),
            issue(2, state_label=LABELS["parked"]),
        ]))
        self.assertIn("| Status |", _section(page, "Ready for work"))
        self.assertNotIn("| Status |", _section(page, "Parked"))

    def test_the_status_column_says_which_state(self):  # DASH-019
        page = render(state(issues=[issue(2, state_label=LABELS["building"])]))
        self.assertIn("in-progress", _section(page, "Ready for work"))

    def test_waiting_for_triage_excludes_the_five_states(self):  # DASH-016
        page = render(state(issues=[
            issue(1, state_label=LABELS["approved"]),
            issue(2, state_label=LABELS["building"]),
            issue(3, state_label=LABELS["pending_approval"]),
            issue(4, state_label=LABELS["clarification"]),
            issue(5, state_label=LABELS["parked"]),
            issue(6, state_label=LABELS["triage"]),
            issue(7, state_label=None),
        ]))
        block = _section(page, "Waiting for triage")
        self.assertIn("Waiting for triage</b> — 2", block)
        self.assertIn("#6", block)
        self.assertIn("#7", block)

    def test_a_closed_issue_is_in_no_section(self):  # DASH-017
        """It still counts towards Done on the chart."""
        page = render(state(issues=[issue(1, closed=True)]))
        for heading in self.HEADINGS:
            self.assertIn(f"{heading}</b> — 0", _section(page, heading))


class TestRows(unittest.TestCase):
    """DASH-018 — what a row contains."""

    def test_the_issue_is_linked(self):  # DASH-018
        block = _section(render(state(issues=[issue(41)])), "Ready for work")
        self.assertIn(f"[#41](https://github.com/{REPO}/issues/41)", block)

    def test_the_milestone_is_linked_by_number(self):  # DASH-018
        block = _section(render(state(issues=[issue(41)])), "Ready for work")
        self.assertIn(f"[#2](https://github.com/{REPO}/milestone/2)", block)

    def test_no_milestone_renders_a_dash(self):  # DASH-018
        block = _section(render(state(issues=[
            issue(41, milestone=None, milestone_number=None)])), "Ready for work")
        self.assertIn("| - |", block)

    def test_blockers_are_linked(self):  # DASH-018
        block = _section(render(state(issues=[issue(41, blockers=[7])])), "Ready for work")
        self.assertIn(f"[#7](https://github.com/{REPO}/issues/7)", block)

    def test_several_blockers_are_comma_separated(self):  # DASH-018
        block = _section(render(state(issues=[issue(41, blockers=[7, 8])])), "Ready for work")
        stripped = block.replace(f"https://github.com/{REPO}", "")
        self.assertIn("[#7](/issues/7), [#8](/issues/8)", stripped)

    def test_no_blocker_renders_a_dash(self):  # DASH-018
        block = _section(render(state(issues=[issue(41)])), "Ready for work")
        self.assertIn("| - |", block)


if __name__ == "__main__":
    unittest.main()
