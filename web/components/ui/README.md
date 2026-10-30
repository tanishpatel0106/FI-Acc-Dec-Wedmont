# components/ui — vendored UI primitives

These files are copied into the repo and owned like any other source (shadcn model).

| Source | Components | Version / registry |
| --- | --- | --- |
| shadcn/ui CLI 4.23.0, style `base-nova` (Base UI) | badge, button, card, command, dialog, dropdown-menu, input, input-group, label, popover, scroll-area, select, separator, sheet, skeleton, slider, sonner, switch, table, tabs, textarea, tooltip | `npx shadcn@4.23.0 add …` (2026-10-30) |
| Aceternity UI free registry (`@aceternity`, `registry:ui`) | sidebar, bento-grid, spotlight, background-beams, text-generate-effect, hover-border-gradient, animated-tabs (registry `tabs`), multi-step-loader, animated-modal, tracing-beam, timeline, glowing-effect, placeholders-and-vanish-input, tooltip-card | `https://ui.aceternity.com/registry/{name}.json` (2026-10-30) |
| Aceternity "expandable card" demo pattern | expandable-card.tsx (generalised) | registry item `expandable-card-demo-standard`; the standalone item requires a Pro token |

Local modifications (kept minimal, marked in the files):

- `animated-tabs.tsx`: added `AnimatedTabBar` — the animated pill selector rendering only the active panel (the stacked-card
  panels of the original would mount every analytics panel at once).
- `timeline.tsx`: optional heading props instead of the demo copy; compact spacing for the Runs audit trail.
- `expandable-card.tsx`: generic content instead of the demo's image cards.
- `cn` imports point at `@/lib/utils`.

Motion rules (brief 8.3): Aceternity effects are confined to the shell, the Overview hero, CTAs, the run loader, the heatmap
drill-down card and the comparison picker; nothing animates behind a chart, and `prefers-reduced-motion` disables
animations globally (`app/globals.css`).
