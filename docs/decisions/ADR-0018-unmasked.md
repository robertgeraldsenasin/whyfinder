# ADR-0018: Unmasked: a theatrical redesign, with the picks dealt as cards

- **Status:** Accepted (supersedes the palette, type, frames and starfall visuals of ADR-0017; its
  closeness formula, tiers, flash cap, sound settings and evidence rules stay)
- **Date:** 2026-11-19
- **Deciders:** Robert Gerald Senasin

## Context

Starfall fixed the ceremony around the picks but not the look. Midnight blue with gold and violet
glow, cut-corner panels, a hero on the left and the sky on the right: Gerald still saw a page that
could have been generated, not designed. He asked for the aesthetic of Aha, the Aeon of Elation in
Honkai: Star Rail (playable from version 4.7, "Now, Lay Laughter to All Stars"), in particular her
red and violet.

What her design is built from, from the official reveal and the character profile:

- a white corset over a crimson skirt, a red ribbon at the waist, a black-and-white crown with heart
  motifs, a wand tipped with a gem; white hair streaked with red and dark purple;
- pink eyes whose pupils are black four-pointed stars;
- the Quantum element, which the game draws in deep violet;
- masks (comedy and tragedy), playing cards with masks on them (in her signature mechanic each
  performer is announced by a card), and a Queen of Hearts reading overall;
- a human form who is a comic artist, in a world (Planarcadia) drawn as pop art and theme park;
- "Let there be laughter": a god of games, the stage and the punchline.

## Options considered

1. Recolour Starfall in crimson and violet. Rejected: the problem is the generic structure, not
   the hue.
2. Copy the game's UI or art. Rejected: it is HoYoverse's, and a fan skin would date fast.
3. **Take the vocabulary, not the character**: a stage at night, crimson, bone and ink with a violet
   layer, playing cards, comic print, spotlights. No HoYoverse art, names, logos or likeness in
   the product.

## Decision

Option 3, named **Unmasked**: a black-box recommender wears a mask; Whyfinder takes it off. The sky
stays the stage (every star is a game); your games are the cast; the ten picks are **dealt as
cards, Ace to 10**, and every card shows its hand.

| Area | Rule |
| --- | --- |
| Palette | Ink `#0B0710` (page, sky), Velvet `#160B1B` (panels), Raised `#241329`, Seam `#3A1E40` (borders), Bone `#F7EFE6` (text, card faces), Ash `#BCAAB9` (secondary text), Crimson `#D1173A` (the pick, the primary action; bone text on it 4.7:1), Crimson hot `#FF2E4F` (light only), Crimson text `#FF5C72`, Rose `#FF8FB1`, Quantum `#7B4DFF` (the graph) and Quantum text `#B9A2FF`, Good `#7FE0B0`, Cold `#74D4E6` (a game that pulls away). Gold is retired. |
| Accents | Crimson is the pick and what to do next; quantum violet is the graph (tags, studios, PageRank). Same two jobs as before, new colours. |
| Type | **Anton** (poster type) for the wordmark, view and panel titles, section labels and card indices, in capitals; **Prata** for names of things (game titles, starter hands); **Josefin Sans** for the interface, in sentence case; **Comic Relief** for what players wrote, in speech balloons; JetBrains Mono for equations and paths. Cutive Mono is dropped. Anton and Comic Relief are OFL and self-hosted from `web/src/assets/fonts/` with their licences. |
| Wordmark | WHY in crimson, FINDER in bone, Anton capitals slanted 8°, with two hard offset shadows (deep crimson, then violet) like a misregistered poster print. On the title screen it carries a crimson ribbon: "Find your next game. Know why." |
| Cards | Rank 1 is the Ace, then 2 to 10. The suit is data: **hearts** when the co-play part (EASE^R) of the pick's exact score is at least the graph part, **clubs** when the graph part (PageRank over tags and studios) is larger. Computed from the attributions, so it is as exact as they are. Picks kept for variety say so in words. |
| Frames | Square panels on velvet with a 1 px seam and a short crimson rule on the top edge. The pick is a bone card face (corner indices, inner rule, the Steam art as its picture, the closeness tier as a rubber stamp) with a hard crimson shadow. Buttons are slanted plates; the primary one is crimson with a bone offset. Inputs that matter are bone: the title-screen search is an admission ticket. |
| Comic print | Halftone dots (crimson, sometimes violet) in corners, behind the wordmark and in impact frames. Player quotes are speech balloons. Bullets and markers are four-pointed stars. |
| Motion | The deal: a spotlight finds where the card will land, the card falls from the top right turning over, and bursts into its star (shockwaves, halftone burst, shards, a short shake). The top three get an impact frame (inverted bone and ink with speed lines). The Ace hangs in the spotlight, lands hardest, and a comic burst ("AHA!") and confetti follow. Then the sky recolours by closeness, as before. |
| Closeness colours | Crimson and violet (default: indigo, violet, orchid, rose, crimson), Crimson (maroon to pale rose, lightness rising), Star temperature (unchanged). Saved settings from Starfall map across. |
| Sound | Added: a card flick when each card is dealt and a short brass "ta-da" for the Ace. The bells, whoosh and impact stay. |

Unchanged from ADR-0017: closeness c = √(s / s_max) and its five tiers; at most three impact
frames in any second; Full, Reduced flashing and Off; reduced motion turns off the fall, flashes,
shake, confetti and twinkle; the starfall can be skipped; sound starts on the first gesture.

## Consequences

- Contrast (WCAG 2.1, computed): Bone ≥ 15.3:1, Ash ≥ 7.9:1, Crimson text ≥ 5.8:1, Quantum text
  ≥ 8.0:1 and Rose ≥ 8.1:1 on every dark surface; ink `#1A0E18` on bone 16.5:1, muted ink `#5E4A58` on
  bone 7.1:1, crimson and the club violet `#4A2BB8` on bone 4.7:1 and 7.9:1; bone on Crimson 4.7:1. Raw Crimson, Crimson hot and Quantum are never text on dark.
- Two more font files (about 77 KB). The demo no longer imports Cutive Mono.
- The e2e suite checks the palette names, that the hand is ten cards with an Ace, and axe at 0
  violations on every view and the settings dialog.
- Nothing from Honkai: Star Rail ships in the product; the inspiration is recorded here only.
