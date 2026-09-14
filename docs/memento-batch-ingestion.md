# Memento rename and session batch ingestion

Memento is the public product name and canonical command; the Python package
is `memento` throughout. `memory` and `session-rag` were both prior names —
their config paths and `MEMORY_CONFIG`/`SESSION_RAG_CONFIG` environment
variables remain as legacy fallbacks, but neither is an installable command
alias anymore.

The `import-sessions` command discovers Claude transcripts from an explicitly
selected registered project (`--project ID` or `--project current`) or every
registered project (`--all-projects`). Cursor conversations are imported in a
separate invocation from a read-only snapshot of Cursor's local search index.
The command supports dry runs, date filtering, and explicit retry of recorded
failures. Every source still passes through sanitization, structured
extraction, immutable artifacts, active revision selection, and the shared
LanceDB rebuild.

Cursor's opaque root fingerprint is not treated as trusted project identity.
Cursor records remain unscoped and require explicit global retrieval.
There is no combined `--source all` option because it would mix scoped Claude
counts with unscoped Cursor counts.
