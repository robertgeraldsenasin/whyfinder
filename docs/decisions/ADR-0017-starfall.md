# ADR-0017: Starfall: a celestial redesign with impact, evidence and sound

- **Status:** Accepted (supersedes the palette, type and theme rules of ADR-0013; extends ADR-0016)
- **Date:** 2026-11-17 (type and frames revised the same day, see Revision)
- **Deciders:** Robert Gerald Senasin

## Context

The first demo worked but read as generic. Picks were small dots that appeared without ceremony, the
only reasons were exact shares and graph links, and there was nothing from the players themselves.
Gerald asked for:

- impact: picks that fall into the sky like a shooting star striking the ground, after the impact-frame
  starfall effects popular in Minecraft videos;
- evidence: the actual game, what its players say, and what connects its community to the user's;
- game feel: sound, transitions and animation;
- a midnight-blue sky with gold and white stars and gold and violet accents;
- a non-linear colour code for how close each game is, with a choice of gold only, gold and violet,
  or a full spectrum.

## Options considered

1. Restyle the existing Star Atlas (new colours, same behaviour).
2. **A new language, Starfall**: the same glass-box engine, a new visual and interaction system built
   around the moment the picks arrive.
3. A 3D/WebGL scene. Rejected: heavy for phones and hard to keep accessible, and canvas 2D with
   additive sprites already gives the glow.

## Decision

Option 2.

| Area | Rule |
| --- | --- |
| Palette | Midnight `#070B1E`, Deep `#0D1433`, Starlight `#F5F2FF`, Dust `#A9AED3`, Gold `#F2C14E`, Violet `#8E6BF0` (text on dark: `#B8A4FF`). Dark only; the light theme is retired. |
| Accents | Gold is the pick and the primary action. Violet is the graph: tags, studios, PageRank glow. These two accents replace "one accent per view". |
| Type | Prata for names of things (the wordmark, headings, game titles, rank numerals); Josefin Sans for the interface, in sentence case; Cutive Mono for what players wrote. JetBrains Mono only for equations and source paths. See Revision. |
| Closeness | c = √(s / s_max) over games you do not own. The square root spreads the many weak matches. Five named tiers: Twin star ≥ 0.9, Close orbit ≥ 0.7, Same constellation ≥ 0.5, Neighbouring sky ≥ 0.3, Distant light. |
| Colour modes | Gold and violet (default), Gold, Star temperature (red far, blue-white close). Interpolated in OKLab. The whole sky recolours by closeness after a run, rippling out from your games. |
| Starfall | Picks fall #10 first, #1 last: lock-on beam and reticle, accelerating streak, impact with shockwaves, embers and a short shake. The top three get an impact frame: two frames of inverted light with speed lines. Skippable (click, Esc, Space, Enter or the Skip button). |
| Flashes | At most three impact frames in any second, whatever the settings. Settings: Full, Reduced flashing (light stays around the star), Off (no flashes, no shake). `prefers-reduced-motion` turns off the fall, flashes, shake and twinkle. |
| Sound | Synthesized with Web Audio: whoosh, impact (thump, crack, a bell tuned so #1 lands on the root), lock-on, select, add. On by default; it starts on the first click, and mute and volume are remembered. |
| Evidence | Per pick: Steam header art and a store link, loaded from Steam at view time and never stored. Also quotes of at most 25 words (NFR-07), preferring players who also played one of your games. Also the words both communities use (log-odds with an informative Dirichlet prior). From `whyfinder export reviews`, train-period reviews only. |

## Revision (same day)

The first build used Bodoni Moda italic and Hanken Grotesk, rounded cards and pill buttons. Gerald
found it read as generic, "AI coded", and pointed at game title lockups (Reverse: 1999, Arknights)
for the type. Changes:

| Area | Rule |
| --- | --- |
| Display | **Prata**: sharp, high-contrast, wedge terminals. The wordmark is set in spaced capitals with two gold double hairlines cut through the Y and the D, and a spaced line beneath on the title screen, the way game logos carry a subtitle. |
| Interface | **Josefin Sans**: a vintage geometric sans that sits with the 1920s mood. |
| Player quotes | **Cutive Mono** on faintly ruled cards, like typed notes in a case file. |
| Frames | Panels have cut corners (an octagon drawn by two clipped layers behind the content, so dropdowns and focus rings are never clipped); data panels get a gold frame. Buttons are slanted plates; tags and the closeness tier are slanted too; markers and bullets are diamonds. No rounded cards or pills. |
| Navigation | Text tabs; the current view is gold with a hairline and a diamond beneath. |

Rejected after a specimen in the real colours: Federo (Art Deco, but reads as a sans and not as a title),
Limelight (too heavy), Marcellus (fantasy, not 1920s), Big Shoulders (industrial), and thin didones
such as Italiana and Antic Didone (too fragile at panel sizes).

## Consequences

- One more data artefact (`reviews.json`, about 1 MB) produced on GitHub's runners with the rest of
  the pipeline. The demo works without it.
- The theme toggle and its tests are gone; e2e now covers settings, skipping and reduced motion, and
  axe must stay at 0 violations on every view, including the settings dialog.
- Steam art depends on Steam's CDN. If an image fails, a generated plate with the title is shown.
- Contrast (WCAG 2.1, computed): Starlight ≥ 14.6:1, Dust ≥ 7.4:1, Gold ≥ 9.6:1 and violet text
  ≥ 7.5:1 on every surface. Raw Violet (4.2:1 on raised) is never used for text.
- All fonts are OFL and self-hosted through Fontsource.
