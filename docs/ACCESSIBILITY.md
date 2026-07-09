# Accessibility Statement — FIFA Nexus AI

> **Scope**: Live Operations Dashboard (`frontend/index.html` / `backend/app/static/index.html`)
> **Standard**: WCAG 2.1 Level AA (target)
> **Date**: 2026-07-09

---

## Overview

FIFA Nexus AI is primarily an operational backend service. The frontend dashboard (`index.html`) is an internal operator tool intended for trained venue managers and dispatchers in a stadium operations centre. 

This document records the implemented accessibility features, recent verification testing, and identified gaps.

---

## Implemented Accessibility Features

| Feature | Implementation | WCAG Guideline |
|---|---|---|
| **Skip Navigation Link** | A skip link `href="#main-content"` is the first element in the DOM, allowing keyboard-only users to bypass the header and immediately focus on the main workspace. | 2.4.1 Bypass Blocks |
| **Reduced Motion Support** | CSS `@media (prefers-reduced-motion: reduce)` disables pulsing breach alerts and flowing redirect animations if the user has activated system-level reduced motion preferences. | 2.2.2 Pause, Stop, Hide |
| **Visible Focus Rings** | Spatial elements (paths, circles) on the interactive SVG map have explicit `:focus` and `:focus-visible` styling (`outline: 3px solid #3B82F6`) to support screen-reader and keyboard tab-navigation. | 2.4.7 Focus Visible |
| **Semantic Structure** | Page structure uses correct landmarks (`<header role="banner">`, `<main id="main-content" role="main">`, `<section>`) and a single `<h1>` for correct screen-reader outline mapping. | 1.3.1 Info and Relationships |
| **Color Contrast** | Custom dark theme uses strict slate/blue backgrounds with high-contrast text (`#E2E8F0` and `#FFFFFF`) yielding a checked contrast ratio of ≥ 4.5:1. | 1.4.3 Contrast (Minimum) |
| **Live Announcements** | The real-time event status stream and connection badge update dynamically and use `aria-live="polite"` to notify screen readers of state changes without interrupting workflow. | 4.1.3 Status Messages |
| **Language Attribute** | The main template explicitly defines `<html lang="en">` to ensure correct screen-reader pronunciation. | 3.1.1 Language of Page |

---

## Verification & Keyboard Review

A manual keyboard walk-through and screen reader outline inspection was conducted on **2026-07-09**:
1. **Tab Sequencing**: Validated that pressing `Tab` correctly transfers focus from the Skip Link, to the Header metrics, to the interactive Stadium Zone Map paths, to the form controls, and finally to the Chat Assistant input. Focus never gets trapped.
2. **Keyboard Activation**: Verified that pressing `Enter` or `Space` correctly activates interactive SVG zones, selects dropdown values, and submits chat queries.
3. **Contrast Compliance**: Contrast values for text elements against card backgrounds were audited using developer tools and found to exceed WCAG AA requirements.

---

## Known Gaps & Roadmap

| Gap | Severity | Rationale & Mitigation |
|---|---|---|
| NVDA/JAWS Screen Reader Run | Medium | While semantic structure and ARIA live regions are in place, a formal screen reader walk-through by an accessibility specialist has not been performed. |
| Mobile Viewport Support | Low | The layout is optimized for large 1080p+ desktop operator monitors in venue control rooms; mobile layout is out of scope. |
| Formal Automated Audit (axe-cli) | Low | No automated Axe audit was run against the deployed Render URL; automated audits are target roadmap items. |

---

## Audit Command (if re-running)

To execute an automated accessibility audit against a local development server, run:
```bash
# Requires axe-cli: npm install -g @axe-core/cli
axe http://localhost:8001/static/index.html --exit
```
