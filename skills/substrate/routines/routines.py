#!/usr/bin/env python3
"""Render ai-sdlc's routine definitions into an exact plan for one repository.

A routine is a saved prompt Claude Code runs in a fresh cloud session when a
schedule or an API trigger fires it. Every adopting repository wants the same
few, differing only in the repository they name, so the definitions live here
and a repository lists the ones it wants in `routines:`.

This module only *plans*. It reads the definitions, the repository's
configuration and its name, and returns everything `create_trigger` needs. It
writes nothing and opens no socket; the agent following SKILL.md makes the
writes, after the operator has seen the plan.

It is installed into consumers, where `lib` does not exist (DIST-042), so it
carries its own reader for the small YAML subset it needs. That reader is
compared with `lib/yaml_lite` and `lib/config` by test rather than shared.

Specification: docs/spec/routines.md (`RTN`).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

DEFINITIONS = Path(__file__).resolve().parent / "definitions"

CONFIG_PATH = Path(".ai-sdlc") / "repo-config.yml"

#: The capability names `lib/config.py` declares, in its order (RTN-004).
CAPABILITIES = ("substrate", "hygiene", "consistency", "labels", "release", "pipeline")

#: Placeholders naming the repository being planned. A project routine uses
#: none of them, so every member renders it identically (RTN-009).
REPOSITORY_PLACEHOLDERS = ("repo", "owner", "repo_name")

#: Placeholders naming the project, from `project:` (RTN-015).
PROJECT_PLACEHOLDERS = ("project", "project_repos")

PLACEHOLDERS = REPOSITORY_PLACEHOLDERS + PROJECT_PLACEHOLDERS

REQUIRED = ("id", "name", "requires", "session")
OPTIONAL = ("schedule", "api", "connectors", "scope")
SESSIONS = ("fresh",)
SCOPES = ("repository", "project")

#: Definitions that no longer exist, and what to list instead (RTN-025). No
#: alias: `triage` would have to pick one of its two successors on the
#: repository's behalf.
RENAMED = {
    "triage": ("'triage' was renamed in the routines skill: list 'repo-triage' for a triage "
               "routine of this repository's own, or 'project-triage' for one shared by every "
               "repository in project.repos"),
}

#: Pairs a repository may not name together (RTN-028). Both triage routines
#: answer the same fire, and a repository has one `fire.endpoint_secret`.
EXCLUSIVE = (("repo-triage", "project-triage"),)

_SLUG = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?/[A-Za-z0-9._-]+$")

#: `{name}` with no whitespace or braces inside: a placeholder, known or not.
_PLACEHOLDER = re.compile(r"\{([^{}\s]*)\}")


class RoutineError(ValueError):
    """Something that stops a plan. Carries every problem found."""

    def __init__(self, problems):
        self.problems = [problems] if isinstance(problems, str) else list(problems)
        super().__init__("\n".join(f"  - {p}" for p in self.problems))


class Definition:
    __slots__ = ("id", "name", "requires", "schedule", "api", "connectors", "session",
                 "scope", "prompt")

    def __init__(self, **values):
        for key in self.__slots__:
            setattr(self, key, values[key])


# --------------------------------------------------------------- the reader


def _strip_comment(line):
    quote = None
    for position, char in enumerate(line):
        if quote:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "#" and (position == 0 or line[position - 1] in " \t"):
            return line[:position]
    return line


def _scalar(text, number):
    if text[:1] in ("&", "*", "{") or (text.startswith("[") and text.replace(" ", "") != "[]"):
        raise RoutineError(f"line {number}: flow style, anchors and aliases are not supported")
    if text.replace(" ", "") == "[]":
        return []
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    lowered = text.lower()
    if lowered in ("null", "~", ""):
        return None
    if lowered in ("true", "false"):
        return lowered == "true"
    try:
        return int(text)
    except ValueError:
        return text


def _split_key(content, number):
    quote = None
    for position, char in enumerate(content):
        if quote:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == ":":
            return content[:position].strip(), content[position + 1:].strip()
    raise RoutineError(f"line {number}: expected 'key: value'")


def _read_block(text, nested=()):
    """Top-level keys: scalars, `- ` lists, and for the keys in `nested` one
    level of `key: value`, whose value may itself be a `- ` list one level
    further in (`project.repos`). Everything this reads, `lib/yaml_lite` reads
    the same way (RTN-003); anything else is refused rather than guessed at."""
    result, current, kind, inner_list = {}, None, None, None
    for number, raw in enumerate(text.splitlines(), start=1):
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        content = line.strip()
        if indent == 0:
            key, value = _split_key(content, number)
            result[key] = _scalar(value, number) if value else None
            current, kind, inner_list = (key if value == "" else None), None, None
            continue
        if indent == 4 and inner_list is not None and (
            content.startswith("- ") or content == "-"
        ):
            mapping, inner = inner_list
            if mapping[inner] is None:
                mapping[inner] = []
            mapping[inner].append(_scalar(content[2:].strip(), number))
            continue
        if current is None or indent != 2:
            raise RoutineError(f"line {number}: unexpected indentation")
        key = current
        if content.startswith("- ") or content == "-":
            if kind == "map":
                raise RoutineError(f"line {number}: a list inside a mapping")
            kind = "list"
            if result[key] is None:
                result[key] = []
            result[key].append(_scalar(content[2:].strip(), number))
        else:
            if key not in nested or kind == "list":
                raise RoutineError(f"line {number}: nested mappings are not supported here")
            kind = "map"
            if result[key] is None:
                result[key] = {}
            inner, value = _split_key(content, number)
            result[key][inner] = _scalar(value, number) if value else None
            inner_list = (result[key], inner) if value == "" else None
    return result


def parse_front_matter(text):
    """Split a definition into (front matter, body)."""
    if not text.startswith("---\n"):
        raise RoutineError("no front matter: the file must start with a '---' line")
    block, separator, body = text[4:].partition("\n---\n")
    if not separator:
        raise RoutineError("front matter is not closed by a '---' line")
    return _read_block(block + "\n"), body


# ------------------------------------------------------------- definitions


def _schedule_problems(cron):
    if not isinstance(cron, str) or not cron.strip():
        return ["'schedule' must be a cron expression"]
    fields = cron.split()
    if fields[0].startswith("CRON_TZ="):
        if fields[0] == "CRON_TZ=":
            return ["'schedule' has an empty CRON_TZ= zone"]
        fields = fields[1:]
    if len(fields) != 5:
        return [f"'schedule' must have five cron fields, found {len(fields)}"]
    minute = fields[0]
    if not minute.isdigit():
        return [f"'schedule' fires more often than once an hour (minute field {minute!r}); "
                "the platform's shortest interval is an hour"]
    if not 0 <= int(minute) <= 59:
        return [f"'schedule' minute {minute} is out of range"]
    return []


def load_definition(path):
    path = Path(path)
    try:
        front, body = parse_front_matter(path.read_text())
    except RoutineError as error:
        raise RoutineError([f"{path.name}: {p}" for p in error.problems]) from error

    problems = []
    for key in front:
        if key not in REQUIRED + OPTIONAL:
            problems.append(f"unknown key {key!r}; valid keys: "
                            f"{', '.join(REQUIRED + OPTIONAL)}")
    for key in REQUIRED:
        if not isinstance(front.get(key), str) or not front.get(key):
            problems.append(f"{key!r} is required")

    if front.get("id") and front.get("id") != path.stem:
        problems.append(f"'id' is {front['id']!r} but the file name is {path.stem!r}")
    requires = front.get("requires")
    if isinstance(requires, str) and requires and requires not in CAPABILITIES:
        problems.append(f"'requires' names {requires!r}; valid capabilities: "
                        f"{', '.join(CAPABILITIES)}")
    session = front.get("session")
    if isinstance(session, str) and session and session not in SESSIONS:
        problems.append(f"'session' is {session!r}; the only session is 'fresh'")

    schedule = front.get("schedule")
    api = front.get("api", False)
    if api not in (True, False, None):
        problems.append("'api' must be true or false")
    if schedule is not None:
        problems.extend(_schedule_problems(schedule))
    if schedule is None and api is not True:
        problems.append("no trigger: a definition needs 'schedule', 'api: true', or both")

    scope = front.get("scope")
    if scope is None:
        scope = "repository"
    if scope not in SCOPES:
        problems.append(f"'scope' is {scope!r}; valid scopes: {', '.join(SCOPES)}")
    elif scope == "project":
        for field, text in (("name", front.get("name")), ("prompt", body)):
            for used in _placeholders(text if isinstance(text, str) else ""):
                if used in REPOSITORY_PLACEHOLDERS:
                    problems.append(
                        f"a project routine's {field} cannot use {{{used}}}: every repository "
                        f"in the project must render the same routine"
                    )

    connectors = front.get("connectors")
    if connectors is None:
        connectors = []
    if not isinstance(connectors, list) or not all(
        isinstance(c, str) and c for c in connectors
    ):
        problems.append("'connectors' must be a list of connector names")
        connectors = []

    if problems:
        raise RoutineError([f"{path.name}: {p}" for p in problems])

    return Definition(
        id=front["id"], name=front["name"], requires=requires, schedule=schedule,
        api=api is True, connectors=list(connectors), session=session, scope=scope,
        prompt=body.strip(),
    )


def load_definitions(directory=DEFINITIONS):
    found, problems = {}, []
    for path in sorted(Path(directory).glob("*.md")):
        try:
            found[path.stem] = load_definition(path)
        except RoutineError as error:
            problems.extend(error.problems)
    if problems:
        raise RoutineError(problems)
    return found


# --------------------------------------------------------------- rendering


def _escaped(template):
    return template.replace("{{", "\0").replace("}}", "\1")


def _placeholders(template):
    """The placeholder names a template uses, literal braces excepted."""
    return [m.group(1) for m in _PLACEHOLDER.finditer(_escaped(template))]


def project_repos(project):
    """`project.repos` sorted and without repeats (RTN-015)."""
    return sorted(set(project["repos"]))


def render(template, repo, where, project=None):
    """Fill the placeholders; refuse an unknown one, and a project one when
    there is no project."""
    owner, _, name = repo.partition("/")
    values = {"repo": repo, "owner": owner, "repo_name": name}
    if project is not None:
        values["project"] = project["name"]
        values["project_repos"] = "\n".join(f"- {r}" for r in project_repos(project))
    escaped = _escaped(template)

    problems = []
    for match in _PLACEHOLDER.finditer(escaped):
        if match.group(1) in values:
            continue
        if match.group(1) in PROJECT_PLACEHOLDERS:
            problems.append(f"{where}: {match.group(0)} needs project: in "
                            f"{CONFIG_PATH.as_posix()}, and this configuration has none")
        else:
            problems.append(f"{where}: unknown placeholder {match.group(0)}; known: "
                            f"{', '.join('{' + p + '}' for p in PLACEHOLDERS)}")
    if problems:
        raise RoutineError(problems)
    out = _PLACEHOLDER.sub(lambda m: values[m.group(1)], escaped)
    return out.replace("\0", "{").replace("\1", "}")


def _origin():
    try:
        done = subprocess.run(["git", "remote", "get-url", "origin"],
                              capture_output=True, text=True, check=False)
    except OSError:
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def repository_slug(explicit=None, environ=None, remote=_origin):
    """`owner/name`, from the flag, the environment, or the origin remote."""
    environ = os.environ if environ is None else environ
    if explicit is not None:
        candidate, source = explicit, "--repo"
    elif environ.get("GITHUB_REPOSITORY"):
        candidate, source = environ["GITHUB_REPOSITORY"], "GITHUB_REPOSITORY"
    else:
        url = remote()
        if not url:
            raise RoutineError("cannot tell which repository this is: pass --repo owner/name")
        # The URL is never quoted back (RTN-014): a cloud session's origin can
        # carry a credential in its userinfo.
        path = re.sub(r"\.git$", "", url.rstrip("/"))
        parts = re.split(r"[/:]", path)
        candidate = "/".join(parts[-2:]) if len(parts) >= 2 else ""
        if not _SLUG.match(candidate) or "@" in candidate:
            raise RoutineError("the origin remote does not end in owner/name: "
                               "pass --repo owner/name")
        return candidate
    if not _SLUG.match(candidate or ""):
        raise RoutineError(f"{source} must be owner/name, found {candidate!r}")
    return candidate


# ---------------------------------------------------------------- planning


def read_config(root):
    path = Path(root) / CONFIG_PATH
    if not path.is_file():
        raise RoutineError(f"no configuration at {CONFIG_PATH.as_posix()}")
    try:
        raw = _read_block(path.read_text(),
                          nested=("fire", "bot", "labels", "commands", "project"))
    except RoutineError as error:
        raise RoutineError([f"{CONFIG_PATH.as_posix()}: {p}" for p in error.problems]) from error

    def names(key):
        listed = raw.get(key) or []
        if not isinstance(listed, list):
            raise RoutineError(f"{CONFIG_PATH.as_posix()}: '{key}' must be a list")
        seen = []
        for name in listed:
            if name not in seen:
                seen.append(name)
        return seen

    fire = raw.get("fire") if isinstance(raw.get("fire"), dict) else {}
    return {"capabilities": names("capabilities"), "routines": names("routines"),
            "fire": dict(fire), "project": _project(raw)}


def _project(raw):
    """`project:` as {name, repos}, repos sorted and collapsed, or None.

    The shape `lib/config.py` validates (CFG-074); a shape this cannot use is
    refused rather than planned around.
    """
    if "project" not in raw:
        return None
    section = raw["project"]
    where = CONFIG_PATH.as_posix()
    if not isinstance(section, dict):
        raise RoutineError(f"{where}: 'project' must be a mapping of name and repos")
    name, repos = section.get("name"), section.get("repos")
    problems = []
    if not isinstance(name, str) or not name.strip():
        problems.append(f"{where}: 'project.name' must be a non-empty string")
    if not isinstance(repos, list) or not repos or not all(
        isinstance(r, str) and _SLUG.match(r) for r in repos
    ):
        problems.append(f"{where}: 'project.repos' must be a non-empty list of owner/name")
    if problems:
        raise RoutineError(problems)
    return {"name": name, "repos": project_repos({"repos": repos})}


def _manual_tasks(definition, name, repo, fire, project):
    endpoint, token = fire.get("endpoint_secret"), fire.get("token_secret")
    if definition.scope == "project":
        return _project_tasks(definition, name, project, endpoint, token)
    tasks = []
    if definition.api:
        if endpoint and token:
            where = (f"as the repository secrets {endpoint} (the URL) and {token} "
                     f"(the token)")
        else:
            where = ("as two repository secrets, and name them under fire.endpoint_secret "
                     "and fire.token_secret in .ai-sdlc/repo-config.yml")
        tasks.append(
            f"On the routine '{name}' in the Claude Code web UI, add an API trigger and "
            f"generate its token. Store the trigger URL and the token {where}. No tool can "
            f"create an API trigger, and the token is shown once."
        )
    tasks.append(
        f"Open the routine '{name}' in the Claude Code web UI and confirm the repository "
        f"{repo} is attached; attach it there if not."
    )
    return tasks


def _project_tasks(definition, name, project, endpoint, token):
    """RTN-035 and RTN-036: the shared routine's steps, for every member."""
    members = ", ".join(project["repos"])
    tasks = []
    if definition.api:
        if endpoint and token:
            where = f"as the repository secrets {endpoint} (the URL) and {token} (the token)"
        else:
            where = ("as two repository secrets, named under fire.endpoint_secret and "
                     "fire.token_secret in each one's .ai-sdlc/repo-config.yml")
        tasks.append(
            f"On the routine '{name}' in the Claude Code web UI, add an API trigger and "
            f"generate its token once for the whole project {project['name']}: if one was "
            f"already added from another of its repositories, use that one and never add a "
            f"second. Store the same trigger URL and token {where} in every repository in the "
            f"project: {members}. No tool can create an API trigger, and the token is shown "
            f"once."
        )
    tasks.append(
        f"Open the routine '{name}' in the Claude Code web UI and attach every repository "
        f"in the project {project['name']}: {members}. Confirm each one is attached."
    )
    return tasks


def _selection_problems(listed):
    problems = [f"routines: {RENAMED[r]}" for r in listed if r in RENAMED]
    for pair in EXCLUSIVE:
        if all(r in listed for r in pair):
            problems.append(f"routines: name one of {' and '.join(repr(r) for r in pair)}, not "
                            f"both: they answer the same fire, and the gatekeeper can reach "
                            f"only one")
    return problems


def plan(root, repo, directory=DEFINITIONS):
    """The plan for one repository, or RoutineError with every problem."""
    config = read_config(root)
    definitions = load_definitions(directory)
    installed = set(config["capabilities"]) | {"substrate"}

    project = config["project"]
    problems, routines = _selection_problems(config["routines"]), []
    for routine_id in config["routines"]:
        if routine_id in RENAMED:
            continue
        definition = definitions.get(routine_id)
        if definition is None:
            problems.append(f"routines: no definition {routine_id!r}; available: "
                            f"{', '.join(sorted(definitions)) or '(none)'}")
            continue
        if definition.requires not in installed:
            problems.append(f"routines: {routine_id!r} requires the {definition.requires!r} "
                            f"capability, which this repository has not installed")
            continue
        if definition.scope == "project":
            if project is None:
                problems.append(f"routines: {routine_id!r} is shared by a project and needs "
                                f"project: (name and repos) in {CONFIG_PATH.as_posix()}")
                continue
            if repo not in project["repos"]:
                problems.append(f"routines: {routine_id!r} is shared by the project "
                                f"{project['name']!r}, and {repo} is not in its project.repos")
                continue
        try:
            name = render(definition.name, repo, f"{routine_id} name", project)
            prompt = render(definition.prompt, repo, f"{routine_id} prompt", project)
        except RoutineError as error:
            problems.extend(error.problems)
            continue
        entry = {
            "id": routine_id,
            "name": name,
            "prompt": prompt,
            "cron": definition.schedule,
            "api": definition.api,
            "connectors": list(definition.connectors),
            "create_new_session_on_fire": True,
            "scope": definition.scope,
            "manual_tasks": _manual_tasks(definition, name, repo, config["fire"], project),
        }
        if definition.scope == "project":
            entry["project_repos"] = list(project["repos"])
        routines.append(entry)

    if problems:
        raise RoutineError(problems)
    return {"repository": repo, "routines": routines}


def dumps(result):
    return json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
