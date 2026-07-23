---
name: architecture-simplicity
description: Prefer the simplest browser-served architecture that meets the approved plan — no unnecessary frameworks or services.
metadata:
  author: neutron
  version: "1.0"
  recommended_agents: architect
---

## Architecture simplicity

When designing the system:

1. **Honor the stack** — static projects stay browser-native HTML/CSS/JS; Next.js only when the project stack is nextjs.
2. **Minimal surface** — fewest files and components that still implement the plan.
3. **No phantom backends** — do not introduce APIs, databases, or auth unless the approved plan requires them and the stack supports them.
4. **Navigation contract** — for static apps, use in-page tab/panel show-hide (`data-tab` / `data-panel`), not root-relative multi-page routes or iframe navigation.
5. **Accessibility by design** — semantic landmarks, focus order, labels, and keyboard paths for interactive UI.
6. **Resolve conflicts** — if plan and brief disagree, choose the simpler interpretation and note the decision.

Prefer clarity over cleverness. Document file layout and component responsibilities so engineering can implement without guessing.
