# ADR 003: Qdrant for SOP Vector RAG Retrieval

## Context and Problem Statement
When a crowd breach event triggers, the system needs to retrieve the exact Standard Operating Procedure (SOP) based on the zone type, severity, and context, then inject this SOP into the LLM context. We need a vector database to perform semantic matches.

## Decision Drivers
* **Search Speed**: Retrieval must complete in `< 25ms`.
* **Scalability**: Capable of indexing hundreds of emergency manuals and playbooks.
* **Resilience**: Support lightweight memory fallbacks for local deployment.

## Considered Options
1. **Pinecone (Managed Service)**
2. **Qdrant (Self-Hosted/Docker)**
3. **PGVector (PostgreSQL Extension)**

## Decision Outcome
Chosen Option: **Qdrant**

### Rationale
* **Fast Semantic Matches**: High-performance Rust-based engine with average search latency of under 5ms.
* **Metadata Filtering**: Allows strict filtering of retrieved SOPs by zone type (e.g. `GATE` vs `CONCOURSE`) before performing vector similarity matches.
* **Local Fallback**: Easily mocked or run via lightweight in-memory lists during offline test runs.

## Pros and Cons of Chosen Option

### Pros
* Extremely fast retrieval times.
* Excellent support for payload metadata queries.
* Developer-friendly python client.

### Cons
* Introduces another container in docker-compose. Resolved by implementing a standard JSON-file fallback in the code when Qdrant is offline.
