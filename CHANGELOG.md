# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-07-08

### Added
- **Visual README Gallery**: Added Live Dashboard Demo walkthrough animation and 4-panel screenshot gallery.
- **Render Deployment Support**: Added `render.yaml` deployment blueprint and `start.sh` startup script.
- **SlowAPI Rate Limiter**: Configured API write endpoints to 30 requests/minute and read endpoints to 100 requests/minute.
- **Trusted Host & Security Headers**: Integrated host validation middleware and security response headers (CSP, X-Frame-Options, etc.).
- **Strict Pydantic Type Enforcements**: Converted statuses, sensor types, and user roles to Pydantic `Literal` schemas for strict runtime checking.
- **Automated CI/CD Workflow**: Created GitHub Actions test workflow for linting, security audits, and testing.
- **Repository Quality Files**: Added CODEOWNERS, `.editorconfig`, dependabot, and pre-commit hook files.

### Fixed
- **Ignore Leak (.env.example)**: Fixed gitignore glob so `.env.example` is committed correctly.
- **DATABASE_URL Fallback**: Fixed backend config to parse injected database URLs from Render/Railway.
- **Sub-string Word Boundaries**: Replaced greedy `in` substring validation with regex word boundaries `\b` for keyword verification.
- **Zone Occupancy Resolution**: Added `current_occupancy` to the database schema.
