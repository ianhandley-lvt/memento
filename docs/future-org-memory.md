# Future goal: organization-wide Memory

Status: exploratory future direction. This document records a possible
destination; it does not expand the current local-first implementation scope.

## Goal

Evolve Memory from a personal, local RAG into a permission-aware organizational
memory service. Authorized users and AI agents should be able to retrieve
relevant knowledge learned across the organization instead of relying only on
records stored on one developer's computer.

Potential shared sources include:

- Sanitized developer-session knowledge
- Curated engineering documentation and architectural decisions
- Repository documentation and runbooks
- Incident investigations and operational resolutions
- Approved content from systems such as Notion, Confluence, Jira, or Slack

The benefit is shared learning: when one person resolves a difficult problem,
the evidence-backed resolution can become available to authorized teammates
without requiring them to repeat the investigation.

## This is RAG, not model training

The future system would continue to store knowledge outside the language model.
It would retrieve authorized evidence at prompt time and provide that evidence
to Claude or another model. It would not update the model's weights or require
training a local LLM.

This distinction preserves properties that matter for organizational knowledge:

- Facts can be updated or deleted immediately.
- Retrieval can enforce user and project permissions.
- Answers can retain citations to their original sources.
- The knowledge layer remains independent of the model consuming it.
- Changing operational knowledge does not require another training run.

Extraction models may structure source material, embedding models may support
semantic search, and reasoning models may consume retrieved evidence. None of
those operations are model training.

## Target shape

Developers should not connect directly to a shared database. They should use an
authenticated Memory service:

```text
Local or managed source
    -> sanitize and structure
    -> authenticated Memory API
    -> immutable shared artifacts
    -> metadata and lifecycle state
    -> hybrid search index

Claude hook
    -> user identity + trusted project scope
    -> Memory API
    -> permission filtering
    -> hybrid retrieval and ranking
    -> cited evidence
    -> Claude
```

The service would likely need:

- An authenticated API as the only client entry point
- Durable, immutable, content-addressed extraction artifacts
- Metadata for source revisions, verification state, temporal scope, duplicate
  links, ownership, and access policy
- A rebuildable hybrid semantic and exact-text search index
- Server-side validation of uploaded records and provenance
- Organization identity integration and authorization checks
- Auditability and enforceable deletion
- Local caching and fail-open hook behavior

The exact AWS products are deliberately undecided. The architecture should be
selected after workload, security, operational, and cost requirements are
measured rather than starting with a database choice.

## Retrieval scopes

Organization-wide Memory must not mean that every user can search every record.
Likely scopes include:

- **Personal:** private knowledge available only to its owner
- **Project or team:** knowledge available to members of a defined group
- **Organization:** approved knowledge available broadly
- **Restricted:** sensitive operational, security, customer, legal, or people
  information available only under narrower policies

Authorization must be enforced by the service before results leave it. Prompt
instructions are not a security boundary, and prompt text must never be able to
widen its own retrieval scope.

## Why not a shared database on every laptop

Giving each developer direct credentials to a central database would expose
implementation details and weaken important controls:

- Clients could bypass validation and lifecycle rules.
- Schema changes and concurrent writes would be difficult to coordinate.
- Database credentials would be distributed across developer machines.
- Permission filtering could be applied inconsistently.
- Sharing only a vector index would lose the immutable artifact and provenance
  model; the index is derived state, not the system of record.

The stable client contract should be a versioned synchronization and retrieval
API, not direct access to storage schemas.

## Suggested path

### 1. Validate the local system

Measure retrieval usefulness, irrelevant-injection rates, citation fidelity,
duplicate rates, latency, and extraction cost. Resolve weaknesses before
increasing the number of users and sources.

### 2. Define synchronization semantics

Specify how immutable artifacts and mutable lifecycle overlays are uploaded,
downloaded, versioned, deduplicated, superseded, and erased. Preserve local
operation while making synchronization optional.

### 3. Pilot an authenticated service

Start with a few trusted users, one project, and a narrow source set. Put an API
in front of all shared storage and validate records at the boundary.

### 4. Add permission-aware retrieval

Integrate organization identity and make every query carry a trusted user and
project scope. Test explicitly for cross-project and revoked-access leakage.

### 5. Add authoritative source connectors

After the shared session pipeline is trustworthy, ingest approved sources
directly. Central connectors should reduce dependence on developers manually
uploading knowledge and should preserve each source's native permissions.

## Conditions before pursuing this goal

The project should not move into shared infrastructure merely because local RAG
works technically. A team pilot should begin only when:

- Local retrieval quality is measured and acceptable.
- The artifact and lifecycle formats are stable enough to version.
- Identity and permission requirements have named owners.
- Secret filtering and source-authorization boundaries have adversarial tests.
- Erasure behavior covers artifacts, indexes, caches, logs, and backups.
- The organization has agreed which sources may be processed by which models.

## Non-goals

- Training or fine-tuning a local language model to hold organizational facts
- Giving developer machines direct write access to shared storage
- Creating one universally searchable bucket without authorization boundaries
- Automatically treating model-extracted content as verified truth
- Replacing authoritative source systems with Memory

## Open questions

- Should extraction remain local, move to managed workers, or support both?
- What identity provider and project-membership source should define access?
- Which artifacts may be shared, and which must remain personal?
- How should native source permissions and later revocation propagate?
- Which verification workflows are required before records become broadly
  retrievable?
- What latency and availability targets should the remote hook meet?
- What offline behavior and local cache policy are acceptable?
- Which storage and search services best fit measured scale and cost?
