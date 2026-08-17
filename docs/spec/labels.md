# Specification — Labels (`LBL`)

The label taxonomy is the pipeline's state machine. It therefore lives in git and is applied from
there, rather than being clicked into the GitHub interface where nothing records what it should be
or notices when it drifts.

`LBL` belongs to the **labels** capability and depends only on the substrate. The taxonomy itself
is configuration, so a repository with no pipeline can still use this to keep its labels described
in one place.

Every requirement below is `auto` (covered by a named test) unless marked otherwise.

---

## Invariants

> **Invariant — a label is deleted only when explicitly listed for deletion.** Labels absent from
> the manifest are left alone. Deleting a label strips it from every issue that carried it and
> cannot be undone, so it is never an implicit consequence of editing a file.

> **Invariant — the core manifest is identical across consumers.** The pipeline's shared code reads
> these names; a repository that redefines one has a pipeline that does not work, while appearing
> adopted.

> **Invariant — sync is idempotent.** Running it twice changes nothing the second time, so it is
> safe on every push rather than something to run carefully.

---

## 1. The two manifests

- **LBL-001** `labels.core.yml` holds the shared vocabulary and is installed, pinned, and not
  hand-edited.
- **LBL-002** `labels.repo.yml` holds a repository's own labels and is hand-written.
- **LBL-003** The applied taxonomy is the union of the two.
- **LBL-004** Separate files rather than sections of one, so an upgrade to the core never produces
  a merge conflict with local labels.
- **LBL-005** A label defined in both is an error naming the label and both files. Silently
  preferring one would make the effective taxonomy depend on load order.
- **LBL-006** A missing `labels.repo.yml` is not an error; a repository may add nothing.

## 2. What a label needs

- **LBL-010** Every label has a name, a colour and a description.
- **LBL-011** A missing description is an error. An undescribed label is one whose meaning lives
  only in whoever created it.
- **LBL-012** A colour is six hexadecimal digits, without a leading `#`.
- **LBL-013** An invalid colour is an error naming the label.
- **LBL-014** Two labels may not share a name.

## 3. Applying

- **LBL-020** A label in the manifest but not the repository is created.
- **LBL-021** A label in both whose colour or description differs is updated.
- **LBL-022** A label already matching is left untouched, and no request is made for it.
- **LBL-023** A label in the repository but not the manifest is left alone.
- **LBL-024** A label listed under `delete:` is deleted if it exists.
- **LBL-025** A label under `delete:` that does not exist is not an error.
- **LBL-026** A label that is both defined and listed for deletion is an error.
- **LBL-027** Applying twice makes no changes the second time.
- **LBL-028** The result reports what was created, updated, deleted and unchanged.

## 4. The core vocabulary

- **LBL-030** The core manifest defines every pipeline state label.
- **LBL-031** It defines the control labels the shared workflows read: `skip-docs` and
  `no-closing-keyword`.
- **LBL-032** It defines `type:epic`, which the gatekeeper's scope rules read.
- **LBL-033** Every state in the configuration schema has a label in the core manifest, checked by
  test rather than by eye.
- **LBL-034** The core manifest contains no `area:*` label, since those are always
  repository-specific.

---

## Traceability

| Section | IDs | Tests |
|---|---|---|
| The two manifests | LBL-001–006 | `test_label_manifest.py` |
| What a label needs | LBL-010–014 | `test_label_manifest.py` |
| Applying | LBL-020–028 | `test_label_sync.py` |
| The core vocabulary | LBL-030–034 | `test_label_core.py` |

**25 requirements, all `auto`.**
