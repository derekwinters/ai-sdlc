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

FULL_SHA = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


def _git_ls_remote(version):  # pragma: no cover - the real network path
    """Ask GitHub what a version resolves to. Injected everywhere else."""
    import subprocess

    result = subprocess.run(
        ["git", "ls-remote", f"https://github.com/{SOURCE}",
         f"refs/tags/{version}", f"refs/tags/{version}^{{}}"],
        capture_output=True, text=True, check=False,
    )
    return result.stdout


def resolve_version(version, resolver=None):
    """The commit a version names.

    A SHA is returned as itself, so passing one costs no network at all.

    For an **annotated** tag `refs/tags/v4` is the tag *object* and only
    `refs/tags/v4^{}` is the commit. Pinning the tag object yields a reference
    that does not resolve — the failure that cost an afternoon in #64 — so the
    dereferenced form wins whenever it is present.
    """
    resolver = resolver or _git_ls_remote

    if FULL_SHA.match(version or ""):
        return version.lower()

    wanted = {f"refs/tags/{version}": None, f"refs/tags/{version}^{{}}": None}
    for line in (resolver(version) or "").splitlines():
        sha, _, ref = line.partition("\t")
        if ref.strip() in wanted:
            wanted[ref.strip()] = sha.strip()

    # The dereferenced commit first; the bare ref only when there is no tag
    # object to dereference (a lightweight tag).
    found = wanted[f"refs/tags/{version}^{{}}"] or wanted[f"refs/tags/{version}"]
    if not found:
        raise AdoptRefused(
            f"{version!r} does not resolve to a commit in {SOURCE}. Check the "
            f"version exists and has been released."
        )
    return found.lower()


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


def with_provenance(body, pin):
    """`body` carrying its provenance header, placed where the format allows.

    In front, except where the file opens with a `---` frontmatter block: a
    comment before that block stops it being frontmatter at all, and a skill
    whose frontmatter does not parse is a skill no agent ever loads. YAML
    comments *inside* the block are legal and ignored, and `_strip_provenance`
    removes the header from wherever it sits, so classification is unaffected.
    """
    header = provenance_header(pin[0] if isinstance(pin, (tuple, list)) else pin,
                               content_hash(body))
    if body.startswith("---\n"):
        opening, rest = body.split("\n", 1)
        return f"{opening}\n{header}{rest}"
    return header + body


def _read_provenance(text):
    match = _PROVENANCE.search(text or "")
    return (match.group("ref"), match.group("hash")) if match else (None, None)


def _strip_provenance(text):
    lines = (text or "").splitlines(keepends=True)
    kept = [line for line in lines if not line.startswith("# ai-sdlc:")
            and not line.startswith("# Managed by `adopt`")
            and not line.startswith("# being updated")]
    return "".join(kept)


def as_pin(pin, resolver=None):
    """Normalise to ``(version, sha)``.

    A caller may pass a version — the usual case, and what a human knows — or
    an already-resolved pair, which costs no network. Resolution happens once
    per command rather than once per file.
    """
    if isinstance(pin, (tuple, list)):
        version, sha = pin
        return (version, sha.lower())
    return (pin, resolve_version(pin, resolver=resolver))


def _pin_line(pin):
    """What the pin file records: the version and the commit.

    Both, so `verify` at the same version needs no network — and so a human
    reading the file can tell what is installed without resolving a SHA.
    """
    version, sha = pin
    return f"{version} {sha}\n"


def read_pin(root):
    """The recorded ``(version, sha)``, or None if nothing is recorded."""
    path = Path(root) / PIN_FILE
    if not path.is_file():
        return None
    parts = path.read_text().split()
    return (parts[0], parts[1]) if len(parts) >= 2 else None


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

    # Provenance records the *version*, which is what a human reads. A tag that
    # moved is still caught: the caller's body carries the SHA, so the content
    # would differ from what this version now says it should be.
    version = pin[0] if isinstance(pin, (tuple, list)) else pin
    return CURRENT if (ref == version and body == wanted) else STALE


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
    for candidate in (root / CONFIG_FILE, root / LEGACY_PATHS[0][0]):
        # The old path is read here for the same reason `plan` reads it: a
        # repository that has not migrated yet still has a stack, and telling
        # it to migrate is more use than telling it that it looks like nothing.
        if candidate.is_file():
            from lib.config import load

            return Detection(list(load(path=candidate).profiles),
                             {"repo-config.yml": True}, proposed=False)

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

        text = path.read_text()

        # Our own caller is not a second handler — it is the handler. Without
        # this, installing `pipeline` makes every later `apply` refuse, which
        # would make ADOPT-046 ("upgrading is the same operation") false for
        # exactly the repositories that took the most (#90).
        #
        # Keyed on provenance rather than on the file name: a consumer's
        # hand-written `dashboard.yml` must still collide, and it is the name
        # that would match.
        if _read_provenance(text)[0] is not None:
            continue

        for event in _triggers(text):
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
                 "detection", "migrations", "current")

    def __init__(self, creates, updates, conflicts, collisions, manual_tasks, detection,
                 migrations=()):
        self.creates = creates
        self.updates = updates
        self.conflicts = conflicts
        self.collisions = collisions
        self.manual_tasks = manual_tasks
        self.detection = detection
        self.migrations = list(migrations)
        self.current = not creates and not updates and not self.migrations

    def __repr__(self):
        return (
            f"<Plan +{len(self.creates)} ~{len(self.updates)} "
            f"!{len(self.conflicts)} collisions={len(self.collisions)}>"
        )


class Applied:
    __slots__ = ("written", "skipped", "manual_tasks", "migrated")

    def __init__(self, written, skipped, manual_tasks, migrated=()):
        self.written = written
        self.skipped = skipped
        self.manual_tasks = manual_tasks
        self.migrated = list(migrated)


#: ai-sdlc's own directory in a consuming repository.
#:
#: `.claude/` is a vendor namespace the way `.github/` and `.vscode/` are, and
#: none of what lives here is Claude Code's: a GitHub Actions job parsing
#: `capabilities`, `owners` and `fire.endpoint_secret` has nothing to do with
#: an AI coding assistant. Squatting there also took a dependency on somebody
#: else's namespace semantics for no gain at all.
#:
#: The one exception is `.claude/skills/`, which genuinely is Claude Code's
#: required path. Nothing under it moves.
CONFIG_DIR = ".ai-sdlc"

CONFIG_FILE = f"{CONFIG_DIR}/repo-config.yml"
PIN_FILE = f"{CONFIG_DIR}/ai-sdlc.pin"
HOUSE_RULES = f"{CONFIG_DIR}/house-rules.md"

#: The resolved state of this adoption, derived from `repo-config.yml` so it
#: cannot drift from it.
ADOPTION_PAGE = f"{CONFIG_DIR}/adoption.md"

#: The discovery surface, at the path Claude Code requires. A directory nothing
#: points at is a directory nobody reads.
SKILL_FILE = ".claude/skills/ai-sdlc/SKILL.md"

IMPORT_LINE = f"@{HOUSE_RULES}"

#: Where each managed file lived until 0.4.18, and where it goes.
#:
#: A half-migrated repository is worse than either location — CI would read one
#: path while `verify` checked the other — so these are moves, never fallbacks,
#: and the old location is removed rather than left as a trap for whoever edits
#: it next.
LEGACY_PATHS = (
    (".claude/repo-config.yml", CONFIG_FILE),
    (".claude/ai-sdlc.pin", PIN_FILE),
    (".claude/ai-sdlc/house-rules.md", HOUSE_RULES),
)

LEGACY_IMPORT_LINE = "@.claude/ai-sdlc/house-rules.md"

MANUAL_TASKS = (
    "Make the checks required: Settings → Branches → protect the default "
    "branch and require the checks this adds. An unrequired check is advisory.",
    "Do not add an `if:` that skips a required check — a skipped required "
    "check stays pending forever and blocks the merge it was meant to permit.",
)

#: The check names an action-based caller reports under.
#:
#: A reusable workflow reports as `<workflow> / <job>`; a job running an action
#: reports as `<job>`. So converting a caller *renames* its status check, and a
#: branch protection rule naming the old one waits for a check that will never
#: report again — the exact trap `MANUAL_TASKS` already warns about from the
#: other direction, arriving this time through an upgrade nobody thought was
#: risky.
RENAMED_CHECKS_TASK = (
    "Settings → Branches: the required check for each caller using an action "
    "is now named after its job alone — `closing-keyword`, not "
    "`closing-keyword / closing-keyword`. Update the protection rule, or it "
    "waits forever on a check that no longer reports."
)

#: The skills a repository with a given capability actually invokes.
#:
#: Only what something *in the consumer* runs: the analysis session reads
#: `triage-issue`, the dev agent reads `pipeline-dev`, and the rest are run by
#: hand or by an agent. Deliberately absent are the skills that only ever
#: execute from ai-sdlc's own tree inside an action or a workflow —
#: `pipeline-gatekeeper`, `pipeline-dashboard`, `label-sync`, `closing-keyword`,
#: `docs-gate`, `skills-update`. A copy of one of those in a consumer is a
#: second version nothing reads, which `DIST-012` would then keep at the pin
#: forever.
#:
#: `adopt` is absent for a different reason: it imports `lib.config`, which is
#: not part of the skill, so an installed copy cannot run at all. Upgrades are
#: run from an ai-sdlc checkout (#153).
INVOKED_LOCALLY = {
    "release": ("release-flow",),
    "pipeline": ("triage-issue", "pipeline-dev", "ci-watch", "milestone-ops"),
}


def _recommended_skills(config):
    """The skills this repository's capabilities suggest, in a stable order."""
    names = []
    for capability, skills in INVOKED_LOCALLY.items():
        if capability in config.capabilities:
            names.extend(name for name in skills if name not in names)
    return names


#: The comment that goes above the seeded list.
#:
#: It says three things a reader needs and cannot get from the key itself: what
#: the list does, that adoption wrote it once, and that it is now theirs to
#: change. Without the last sentence the key reads like something central that
#: will be re-asserted, and a repository that wanted to prune a name would
#: reasonably expect it back on the next upgrade.
SEED_COMMENT = (
    "# Which ai-sdlc skills this repository installs. `skills-update` opens a\n"
    "# pull request when one of them changes upstream, and a name removed here\n"
    "# is uninstalled on the next run.\n"
    "#\n"
    "# Seeded once by `adopt` from the capabilities above, and never touched\n"
    "# again: this list is yours. Add to it, prune it, or set it to `[]` to\n"
    "# install none — whatever is here is what a later adoption will honour.\n"
)


def _seed_block(names, newline="\n"):
    """The `skills:` key as it is appended to a repository's configuration."""
    body = SEED_COMMENT + "skills:\n" + "".join(f"  - {name}\n" for name in names)
    return body.replace("\n", newline) if newline != "\n" else body


def _seed_for(root, config):
    """The list adoption would seed, or `()` if it would seed none.

    Absent and empty are different answers. A repository that wrote
    `skills: []` has decided; writing a central answer over a decision the
    repository already made is the registry behaviour `DIST` refuses, and it is
    what got two previous fleet syncs disabled.
    """
    if "skills" in _raw_config(root):
        return ()
    return tuple(_recommended_skills(config))


def _write_seed(root, names):
    """Append the key. Every byte already in the file is left where it is.

    This is the one file a consuming repository authors itself, and it carries
    hand-written comments explaining every choice in it. Adoption may add a key
    to the end; it may not reformat, reorder, or rewrite a line of it — so this
    appends text rather than round-tripping the document through a parser.
    """
    path = Path(root) / CONFIG_FILE

    # `newline=""` on both, so line endings survive the round trip. The default
    # translates on read, which would quietly rewrite a CRLF file as LF — every
    # line changed, in a diff that claims to add one key.
    text = ""
    if path.is_file():
        with path.open(newline="") as handle:
            text = handle.read()

    newline = "\r\n" if "\r\n" in text else "\n"
    if text and not text.endswith(("\n", "\r")):
        text += newline

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        handle.write(text + newline + _seed_block(names, newline))


#: A permission `apply` cannot grant itself. Without it `skills-update` pushes
#: its branch and then fails at `gh pr create`, which leaves a branch and no
#: pull request — the confusing half of a failure rather than the loud one.
PULL_REQUEST_TASK = (
    "Settings → Actions → General → Workflow permissions: switch on 'Allow "
    "GitHub Actions to create and approve pull requests'. Without it "
    "`skills-update` pushes its branch and then cannot open the pull request."
)


def _manual_tasks(config):
    """The work no agent can do, for this repository's configuration."""
    tasks = list(MANUAL_TASKS)
    if _uses_an_action(config):
        tasks.append(RENAMED_CHECKS_TASK)
    if getattr(config, "skills", ()):
        tasks.append(PULL_REQUEST_TASK)
    return tasks


def _uses_an_action(config):
    """Whether this repository installs any caller that runs an action."""
    return "hygiene" in config.capabilities or "mkdocs" in getattr(config, "profiles", ())


def _files_for(config, pin):
    """Every file adoption owns, given a repository's configuration."""
    files = _installed(config, pin)

    # Installed whatever the capabilities are, because every adoption has a
    # resolved state and every adoption needs to be findable. A directory
    # nothing points at is a directory nobody reads.
    files[ADOPTION_PAGE] = _adoption_page(config, pin)
    files[SKILL_FILE] = _skill(pin)
    return files


def _installed(config, pin):
    """What the capabilities and profiles install.

    Separate from `_files_for` because the generated page lists these, and a
    page that listed itself would have to be generated from itself.
    """
    files = {}

    if "hygiene" in config.capabilities:
        files[HOUSE_RULES] = _house_rules()
        files[".github/workflows/closing-keyword.yml"] = _action_caller(
            "closing-keyword", "closing-keyword", pin,
            trigger=(
                "  pull_request:\n"
                "    types: [opened, edited, reopened, synchronize, labeled, unlabeled]\n"
            ),
        )

    if "labels" in config.capabilities:
        # The manifest the sync reads, not only the workflow that calls it. A
        # capability that installs half of itself fails when something runs,
        # long after the review that would have caught it (#75).
        files[".github/labels.core.yml"] = _core_labels()
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

    # Profiles add on top of capabilities. A profile that installs nothing is
    # indistinguishable from one that is working, which is how `mkdocs` shipped
    # fully specified and entirely inert (#81).
    if "mkdocs" in getattr(config, "profiles", ()):
        # The strict build. It builds and stops — the profile installs no
        # publisher, because publishing is repository-specific and a second one
        # underneath a working publisher is not a migration (#100).
        files[".github/workflows/docs-build.yml"] = _caller(
            "docs-build", "reusable-docs-build.yml", pin,
            trigger=(
                "  pull_request:\n"
                "  push:\n"
                "    branches: [main]\n"
            ),
        )

        files[".github/workflows/docs-gate.yml"] = _action_caller(
            "docs-gate", "docs-gate", pin,
            # `labeled` is load-bearing: the gate's verdict depends on the
            # pull request's labels as well as its files, so adding
            # `skip-docs` to an already-failed run has to start a fresh one.
            trigger=(
                "  pull_request:\n"
                "    types: [opened, synchronize, reopened, labeled, unlabeled]\n"
            ),
        )

    if "pipeline" in config.capabilities:
        # Four callers, one action. They differ in their trigger — which cannot
        # be centralised — and in the mode they ask for. Everything else that
        # used to differ between them was accidental.
        fire = _fire_inputs(config)

        files[".github/workflows/gatekeeper-comment.yml"] = _action_caller(
            "gatekeeper-comment", "gatekeeper", pin,
            trigger="  issue_comment:\n    types: [created]\n",
            concurrency=ISSUE_GROUP,
            # A pull request comment is not an issue comment for these purposes.
            condition="github.event.issue.pull_request == null",
            inputs="          mode: comment\n" + fire,
        )
        # Firing keyed on the label event rather than on the gatekeeper, so an
        # issue entering triage fires exactly once however the label got there
        # — including by hand, which used to fire nothing at all (#123).
        files[".github/workflows/triage.yml"] = _action_caller(
            "triage", "gatekeeper", pin,
            trigger="  issues:\n    types: [labeled]\n",
            concurrency=ISSUE_GROUP,
            condition=(
                "github.event.label.name == "
                f"'{config.labels['triage_queued']}'"
            ),
            inputs="          mode: labeled\n" + fire,
        )
        files[".github/workflows/gatekeeper-close.yml"] = _action_caller(
            "gatekeeper-close", "gatekeeper", pin,
            trigger="  issues:\n    types: [closed]\n",
            concurrency=ISSUE_GROUP,
            inputs="          mode: closed\n",
        )
        # The backstop for a lost poke (#136). Hourly rather than on the
        # dashboard's daily schedule: an issue whose session never answered is
        # dead until something notices, and a day of that is a day of nothing
        # happening.
        files[".github/workflows/gatekeeper-sweep.yml"] = _action_caller(
            "gatekeeper-sweep", "gatekeeper", pin,
            trigger="  schedule:\n    - cron: \"17 * * * *\"\n  workflow_dispatch:\n",
            concurrency=SWEEP_GROUP,
            # Thirty minutes, written here rather than defaulted in the action:
            # the value belongs where somebody can see and change it, and a
            # caller that omits it fails loudly (`GK-141`).
            #
            # No fire inputs. The sweep starts no sessions, so it has nothing
            # to authenticate to.
            inputs="          mode: sweep\n          stale-after: \"1800\"\n",
        )
        # The other half of report-rather-than-repair: nothing silently fixes
        # drift, so the board has to show it. A pipeline with no dashboard is
        # the half that repairs nothing without the half that reports it (#84).
        files[".github/workflows/dashboard.yml"] = _caller(
            "dashboard", "reusable-dashboard.yml", pin,
            trigger=(
                "  issues:\n"
                "    types: [opened, closed, reopened, labeled, unlabeled, milestoned,"
                " demilestoned]\n"
                "  schedule:\n"
                "    - cron: \"0 12 * * *\"\n"
                "  workflow_dispatch:\n"
            ),
        )

    # Driven by the list rather than by a capability: the list is what makes
    # the job useful, and a scheduled workflow with nothing to install is one
    # that runs every night to say so (#144).
    if getattr(config, "skills", ()):
        files[".github/workflows/skills-update.yml"] = _caller(
            "skills-update", "reusable-skills-update.yml", pin,
            # Daily. A run at an unchanged pin classifies everything as current
            # and opens nothing, so the cost of a quiet day is one green job —
            # and the day that matters is the one right after an upgrade merges.
            trigger="  schedule:\n    - cron: \"41 5 * * *\"\n  workflow_dispatch:\n",
            # No `skills:` input. The list lives in `repo-config.yml`, where the
            # schema keeps it honest; put in the caller it would be a hand-edit
            # to an `adopt`-managed file, which becomes a CONFLICT and stops the
            # file being upgraded ever again.
        )

    return files


def _house_rules():
    """The shared rules fragment, as installed.

    Read from this repository so there is one copy: a second copy embedded here
    would drift from the one the site publishes, and the drift would be
    invisible.
    """
    source = Path(__file__).resolve().parents[3] / "house-rules" / "house-rules.md"
    return source.read_text()


def _spec_pages():
    """Every specification page, as `(area, title, capability, path)`.

    Read from the pages themselves rather than from a table here. A table would
    be a second description of which capability owns what, and the whole reason
    the generated page exists is that a second copy of something rots.
    """
    directory = Path(__file__).resolve().parents[3] / "docs" / "spec"
    pages = []
    for path in sorted(directory.glob("*.md")):
        text = path.read_text()
        title = re.search(r"^#\s+Specification\s+—\s+(.+?)\s*\(`([A-Z]+)`\)", text, re.M)
        owner = re.search(r"belongs to the \*\*(\w+)\*\* capability", text)
        if title and owner:
            pages.append((title.group(2), title.group(1), owner.group(1),
                          f"docs/spec/{path.name}"))
    return pages


def _bullets(values, empty):
    return "\n".join(f"- `{value}`" for value in values) if values else empty


def _adoption_page(config, pin):
    """This repository's resolved adoption, derived from its configuration.

    **Nothing here explains how anything behaves.** That is what the links are
    for, and a restatement is the thing that rots: one consumer carried four
    label colours that disagreed with the manifest and 27 references to a
    pipeline state that no longer existed, both copies of things ai-sdlc
    already generates.
    """
    version, sha = pin
    tree = f"https://github.com/{SOURCE}/blob/{sha}"

    callers = sorted(
        path for path in _installed(config, pin)
        if path.startswith(".github/workflows/")
    )
    specs = [
        f"- [{title}]({tree}/{path}) — `{area}`"
        for area, title, capability, path in _spec_pages()
        if capability in config.capabilities
    ]
    # Only where the pipeline runs. A state-to-label table in a repository
    # with no pipeline is a table of vocabulary nothing here uses.
    mapped = getattr(config, "labels", {}) or {}
    labels = "\n".join(
        f"| `{state}` | `{mapped[state]}` |" for state in sorted(mapped)
    ) if "pipeline" in config.capabilities else ""

    if labels:
        labels = f"## Pipeline-state labels\n\n| State | Label |\n| --- | --- |\n{labels}\n\n"

    return f"""# ai-sdlc in this repository

Generated by `adopt` from `{CONFIG_FILE}`. It is this repository's *resolved*
state — what is installed, and at which version — and nothing else. How any of
it behaves is in the specification, linked below at the pinned commit.

Do not edit this file. Change `{CONFIG_FILE}` and run `adopt apply`.

## Pinned at

**{version}** — [`{sha[:12]}`](https://github.com/{SOURCE}/tree/{sha})

## Capabilities

{_bullets(config.capabilities, "- none")}

## Profiles

{_bullets(getattr(config, "profiles", ()), "- none")}

{labels}## Callers installed here

{_bullets(callers, "- none")}

## Skills installed here

{_bullets(getattr(config, "skills", ()), "- none, and `skills-update` is not installed")}

## The specification, at this pin

{chr(10).join(specs)}
- [House rules]({tree}/house-rules/house-rules.md) — imported by `CLAUDE.md`
"""


def _skill(pin):
    """The discovery surface, at the path Claude Code requires.

    The `description` is the load-bearing half: it is the only text a model
    sees when deciding whether to load anything, so it names the things an
    agent is about to touch — issues, labels, milestones, triage, releases —
    rather than offering context in the abstract.

    It is deliberately not the whole manual. The import in `CLAUDE.md` is
    always-on and cannot be missed; this is loaded on demand and can afford
    detail. The two are halves of one mechanism, not alternatives.
    """
    version, _ = pin
    return f"""---
name: ai-sdlc
description: >-
  How this repository's issues, labels, milestones, triage, pull-request gates
  and releases actually work. They are run by ai-sdlc, a shared pipeline this
  repository adopted, so the rules live outside this repository and the
  workflows here are thin callers. Use before changing a label or milestone,
  moving an issue between pipeline states, editing anything under
  `.github/workflows/`, cutting a release, or updating a document that
  describes any of those.
allowed-tools: Read, Grep, Glob, Bash
---

# ai-sdlc, in this repository

This repository has adopted [ai-sdlc](https://github.com/{SOURCE}), which owns its
pipeline, its label taxonomy, its release flow and its pull-request gates. It is
installed at **{version}**.

## Read these, in this order

| File | What it settles |
| --- | --- |
| [`{ADOPTION_PAGE}`](../../../{ADOPTION_PAGE}) | What is installed here, and at which version |
| [`{CONFIG_FILE}`](../../../{CONFIG_FILE}) | Everything this repository decides for itself |
| [`{HOUSE_RULES}`](../../../{HOUSE_RULES}) | The rules an agent works under, imported by `CLAUDE.md` |

`{ADOPTION_PAGE}` links every specification page that applies here, pinned to
the exact commit this repository runs. The specification is the answer to *how
does this behave*; nothing in this repository restates it, on purpose.

## What you may not hand-edit

Files carrying a `# ai-sdlc: …@… hash=…` header are written by `adopt`. Editing
one makes it a **conflict**: it is never overwritten, and it is never updated
again either, so a hand-edit silently freezes that file at the version it was
edited at. `adopt verify` reports them.

That covers the callers under `.github/workflows/`, `.github/labels.core.yml`,
the house rules, and this file.

## Changing something

- **A setting** — edit `{CONFIG_FILE}`. It is the only file here ai-sdlc reads
  and never writes.
- **A version** — run `adopt apply <version>` from an ai-sdlc checkout. Install
  and upgrade are one operation.
- **A rule, a gate, a workflow** — it is not in this repository. Open an issue
  in ai-sdlc.
"""


def _core_labels():
    """The shared taxonomy, as installed.

    Read from the skill so there is one copy: a second embedded here would
    drift from the one the sync applies, and the drift would be invisible —
    the same reason `_house_rules()` reads rather than embeds.
    """
    source = (Path(__file__).resolve().parents[2]
              / "labels" / "label-sync" / "labels.core.yml")
    return source.read_text()


#: What each reusable workflow needs the caller to grant. A called workflow
#: cannot be given more than its caller has, so a caller that grants too little
#: fails as `startup_failure` — no jobs, no logs, no annotation (#78).
#:
#: Read from the workflow files by test, so this cannot drift from what they
#: actually declare.
GRANTS = {
    "reusable-docs-build.yml": {"contents": "read"},
    "reusable-labels-sync.yml": {"contents": "read", "issues": "write"},
    "reusable-dashboard.yml": {"contents": "read", "issues": "write"},
    # The only workflow that commits. It writes to its own branch and opens a
    # pull request; it never pushes to the default branch.
    "reusable-skills-update.yml": {"contents": "write", "pull-requests": "write"},
}


#: What each action needs the caller to grant, for the same reason `GRANTS`
#: exists: a job that grants too little fails before any step runs.
ACTION_GRANTS = {
    "closing-keyword": {"contents": "read"},
    "docs-gate": {"contents": "read"},
    "gatekeeper": {"contents": "read", "issues": "write"},
}

#: How a caller serialises against others on the same issue.
#:
#: An action cannot declare `concurrency` — it is a workflow-level key — so the
#: caller carries it, which makes race prevention generated code rather than
#: central code. That is why it is written here, from one table, and asserted
#: by test rather than left to whoever writes a caller next.
#:
#: **Every issue-scoped mode shares one group.** `set_labels` is
#: `PUT /issues/{n}/labels` with the whole list — a replacement, not a patch —
#: so two runs on one issue read-modify-write the same set and one silently
#: loses, whichever label each meant to touch. Before #157 triage had a group
#: of its own, so labelling an issue by hand could fire triage while a
#: gatekeeper comment was mid-write on the same issue.
ISSUE_GROUP = (
    "  # Every writer on one issue serialises. `set_labels` replaces the whole\n"
    "  # label set rather than patching it, so two runs would read-modify-write\n"
    "  # the same list and one would silently lose.\n"
    "  group: gatekeeper-${{ github.event.issue.number }}\n"
    "  cancel-in-progress: false\n"
)

SWEEP_GROUP = (
    "  # One sweep at a time, and never cancelled: it reads the whole board,\n"
    "  # and a cancelled run leaves the labels it was moving half applied.\n"
    "  group: gatekeeper-sweep\n"
    "  cancel-in-progress: false\n"
)


def _action_caller(name, action, pin, trigger, concurrency=None, inputs="", condition=None):
    """A caller that `uses:` an action, and checks nothing out.

    The whole point of the shape. A reusable workflow has to fetch the code it
    runs, which meant every consumer's run cloned ai-sdlc into its own
    workspace — and `actions/checkout` empties the directory it writes into, so
    that clone was one naming collision away from replacing the consumer's own
    configuration and being read instead of it (#150).

    A path-based action is fetched by the runner into its own directory before
    any step executes. Nothing lands in the workspace, so there is nothing to
    collide with.

    There is also only **one** reference now, rather than a `uses:` and a `ref:`
    that had to agree. `ADOPT-060` existed to keep those two in step; with one,
    they cannot disagree.

    ``concurrency`` is written by the caller because an action cannot declare
    it — it is a workflow-level key. Where a group is what stops two runs
    racing, that makes it generated code rather than central code, which is why
    a test asserts every caller carrying one.
    """
    version, sha = pin
    grants = "".join(
        f"  {scope}: {level}\n" for scope, level in sorted(ACTION_GRANTS[action].items())
    )
    return (
        f"name: {name}\n\n"
        f"# A caller. The logic is in ai-sdlc; this exists because a trigger\n"
        f"# cannot be centralised — it must be declared in the repository it\n"
        f"# fires for.\n#\n"
        f"# Pinned to a commit rather than a tag: a tag can move, and this runs\n"
        f"# with this repository's token. Upgrade with `adopt apply <version>`,\n"
        f"# which rewrites both the SHA and the comment.\n#\n"
        f"# Nothing is checked out here. The action is fetched by the runner,\n"
        f"# outside this repository's workspace.\n\n"
        f"on:\n{trigger}\n"
        f"permissions:\n{grants}\n"
        + (f"concurrency:\n{concurrency}\n" if concurrency else "")
        + f"jobs:\n"
        f"  {name}:\n"
        # A job-level condition, where the trigger alone is too broad — a
        # comment on a pull request is not an issue comment for these purposes.
        + (f"    if: {condition}\n" if condition else "")
        + f"    runs-on: ubuntu-latest\n"
        f"    steps:\n"
        f"      - uses: {SOURCE}/.github/actions/{action}@{sha} # {version}\n"
        + (f"        with:\n{inputs}" if inputs else "")
    )


def _caller(name, reusable, pin, trigger, secrets=None, condition=None, inputs=""):
    """A thin caller. All logic lives in the reusable workflow.

    ``pin`` is ``(version, sha)``. The reference is the **SHA**, with the
    version as a trailing comment: a reusable workflow runs with the caller's
    token, on `issue_comment` and `issues`, inside the consumer's repository, so
    a mutable ref there is the same exposure as a mutable action. Publishing it
    ourselves says who could move the tag, not that it cannot move.

    `ref:` is that same SHA rather than the version, so the workflow and the
    code it checks out cannot come from two different commits.

    ``inputs`` is extra lines for the `with:` block, already indented. Used by
    the sweep, where the caller's trigger is what decides whether that run may
    requeue — the reusable workflow cannot tell a schedule from an event.

    ``secrets`` maps a called workflow's secret input to the name of a secret
    in the consumer's repository. Named rather than inherited: `secrets:
    inherit` is one line and hands the called workflow every secret the
    repository holds, which is the opposite of ADOPT-068. A repository naming
    none gets no block, and keeps a routine-less pipeline working (#118).
    """
    version, sha = pin
    grants = "".join(
        f"  {scope}: {level}\n"
        for scope, level in sorted(GRANTS[reusable].items())
    )
    return (
        f"name: {name}\n\n"
        f"# A caller. The logic is in ai-sdlc; this exists because a trigger\n"
        f"# cannot be centralised — it must be declared in the repository it\n"
        f"# fires for.\n#\n"
        f"# Pinned to a commit rather than a tag: a tag can move, and this runs\n"
        f"# with this repository's token. Upgrade with `adopt apply <version>`,\n"
        f"# which rewrites both the SHA and the comment.\n\n"
        f"on:\n{trigger}\n"
        f"permissions:\n{grants}\n"
        f"jobs:\n"
        f"  {name}:\n"
        # A job-level condition, where the trigger alone is too broad — the
        # `labeled` event fires for every label, and only one of them means
        # triage. A workflow condition cannot read configuration, so the
        # configured name is written in here.
        + (f"    if: {condition}\n" if condition else "")
        + f"    uses: {SOURCE}/.github/workflows/{reusable}@{sha} # {version}\n"
        + f"    with:\n"
        + f"      ref: {sha}\n"
        + inputs
        + _secrets(secrets)
    )


def _secrets(secrets):
    """The `secrets:` block, or nothing at all.

    The value never passes through here — only the *name* of a secret, which
    GitHub resolves at run time in the consumer's own repository.
    """
    if not secrets:
        return ""
    lines = "".join(
        f"      {given}: ${{{{ secrets.{named} }}}}\n"
        for given, named in sorted(secrets.items())
    )
    return f"    secrets:\n{lines}"


def _fire_inputs(config):
    """The analysis routine's endpoint and token, as action inputs.

    An action takes `with:` where a reusable workflow took `secrets:`. The
    *value* still never appears — only `${{ secrets.NAME }}`, which GitHub
    resolves in the consumer's own repository and masks in the log. A
    repository naming neither gets neither, and a pipeline with no routine
    keeps working (`GK-119`).
    """
    fire = getattr(config, "fire", None)
    named = (
        ("fire-endpoint", getattr(fire, "endpoint_secret", None)),
        ("fire-token", getattr(fire, "token_secret", None)),
    )
    return "".join(
        f"          {given}: ${{{{ secrets.{name} }}}}\n" for given, name in named if name
    )


def _fire_secrets(config):
    """Map the called workflow's secret inputs to the repository's own names."""
    fire = getattr(config, "fire", None)
    named = {
        "fire_endpoint": getattr(fire, "endpoint_secret", None),
        "fire_token": getattr(fire, "token_secret", None),
    }
    return {given: name for given, name in named.items() if name}


# ---------------------------------------------------------------- migration


def migration(root):
    """The moves this repository still needs, as `(old, new)`. Writes nothing.

    Refuses outright when a path exists in both places. That is not a state to
    guess at: one of the two is what CI reads and the other is what somebody
    will edit next, and nothing here can tell which is which.
    """
    root = Path(root)
    moves, both = [], []

    for old, new in LEGACY_PATHS:
        if not (root / old).is_file():
            continue
        if (root / new).is_file():
            both.append(f"{old} and {new}")
        else:
            moves.append((old, new))

    if both:
        raise AdoptRefused(
            "these files exist in both the old and the new location: "
            + "; ".join(both)
            + ". One of them is what CI reads and the other is what somebody "
            "will edit next, and nothing here can tell which is which. Delete "
            "whichever is stale, then run this again."
        )

    return moves


def migrate(root):
    """Move a repository out of `.claude/`. Returns what it moved.

    `repo-config.yml` is authored by the repository, not written by this tool —
    a consumer's copy carries hand-written comments explaining every choice — so
    it moves **byte-for-byte** and is never rewritten. The old location is
    removed rather than left behind: a stale copy alongside a live one is a
    trap that gets edited eventually.

    Idempotent, because it is driven by what is actually there: a repository
    with nothing left in the old location has nothing to move.
    """
    root = Path(root)
    moved = []

    for old, new in migration(root):
        source, target = root / old, root / new
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        source.unlink()
        moved.append((old, new))

    # The directory that held the house rules, and nothing else. Removed only
    # when empty — anything a consumer put in there is theirs.
    stale = root / ".claude" / "ai-sdlc"
    if stale.is_dir() and not any(stale.iterdir()):
        stale.rmdir()

    if _rewrite_import(root):
        moved.append((LEGACY_IMPORT_LINE, IMPORT_LINE))

    return moved


def _rewrite_import(root):
    """Point the `CLAUDE.md` import at the moved file.

    The one edit adoption makes to a file it did not write, and it is to the
    single line adoption itself put there. Leaving it would dangle: the import
    would name a file that no longer exists, and the rules would silently stop
    reaching the agent.
    """
    path = Path(root) / "CLAUDE.md"
    if not path.is_file():
        return False

    text = path.read_text()
    if LEGACY_IMPORT_LINE not in text:
        return False

    path.write_text(text.replace(LEGACY_IMPORT_LINE, IMPORT_LINE))
    return True


def _raw_config(root):
    """The configuration as written, before defaults are applied.

    `lib.config` defaults `skills` to the empty list, which loses the one
    distinction that matters here: a repository that never answered the
    question versus one that answered "none". Advising the second would be the
    registry behaviour `DIST` refuses.
    """
    from lib.yaml_lite import parse

    root = Path(root)
    for candidate in (root / CONFIG_FILE, root / LEGACY_PATHS[0][0]):
        if candidate.is_file():
            try:
                return parse(candidate.read_text()) or {}
            except Exception:  # noqa: BLE001 - a bad file is reported by the loader
                return {}
    return {}


def _load_config(root):
    """The configuration, from wherever this repository currently keeps it.

    `plan` is read-only and has to work on a repository that has not migrated
    yet — telling it to migrate is most of what the plan is for. Everywhere
    else `migrate` has already run, so this finds the new path.
    """
    from lib.config import load

    legacy = Path(root) / LEGACY_PATHS[0][0]
    if not (Path(root) / CONFIG_FILE).is_file() and legacy.is_file():
        return load(path=legacy)
    return load(root=root)


def plan(root, pin, acknowledged=(), resolver=None):
    """What adoption would do. Writes nothing."""
    root = Path(root)
    pin = as_pin(pin, resolver=resolver)
    pending = migration(root)
    config = _load_config(root)

    # The seed is decided before the file list, not after, so one adoption both
    # writes the key and installs what the key then asks for. Deciding it
    # afterwards would leave `skills-update.yml` to a second run nobody knew to
    # make.
    seed = _seed_for(root, config)
    if seed:
        config.skills = list(seed)

    wanted = _files_for(config, pin)

    # A file about to be moved is classified where it currently *is*. Reading
    # the destination would report an upgrade of an existing house-rules file
    # as a fresh create, which reads as "this repository had none" — and it is
    # the only line in the plan a reviewer would use to check that.
    moving = {new: old for old, new in pending}

    creates, updates, conflicts = [], [], []
    for path, body in sorted(wanted.items()):
        state = classify(root, moving.get(path, path), body, pin)
        if state == ABSENT:
            creates.append(path)
        elif state == STALE:
            updates.append(path)
        elif state == CONFLICT:
            conflicts.append(path)

    if seed:
        (updates if (root / CONFIG_FILE).is_file() else creates).append(CONFIG_FILE)

    recorded = root / moving.get(PIN_FILE, PIN_FILE)
    if recorded.is_file():
        if recorded.read_text().strip() != _pin_line(pin).strip():
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
        manual_tasks=_manual_tasks(config),
        detection=detect(root),
        migrations=pending,
    )


def _claimed_by(config):
    claimed = []
    if "pipeline" in config.capabilities:
        claimed += ["issue_comment", "issues"]
    return claimed


def apply(root, pin, acknowledged=(), resolver=None):
    """Make the changes. Refuses on an unacknowledged trigger collision."""
    root = Path(root)
    pin = as_pin(pin, resolver=resolver)
    proposed = plan(root, pin, acknowledged=acknowledged)

    # Before anything is written, so the rest of this run reads and writes one
    # location. A half-migrated repository is worse than either.
    migrated = migrate(root)

    if proposed.collisions:
        named = ", ".join(f"{c.workflow} (on {c.event})" for c in proposed.collisions)
        raise AdoptRefused(
            f"these workflows already handle events this adoption claims: {named}. "
            f"Two handlers on one event race, and both write. Disable them in the "
            f"same change, or acknowledge them deliberately."
        )

    config = _load_config(root)
    written, skipped = [], []

    # Before the file list is built, for the reason `plan` gives.
    seed = _seed_for(root, config)
    if seed:
        _write_seed(root, seed)
        config.skills = list(seed)
        written.append(CONFIG_FILE)

    wanted = _files_for(config, pin)

    for path, body in sorted(wanted.items()):
        state = classify(root, path, body, pin)
        if state in (ABSENT, STALE):
            full = root / path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(with_provenance(body, pin))
            written.append(path)
        elif state == CONFLICT:
            skipped.append(path)

    pin_file = root / PIN_FILE
    if not pin_file.is_file() or pin_file.read_text().strip() != _pin_line(pin).strip():
        pin_file.parent.mkdir(parents=True, exist_ok=True)
        pin_file.write_text(_pin_line(pin))
        written.append(PIN_FILE)

    if _add_import(root):
        written.append("CLAUDE.md")

    tasks = _manual_tasks(config)
    if "pipeline" in config.capabilities and not config.dashboard_issue:
        tasks.append("Create a dashboard issue and set `dashboard_issue` in the config.")

    return Applied(written=sorted(written), skipped=sorted(skipped), manual_tasks=tasks,
                   migrated=migrated)


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


def verify(root, pin, resolver=None):
    """Whether the repository still matches its pin. Writes nothing.

    Reports rather than repairs, for the same reason everything else here does:
    a repository keeping its own version of a file should be visibly
    non-standard, not silently corrected back.
    """
    root = Path(root)
    pin = as_pin(pin, resolver=resolver)
    problems = []

    try:
        config = _load_config(root)
    except Exception as error:  # noqa: BLE001 - a bad config is the problem
        return Verified([f"the configuration could not be read: {error}"])

    for old, new in migration(root):
        problems.append(
            f"{old} has not been migrated to {new}; run `adopt apply` to move it"
        )

    recorded = (root / PIN_FILE).read_text().strip() if (root / PIN_FILE).is_file() else None
    if recorded != _pin_line(pin).strip():
        problems.append(
            f"installed at {recorded or '(no pin recorded)'}, current is "
            f"{_pin_line(pin).strip()}"
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
