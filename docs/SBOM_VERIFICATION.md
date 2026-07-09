# Software Bill of Materials (SBOM) Verification — FIFA Nexus AI

This document verifies and tracks the Software Bill of Materials (SBOM) for the FIFA Nexus AI platform.

---

## 1. SBOM Metadata

- **Generated On**: 2026-07-10
- **Tool Version**: `cyclonedx-py 7.3.0` (utilizing `cyclonedx-python-lib 11.11.0`)
- **Generation Command**:
  ```bash
  cyclonedx-py environment --of JSON -o docs/sbom.json
  ```
- **SBOM Schema Version**: CycloneDX 1.6 JSON (`http://cyclonedx.org/schema/bom-1.6.schema.json`)
- **Main Component Type**: `application`

---

## 2. Verification Summary

The regenerated SBOM file at [sbom.json](sbom.json) contains a complete, cryptographically hashed inventory of the virtual environment dependencies. Key metrics from the audit include:
- **Total Tracked Components**: 142 Python packages and library dependencies.
- **Root Component**: `fifa-nexus-ai`
- **Metadata**: Each package entry includes its Package URL (PURL), homepage reference, author, exact pinned version, and license expressions where available.
