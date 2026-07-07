# Contributing

Thanks for taking care with CodeAtlas. Keep changes focused and preserve the graph-first security boundaries.

## Development Setup

Install backend dependencies with the beginner-friendly pip path:

```bash
python -m pip install -e "backend[dev]"
```

For CI-equivalent backend dependency resolution, use the committed `backend/uv.lock`:

```bash
uv sync --project backend --extra dev --frozen
```

CI points `CODEATLAS_PYTHON` at the `backend/.venv` interpreter created by `uv`; the pip setup remains the simplest local path for `pnpm run verify`.

Install frontend dependencies:

```bash
pnpm install
```

Run the app:

```bash
pnpm run dev
```

## Verification

The normal completion gate is:

```bash
pnpm run verify
```

Do not claim completion before the required verification passes.

## Architecture Principles

Contributions must preserve:

- no target repository execution
- deterministic graph generation
- deterministic retrieval remains the source of truth
- AI must not replace deterministic scoring
- AI references must remain server validated
- client graph input must not become authoritative

## Tests

Bug fixes require regression tests when reasonably reproducible. Tests must not be deleted, skipped, weakened, or replaced with empty checks merely to make CI pass.

Risky parser, import, graph identity, cache isolation, AI validation, and request-boundary cases should use adversarial fixtures.

## Scope

Broad language support and call-graph features materially change analysis semantics. Discuss those before large implementation changes.
