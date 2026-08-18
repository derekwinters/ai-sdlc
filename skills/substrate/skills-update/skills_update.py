#!/usr/bin/env python3
"""Keep a repository's installed ai-sdlc skills at the version it pins.

`docs/design.md` §7 settled the mechanism — `gh skill install`, pinned, with
provenance in each installed skill's frontmatter — and then nothing ran it. This
is the thing that runs it: it installs what `skills:` names and is missing, and
reinstalls what has fallen behind the pin.

**The one rule that matters.** A scheduled skill sync has been built twice in
this fleet and disabled twice, both times because it reverted work somebody had
done in a consumer. `gh skill install` overwrites a locally-modified skill with
the original content — that is documented behaviour, not a bug — and moving a
pinned skill to a new version *is* a reinstall. So a skill is compared against
ai-sdlc's own copy before anything is run, and one that differs is reported and
left alone. Never overwritten, never quietly.

The comparison is against ai-sdlc's copy **at the ref the installation
records**, not at the pin. Comparing against the pin would call every merely
outdated skill modified, and the job would never do anything at all.

Specification: docs/spec/distribution.md (`DIST`).
"""

from __future__ import annotations

from pathlib import Path

SOURCE = "derekwinters/ai-sdlc"

#: Where `gh skill install --agent claude-code --scope project` puts things.
INSTALL_ROOT = Path(".claude") / "skills"

#: The frontmatter keys `gh skill` injects on install. They are absent from
#: ai-sdlc's own copy, so comparing them would make every installed skill look
#: modified — and nothing would ever be updated again.
PROVENANCE_KEYS = ("github-repo", "github-ref", "github-path", "github-tree-sha")

#: Written by running a skill, not by editing one.
IGNORED = ("__pycache__",)

ABSENT = "absent"
CURRENT = "current"
STALE = "stale"
UNMANAGED = "unmanaged"
MODIFIED = "modified"
UNKNOWN = "unknown"
UNVERIFIABLE = "unverifiable"

#: The states that mean "do not write here". Everything not in this set is
#: either current or something to install.
SKIPPED_STATES = (UNMANAGED, MODIFIED, UNKNOWN, UNVERIFIABLE)


class SourceUnavailable(Exception):
    """ai-sdlc's copy at some ref cannot be read from this checkout."""


class InstallFailed(RuntimeError):
    """`gh skill install` refused. Reported; it does not stop the other skills."""


# ------------------------------------------------------------------ provenance


def _frontmatter(text):
    """The `---` block at the top of a SKILL.md, as (lines, rest).

    Returns `(None, text)` when there is no block, which is how a hand-written
    directory is told from an installed one.
    """
    lines = (text or "").splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None, text
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return lines[1:index], "".join(lines[index + 1:])
    return None, text


def provenance(text):
    """What the installer recorded: source repository, ref, path, tree SHA."""
    lines, _ = _frontmatter(text)
    found = {}
    for line in lines or []:
        key, separator, value = line.partition(":")
        if separator and key.strip() in PROVENANCE_KEYS:
            found[key.strip()] = value.strip()
    return found


def without_provenance(text):
    """The file as ai-sdlc holds it — the injected keys removed, nothing else."""
    lines, rest = _frontmatter(text)
    if lines is None:
        return text
    kept = [line for line in lines if line.partition(":")[0].strip() not in PROVENANCE_KEYS]
    return "---\n" + "".join(kept) + "---\n" + rest


# ----------------------------------------------------------------- the installed


def installed_files(root, name):
    """Every file of an installed skill, as {relative path: text}.

    Read with `surrogateescape` so a byte nobody expected round-trips rather
    than raising: this is a comparison, and a file that cannot be decoded is
    still a file that either matches or does not.
    """
    directory = Path(root) / INSTALL_ROOT / name
    if not directory.is_dir():
        return {}

    files = {}
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(directory)
        if any(part in IGNORED for part in relative.parts):
            continue
        files[relative.as_posix()] = path.read_text(errors="surrogateescape")
    return files


def _matches(installed, source):
    """Whether an installed skill is ai-sdlc's copy, or somebody's edit of it."""
    normalised = dict(installed)
    if "SKILL.md" in normalised:
        normalised["SKILL.md"] = without_provenance(normalised["SKILL.md"])
    return normalised == source


# ------------------------------------------------------------- classification


class Skill:
    __slots__ = ("name", "state", "detail")

    def __init__(self, name, state, detail=""):
        self.name = name
        self.state = state
        self.detail = detail

    @property
    def skipped(self):
        return self.state in SKIPPED_STATES

    def __repr__(self):
        return f"<Skill {self.name} {self.state}>"


class Plan:
    __slots__ = ("skills", "install", "update", "current", "skipped", "changes")

    def __init__(self, skills):
        self.skills = list(skills)
        self.install = [s.name for s in self.skills if s.state == ABSENT]
        self.update = [s.name for s in self.skills if s.state == STALE]
        self.current = [s.name for s in self.skills if s.state == CURRENT]
        self.skipped = [s for s in self.skills if s.skipped]
        self.changes = bool(self.install or self.update)

    def __repr__(self):
        return (
            f"<Plan +{len(self.install)} ~{len(self.update)} "
            f"={len(self.current)} !{len(self.skipped)}>"
        )


def classify(name, ref, root, source):
    """What may be done with one named skill. Writes nothing, ever."""
    installed = installed_files(root, name)

    if not installed:
        if source(name, ref) is None:
            return Skill(name, UNKNOWN, f"ai-sdlc has no skill {name!r} at {ref}")
        return Skill(name, ABSENT, "not installed")

    recorded = provenance(installed.get("SKILL.md", "")).get("github-ref")
    if not recorded:
        return Skill(
            name, UNMANAGED,
            "installed with no provenance — written by hand, or by something "
            "other than `gh skill`",
        )

    try:
        original = source(name, recorded)
    except SourceUnavailable as error:
        return Skill(
            name, UNVERIFIABLE,
            f"cannot read ai-sdlc at {recorded}, so a local edit cannot be ruled "
            f"out ({error})",
        )

    if original is None:
        return Skill(name, UNKNOWN, f"ai-sdlc has no skill {name!r} at {recorded}")

    if not _matches(installed, original):
        return Skill(name, MODIFIED, f"edited locally since it was installed at {recorded}")

    if recorded == ref:
        return Skill(name, CURRENT, f"installed at {recorded}")

    if source(name, ref) is None:
        return Skill(name, UNKNOWN, f"ai-sdlc has no skill {name!r} at {ref}")

    return Skill(name, STALE, f"installed at {recorded}, pinned at {ref}")


def plan(names, ref, root=".", source=None):
    """Classify every named skill. Reads; writes nothing."""
    source = source or _git_source(root)
    return Plan(classify(name, ref, root, source) for name in names)


# --------------------------------------------------------------------- the run


class Applied:
    __slots__ = ("installed", "updated", "current", "skipped", "failed", "changes")

    def __init__(self, installed, updated, skipped, failed, current=()):
        self.installed = list(installed)
        self.updated = list(updated)
        self.current = list(current)
        self.skipped = list(skipped)
        self.failed = list(failed)
        self.changes = bool(self.installed or self.updated)


def apply(proposed, ref, installer=None):
    """Run the installs the plan calls for. Skips are not failures.

    A skill that cannot be installed is recorded and the rest continue: the
    same bargain `adopt` makes with a conflict, for the same reason — stopping
    at the first problem leaves a repository half-installed with nothing saying
    which half.
    """
    installer = installer or _gh_install
    installed, updated, failed = [], [], []

    for name in proposed.install + proposed.update:
        try:
            installer(name, ref)
        except Exception as error:  # noqa: BLE001 - reported, never raised on
            failed.append(Skill(name, "failed", str(error)))
            continue
        (installed if name in proposed.install else updated).append(name)

    return Applied(installed, updated, proposed.skipped, failed, proposed.current)


# ------------------------------------------------------------------ the report


def report(applied, ref):
    """What happened, in Markdown — printed, and used as the pull request body.

    One text for both, because a report that differs from the pull request it
    accompanies is a report somebody has to reconcile by hand.
    """
    lines = [f"Installed skills reconciled against ai-sdlc at `{ref}`.", ""]

    if applied.changes:
        for name in applied.installed:
            lines.append(f"- **{name}** — installed at `{ref}`")
        for name in applied.updated:
            lines.append(f"- **{name}** — updated to `{ref}`")
    else:
        lines.append("**Nothing changed.** Every skill named is already at the pin, "
                     "or was left alone for a reason below.")

    if applied.current:
        lines += ["", "### Already at the pin", ""]
        lines += [f"- **{name}**" for name in applied.current]

    if applied.skipped:
        lines += ["", "### Left alone", ""]
        for skill in applied.skipped:
            lines.append(f"- **{skill.name}** ({skill.state}) — {skill.detail}")

    if applied.failed:
        lines += ["", "### Failed", ""]
        for skill in applied.failed:
            lines.append(f"- **{skill.name}** — the install failed: {skill.detail}")

    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------- the seams


def install_command(name, ref):
    """The `gh skill install` invocation, as argv.

    Separated from running it so the shape of the command is testable without
    `gh` on the machine and without reaching GitHub.

    No `--force`. Forcing is precisely how a locally-modified skill gets
    overwritten, and the plan has already decided that nothing here is one.
    """
    return [
        "gh", "skill", "install", SOURCE, f"{name}@{ref}",
        "--agent", "claude-code", "--scope", "project",
    ]


def _gh_install(name, ref):  # pragma: no cover - the real network path
    import subprocess

    result = subprocess.run(
        install_command(name, ref), capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise InstallFailed((result.stderr or result.stdout).strip())


def _git_source(checkout):  # pragma: no cover - the real filesystem path
    """Read ai-sdlc's own copy of a skill at a ref, from a checkout of it.

    `git show` rather than a working-tree read, because the ref wanted is
    usually *not* the one checked out: classification asks for the ref each
    installed skill records, which is by definition an older one.
    """
    import subprocess

    def read(name, ref):
        listing = subprocess.run(
            ["git", "-C", str(checkout), "ls-tree", "-r", "--name-only", ref, "--", "skills"],
            capture_output=True, text=True, check=False,
        )
        if listing.returncode != 0:
            raise SourceUnavailable((listing.stderr or "").strip() or f"no ref {ref}")

        prefix = None
        for path in listing.stdout.splitlines():
            parts = path.split("/")
            if len(parts) >= 4 and parts[0] == "skills" and parts[2] == name:
                prefix = "/".join(parts[:3]) + "/"
                break
        if prefix is None:
            return None

        files = {}
        for path in listing.stdout.splitlines():
            if not path.startswith(prefix):
                continue
            relative = path[len(prefix):]
            if any(part in IGNORED for part in relative.split("/")):
                continue
            blob = subprocess.run(
                ["git", "-C", str(checkout), "show", f"{ref}:{path}"],
                capture_output=True, text=True, check=False,
            )
            if blob.returncode != 0:
                raise SourceUnavailable(f"cannot read {path} at {ref}")
            files[relative] = blob.stdout
        return files

    return read
