# Star-atlas web demo

TypeScript + Vite + Svelte, static on GitHub Pages. Unlike a viewer, it runs the glass-box engine live
in a Web Worker on a 500-game slice of the catalogue (ADR-0015): EASE^R, PPR forward push, the blend,
DPP re-ranking, exact attributions and counterfactuals, each one golden-matched to the Python core.

Design: `docs/spec/11_DESIGN_SYSTEM.md`, tokens in `docs/design/tokens.css`, motion in ADR-0016.

Views: **Discover** (your games, picks, why panel), **Under the hood** (the pipeline step by step on
your history) and **Architecture** (the system as a live diagram).
