#!/usr/bin/env python3
"""Check that every requirement is verified by something.

A specification nobody verifies is a wish. This validator is what makes the
difference between "the spec says" and "the spec is true": a requirement no
test names fails the build, and a test naming a requirement that does not exist
fails it too — because that is either a typo or a requirement someone deleted
without noticing what depended on it.

Specification: docs/spec/validators.md (`VAL`), §1–2.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

#: A declaration, not a mention: "- **AREA-NNN** text".
DECLARATION = re.compile(r"^\s*[-*]\s+\*\*([A-Z]{2,10})-(\d{3})\*\*\s*(.*)$")

#: Any citation of an identifier, used when scanning tests.
CITATION = re.compile(r"\b([A-Z]{2,10})-(\d{3})\b")

#: The page's area, from its title: "# Specification — Thing (`AREA`)".
PAGE_AREA = re.compile(r"^#\s+.*\(`([A-Z]{2,10})`\)")

MANUAL = re.compile(r"\*\(manual:\s*(?P<reason>[^)]*)\)\*")
MANUAL_BARE = re.compile(r"\*\(manual\s*\)\*")

#: A page specified ahead of its implementation. Writing the specification
#: first is the process working; the marker names the issue that closes the
#: gap, so the debt is explicit and dated rather than silent.
PLANNED = re.compile(r">\s*\*\*Status\s*—\s*planned\s*\(#(?P<issue>\d+)\)\.?\*\*")
PLANNED_BARE = re.compile(r">\s*\*\*Status\s*—\s*planned[^(]*\*\*")


class Requirement:
    __slots__ = ("identifier", "page", "manual", "reason")

    def __init__(self, identifier, page, manual=False, reason=""):
        self.identifier = identifier
        self.page = page
        self.manual = manual
        self.reason = reason

    def __repr__(self):
        return f"<{self.identifier} {self.page}>"


class Summary:
    __slots__ = ("total", "covered", "manual", "planned")

    def __init__(self, total, covered, manual, planned=0):
        self.total = total
        self.covered = covered
        self.manual = manual
        self.planned = planned


def spec_pages(root):
    directory = Path(root) / "docs" / "spec"
    return sorted(directory.glob("*.md")) if directory.is_dir() else []


def _planned_pages(root):
    """Pages exempt from coverage, mapped to the issue that will implement them."""
    planned = {}
    for page in spec_pages(root):
        text = page.read_text()
        match = PLANNED.search(text)
        if match:
            planned[str(page.relative_to(root))] = match.group("issue")
        elif PLANNED_BARE.search(text):
            planned[str(page.relative_to(root))] = None
    return planned


def collect_requirements(root):
    """Every requirement declared across the specification pages."""
    found = []
    for page in spec_pages(root):
        relative = str(page.relative_to(root))
        for line in page.read_text().splitlines():
            match = DECLARATION.match(line)
            if not match:
                continue
            area, number, text = match.groups()
            manual_match = MANUAL.search(text)
            bare = MANUAL_BARE.search(text)
            found.append(
                Requirement(
                    identifier=f"{area}-{number}",
                    page=relative,
                    manual=bool(manual_match) or bool(bare),
                    reason=(manual_match.group("reason").strip() if manual_match else ""),
                )
            )
    return found


def _cited_identifiers(root):
    cited = set()
    tests = Path(root) / "tests"
    if not tests.is_dir():
        return cited
    for path in sorted(tests.rglob("*.py")):
        for area, number in CITATION.findall(path.read_text()):
            cited.add(f"{area}-{number}")
    return cited


def validate_specs(root):
    """Return every problem found. An empty list means consistent."""
    root = Path(root)
    problems = []
    requirements = collect_requirements(root)

    seen = {}
    for requirement in requirements:
        if requirement.identifier in seen:
            problems.append(
                f"{requirement.identifier} is declared twice: "
                f"{seen[requirement.identifier]} and {requirement.page}"
            )
        else:
            seen[requirement.identifier] = requirement.page

    for page in spec_pages(root):
        relative = str(page.relative_to(root))
        text = page.read_text()
        first = text.splitlines()[0] if text.splitlines() else ""
        area_match = PAGE_AREA.match(first)
        if not area_match:
            problems.append(
                f"{relative}: the page does not declare its area in the title, "
                "expected '# Specification — Name (`AREA`)'"
            )
            continue
        area = area_match.group(1)
        for requirement in requirements:
            if requirement.page == relative and not requirement.identifier.startswith(area + "-"):
                problems.append(
                    f"{relative}: {requirement.identifier} does not belong to this page's "
                    f"area {area!r}"
                )

    cited = _cited_identifiers(root)
    declared = {requirement.identifier for requirement in requirements}
    planned = _planned_pages(root)

    for page, issue in sorted(planned.items()):
        if issue is None:
            problems.append(
                f"{page}: the planned marker names no issue; an exemption with no reference "
                "is one nobody comes back to"
            )

    for requirement in requirements:
        if requirement.page in planned:
            continue
        if requirement.manual:
            if not requirement.reason:
                problems.append(
                    f"{requirement.identifier} ({requirement.page}) is marked manual with no "
                    "reason; an exemption without a justification is an unexplained gap"
                )
            continue
        if requirement.identifier not in cited:
            problems.append(
                f"{requirement.identifier} ({requirement.page}) is not referenced by any test"
            )

    # An orphan is a citation in an area this repository declares — GK-999 when
    # GK exists is a typo or a deleted requirement, and worth reporting. An
    # identifier in an unknown area (a fixture, another project's vocabulary) is
    # not this validator's business, and treating it as one produces noise that
    # trains people to ignore the output.
    areas = {identifier.split("-")[0] for identifier in declared}
    for identifier in sorted(cited - declared):
        if identifier.split("-")[0] in areas:
            problems.append(
                f"a test cites {identifier}, which no specification declares"
            )

    return problems


def summarise(root):
    requirements = collect_requirements(root)
    cited = _cited_identifiers(root)
    planned_pages = _planned_pages(root)

    planned = sum(1 for r in requirements if r.page in planned_pages)
    live = [r for r in requirements if r.page not in planned_pages]
    manual = sum(1 for r in live if r.manual)
    covered = sum(1 for r in live if not r.manual and r.identifier in cited)
    return Summary(
        total=len(requirements), covered=covered, manual=manual, planned=planned
    )


def main(root="."):
    problems = validate_specs(root)
    summary = summarise(root)
    for problem in problems:
        print(f"  - {problem}", file=sys.stderr)
    if problems:
        print(f"specs: {len(problems)} problem(s)", file=sys.stderr)
        return 1
    print(
        f"specs: {summary.total} requirements — {summary.covered} covered by tests, "
        f"{summary.manual} manual, {summary.planned} planned"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
