---
name: browser-native-spa
description: Implement static web apps as complete, directly servable HTML/CSS/JS with tab navigation and no build step.
metadata:
  author: neutron
  version: "1.0"
  recommended_agents: engineer
---

## Browser-native SPA implementation

When writing project files:

1. **Write real files** through the provided code tools — never only describe code in chat.
2. **Required artifacts** — produce the stack's required files (typically `index.html`, styles, and scripts).
3. **Navigation** — wire tabs/pages with `data-tab` / `data-panel` show-hide logic; never use root-relative routes (`/about`) or iframe navigation for static multi-view UIs.
4. **Semantic HTML** — landmarks, headings hierarchy, labels, buttons vs links used correctly.
5. **CSS** — maintainable layout (flex/grid), responsive breakpoints, visible focus styles.
6. **JavaScript** — progressive enhancement; guard null DOM nodes; no framework runtime unless the stack is Next.js.
7. **Completeness** — implement empty states, basic validation, and interactive behaviors described in the plan.

Faithful implementation beats premature abstraction.
