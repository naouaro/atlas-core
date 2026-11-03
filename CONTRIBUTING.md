# Contributing to Atlas Core

Thanks for your interest! Atlas Core aims to stay small, readable, and
dependency-light. Contributions that keep it that way are very welcome.

## Dev setup

```bash
pip install -e ".[dev,local,langchain]"   # core + tests + offline model + langchain adapter
pytest -q                                  # run the suite (offline; no cloud needed)
ruff check .                               # lint
```

The test suite runs fully offline (hashed local embeddings + `NullLLM`), so no API
keys or network are required.

## Ground rules

- **Keep the core generic.** `atlas_core/` must stay domain-agnostic — no company,
  dataset, or deployment specifics. Provider/store integrations go behind the existing
  interfaces (`providers/`, `store/`).
- **Add a test** for any behavior change; keep it offline and deterministic.
- **Run `ruff check .` and `pytest -q`** before opening a PR — CI runs both on 3.10 and 3.12.
- Prefer small, focused PRs with a clear description of the problem and the fix.

## Design seams

- New data source → write an `Ingester` (`atlas_core/ingest/`).
- New embedding/LLM backend → implement the `providers/base` ABCs.
- New storage → implement `store/base.VectorStore`.

By contributing you agree your contributions are licensed under the project's
Apache-2.0 license.
