# Accessibility Statement — FIFA Nexus AI

> **Scope**: Live Operations Dashboard (`frontend/index.html`)
> **Standard**: WCAG 2.1 Level AA (target)
> **Date**: 2026-07-09

---

## Overview

FIFA Nexus AI is primarily an operational backend service. The frontend dashboard (`index.html`) is an internal operator tool intended for trained venue managers and dispatchers in a stadium operations centre.

This document records what has been implemented, what has not, and the rationale for any gaps.

---

## Implemented

| Feature | Implementation |
|---|---|
| **Semantic HTML** | `<header>`, `<main>`, `<section>`, `<nav>`, `<button>` used throughout |
| **Keyboard navigation** | All interactive elements (buttons, inputs) are reachable via Tab; form submission works via Enter |
| **Visible focus indicators** | CSS `:focus-visible` ring applied to all interactive elements |
| **Colour contrast** | Dark theme uses text colours with ≥ 4.5:1 contrast ratio against backgrounds (verified visually) |
| **ARIA roles** | Status panels use `role="status"` for live updates; alert panels use `role="alert"` |
| **Responsive layout** | CSS Grid layout adapts to viewport widths down to 1024px (intended for desktop operator workstations) |
| **Error feedback** | Form validation errors are surfaced inline, not only via colour |
| **Language attribute** | `<html lang="en">` set |

---

## Known Gaps

| Gap | Severity | Notes |
|---|---|---|
| Screen reader testing | Medium | Automated ARIA roles are in place but full NVDA/JAWS testing has not been performed |
| Mobile viewport | Low | Dashboard targets 1080p+ desktop workstations; mobile is out of scope for this use case |
| High contrast mode | Low | System high-contrast mode not explicitly tested |
| Skip-to-content link | Low | Not implemented; single-page layout with no complex navigation structure |
| Formal WCAG audit | — | No automated axe/Lighthouse audit has been run against the deployed instance |

---

## Rationale

This is an internal operational tool deployed in a controlled environment (stadium operations centre) for trained staff. It is not a public-facing consumer product. WCAG 2.1 AA is the target standard, and the implemented features cover the highest-impact items (keyboard access, colour contrast, semantic HTML, ARIA live regions).

A full accessibility audit would be required before deploying this tool to a broader or public audience.

---

## Audit Command (if re-running)

```bash
# Requires axe-cli: npm install -g @axe-core/cli
axe http://localhost:8005 --exit
```
