---
name: accessibility-wcag
description: Apply practical WCAG-oriented checks for keyboard access, contrast, semantics, and screen-reader friendly UI.
metadata:
  author: neutron
  version: "1.0"
  recommended_agents: engineer,architect
---

## Accessibility checklist (practical WCAG)

Apply these checks when designing or implementing UI:

1. **Structure** — one main landmark; logical heading order; lists for list content.
2. **Keyboard** — all interactive controls reachable and operable without a mouse; visible focus rings.
3. **Labels** — every input has an associated label; icon-only buttons have accessible names (`aria-label`).
4. **Images** — meaningful images have `alt` text; decorative images use empty `alt`.
5. **Color** — do not rely on color alone; aim for readable contrast on text and controls.
6. **Motion** — avoid essential information that appears only in brief animations.
7. **Forms** — errors identified in text and linked to fields; required fields indicated accessibly.
8. **Dynamic UI** — status messages for important updates; expand/collapse state exposed to assistive tech when needed.

When time is limited, prioritize keyboard access, labels, and contrast over decorative polish.
