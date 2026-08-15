---
name: label-sync
description: Apply a repository's label taxonomy from two manifests in git — the shared core vocabulary and the repository's own labels. Use when adding or changing a label, adopting the labels capability, or when labels have drifted from what the manifests describe.
allowed-tools: Bash, Read
---

# Label sync

The label taxonomy is the pipeline's state machine. It lives in git and is applied from there,
rather than being clicked into the GitHub interface where nothing records what it should be or
notices when it drifts.

## Two manifests

| File | Owner | Contents |
| --- | --- | --- |
| `labels.core.yml` | ai-sdlc, pinned | pipeline states, `skip-docs`, `no-closing-keyword`, `type:epic` |
| `labels.repo.yml` | this repository | `area:*` and anything local |

Separate files, not sections of one, so upgrading the core never conflicts with your own labels.
A label defined in both is an error — the effective taxonomy would otherwise depend on load order.

## Applying

```bash
GITHUB_TOKEN=... GITHUB_REPOSITORY=owner/repo \
  python3 .claude/skills/label-sync/label_sync.py .github
```

Idempotent: a second run makes no requests at all. Safe to run on every push.

## What it will and will not do

| | |
| --- | --- |
| In the manifest, missing from the repository | created |
| In both, colour or description differs | updated |
| In both, identical | untouched — no request made |
| In the repository, not in the manifest | **left alone** |
| Listed under `delete:` | deleted |

**Nothing is deleted unless you list it under `delete:`.** Repositories accumulate labels for
reasons a manifest cannot see, and deleting one strips it from every issue that carried it,
irreversibly. That is never an implicit consequence of editing a file.

## Every label needs a description

A label with no description is refused. An undescribed label is one whose meaning lives only in
whoever created it — which is exactly the drift this capability exists to stop.

Colours are six hex digits with no `#`.

Specification: `docs/spec/labels.md` (`LBL`), 25 requirements.
