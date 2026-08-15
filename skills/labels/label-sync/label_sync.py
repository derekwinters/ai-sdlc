#!/usr/bin/env python3
"""Apply a label taxonomy from git.

The label taxonomy is the pipeline's state machine, so it lives in a file that
can be reviewed and diffed rather than being clicked into the GitHub interface,
where nothing records what it should be or notices when it drifts.

Two manifests, deliberately separate files. `labels.core.yml` is installed and
pinned; `labels.repo.yml` is the repository's own. Sections of one file would
produce a merge conflict on every core upgrade, and the whole point is that an
upgrade is boring.

Deletion is explicit and nothing else. A label absent from the manifest is left
alone: repositories accumulate labels for reasons this tool cannot see, and
deleting one strips it from every issue that carried it, irreversibly.

Specification: docs/spec/labels.md (`LBL`).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from lib.yaml_lite import YamlError, parse

CORE_FILE = "labels.core.yml"
REPO_FILE = "labels.repo.yml"

COLOUR = re.compile(r"^[0-9a-fA-F]{6}$")


class ManifestError(ValueError):
    """A taxonomy that cannot be applied safely."""


class Label:
    __slots__ = ("name", "color", "description", "source")

    def __init__(self, name, color, description, source):
        self.name = name
        self.color = color
        self.description = description
        self.source = source

    def __getitem__(self, key):
        return getattr(self, key)

    def matches(self, existing):
        """True when the repository already has exactly this label."""
        return (
            existing.get("color", "").lower() == self.color.lower()
            and (existing.get("description") or "") == self.description
        )

    def __repr__(self):
        return f"<Label {self.name}>"


class Manifest:
    __slots__ = ("labels", "delete")

    def __init__(self, labels, delete):
        self.labels = labels
        self.delete = delete


class Result:
    __slots__ = ("created", "updated", "deleted", "unchanged")

    def __init__(self):
        self.created, self.updated, self.deleted, self.unchanged = [], [], [], []

    def __repr__(self):
        return (
            f"<Result created={len(self.created)} updated={len(self.updated)} "
            f"deleted={len(self.deleted)} unchanged={len(self.unchanged)}>"
        )


# ---------------------------------------------------------------- manifests


def load_manifests(directory):
    """Read both manifests and validate their union."""
    directory = Path(directory)
    core_path = directory / CORE_FILE
    if not core_path.is_file():
        raise ManifestError(f"no {CORE_FILE} in {directory}")

    labels, deletions, problems = [], [], []
    seen = {}

    for path in (core_path, directory / REPO_FILE):
        if not path.is_file():
            continue
        section = _read(path)

        for entry in section.get("labels") or []:
            name = (entry.get("name") or "").strip()
            problem = _invalid(entry, name)
            if problem:
                problems.append(problem)
                continue
            if name in seen:
                problems.append(
                    f"label {name!r} is defined in both {seen[name]} and {path.name}; "
                    "the effective taxonomy would depend on load order"
                )
                continue
            seen[name] = path.name
            labels.append(
                Label(name, entry["color"], entry["description"], source=path.name)
            )

        deletions.extend(section.get("delete") or [])

    for name in deletions:
        if name in seen:
            problems.append(
                f"label {name!r} is both defined and listed for deletion"
            )

    if problems:
        raise ManifestError("\n".join(f"  - {p}" for p in problems))

    return Manifest(sorted(labels, key=lambda l: l.name), sorted(set(deletions)))


def _read(path):
    try:
        return parse(path.read_text()) or {}
    except YamlError as error:
        raise ManifestError(f"{path.name}: {error}") from error


def _invalid(entry, name):
    if not name:
        return "a label has no name"
    if not (entry.get("description") or "").strip():
        return f"label {name!r} has no description; its meaning would live only in whoever made it"
    colour = entry.get("color")
    if not colour:
        return f"label {name!r} has no colour"
    if not COLOUR.match(str(colour)):
        return (
            f"label {name!r} has colour {colour!r}; expected six hexadecimal "
            f"digits with no leading '#'"
        )
    return None


# ----------------------------------------------------------------- applying


def apply_labels(api, labels, delete):
    """Create, update and delete so the repository matches the manifest."""
    result = Result()
    existing = {label["name"]: label for label in api.labels()}

    for label in sorted(labels, key=lambda l: l.name):
        found = existing.get(label.name)
        if found is None:
            api.create_label(label.name, label.color, label.description)
            result.created.append(label.name)
        elif label.matches(found):
            result.unchanged.append(label.name)
        else:
            api.update_label(label.name, label.color, label.description)
            result.updated.append(label.name)

    for name in sorted(delete):
        if name in existing:
            api.delete_label(name)
            result.deleted.append(name)

    return result


def main(directory="."):
    from lib.github import GitHub
    import os

    manifest = load_manifests(directory)
    api = GitHub(os.environ["GITHUB_TOKEN"], os.environ["GITHUB_REPOSITORY"])
    result = apply_labels(api, manifest.labels, manifest.delete)

    for name in result.created:
        print(f"created  {name}")
    for name in result.updated:
        print(f"updated  {name}")
    for name in result.deleted:
        print(f"deleted  {name}")
    print(
        f"labels: {len(result.created)} created, {len(result.updated)} updated, "
        f"{len(result.deleted)} deleted, {len(result.unchanged)} unchanged"
    )
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path.cwd()))
    raise SystemExit(main(*sys.argv[1:]))
