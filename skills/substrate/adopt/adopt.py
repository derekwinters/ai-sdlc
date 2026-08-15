#!/usr/bin/env python3
"""Join a repository to ai-sdlc, and move it between versions afterwards.

Per-repository and run in place. There is deliberately no fleet operation: a
single command that changed eleven repositories at once would be exactly the
"how many changes did that just make" problem this project exists to avoid.

Three subcommands. `plan` is read-only and safe to run on a repository nobody
has decided about. `apply` writes, to a branch, and never replaces content it
did not create. `verify` reports whether a repository still matches its pin.

The rule that does the most work is provenance: a file this tool wrote carries
a header naming the ref and the content hash. That is how "we may update this"
is distinguished from "somebody else's file", and how a locally-edited managed
file is distinguished from a merely outdated one — an edit is a conflict, not
something to overwrite.

Specification: docs/spec/adopt.md (`ADOPT`).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

SOURCE = "derekwinters/ai-sdlc"

ABSENT = "absent"
CURRENT = "current"
STALE = "stale"
CONFLICT = "conflict"

#: Events where the pipeline is the sole writer. A second handler on one of
#: these races with ours, and both write.
#:
#: `pull_request` is deliberately absent. Almost every repository has a test or
#: lint workflow on it; they coexist happily, and flagging them all would train
#: the owner to acknowledge collisions without reading them — which defeats the
#: mechanism far more thoroughly than missing one would.
CLAIMED_EVENTS = ("issue_comment", "issues")

#: Marker files, in the order they are checked.
MARKERS = (
    ("unity", "ProjectSettings/ProjectVersion.txt"),
    ("mkdocs", "mkdocs.yml"),
    ("python", "pyproject.toml"),
    ("node", "package.json"),
    ("kotlin", "build.gradle.kts"),
    ("kotlin", "build.gradle"),
)

_PROVENANCE = re.compile(
    r"^#\s*ai-sdlc:\s*(?P<source>\S+)@(?P<ref>\S+)\s+hash=(?P<hash>\S+)\s*$",
    re.MULTILINE,
)


# --------------------------------------------------------------- provenance


def content_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def provenance_header(ref, digest):
    """The header identifying a file as ours, and which version wrote it."""
    return (
        f"# ai-sdlc: {SOURCE}@{ref} hash={digest}\n"
        f"# Managed by `adopt`. Local edits are preserved but stop this file\n"
        f"# being updated — `adopt verify` will report it.\n"
    )


def _read_provenance(text):
    match = _PROVENANCE.search(text or "")
    return (match.group("ref"), match.group("hash")) if match else (None, None)


def _strip_provenance(text):
    lines = (text or "").splitlines(keepends=True)
    kept = [line for line in lines if not line.startswith("# ai-sdlc:")
            and not line.startswith("# Managed by `adopt`")
            and not line.startswith("# being updated")]
    return "".join(kept)


def classify(root, path, wanted, pin):
    """What may be done with this path."""
    full = Path(root) / path
    if not full.is_file():
        return ABSENT

    text = full.read_text()
    ref, digest = _read_provenance(text)
    if ref is None:
        # Somebody else's file. Never ours to overwrite, whatever it contains.
        return CONFLICT

    body = _strip_provenance(text)
    if content_hash(body) != digest:
        # We wrote it, and it has been edited since. Overwriting would discard
        # the edit silently, which is worse than refusing.
        return CONFLICT

    return CURRENT if (ref == pin and body == wanted) else STALE


# ---------------------------------------------------------------- detection


class Detection:
    __slots__ = ("profiles", "evidence", "proposed", "undetectable")

    def __init__(self, profiles, evidence, proposed=True):
        self.profiles = profiles
        self.evidence = evidence
        self.proposed = proposed
        self.undetectable = proposed and not profiles


def detect(root):
    """Which profiles a repository looks like it wants.

    Configuration wins outright: a repository that has said what it is does not
    get second-guessed by a marker file.
    """
    root = Path(root)
    config = root / ".claude" / "repo-config.yml"
    if config.is_file():
        from lib.config import load

        return Detection(list(load(path=config).profiles), {"repo-config.yml": True},
                         proposed=False)

    profiles, evidence = [], {}
    for profile, marker in MARKERS:
        if (root / marker).is_file():
            evidence[marker] = profile
            if profile not in profiles:
                profiles.append(profile)

    return Detection(sorted(profiles), evidence)


# --------------------------------------------------------------- collisions


class Collision:
    __slots__ = ("workflow", "event")

    def __init__(self, workflow, event):
        self.workflow = workflow
        self.event = event

    def __repr__(self):
        return f"<Collision {self.workflow} on {self.event}>"


def collisions(root, claims=CLAIMED_EVENTS, acknowledged=()):
    """Existing workflows listening on an event the adoption claims.

    Compared by trigger rather than by file name. A collision between
    differently-named workflows is precisely the one a file comparison misses,
    and it is the dangerous one: two handlers on one event race, and both write.
    """
    workflows = Path(root) / ".github" / "workflows"
    if not workflows.is_dir():
        return []

    found = []
    acknowledged = set(acknowledged)

    for path in sorted(workflows.glob("*.yml")) + sorted(workflows.glob("*.yaml")):
        if path.name in acknowledged:
            continue
        for event in _triggers(path.read_text()):
            if event in claims:
                found.append(Collision(path.name, event))
                break

    return found


def _triggers(text):
    """Event names under a workflow's `on:` block."""
    events, in_on = set(), False
    for line in text.splitlines():
        if re.match(r"^on:\s*$", line):
            in_on = True
            continue
        if re.match(r"^on:\s*\S", line):
            # Inline form: `on: [issue_comment]` or `on: push`
            events.update(re.findall(r"[A-Za-z_]+", line.split(":", 1)[1]))
            continue
        if in_on:
            if line and not line[0].isspace():
                break
            match = re.match(r"^  ([A-Za-z_]+):", line)
            if match:
                events.add(match.group(1))
    return events


# --------------------------------------------------------------- the plan


class AdoptRefused(RuntimeError):
    """A change that would race with something already running."""


class Plan:
    __slots__ = ("creates", "updates", "conflicts", "collisions", "manual_tasks",
                 "detection", "current")

    def __init__(self, creates, updates, conflicts, collisions, manual_tasks, detection):
        self.creates = creates
        self.updates = updates
        self.conflicts = conflicts
        self.collisions = collisions
        self.manual_tasks = manual_tasks
        self.detection = detection
        self.current = not creates and not updates

    def __repr__(self):
        return (
            f"<Plan +{len(self.creates)} ~{len(self.updates)} "
            f"!{len(self.conflicts)} collisions={len(self.collisions)}>"
        )


class Applied:
    __slots__ = ("written", "skipped", "manual_tasks")

    def __init__(self, written, skipped, manual_tasks):
        self.written = written
        self.skipped = skipped
        self.manual_tasks = manual_tasks


PIN_FILE = ".claude/ai-sdlc.pin"
IMPORT_LINE = "@.claude/ai-sdlc/house-rules.md"

MANUAL_TASKS = (
    "Make the checks required: Settings → Branches → protect the default "
    "branch and require the checks this adds. An unrequired check is advisory.",
    "Do not add an `if:` that skips a required check — a skipped required "
    "check stays pending forever and blocks the merge it was meant to permit.",
)


def _files_for(config, pin):
    """The files adoption owns, given a repository's configuration."""
    files = {}

    if "hygiene" in config.capabilities:
        files[".github/workflows/closing-keyword.yml"] = _caller(
            "closing-keyword", "reusable-closing-keyword.yml", pin,
            trigger=(
                "  pull_request:\n"
                "    types: [opened, edited, reopened, synchronize, labeled, unlabeled]\n"
            ),
        )

    if "labels" in config.capabilities:
        files[".github/workflows/labels-sync.yml"] = _caller(
            "labels-sync", "reusable-labels-sync.yml", pin,
            trigger=(
                "  push:\n"
                "    branches: [main]\n"
                "    paths:\n"
                "      - .github/labels.core.yml\n"
                "      - .github/labels.repo.yml\n"
                "  workflow_dispatch:\n"
            ),
        )

    if "pipeline" in config.capabilities:
        files[".github/workflows/gatekeeper-comment.yml"] = _caller(
            "gatekeeper-comment", "reusable-gatekeeper-comment.yml", pin,
            trigger="  issue_comment:\n    types: [created]\n",
        )
        files[".github/workflows/gatekeeper-close.yml"] = _caller(
            "gatekeeper-close", "reusable-gatekeeper-close.yml", pin,
            trigger="  issues:\n    types: [closed]\n",
        )

    return files


def _caller(name, reusable, pin, trigger):
    """A thin caller. All logic lives in the reusable workflow."""
    return (
        f"name: {name}\n\n"
        f"# A caller. The logic is in ai-sdlc; this exists because a trigger\n"
        f"# cannot be centralised — it must be declared in the repository it\n"
        f"# fires for.\n\n"
        f"on:\n{trigger}\n"
        f"permissions:\n  contents: read\n\n"
        f"jobs:\n"
        f"  {name}:\n"
        f"    uses: {SOURCE}/.github/workflows/{reusable}@{pin}\n"
        f"    with:\n"
        f"      ref: {pin}\n"
    )


def _load_config(root):
    from lib.config import load

    return load(root=root)


def plan(root, pin, acknowledged=()):
    """What adoption would do. Writes nothing."""
    root = Path(root)
    config = _load_config(root)
    wanted = _files_for(config, pin)

    creates, updates, conflicts = [], [], []
    for path, body in sorted(wanted.items()):
        state = classify(root, path, body, pin)
        if state == ABSENT:
            creates.append(path)
        elif state == STALE:
            updates.append(path)
        elif state == CONFLICT:
            conflicts.append(path)

    if (root / PIN_FILE).is_file():
        if (root / PIN_FILE).read_text().strip() != pin:
            updates.append(PIN_FILE)
    else:
        creates.append(PIN_FILE)

    claimed = _claimed_by(config)
    found = collisions(root, claims=claimed, acknowledged=acknowledged) if claimed else []

    return Plan(
        creates=sorted(creates),
        updates=sorted(updates),
        conflicts=sorted(conflicts),
        collisions=found,
        manual_tasks=list(MANUAL_TASKS),
        detection=detect(root),
    )


def _claimed_by(config):
    claimed = []
    if "pipeline" in config.capabilities:
        claimed += ["issue_comment", "issues"]
    return claimed


def apply(root, pin, acknowledged=()):
    """Make the changes. Refuses on an unacknowledged trigger collision."""
    root = Path(root)
    proposed = plan(root, pin, acknowledged=acknowledged)

    if proposed.collisions:
        named = ", ".join(f"{c.workflow} (on {c.event})" for c in proposed.collisions)
        raise AdoptRefused(
            f"these workflows already handle events this adoption claims: {named}. "
            f"Two handlers on one event race, and both write. Disable them in the "
            f"same change, or acknowledge them deliberately."
        )

    config = _load_config(root)
    wanted = _files_for(config, pin)
    written, skipped = [], []

    for path, body in sorted(wanted.items()):
        state = classify(root, path, body, pin)
        if state in (ABSENT, STALE):
            full = root / path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(provenance_header(pin, content_hash(body)) + body)
            written.append(path)
        elif state == CONFLICT:
            skipped.append(path)

    pin_file = root / PIN_FILE
    if not pin_file.is_file() or pin_file.read_text().strip() != pin:
        pin_file.parent.mkdir(parents=True, exist_ok=True)
        pin_file.write_text(pin + "\n")
        written.append(PIN_FILE)

    if _add_import(root):
        written.append("CLAUDE.md")

    tasks = list(MANUAL_TASKS)
    if "pipeline" in config.capabilities and not config.dashboard_issue:
        tasks.append("Create a dashboard issue and set `dashboard_issue` in the config.")

    return Applied(written=sorted(written), skipped=sorted(skipped), manual_tasks=tasks)


def _add_import(root):
    """Insert the shared-rules import. Never rewrites the file.

    A repository's CLAUDE.md is hand-written and often the most carefully
    considered file it has. Adoption appends one line to it and nothing else.
    """
    path = Path(root) / "CLAUDE.md"
    if not path.is_file():
        return False

    text = path.read_text()
    if IMPORT_LINE in text:
        return False

    path.write_text(text.rstrip() + f"\n\n{IMPORT_LINE}\n")
    return True


# ------------------------------------------------------------- verification


class Verified:
    __slots__ = ("ok", "problems")

    def __init__(self, problems):
        self.problems = problems
        self.ok = not problems


def verify(root, pin):
    """Whether the repository still matches its pin. Writes nothing.

    Reports rather than repairs, for the same reason everything else here does:
    a repository keeping its own version of a file should be visibly
    non-standard, not silently corrected back.
    """
    root = Path(root)
    problems = []

    try:
        config = _load_config(root)
    except Exception as error:  # noqa: BLE001 - a bad config is the problem
        return Verified([f"the configuration could not be read: {error}"])

    recorded = (root / PIN_FILE).read_text().strip() if (root / PIN_FILE).is_file() else None
    if recorded != pin:
        problems.append(
            f"installed at {recorded or '(no pin recorded)'}, current is {pin}"
        )

    for path, body in sorted(_files_for(config, pin).items()):
        state = classify(root, path, body, pin)
        if state == ABSENT:
            problems.append(f"{path} is missing")
        elif state == CONFLICT:
            problems.append(
                f"{path} is not managed by adopt — either edited locally or "
                f"written by hand; it will not be updated"
            )

    return Verified(problems)
