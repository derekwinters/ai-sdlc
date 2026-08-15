# ai-sdlc — Migration Plan and Evidence

Companion to the design doc. This is the *transitional* document: why ai-sdlc is being built, what
the existing implementations contain, the decisions taken and their justification, and the order of
work. It is expected to become obsolete once migration completes; the durable parts graduate to
`docs/decisions/` in ai-sdlc.

---

## 1. Why

The pipeline exists twice — in `lucas-doggiehood` and in `connor-multiplying-frogs` — and the two
copies have diverged. Fixes made in one were re-made by hand in the other. The port to connor was
carried out as "copy the process from lucas into this repo", which an agent executed as *read the
documentation and rebuild it*, so the two are independent implementations of the same design rather
than a copy and a fork.

Evidence — function-name overlap in the four largest shared files:

| File | doggiehood defs | connor defs | shared names |
|---|---|---|---|
| `parse_commands.py` | 9 | 7 | **0** |
| `release_flow.py` | 32 | 8 | 1 |
| `reconcile.py` | 14 | 11 | 2 |
| `render_dashboard.py` | 24 | 24 | 2 |

All 42 shared files differ, and all 42 still differ after normalising repository, project, and
child names away. Nothing was copied.

## 2. Neither implementation is the standard

| Skill | impl LOC (dogg/connor) | defs | tests | Ahead |
|---|---|---|---|---|
| pipeline-gatekeeper | 1492 / **1808** | 37 / **66** | 95 / **240** | **connor**, decisively |
| triage-issue | 66 / **374** | 2 / **11** | 15 / **60** | **connor**, decisively |
| issue-blockers | 169 / **257** | 12 / 13 | 7 / **34** | **connor** |
| pipeline-dev | 132 / **187** | 4 / **8** | 12 / **33** | **connor** |
| scaffold-core | 112 / **192** | 3 / **9** | **0** / **24** | **connor** (doggiehood untested) |
| ci-watch | **0** / 248 | 0 / 10 | **0** / 20 | **connor** (doggiehood prose-only) |
| pipeline-reconcile | **627** / 279 | **14** / 11 | **99** / 42 | **doggiehood** |
| release-flow | **507** / 205 | **32** / 8 | **46** / 22 | **doggiehood** |
| pipeline-dashboard | **886** / 611 | 24 / 25 | 71 / **75** | doggiehood implementation; connor holds fix #293 |
| milestone-ops | **227** / 181 | **16** / 11 | 16 / 15 | doggiehood, marginally |
| pipeline-analysis | **137** / 100 | 4 / 4 | 15 / **18** | too close to call |

Totals: **376 tests in doggiehood, 583 in connor.**

LOC and test counts are proxies. Two entries are not: doggiehood has zero tests for
`scaffold-core` and zero code for `ci-watch`. On the gatekeeper, connor leads on all three
measures simultaneously.

**Conclusion.** `lucas-doggiehood` is the standard for the *process and its documentation*. It is
not the standard for the *implementations*. Neither repository is adopted as canonical source;
both are treated as requirements input, and ai-sdlc is built spec-first from their union.

*Caveat:* both clones are shallow (50 commits), so history-derived claims are incomplete. The
structural evidence above does not depend on history.

## 3. Fixes to carry forward from connor

Three commits touched connor's skills after the port:

- **#293** — the dashboard shows every issue needing attention, not only the focus milestone's.
- **#306** — the auto-revisit sweep no longer re-wakes an issue forever.
- **#307** — a gate refusal explains itself instead of crashing.

Structural properties to carry forward regardless of which implementation wins on logic:

- A real GitHub client (`_github_api.py`, 10 functions: pagination with a runaway cap, ordered
  results, empty- and null-page safety, label and milestone writes, watermarking) rather than a
  two-function request helper. This is the seam that makes offline testing possible.
- Dataclasses at every stage boundary rather than dictionary passing.
- Gate logic factored into its own module with a `Verdict` type, rather than embedded in command
  parsing.
- Graceful degradation: a failing sub-request degrades the result rather than discarding it.
- Architectural tests asserting that pure-logic modules cannot reach the network.

## 4. Capabilities present in only one implementation

**Connor only.** Sweep comment-replay: owner commands issued while no webhook fired are replayed
on the cron pass, bounded by a window, ordered ascending, gathered in one repository-wide call.
**Not adopted** — superseded by per-issue catch-up, `/retry`, and dashboard visibility. See §5.1.
The problem it solved is real; the mechanism is replaced by a cheaper one.

**Doggiehood only.** Separable acknowledgement concerns (`milestone_write_for`, `render_skip_ack`,
`reactions_for`); deeper revisit coverage over mixed wireframe and ordinary blocker sets, including
stability across repeated sweeps; and a more evolved approve/milestone policy.

## 5. Behavioural contradictions and their resolutions

All five are **resolved**. Decided by Derek, 2026-08-15.

| # | Question | Resolution |
|---|---|---|
| C1 | Which reaction is the watermark? | **Three states.** 👀 on sight; upgraded to 👍 when action was taken, 👎 when refused. |
| C2 | Is a refused command watermarked? | **Yes** — 👎. |
| C3 | Does a refusal reply? | **Yes**, a short reply only. |
| C4 | May `approve` carry an inline milestone? | **No.** `/milestone` then `/approve`, as doggiehood requires today. |
| C5 | Is sweep comment-replay core? | **No — the cron sweep is removed entirely.** See §5.1. |

The three-reaction scheme is load-bearing: it makes "unprocessed" a fact stored on GitHub rather
than something inferred from timestamps. A comment still showing a bare 👀 after its run should
have finished is a command that died mid-flight, and nothing else.

**Invariant — every owner command ends in exactly one of 👍 or 👎. A 👀 that outlives its run is a
visible fault, never a silent drop.**

### 5.1 Replacing the sweep

The scheduled sweep did three jobs. All three are removed or relocated.

| Job | Disposition |
|---|---|
| Comment replay | **Removed.** Replaced by per-issue catch-up on the next event for that issue, plus `/retry`, plus a read-only dashboard flag for lingering 👀. |
| Reconcile drift | **Event-driven.** Stale labels are stripped on `issues.closed`; merged work advances on `pull_request.closed`. Stalled `in-progress` with no PR has no event and becomes a read-only dashboard flag. |
| Blocker revisits | **Removed entirely.** See §5.2. |

Catch-up is scoped to the single issue whose event fired, so it cannot race another issue's
handler and needs no time window — the two properties that made replay conflict-prone.

### 5.2 Blockedness is derived, not stored

`select_queue.py` already excludes an issue whose hard blockers are open, in both implementations:

```python
open_blockers = [b for b in issue.get("blocked_by", []) if b in open_set]
if open_blockers:
    return False, "blocked by %s (open)" % joined
```

Eligibility is therefore recomputed from the live dependency graph on every run. An approved but
blocked issue is simply not selected, and becomes selectable again when its blocker closes, with
no action required from anything.

The revisit machinery existed because triage moved a blocked issue **out** of the pipeline into
`needs-clarification` — a state exitable only by Derek's comment — and a second mechanism was then
needed to move it back. The revisit module's own docstring records this. Storing blockedness as a
label denormalises a fact GitHub tracks live, and the sync mechanism for that copy is precisely
the machinery being deleted.

**Invariant — blockedness is derived from the dependency graph at selection time, never stored as
a label. An issue is never moved out of its state because it is blocked.**

Removed as a consequence: `check_revisits.py` and its 22 doggiehood / 25 connor tests; the
`issues.labeled` workflow; the wireframe carve-out; and connor's fix **#306**, which was a defect
*in* the revisit machinery rather than in the pipeline.

`needs-clarification` is retained for its true meaning — a human must answer a question. It is no
longer used for blockedness. The dashboard reports blockedness as derived, read-only state.

### 5.2a Missing closing keywords — prevent, don't reconcile

Pull requests merging without a `Closes #N` keyword is the condition the reconcile process was
largely built to clean up: the issue stays open in `in-progress`, and nothing ever moves it.
Both repositories' CLAUDE.md already require the keyword (rule #10); nothing enforces it.

**Enforced at the pull request, not repaired afterwards.** The shared pull-request lint workflow
gains a `closing-keyword` check: a pull request whose body carries no `Closes`/`Fixes`/`Resolves
#N` fails, with the `no-closing-keyword` label as the deliberate escape hatch — the same shape as
the existing `skip-docs` opt-out.

The check is a **required status check** on every consumer's default branch, so a pull request
cannot merge without either a closing keyword or the explicit label.

**Implementation constraint — the check always runs and passes when the label is present; it is
never skipped.** A workflow-level `if:` that skips the job leaves a required check permanently
pending, which blocks the merge rather than allowing it. The label must produce a *passing* run,
not an absent one.

Enabling the required check is repository-admin work and cannot be done by an agent: one
`Direct Involvement Needed` issue per consumer repository, each naming the check and how to verify
it.

This removes the drift class rather than detecting it, and it makes GK-103 honest: after the gate
exists, a keyword-less merge is genuinely a decision rather than an oversight.

### 5.2b Milestone operations — the missing half

`milestone-ops` exists in both repositories because the GitHub MCP server exposes no milestone
CRUD at all. Its own heading calls it "milestone CRUD the MCP server doesn't have", but neither
implementation has the C or the U:

| Operation | doggiehood | connor |
|---|---|---|
| list / number / count | yes | yes |
| close (refusing on open work) | yes | yes |
| reopen | yes | yes |
| **create** | **no** | **no** |
| **edit** (title, description, due date) | **no** | **no** |

Milestone creation is therefore hand-worked or skipped, which is the reported problem. It matters
more than it looks: the focus milestone is matched live **by description**, and connor's
`is_frozen(description)` overloads the same field, so a milestone created without the right
description is invisible to the pipeline that is supposed to consume it.

**The `MS` spec covers create and edit as first-class operations**, including the description
convention, with the same refusal discipline the existing operations use (close refuses while open
work remains). Connor's frozen-milestone concept is carried forward.

### 5.2c Capabilities, not a monolithic core

The original three-layer model had a single "universal core" holding both general machinery
(distribution, Conventional Commits, spec/test consistency) and the specific issue pipeline. That
made adoption all-or-nothing: a repository wanting only the consistency gates had to take an
opinionated issue lifecycle with it.

The core is therefore split into six independently installable **capabilities**, ordered by how
much each assumes — substrate, hygiene, consistency, labels, release, pipeline. The pipeline, the
part encoding "AI triages, a human approves, AI builds", is the top layer rather than the centre,
because it is the most opinionated element and the least likely to suit anyone else.

**A latent defect prompted this.** GK-054 refused `/approve` when a blocker sat in a milestone
whose title could not be ordered, and GK-061 ordered titles by semantic version. Against a
standing non-version milestone — `Direct Involvement Needed`, which this project uses — that made
any issue natively blocked by a human-task issue permanently unapprovable, with a refusal message
pointing at ordering rather than at the cause. The behaviour exists in both current
implementations; connor has a test asserting it.

The fix generalises rather than special-cases. Milestone ordering becomes a configured strategy
(`semver`, `date`, `lexical`, `none`), and the gate refuses only on evidence of inversion, never
on absence of evidence; unorderable blockers are reported on the dashboard instead. Owner
authority likewise becomes a list, of which a single owner is a list of one.

That the generalisation also fixed a real bug for the first consumer is the test to apply to any
further generalisation proposed here. Configuration that describes how a repository differs earns
its place; configuration that forks behaviour is a sign a separate capability is wanted.

### 5.3 Actor identity

Pipeline writes are authored by a bot, never by Derek's account.

Default: the built-in `GITHUB_TOKEN`, authoring as `github-actions[bot]`. A custom GitHub App is
supported by configuration, without a code change:

```yaml
bot:
  identity: github-actions      # or: app
  app_id_secret: SDLC_APP_ID    # only when identity: app
```

`claude[bot]` (GitHub App 209825114, `https://github.com/apps/claude`) is Anthropic's App. A token
for it is minted only when Claude Code itself runs through that App, so deterministic workflow
scripts cannot author as it. LLM-authored content — triage analyses, issue reports, PR bodies —
continues to appear as `claude[bot]`; mechanical state changes appear as the pipeline bot. The
distinction is deliberate and visible.

Two consequences for the gatekeeper: the watermark is a reaction **by the configured bot
identity**, not by any user; and the bot's own comments are never treated as commands.

### 5.4 Resulting workflow set

| Workflow | Trigger | Responsibility |
|---|---|---|
| `gatekeeper-comment` | `issue_comment` | parse, gate, apply, watermark, acknowledge, per-issue catch-up |
| `gatekeeper-close` | `issues.closed` | strip stale pipeline labels |
| `gatekeeper-merge` | `pull_request.closed` | advance the issue the pull request closed |
| `dashboard` | `schedule` | read-only render: blocked, lingering 👀, stalled `in-progress` |

No scheduled job writes to an issue. Every write is a reaction to an action taken by Derek or by
CI.

## 6. Order of work

1. **Pilot — `pipeline-gatekeeper` end to end.** Spec, tests, implementation, docs page, all six
   CI gates, a pre-release published with `gh skill publish`, installed into one consumer and
   verified. Chosen because it is the most contested component, the most central, and it exercises
   every structural question while they are still cheap to change.
2. **Freeze the shape.** Spec format, fake-GitHub layer, config schema, gate set — revised from
   what the pilot teaches.
3. **Remaining core skills**, most-contested first: triage-issue, pipeline-dev, pipeline-dashboard
   (carrying #293), pipeline-reconcile, issue-blockers, ci-watch, milestone-ops, release-flow,
   pipeline-analysis.
4. **Profiles** — `unity`, then `mkdocs`, then the per-runtime CI modules.
5. **Workflows** — extract to reusable `workflow_call`; replace consumer copies with callers.
6. **CLAUDE.md split** — shared fragment plus `@import`; per-repo specifics stay hand-written.
7. **Consumer adoption**, one repository per pull request: doggiehood and connor first, then
   chores-web, then roadtrip.

## 7. Relationship to `ai-skills`

`ai-skills` built a sync engine (`distribution/sync.py` plus `registry.yml`) to solve
distribution. `gh skill` now solves the same problem natively, including provenance and pinning,
and its `skills/{scope}/` discovery convention supplies the profile layer without a registry.

**Recommendation:** ai-sdlc supersedes the ai-skills distribution machinery. What carries forward
is the generic `dev` agent and the decisions captured in its issues. Disposition of trackers
`ai-skills#18`, `#8`, `#24` and their per-repo sub-issues is pending Derek's decision.

## 8. Out of scope

- Cross-repository project management and reporting — deferred.
- Enabling "Allow GitHub Actions to create and approve PRs"; self-updaters remain off.
- Any change to product or application code in any consumer.
- Unifying the issue-flow model across families. The design supports both a scheduled autonomous
  pipeline and an on-demand one; that choice is deferred and does not block the pilot.

## 9. Open questions

- **Q1** — C1 to C5 above. Blocks the gatekeeper spec.
- **Q2** — Disposition of the ai-skills trackers (§7).
- **Q3** — Issue-flow unification: all repositories onto the scheduled pipeline, or full automation
  for the games and a lighter model for chores-web and roadtrip?
- **Q4** — Claude Code scheduled routines versus GitHub Actions for the deterministic steps.
- **Q5** — Does ai-sdlc run its own development under the pipeline it is building?
