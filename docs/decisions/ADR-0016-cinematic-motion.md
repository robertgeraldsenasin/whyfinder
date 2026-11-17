# ADR-0016: Cinematic motion for the Star Atlas

- **Status:** Accepted (amends the motion and space-effect rules of ADR-0013)
- **Date:** 2026-11-17
- **Deciders:** Robert Gerald Senasin

## Context

ADR-0013 chose the Star Atlas language with deliberately calm motion: a slow starfield drift, lines
that draw in once, a glow only on the selected pick, and space effects at most 10% of the visual
weight. Gerald wants the demo to feel innovative and fluid, and ADR-0015 adds live algorithm
animations (push residuals spreading through the graph, DPP steps) that need more motion than the
original rules allow.

## Options considered

1. Keep the restrained rules as written.
2. **Cinematic within the same system**: depth and motion on the map, solid and quiet reading panels.
3. A full sci-fi HUD (rejected in ADR-0013).

## Decision

Option 2. The palette, type, one-accent rule and accessibility targets of ADR-0013 stay. What changes:

| Allowed now | Rule |
| --- | --- |
| Full-bleed star map | The atlas is the page background; panels float above it on solid `--surface` |
| Parallax starfield | Three depth layers that follow the camera and, gently, the pointer |
| Camera glides | Spring-eased pan and zoom between stars, ≤ 900 ms |
| Light along reasons | Particles travel along constellation lines from your game to the pick; their density follows the contribution share |
| Algorithm motion | Under the hood: push pulses, DPP steps and Cholesky sweeps animate the real computation, step by step |
| View morphs | Cross-fades and shared-element morphs between Discover, Under the hood and Architecture |

Unchanged: no blur, glow or animation behind text; no neon or gradient text; one accent per view;
contrast targets; `prefers-reduced-motion` makes everything static (camera jumps, lines appear,
step-through stays manual). The animation loop sleeps when nothing moves or the tab is hidden.

## Consequences

More motion to test: Playwright runs with reduced motion forced on and off, and axe must stay at
0 violations in both themes. The 10% space-effect cap now applies to the reading panels' surroundings
only, not to the map itself.
