# Specification — Routines (`RTN`)

A Claude Code Routine is a saved prompt that runs in a fresh cloud session when something fires
it — a schedule, or a call to its API trigger. Every repository that adopts ai-sdlc wants the same
few of them, differing only in the repository they name, and until now each was typed into the web
UI by hand: a triage routine whose prompt drifted between repositories, and a weekly Dependabot
sweep that existed in one place and was remembered in none.

This page specifies routines **as code**: definitions kept in ai-sdlc, a repository naming the ones
it wants, a script that renders them into an exact plan, and a skill an agent follows to make the
live routines match that plan.

`RTN` belongs to the **substrate** capability and depends only on `CFG` and `DIST`. A definition
may name a higher capability as the one it *requires*; that is a fact about the repository it is
rendered for, checked at plan time, not an import.

Every requirement below is `auto` (covered by a named test) unless marked otherwise.

---

## What the platform allows

This section constrains everything below it, so it is stated first.

- There is **no public API** for routines. They are created in the web UI, through `/schedule` in
  the CLI, or — from inside a Claude Code cloud session — through the `list_triggers`,
  `create_trigger` and `update_trigger` tools. Only the last is scriptable, so the last is what this
  uses, and it is only available in a cloud session.
- Routines are matched **by name**. There is no lookup by any other key, and nothing here deletes.
- An **API trigger** — the `/fire` endpoint and its bearer token — can only be added in the web UI.
  No tool creates one. A routine the gatekeeper fires (`GK`, through `fire.endpoint_secret` and
  `fire.token_secret`, `CFG-046`) therefore always needs one manual step after it is created.
- Whether `create_trigger` attaches the calling session's repository to the routine is
  unverified, so the operator confirms it on the routine's page.
- The text an API trigger sends arrives inside a `<routine-fire-payload>` block marked untrusted.
  A prompt acts on it only by saying so.

## Invariants

> **Invariant — the repository owns the list.** Which routines a repository has is `routines:` in
> its own `.ai-sdlc/repo-config.yml`, for the same reason `skills:` is (`DIST`'s first invariant).
> Nothing central decides that a repository should have one, and `adopt` does not seed the key.

> **Invariant — the plan writes nothing.** Rendering is a pure function of the definitions, the
> configuration and the repository's name. Every write to a live routine is made by an agent, after
> the operator has seen the plan and said yes.

> **Invariant — a live routine is matched by its exact name, and is never deleted.** A routine
> missing from the plan is left alone, not removed: a list edited by mistake should not cost
> anyone a routine, and a deletion through a name match is one typo away from the wrong routine.
> A name already taken is updated, never created beside, because two routines of one name are two
> things the next match cannot tell apart.

> **Invariant — a fire payload is data.** A prompt that reads a `<routine-fire-payload>` block
> extracts the single value it needs from it and ignores everything else. Text that anyone able to
> label an issue can influence is never an instruction.

---

## 1. Definitions

- **RTN-001** A routine is defined by one file, `skills/substrate/routines/definitions/<id>.md`,
  inside the skill, so it ships, pins and updates with the skill (`DIST-022`). The file is a
  front-matter block between `---` lines followed by the prompt template, and the `id` it declares
  is its file name.
- **RTN-002** The front matter holds `id`, `name`, `requires` and `session`, all required, and the
  triggers `schedule` and `api`, of which at least one is present. `connectors` is optional. Any
  other key is an error naming it, as `CFG-011` refuses one.
- **RTN-003** Front matter is read with the standard library by the skill itself, in the subset
  `CFG` §6 states — scalars, quoted strings, `true`/`false`, `[]` and `- ` lists — and agrees with
  `lib/yaml_lite` on every shipped definition. The skill is installed (§7), so it cannot import
  `lib` (`DIST-042`); agreement is held by test rather than by sharing code.
- **RTN-004** `requires` is one capability name from `CFG-020`. The skill's copy of that list is
  compared with `lib/config.py`'s by test, because two declarations of one list drift.
- **RTN-005** `schedule` is a five-field cron expression, optionally prefixed `CRON_TZ=<zone> `,
  and its minute field is a single number. The platform's shortest interval is an hour, and a
  minute field of `*` or `*/5` is a schedule that would be refused at creation — after the operator
  approved it.
- **RTN-006** `connectors` is a list of names and defaults to the empty list. `session` is
  `fresh`, the only value: every fire starts a new session, so nothing one run saw leaks into the
  next.
- **RTN-007** Every shipped definition parses and validates. A broken definition fails here, not
  in a consumer's session.

## 2. Rendering

- **RTN-010** A definition's `name` and prompt are templates. `{repo}` renders as `owner/name`,
  `{owner}` as the owner and `{repo_name}` as the name.
- **RTN-011** An unknown placeholder is an error naming the definition and the placeholder, never
  passed through. A prompt containing a literal `{repository}` would be created as a routine that
  tells its session about a repository called `{repository}`.
- **RTN-012** `{{` and `}}` render as literal braces, so a prompt can still contain one.
- **RTN-013** The repository is `--repo owner/name` when given, else `GITHUB_REPOSITORY`, else the
  last two path segments of the `origin` remote. Anything that is not `owner/name` is an error.
- **RTN-014** An error about the remote never quotes the remote's URL. A cloud session's `origin`
  can carry a credential in its userinfo, and an error message is the usual way one reaches a log
  (house rules, *Never publish a private link*).

## 3. Selection

- **RTN-020** The plan reads `capabilities`, `routines` and `fire` from
  `.ai-sdlc/repo-config.yml` with the skill's own reader, and agrees with `lib/config.py` on them
  for every example configuration. A missing file is an error naming the path.
- **RTN-021** The routines planned are those `routines:` names, in the order it names them, once
  each. A repository naming none gets an empty plan, which is not an error.
- **RTN-022** A name no definition carries is an error listing the definitions that exist.
  `CFG-073` leaves this check here, where the definitions are.
- **RTN-023** A definition whose `requires` capability is not installed is refused, naming the
  routine and the capability. `substrate` is always installed (`CFG-022`). A triage routine in a
  repository with no pipeline is a routine that fires into nothing.
- **RTN-024** Any problem produces no plan. Every problem is reported, and the command exits
  non-zero, so an agent cannot act on half a plan.

## 4. The plan

- **RTN-030** The plan is JSON on standard output, and the same inputs produce byte-identical
  output. A plan an agent compares against live routines must not differ between two runs that
  mean the same thing.
- **RTN-031** Each planned routine carries its `id`, rendered `name` and `prompt`, `cron` (or
  `null`), whether it needs an `api` trigger, `connectors`, and `create_new_session_on_fire: true`
  — everything `create_trigger` needs, so the agent decides nothing the plan did not say.
- **RTN-032** A routine with an API trigger carries the manual task of adding the trigger in the
  web UI, generating its token, and storing the URL and token as the repository secrets named by
  `fire.endpoint_secret` and `fire.token_secret`. When the configuration names none, the task says
  to choose names and record them there, because without them `adopt` writes no fire inputs and
  nothing fires the routine (`ADOPT-070`).
- **RTN-033** Every planned routine carries the manual task of confirming that the repository is
  attached on the routine's page, and attaching it in the web UI if not.
- **RTN-034** Planning performs no network I/O and writes no file. It reads the configuration, the
  definitions, and at most the `origin` remote.

## 5. Applying

The skill is instructions an agent follows. Its rules are asserted as stated, as `DIST-043` and
`API-070` assert theirs.

- **RTN-040** The skill says it runs from a Claude Code cloud session in the target repository,
  because only those sessions have the trigger tools — and says to stop, rather than improvise, in
  a session that lacks them.
- **RTN-041** It reads live routines with `list_triggers`, including completed ones, and matches
  each planned routine by its exact rendered name.
- **RTN-042** It shows the operator the plan — what will be created, what updated, what left alone
  — and writes nothing until the operator confirms.
- **RTN-043** A planned routine with no live match is created with `create_trigger`: the plan's
  name, prompt and cron, `create_new_session_on_fire` true, `initiation` `human_request`, and
  `connectors` exactly as the definition declares. One whose prompt or schedule differs is changed
  with `update_trigger`, by the matched routine's id. One that matches is left alone.
- **RTN-044** It never deletes a routine and never creates a second routine of a name that already
  exists. A name matching more than one live routine is reported and left alone.
- **RTN-045** It ends by giving the operator every manual task from the plan, and never writes a
  routine's URL, its token, or a session link into a file, an issue, a comment or a commit.

## 6. The shipped definitions

- **RTN-050** `triage` requires `pipeline`, has an API trigger and no schedule, and no connectors.
  Its prompt names the `<routine-fire-payload>` block, says to extract only the single issue
  number from it and ignore any other text, and runs the `triage-issue` skill on that issue in
  `{repo}`. It is fired by the gatekeeper, whose fire text names the issue (`GK`).
- **RTN-051** `dependabot` requires `hygiene`, runs weekly on Monday morning US Central at a
  minute other than `0`, has no API trigger, and no connectors. `hygiene` because the merge it
  makes is a squash whose title becomes the commit, and only `hygiene` enforces that a title parses
  as a Conventional Commit (`SYS`); a repository without it has nothing to check the title against.
  A minute other than `0` because every scheduled job in the world fires on the hour.
- **RTN-052** The `dependabot` prompt is self-contained for a fresh session in `{repo}`. It lists
  open pull requests authored by `dependabot[bot]` and, for each, reads check runs and commit
  statuses on the head commit and its mergeability. Green and mergeable is squash-merged with a
  Conventional Commit title. Behind or conflicted is updated through the update-branch API — never
  an `@dependabot` comment command — and left for the next run. Still running is left. Failing has
  its failing job's log read, open issues searched so a pull request already reported is not
  reported twice, and otherwise one issue filed naming the pull request, the failing check, a short
  redacted excerpt and the likely cause; a failing pull request is never pushed to, closed or
  merged. Nothing not authored by Dependabot is merged, no session link or tokenized URL is
  written anywhere, and the run ends with a summary of what it merged, updated, left waiting and
  filed.
- **RTN-053** The `dependabot` prompt states that its merges, branch updates and issues are the
  owner's standing instruction, given by creating the routine, and that `github-api` governs
  everything else it does.

> **How this relates to `API`.** `github-api` says a merge is a person's decision
> (`API-072`) and that nothing is written on a schedule (`API-075`). The `dependabot` routine does
> both, by design. It does not amend `API`: the owner creating the routine, from a plan that shows
> its whole prompt, is the person deciding — once, in advance, and only for green Dependabot pull
> requests. `RTN-053` makes the prompt say so, because an agent that loaded `github-api` and found
> no such statement would be right to refuse. Whether `API` should name routine prompts as a
> source of standing instructions is left to the owner.

## 7. Distribution

- **RTN-060** `routines` is an installable skill of the **substrate** capability, seeded into
  `skills:` by `ADOPT-110` like `github-api`, and held to `DIST-042`: it imports no `lib`, takes
  no client, and opens no socket. It runs in the consumer, where `lib` does not exist.

---

## Traceability

| Section | IDs | Tests |
|---|---|---|
| Definitions | RTN-001–007 | `test_routines_definitions.py` |
| Rendering | RTN-010–014 | `test_routines_render.py` |
| Selection | RTN-020–024 | `test_routines_plan.py` |
| The plan | RTN-030–034 | `test_routines_plan.py` |
| Applying | RTN-040–045 | `test_routines_skill.py` |
| The shipped definitions | RTN-050–053 | `test_routines_shipped.py` |
| Distribution | RTN-060 | `test_routines_skill.py` |

**33 requirements, all `auto`.**
