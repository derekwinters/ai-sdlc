#!/usr/bin/env python3
"""Load and validate a consuming repository's `.claude/repo-config.yml`.

This file is the only thing that differs between repositories. The skills,
workflows and specifications are identical everywhere; a repository says here
how many owners it has, what its milestones mean, and which capabilities it
installed.

Configuration *describes* a repository — it does not switch behaviour on and
off. A key exists because repositories genuinely differ. A proposed key that
would fork behaviour is a sign that a separate capability is wanted.

Unknown keys are refused rather than ignored: a typo that silently does nothing
is worse than one that stops the run, because nobody goes looking for a setting
that appears to be applied.

Specification: docs/spec/configuration.md (`CFG`).
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path

from lib.yaml_lite import YamlError, parse

CONFIG_PATH = Path(".claude") / "repo-config.yml"

#: Ordered by how much each assumes about how a repository works. A capability
#: may depend only on capabilities earlier in this tuple.
CAPABILITIES = ("substrate", "hygiene", "consistency", "labels", "release", "pipeline")

DEPENDENCIES = {
    "substrate": (),
    "hygiene": ("substrate",),
    "consistency": ("substrate",),
    "labels": ("substrate",),
    "release": ("substrate", "hygiene"),
    "pipeline": ("substrate", "hygiene", "consistency", "labels", "release"),
}

PROFILES = ("unity", "mkdocs", "python", "node", "kotlin")

#: Pipeline states and the labels they carry unless a repository says otherwise.
STATES = {
    "triage": "ai-triage",
    "pending_approval": "pending-approval",
    "clarification": "needs-clarification",
    "approved": "ready-for-work",
    "building": "in-progress",
    "parked": "parked",
}

ORDERING_STRATEGIES = ("semver", "date", "lexical", "none")

BOT_IDENTITIES = ("github-actions", "app")

#: A value that looks like a credential rather than the *name* of one.
_LOOKS_LIKE_A_SECRET = re.compile(r"^(https?://|gh[pousr]_|github_pat_)", re.IGNORECASE)


class ConfigError(ValueError):
    """A configuration that cannot be trusted. Reports every problem found."""

    def __init__(self, problems, source=None):
        self.problems = list(problems)
        self.source = source
        heading = "The configuration is not valid"
        if source:
            heading += f" ({source})"
        super().__init__(heading + ":\n" + "\n".join(f"  - {p}" for p in self.problems))


class _Bot:
    __slots__ = ("identity", "login", "app_id_secret", "private_key_secret")

    def __init__(self, identity, login, app_id_secret, private_key_secret):
        self.identity = identity
        self.login = login
        self.app_id_secret = app_id_secret
        self.private_key_secret = private_key_secret


class _Commands:
    __slots__ = ("test", "verify", "spec_validator")

    def __init__(self, test=None, verify=None, spec_validator=None):
        self.test = test
        self.verify = verify
        self.spec_validator = spec_validator


class _Fire:
    __slots__ = ("endpoint_secret", "token_secret")

    def __init__(self, endpoint_secret=None, token_secret=None):
        self.endpoint_secret = endpoint_secret
        self.token_secret = token_secret


class Config:
    """A validated configuration. Every optional key has a value."""

    __slots__ = (
        "capabilities",
        "profiles",
        "owners",
        "bot",
        "labels",
        "milestone_ordering",
        "dashboard_issue",
        "commands",
        "fire",
    )

    def __init__(self, **values):
        for name in self.__slots__:
            setattr(self, name, values[name])

    def has(self, capability):
        return capability in self.capabilities

    def label(self, state):
        return self.labels[state]

    def __repr__(self):
        return f"<Config capabilities={self.capabilities}>"


# ----------------------------------------------------------------------- entry


def load(root=None, path=None):
    """Load from a repository root, or from an explicit path."""
    if path is None:
        path = Path(root or ".") / CONFIG_PATH
    path = Path(path)

    if not path.is_file():
        raise ConfigError([f"no configuration file at {path}"], source=str(path))

    try:
        return parse_config(path.read_text(), source=path.name)
    except YamlError as error:
        raise ConfigError([str(error)], source=path.name) from error


def parse_config(text, source=None):
    """Parse and validate configuration text."""
    try:
        raw = parse(text)
    except YamlError as error:
        raise ConfigError([str(error)], source=source) from error

    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ConfigError(["the file must be a mapping of settings"], source=source)

    problems = []
    _reject_unknown(raw, _SCHEMA_KEYS, "", problems)

    capabilities = _capabilities(raw, problems)
    pipeline = "pipeline" in capabilities

    config = Config(
        capabilities=capabilities,
        profiles=_profiles(raw, problems),
        owners=_owners(raw, pipeline, problems),
        bot=_bot(raw, problems),
        labels=_labels(raw, problems),
        milestone_ordering=_choice(
            raw, "milestone_ordering", ORDERING_STRATEGIES, "semver", problems
        ),
        dashboard_issue=_dashboard_issue(raw, pipeline, problems),
        commands=_commands(raw, problems),
        fire=_fire(raw, problems),
    )

    if problems:
        raise ConfigError(problems, source=source)
    return config


# ------------------------------------------------------------------ validation


_SCHEMA_KEYS = {
    "capabilities": list,
    "profiles": list,
    "owners": list,
    "bot": dict,
    "labels": dict,
    "milestone_ordering": str,
    "dashboard_issue": int,
    "commands": dict,
    "fire": dict,
}

_NESTED_KEYS = {
    "bot": {"identity": str, "login": str, "app_id_secret": str, "private_key_secret": str},
    "commands": {"test": str, "verify": str, "spec_validator": str},
    "fire": {"endpoint_secret": str, "token_secret": str},
}


def _reject_unknown(raw, allowed, prefix, problems):
    for key, value in raw.items():
        path = f"{prefix}{key}"
        if key not in allowed:
            problems.append(f"unknown key {path!r}{_did_you_mean(key, allowed)}")
            continue
        expected = allowed[key]
        if value is not None and not isinstance(value, expected):
            problems.append(
                f"{path!r} must be a {expected.__name__}, found {type(value).__name__}"
            )
            continue
        if key in _NESTED_KEYS and isinstance(value, dict):
            _reject_unknown(value, _NESTED_KEYS[key], f"{path}.", problems)


def _did_you_mean(key, allowed):
    close = difflib.get_close_matches(key, list(allowed), n=1, cutoff=0.6)
    suggestion = f"; did you mean {close[0]!r}?" if close else ""
    return f"{suggestion} valid keys: {', '.join(sorted(allowed))}"


def _section(raw, name):
    value = raw.get(name)
    return value if isinstance(value, dict) else {}


def _choice(raw, key, options, default, problems, container=None):
    source = container if container is not None else raw
    value = source.get(key, default)
    if value is None:
        value = default
    if value not in options:
        problems.append(f"{key!r} must be one of {', '.join(options)}, found {value!r}")
        return default
    return value


# ------------------------------------------------------------------- the parts


def _capabilities(raw, problems):
    listed = raw.get("capabilities") or []
    if not isinstance(listed, list):
        return ["substrate"]

    selected = []
    for name in listed:
        if name not in CAPABILITIES:
            problems.append(
                f"unknown capability {name!r}; valid capabilities: {', '.join(CAPABILITIES)}"
            )
            continue
        if name not in selected:
            selected.append(name)

    if "substrate" not in selected:
        selected.append("substrate")

    for name in selected:
        missing = [need for need in DEPENDENCIES[name] if need not in selected]
        if missing:
            problems.append(
                f"capability {name!r} depends on {', '.join(missing)}, which "
                f"{'is' if len(missing) == 1 else 'are'} not enabled"
            )

    return [name for name in CAPABILITIES if name in selected]


def _profiles(raw, problems):
    listed = raw.get("profiles") or []
    if not isinstance(listed, list):
        return []
    for name in listed:
        if name not in PROFILES:
            problems.append(f"unknown profile {name!r}; valid profiles: {', '.join(PROFILES)}")
    return [name for name in listed if name in PROFILES]


def _owners(raw, pipeline, problems):
    if "owners" in raw and raw["owners"] is not None and not isinstance(raw["owners"], list):
        # The type error is already reported; a scalar owner is a common mistake
        # worth naming precisely.
        return []

    owners = raw.get("owners") or []
    if pipeline and not owners:
        problems.append(
            "'owners' must list at least one login when the pipeline capability is enabled"
        )
    return list(owners)


def _bot(raw, problems):
    section = _section(raw, "bot")
    identity = _choice(raw, "identity", BOT_IDENTITIES, "github-actions", problems, section)

    app_id = section.get("app_id_secret")
    private_key = section.get("private_key_secret")

    if identity == "app":
        for name, value in (("app_id_secret", app_id), ("private_key_secret", private_key)):
            if not value:
                problems.append(f"'bot.{name}' is required when bot.identity is 'app'")
    else:
        for name, value in (("app_id_secret", app_id), ("private_key_secret", private_key)):
            if value:
                problems.append(
                    f"'bot.{name}' is only meaningful when bot.identity is 'app'"
                )

    return _Bot(identity, section.get("login") or "github-actions[bot]", app_id, private_key)


def _labels(raw, problems):
    labels = dict(STATES)
    overrides = _section(raw, "labels")

    for state, name in overrides.items():
        if state not in STATES:
            problems.append(
                f"unknown pipeline state {state!r} in 'labels'; "
                f"valid states: {', '.join(sorted(STATES))}"
            )
            continue
        labels[state] = name

    seen = {}
    for state, name in labels.items():
        if name in seen:
            problems.append(
                f"label {name!r} is used for both {seen[name]!r} and {state!r}; "
                "each state needs its own label"
            )
        seen[name] = state

    return labels


def _dashboard_issue(raw, pipeline, problems):
    value = raw.get("dashboard_issue")
    if value is None:
        if pipeline:
            problems.append(
                "'dashboard_issue' is required when the pipeline capability is enabled"
            )
        return None
    if not isinstance(value, int) or value <= 0:
        problems.append(f"'dashboard_issue' must be a positive issue number, found {value!r}")
        return None
    return value


def _commands(raw, problems):
    section = _section(raw, "commands")
    return _Commands(
        test=section.get("test"),
        verify=section.get("verify"),
        spec_validator=section.get("spec_validator"),
    )


def _fire(raw, problems):
    section = _section(raw, "fire")
    for key in ("endpoint_secret", "token_secret"):
        value = section.get(key)
        if value and _LOOKS_LIKE_A_SECRET.match(str(value)):
            problems.append(
                f"'fire.{key}' names a secret, it does not hold one; "
                f"found something that looks like a value rather than a name"
            )
    return _Fire(section.get("endpoint_secret"), section.get("token_secret"))
