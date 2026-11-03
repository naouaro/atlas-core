# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project adheres to
semantic versioning.

## [0.2.0]

### Added
- **Chunking** — `chunk_text()` plus opt-in `DocumentIngester(chunk_chars=…)` that
  splits long documents into overlapping chunk child-nodes (linked `chunk_of` to the
  parent) so buried passages stay retrievable. Language-agnostic.
- **Hybrid search** — `Atlas.search(..., hybrid=True, alpha=…)` reranks the vector
  candidates by blending cosine with lexical token-overlap; helpful when exact terms
  matter, and multilingual-safe.
- **Turkish support** — `atlas_core.textnorm.fold()` (Turkish-safe casefolding: `İ↔i`)
  wired into glossary matching, cluster labels, and the hashed tokenizer.
- **Glossary** — `Glossary` maps business terms/aliases to nodes; `expand_query()`
  enriches a query before embedding (`Atlas.search(..., expand=glossary)`).
- **LangChain adapter** — `atlas_core.integrations.langchain.atlas_search_tool`.
- Packaging: `[project.urls]`, authors, trove classifiers; `ruff` config + CI
  (GitHub Actions, Python 3.10/3.12).

### Changed
- **License: MIT → Apache-2.0** (explicit patent grant).
- **Clustering scales** — uses `MiniBatchKMeans` for large maps (bounded memory, far
  faster) and plain `KMeans` for small ones.

### Fixed
- **`upsert_links` is now idempotent** — re-syncing the same edges replaces them
  instead of appending, so a scheduled sync no longer grows the links table without
  bound (both the pgvector and in-memory stores).

## [0.1.0]

- Initial release: ingest → embed → cluster → summarize → narrate → semantic search;
  pluggable providers (Local / Bedrock / OpenAI) and stores (in-memory / pgvector);
  incremental `sync()`; `SqlIngester`; tenant/group scoping; scheduled-sync deploy recipe.
