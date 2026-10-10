---
name: routines
description: Create or update this repository's Claude Code routines (scheduled and API-triggered prompts such as repository or project triage and the weekly Dependabot sweep) from ai-sdlc's definitions, so they match `routines:` in .ai-sdlc/repo-config.yml. Use when setting up routines for a repository, when a routine's prompt or schedule has drifted, or when asked what routines a repository should have.
allowed-tools: Bash, Read
---

# Routines

A routine is a saved prompt Claude Code runs in a fresh cloud session when a schedule or an API
trigger fires it. ai-sdlc keeps the definitions in `definitions/` beside this file. The repository
lists the ones it wants under `routines:` in `.ai-sdlc/repo-config.yml`; that list is the
repository's own, and nothing here adds to it.

You make the live routines match the plan. You do not decide what the plan says.

## Where this runs

Run this from a **Claude Code cloud session in the target repository**. Only those sessions have
the `list_triggers`, `create_trigger` and `update_trigger` tools. If you do not have them, stop and
say so: there is no API to fall back on, and a routine typed in by hand is the drift this exists to
end.

## 1. Plan

From the repository root:

```bash
python3 .claude/skills/routines/main.py plan
```

It reads the configuration and the repository's name (`--repo owner/name` overrides) and prints a
JSON plan: for each routine its exact `name`, `prompt`, `cron` (or `null`), whether it needs an
`api` trigger, its `connectors`, its `scope` (`repository` or `project`), for a project routine
its `project_repos`, and its `manual_tasks`. It writes nothing.

If it exits non-zero it prints every problem — an unknown routine, a routine whose capability is
not installed, a bad placeholder, `triage` (renamed to `repo-triage` and `project-triage`), both of
those at once, a project routine with no `project:` or in a repository not in `project.repos`.
Report them and stop. Never work around a refusal by editing the
plan or a prompt by hand.

An empty `routines` list means the repository has asked for none. Say so, and that the list is
`routines:` in `.ai-sdlc/repo-config.yml`.

## 2. Match

Call `list_triggers` with `include_completed` true, so a routine that has finished a run-once is
still seen. Match each planned routine to a live one by **exact name** — the rendered `name` from
the plan, character for character. Nothing else identifies a routine.

Each planned routine is then one of:

| Live routines with that name | Action |
| --- | --- |
| none | **create** |
| one, prompt and schedule identical | **leave alone** |
| one, prompt or schedule differs | **update** that routine, by its `trig_` id — for a project routine, only as *Project routines* below says |
| more than one | **report and leave alone** — you cannot tell which is meant |

A live routine that is not in the plan is left alone. Never delete a routine — not one missing
from the plan, not a duplicate, not one you created by mistake. Report it instead.

## Project routines

A routine whose `scope` is `project` is one live routine shared by every repository in
`project_repos`, and each of them plans it from its own `.ai-sdlc/repo-config.yml`. When their
`project:` blocks agree, every member plans the same name and the same prompt, so from any of them
it is the same match.

When a project routine's live prompt differs from the plan, compare the repository list in the live
prompt with the plan's `project_repos` and tell the operator which repositories the plan adds and
which it removes. Say that the likely cause is another member's `project.repos` disagreeing with
this one, and that the fix is to make `project:` identical in every member — otherwise each
member's run updates the routine back to its own list, and none of them is ever told why. Then ask
for an explicit confirmation of **that update**, naming the routine and the difference: a general
yes is not enough for it, including the one step 3 asks for. Without that explicit confirmation,
report the disagreement and leave the routine alone.

## 3. Confirm

Show the operator the plan before writing anything: each routine's name, whether it will be
created, updated or left alone, its schedule, and for an update what changes. Show the full prompt
of anything being created or updated. Then ask them to confirm, and write nothing until they do.

## 4. Write

For a routine to **create**, call `create_trigger` with:

- `name`, `prompt` and `cron_expression` exactly as the plan gives them (omit the cron when it is
  `null` — such a routine is fired only through its API trigger);
- `create_new_session_on_fire` true;
- `initiation` `human_request`;
- `connectors` exactly as the plan declares them — `[]` when it declares none, never a connector
  you think might help.

For a routine to **update**, call `update_trigger` with the matched routine's `trig_` id and the
plan's prompt and cron.

Never create a second routine with a name that already exists. If a create reports a name
conflict, list again and treat it as an update.

## 5. Hand over

Give the operator every entry of every routine's `manual_tasks`. They are the steps no tool can
take:

- **An API trigger** — added on the routine's page in the web UI, with its token generated there
  and shown once. The URL and token go into the repository secrets the plan names (from
  `fire.endpoint_secret` and `fire.token_secret`), which is how the gatekeeper fires triage.
- **The repository** — confirm it is attached on the routine's page, and attach it there if not.
  Whether `create_trigger` attaches it is not something you can check. For a project routine,
  that is every repository in `project_repos`, not only this one.
- **A project routine's trigger** is added **once**, on the shared routine. If another member
  already added it, it is reused, never a second one, and the same URL and token are stored in
  every member's `fire.*` secrets.

Never write a routine's URL, its token, or a session link into a file, an issue, a comment or a
commit. Say that a routine was created or updated, by name.

Specification: `docs/spec/routines.md` (`RTN`).
