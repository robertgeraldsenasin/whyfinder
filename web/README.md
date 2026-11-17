# Star-atlas web demo

TypeScript + Vite + Svelte, static on GitHub Pages: <https://robertgeraldsenasin.github.io/whyfinder/>.
Unlike a viewer, it runs the glass-box engine live in a Web Worker on a 500-game slice of the
catalogue (ADR-0015): EASE^R, PageRank by forward push, the blend, DPP re-ranking, exact attributions,
counterfactuals and paths, each one golden-matched to the Python core.

```bash
npm ci
npm run dev      # http://localhost:5173/whyfinder/
npm test         # Vitest: the engine must reproduce web/src/engine/__goldens__ (from `uv run whyfinder export model`)
npm run check    # svelte-check + TypeScript
npm run e2e      # Playwright on desktop and phone, axe in both themes (WHYFINDER_CHROME=/path/to/chrome to use a local Chrome)
```

| Path | What |
| --- | --- |
| `src/engine/` | the engine (pure TypeScript, no DOM) and its worker |
| `src/lib/views/` | Discover, Under the hood, Architecture |
| `src/lib/components/Atlas.svelte` | the full-bleed star map (canvas) with keyboard markers |
| `public/data/` | `demo-slice.json` (from `whyfinder export demo`) and `model.json` (from `whyfinder export model`) |

Design: `docs/spec/11_DESIGN_SYSTEM.md`, tokens in `docs/design/tokens.css` (imported directly), motion
in ADR-0016.
