# Product Roadmap: FIFA Nexus AI

FIFA Nexus AI is designed to scale across multiple stadium venues. The following roadmap outlines planned phases leading to the production deployment at the FIFA World Cup 2026.

## Phase 1: Security Hardening & RBAC (Q3 2026)
- **OAuth2 & JWT Auth**: Transition from a static API key to JWT-based session tokens with specific user role permissions.
- **Audit Logging**: Fully implement cryptographic signing on `audit_logs` entries to guarantee non-repudiation of operational directives.
- **Secure Secret Manager**: Move secrets out of `.env` files into AWS Secrets Manager or HashiCorp Vault.

## Phase 2: High-Availability & Scalability (Q4 2026)
- **Distributed Redis Clustering**: Cluster Redis nodes to support sub-millisecond lookups under peak crowd loads exceeding 80,000 spectators.
- **Qdrant Vector Sharding**: Partition the vector database across multiple availability zones.
- **Geographic PostGIS Queries**: Replace simple distance constants with active SQL PostGIS geospatial queries for precise route calculations.

## Phase 3: Advanced AI & Simulator (Q1 2027)
- **Predictive Evacuation Simulations**: Build Monte Carlo routing simulation engines to pre-test AI strategies before operator approval.
- **Multi-Modal Feeds**: Ingest live video camera feeds directly, utilizing edge object detection to count spectators in real time.
