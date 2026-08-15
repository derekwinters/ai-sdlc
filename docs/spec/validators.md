# Specification — Consistency (`VAL`)

The specification, the tests, the skills and the published documentation describe one system. They
stay describing one system because these validators fail the build when they stop.

Documented intentions decay. A rule that nothing checks is a rule that is true on the day it is
written and slowly stops being true afterwards, with no moment at which anyone notices. Every gate
here exists because the alternative is a document that lies.

`VAL` belongs to the **consistency** capability and depends only on the substrate.

Every requirement below is `auto` (covered by a named test) unless marked otherwise.

---

## Invariants

> **Invariant — a requirement that no test references is a build failure, not a warning.** A
> specification nobody verifies is a wish.

> **Invariant — a validator reports every problem it finds, not the first.** Fixing a repository
> one error per run wastes the run.

> **Invariant — a validator never edits.** It reports and exits non-zero. Repair is a human or an
> agent decision, never a side effect of checking.

---

## 1. Requirement identifiers

- **VAL-001** A requirement is declared as `- **AREA-NNN** …` in a specification page, where
  `AREA` is uppercase letters and `NNN` is digits.
- **VAL-002** Every requirement identifier is unique across every specification page.
- **VAL-003** A duplicate identifier is reported with both locations.
- **VAL-004** A specification page declares its area, and every requirement on it belongs to that
  area.
- **VAL-005** Identifiers within an area need not be contiguous; gaps are deliberate and are not
  reported.

## 2. Specification and tests

- **VAL-010** A requirement is covered when a test file names it in a test name, a comment, or a
  docstring.
- **VAL-011** An uncovered requirement is reported with its identifier and page.
- **VAL-012** A requirement explicitly marked `*(manual: …)*` is exempt, and its reason is
  required.
- **VAL-013** A `manual` marker with no reason is reported: an exemption without a justification
  is an unexplained gap.
- **VAL-014** A test naming an identifier in a **declared area** that no specification declares is
  reported: that is either a typo or a requirement someone deleted. An identifier in an unknown
  area is ignored, because flagging every identifier-shaped string produces noise that trains
  people to ignore the output.
- **VAL-015** The count of requirements, covered and manual, is reported on success, so a
  shrinking specification is visible.
- **VAL-016** A page may declare itself `> **Status — planned (#N).**`, exempting its requirements
  from coverage until it is implemented. Specifying an area before building it is the process
  working, not a gap to hide; the marker makes the debt explicit and dated.
- **VAL-017** A planned marker without an issue number is reported. An exemption with no
  reference is one nobody will ever come back to.
- **VAL-018** Planned requirements are counted separately in the summary, so the size of the
  unimplemented specification is visible rather than blended in.

## 3. Specification and documentation

- **VAL-020** Every page under `docs/spec/` appears in the site navigation.
- **VAL-021** A navigation entry pointing at a missing page is reported.
- **VAL-022** Every specification page states which capability owns it.
- **VAL-023** A capability named by a specification page is one of the six.

## 4. Capability boundaries

- **VAL-030** A module belonging to one capability may import only from capabilities at or below
  its own level.
- **VAL-031** An upward import is reported with the importing module, the imported module, and
  both capabilities.
- **VAL-032** The capability of a module is determined by its path; a module outside any
  capability directory belongs to the substrate.
- **VAL-033** The dependency order used here is the one declared in `lib/config.py`, not a second
  copy.

## 5. Running

- **VAL-040** Each validator is a script runnable alone, with no arguments, from the repository
  root.
- **VAL-041** Each exits `0` when clean and `1` when not.
- **VAL-042** Each prints a summary line even when clean, so a passing run is evidence rather than
  silence.
- **VAL-043** The validators use only the standard library, so a consuming repository of any stack
  can run them.
- **VAL-044** A validator's own output is stable between runs given the same inputs, so it is
  usable in a diff. *(manual: ordering is asserted; determinism across environments is observed in
  CI.)*

---

## Traceability

| Section | IDs | Tests |
|---|---|---|
| Requirement identifiers | VAL-001–005 | `test_validate_specs.py` |
| Specification and tests | VAL-010–018 | `test_validate_specs.py` |
| Specification and documentation | VAL-020–023 | `test_validate_docs.py` |
| Capability boundaries | VAL-030–033 | `test_validate_boundaries.py` |
| Running | VAL-040–044 | `test_validators_run.py` |

**29 requirements, 28 `auto` and 1 `manual`.**
