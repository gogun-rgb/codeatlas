# Validation and Cross-Check Record

This record documents engineering validation for CodeAtlas. It is not marketing copy, and passing tests were not treated as proof by themselves.

## Initial Implementation

The initial MVP implementation completed the normal local verification workflow.

Observed initial test snapshot:

- backend tests initially reported 14 passed
- frontend tests initially reported 3 passed

That result established a working baseline, not complete correctness.

## Independent Cross-Check

An independent cross-check review returned:

```text
REVISION_REQUIRED
```

Verified findings included:

- P1: duplicate symbol node IDs were not collision-safe
- P1: Python `from . import scoring` could create a false `IMPORTS` edge to `pkg/__init__.py`
- P2: JavaScript and TypeScript extension resolution was too naive
- P2: parser errors existed in graph metadata but were not visible in the Inspector
- P2: tests did not cover the risky documented cases

## Revision

The revision addressed those findings with focused implementation changes:

- deterministic collision-safe symbol IDs
- container scope and source-position identity for symbols
- corrected Python relative import alias handling
- language-aware JavaScript and TypeScript resolution
- `index.ts`, `index.tsx`, `index.js`, and `index.jsx` candidate support
- explicit `.js` and `.jsx` specifier mapping for supported TypeScript source cases
- parser warning UI in the Inspector
- adversarial regression coverage for duplicate symbols and import edge cases

## Revision Verification

Independent reproduction evidence after the revision included:

```text
DUPLICATE_RENDER_IDS_UNIQUE True
DUPLICATE_NODE_IDS_STABLE True
EDGE_IDS_UNIQUE True
CONTAINS_COVERS_ALL_SYMBOLS True
PY_FALSE_INIT_EDGE False
```

Focused Python import resolution produced the expected internal targets:

```text
pkg/scoring.py
pkg/weights.py
pkg/services/user.py
```

No false package `__init__.py` import edge was produced for the reproduced defect.

Final independent revision verdict:

```text
PASS
```

## Operational Hardening

Optional `GITHUB_TOKEN` support was added after a live unauthenticated GitHub API rate-limit test.

Validation points:

- the token is read only by the server-side GitHub repository loader
- no `Authorization` header is sent when `GITHUB_TOKEN` is absent
- authenticated requests include the expected GitHub API authorization header
- token values are not returned in repository snapshots
- token values are not exposed to frontend response models
- token values are not included in rate-limit error messages

The feature improves GitHub API rate-limit headroom for local public-repository analysis. It does not change the public-repository-only MVP scope.

## Current Verification Snapshot

After the graph-first quality revision, the actual local verification workflow was run:

```bash
pnpm run verify
```

Observed result:

- Ruff passed
- mypy passed
- pytest collected 44 backend tests and all passed
- ESLint passed
- TypeScript checking passed
- Vite production build passed
- Vitest ran 5 frontend test files / 7 tests and all passed

The GitHub Actions `Verify` workflow runs the same normal verification command on push and pull request. Remote CI evidence for unpushed local changes is not available until those changes are pushed.

## Graph-First Quality Revision

The focused revision strengthened the existing MVP without adding new product scope.

Implemented and tested changes:

- React Flow graph layout is explicitly non-editable; selection, highlighting, zooming, panning, minimap, controls, filtering, and fit behavior remain.
- `/api/analyze` and `/api/demo` return opaque `analysis_id` values.
- `/api/question` uses server-owned analysis state from a bounded in-memory TTL cache and rejects client-supplied graph payloads.
- GraphSearch v2 adds deterministic query normalization, small explicit concept expansion, lexical seed retrieval, bounded two-hop graph expansion, structural reranking, stable tie-breaking, and beginner-readable deterministic answers.
- Optional AI explanation remains below the graph result and is discarded when structured path or symbol references fail validation.
- GitHub blob loading uses bounded asynchronous concurrency with deterministic final file ordering and ordered total source-size enforcement.
- JavaScript and TypeScript export regression coverage now includes default function/class exports and export aliases such as `foo as bar` and `foo as default`.
- MIT `LICENSE` was added after checking that no existing license or conflicting project constraint was present.

Focused evidence before final verification:

- Backend focused suite: 44 passed.
- Frontend focused suite: 5 files / 7 tests passed.
- Backend Ruff and mypy passed.
- Frontend ESLint passed.
- Frontend TypeScript/Vite build passed outside the filesystem sandbox after sandboxed config resolution was denied.
