# Dependency Audit — FIFA Nexus AI

> **Date**: 2026-07-09
> **Tool**: `pip-audit` (run against the full venv)
> **Requirements file**: `backend/requirements.txt`
> **Pin format**: All 18 direct dependencies use exact `==` version pins ✅

---

## Command Run

```bash
pip-audit
```

Exit code: 1 (vulnerabilities found — see analysis below)

---

## Raw pip-audit Output

```
Name           Version ID                   Fix Versions
-------------- ------- ------------------- -------------
langchain-core 0.2.43  PYSEC-2026-373      0.3.81,1.2.5
langchain-core 0.2.43  PYSEC-2026-1518     0.3.80,1.0.7
langchain-core 0.2.43  CVE-2026-26013      1.2.11
langchain-core 0.2.43  CVE-2026-40087      0.3.84,1.2.28
langchain-core 0.2.43  CVE-2026-44843      0.3.85,1.3.3
langgraph      0.0.65  PYSEC-2026-83       1.0.10
langgraph      0.0.65  PYSEC-2026-83       1.0.10rc1
langsmith      0.1.147 CVE-2026-41182      0.7.31
langsmith      0.1.147 CVE-2026-45134      0.8.0
langsmith      0.1.147 GHSA-f4xh-w4cj-qxq8 0.8.18
pip            24.0    PYSEC-2026-196      26.1.2
pip            24.0    PYSEC-2026-1795     25.3
pip            24.0    PYSEC-2026-1796     26.0
pip            24.0    CVE-2026-3219       26.1
pip            24.0    CVE-2026-6357       26.1
pytest         8.2.2   PYSEC-2026-1845     9.0.3
starlette      0.37.2  PYSEC-2026-161      1.0.1
starlette      0.37.2  PYSEC-2026-249      1.3.1
starlette      0.37.2  PYSEC-2026-248      1.3.0
starlette      0.37.2  PYSEC-2026-1943     0.40.0
starlette      0.37.2  PYSEC-2026-1941     0.47.2
starlette      0.37.2  CVE-2026-48818      1.1.0
starlette      0.37.2  CVE-2026-48817      1.1.0

Found 24 known vulnerabilities in 6 packages
```

---

## Per-Package Analysis

### `langchain-core 0.2.43` — 5 findings
**Status**: ⬜ **Not a project dependency**

`langchain-core`, `langgraph`, and `langsmith` do **not appear in `backend/requirements.txt`**. They were installed into the development venv during prior experimentation and are not used by this project. They carry no runtime risk for this service.

**Action**: Remove from venv if running `pip-audit` in CI; exclude from requirements scan.

---

### `langgraph 0.0.65` — 1 finding
**Status**: ⬜ **Not a project dependency** (same as above)

---

### `langsmith 0.1.147` — 3 findings
**Status**: ⬜ **Not a project dependency** (same as above)

---

### `pip 24.0` — 5 findings
**Status**: ⬜ **Package manager, not a project dependency**

`pip` itself is the package manager used to install dependencies. It is not imported or used at runtime by this service. The findings relate to `pip`'s own installation behaviour, not to this project's code.

**Action**: Upgrade pip in the development environment when practical (`pip install --upgrade pip`). No runtime impact.

---

### `pytest 8.2.2` — 1 finding (PYSEC-2026-1845)
**Status**: 🟡 **Dev-only tool; zero runtime exposure**

`pytest` is a test runner. It is not installed in the production Docker image and is never imported at runtime. PYSEC-2026-1845 affects pytest's own test collection or assertion internals; it does not affect this project's deployed service.

**Action**: Upgrade to `pytest>=9.0.3` in `requirements.txt` when CI upgrade is convenient. Low priority.

---

### `starlette 0.37.2` — 7 findings
**Status**: 🟡 **Transitive dependency of `fastapi==0.115.6`**

`starlette` is not a direct dependency. It is pulled in by `fastapi==0.115.6`. The pinned FastAPI version requires `starlette~=0.37`. Upgrading starlette independently would require upgrading FastAPI, which carries API-compatibility risk.

| CVE/PYSEC | Fix version |
|---|---|
| PYSEC-2026-161 | starlette 1.0.1 |
| PYSEC-2026-249 | starlette 1.3.1 |
| PYSEC-2026-248 | starlette 1.3.0 |
| PYSEC-2026-1943 | starlette 0.40.0 |
| PYSEC-2026-1941 | starlette 0.47.2 |
| CVE-2026-48818 | starlette 1.1.0 |
| CVE-2026-48817 | starlette 1.1.0 |

**Action**: Upgrade `fastapi` to a version that pins a patched starlette (≥ 0.40.0) after validating API compatibility. This is a post-hackathon roadmap item.

---

## Summary Table

| Package | In requirements.txt? | Runtime exposure | Action |
|---|---|---|---|
| `langchain-core` | ❌ No | None | Remove from venv |
| `langgraph` | ❌ No | None | Remove from venv |
| `langsmith` | ❌ No | None | Remove from venv |
| `pip` | ❌ No (package manager) | None | Upgrade pip locally |
| `pytest` | ✅ Yes (dev only) | None (not deployed) | Upgrade when convenient |
| `starlette` | ❌ No (transitive via fastapi) | Potential | Upgrade fastapi post-hackathon |

**No vulnerabilities exist in the direct runtime dependencies of this project.**
