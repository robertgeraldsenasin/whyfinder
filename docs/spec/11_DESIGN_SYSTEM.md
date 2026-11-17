# 11 · Design system: "Star Atlas"

Whyfinder looks like a navigator's star chart from a space game: cinematic on the map, quiet on the page. Your games are
stars you've visited; picks are new stars; the **lines between them are the reasons**. The space
setting is the frame; the content (picks, reasons, evidence) is always on solid, quiet panels.

Tokens: [`docs/design/tokens.css`](../design/tokens.css). Logo: [`docs/design/logo.svg`](../design/logo.svg).
Static mockup: [`docs/design/mockup.html`](../design/mockup.html) (open it in a browser).

## Principles

1. **The metaphor carries meaning.** Constellation lines exist only where an attribution exists; line
   weight = contribution share. Nothing decorative pretends to be data.
2. **One accent per view.** Amber marks the pick and the primary action. Cyan marks reasoning lines.
   Violet "nebula" appears only as a faint background wash (≤ 12% opacity).
3. **The map is the stage; panels are the page.** The atlas fills the screen behind everything and
   may carry depth and motion (ADR-0016). Reading panels sit in front on solid surfaces: no glow,
   blur or animation behind text; no neon, no gradient text, no glassmorphism.
4. **Data looks like instruments.** Mono micro-labels, thin rules and corner ticks on data panels only
   (the "HUD" layer), never on body text.
5. **Cinematic but purposeful motion** (ADR-0016). The camera glides between stars, light travels
   along reasons, and Under the hood animates the real computation step by step. Every motion shows
   something the model did; everything is static under `prefers-reduced-motion`.

## Themes

| Token | Deep Field (dark, default) | Atlas Paper (light) | Use |
| --- | --- | --- | --- |
| `--bg` | `#0A0F1F` | `#F5F1E6` | page |
| `--surface` | `#111A2E` | `#FFFCF4` | panels, cards |
| `--raised` | `#18233B` | `#EFE9DA` | hover, selected rows |
| `--line` | `#2A3654` | `#D6CDB8` | borders, rules (non-text) |
| `--text` | `#E8EDF7` | `#172038` | body text |
| `--muted` | `#A3AEC7` | `#555F75` | secondary text, labels |
| `--pick` | `#F4B860` | `#9A5A00` | pick stars, primary button, focus ring |
| `--link` | `#7DD3E3` | `#17707F` | constellation lines, links |
| `--nebula` | `#8B7CF0` | `#5B4BC4` | background wash only |
| `--good` | `#6FD8A3` | `#1E7A4E` | verified evidence |
| `--bad` | `#F28B8B` | `#B3261E` | negative contributions, errors |

Contrast (WCAG 2.1, computed): body text ≥ 13.3:1 and muted text ≥ 5.2:1 on every surface in both
themes; amber and cyan text ≥ 4.5:1 on `--bg` and `--surface` in both themes. In Atlas Paper, don't
put `--good` text on `--raised` (4.39:1); use it on `--surface`.

## Type

| Role | Font (OFL, self-hosted) | Size / weight |
| --- | --- | --- |
| Display (wordmark, h1, pick names) | Space Grotesk | 32 / 600, 24 / 600, 20 / 600 |
| Body | Inter | 16 / 400, line-height 1.55 |
| Data and micro-labels | JetBrains Mono | 12 / 500, uppercase, tracking 0.08em |

Fallback stack until fonts are self-hosted: `ui-sans-serif, system-ui, -apple-system, "Segoe UI",
sans-serif` and `ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace`.

## Layout

- 12-column grid, max width 1200 px, gutters 24 px; spacing scale 4 · 8 · 12 · 16 · 24 · 32 · 48.
- Desktop: the star map is full-bleed behind the page; "Your games" floats left (3 cols), "Why this
  pick" right (3 cols), the picks rail along the bottom, the map's focus in the centre.
- Three views share the map: **Discover** (picks and reasons), **Under the hood** (the pipeline run
  step by step on your history) and **Architecture** (the system as a live diagram).
- Phone: query bar → your games (chips) → star map (aspect 4:3) → pick list → why panel (a bottom sheet in the real app).
- Radius: 10 px panels, 999 px chips. Borders 1 px `--line`.

## Components

| Component | Notes |
| --- | --- |
| Query bar | "Like Hades but co-op…"; parsed anchors become chips, unresolved words listed below |
| Game chip | cover-less: title + small star glyph; removable; keyboard reachable |
| Star map | SVG. History = white dots (r 4); picks = 4-point amber sparkles (r 7); lines = cyan, width 1–4 px by share, dashed for "related by" paths; labels on hover/focus; a list view alternative for screen readers |
| Pick card | rank, title, price, tags (max 3), "kept for variety" badge, one-line top reason |
| Why panel | attribution bars (exact %), counterfactual sentence with its guarantee, "related by" paths, verified claims each with an evidence chip (✓ verified) |
| Evidence chip | `ATTR 588650` or `REVIEW c_8812_0`; opens the quote or the attribution row |
| HUD frame | corner ticks + mono label; used on the star map and the why panel only |
| Theme toggle | Deep Field ↔ Atlas Paper; remembers choice |
| Stage rail | Under the hood: the pipeline stages in order, each with its live timing; step, play, pause, speed |
| Stage panel | One stage's picture, its equation, the live numbers, its cost and the source file that implements it |
| System diagram | Architecture: offline and online lanes; replay a request or the build; planned parts dashed with their milestone |

## Motion (ADR-0016)

| Element | Motion | Reduced motion |
| --- | --- | --- |
| Starfield | three parallax layers following the camera and, gently, the pointer | static |
| Camera | spring-eased pan and zoom to frame a pick and its reasons, ≤ 900 ms | jumps |
| Constellation lines | draw in (stroke-dashoffset, 600 ms, ease-out); then light particles travel from your game to the pick, density ∝ share | appear instantly; no particles |
| Pick star | soft glow pulse on selection | none |
| Under the hood | push pulses, Cholesky sweep, DPP steps, counterfactual removals replay the real computation | manual stepping only |
| Panels and views | 150 ms fade/slide 4 px; cross-fade between views | none |

The animation loop sleeps when nothing moves or the tab is hidden.

## Accessibility

- Every star map has a list alternative ("Picks and their reasons") with the same content.
- Focus ring 2 px `--pick` offset 2 px on every interactive element.
- Colour never carries meaning alone: negative contributions also show a minus sign; dashed lines are
  also labelled "related by".
- Target: axe 0 violations in both themes (NFR-09).

## Logo

A constellation of four stars forming a **Y** ("why"): three outer stars joined to a centre star, the
lower one amber (the pick). Wordmark "whyfinder" in Space Grotesk 600, lowercase.
