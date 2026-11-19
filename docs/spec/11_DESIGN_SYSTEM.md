# 11 · Design system: "Unmasked"

A black-box recommender wears a mask; Whyfinder takes it off. The demo is a stage at night. Every
star is a game, placed by the players it shares with other games. Your games are the cast. When you
ask for picks, ten cards are dealt into the sky, Ace to 10, and every card shows its hand: the lines
between your stars and a pick are the exact reasons. The sky carries the spectacle; the reading
panels stay solid and calm. Decision record: [ADR-0018](../decisions/ADR-0018-unmasked.md)
(closeness and flashes: ADR-0017; motion: ADR-0016).

Tokens: [`docs/design/tokens.css`](../design/tokens.css). Logo: [`docs/design/logo.svg`](../design/logo.svg).

## Principles

1. **The metaphor carries meaning.** Lines exist only where an attribution exists, and line weight is
   the contribution share. Star colour is closeness to your taste. A card's rank is its place in your
   ten and its suit is the part of the model that carried it. Nothing decorative pretends to be data.
2. **One moment of spectacle.** The deal is the memorable moment. Everything around it is quiet:
   solid panels, sentence-case reading text, no glow behind text.
3. **Evidence from people, not only numbers.** Each pick shows the game itself (Steam art and store
   link), what its players say and the words both communities use, next to the exact shares.
4. **Human words.** Plain verbs and sentence case in everything you read. Poster capitals only for
   titles and labels. The technical story lives in Under the hood and Architecture.
5. **Respect the viewer.** Flashes are capped, effects and sound can be turned down or off, and reduced
   motion turns every effect off.

## Colour

| Token | Hex | Use |
| --- | --- | --- |
| `--ink` (`--bg`) | `#0B0710` | the sky, the page |
| `--velvet` (`--surface`) | `#160B1B` | panels (97% opaque) |
| `--raised` | `#241329` | hover, selected rows |
| `--seam` (`--line`) | `#3A1E40` | borders, rules (non-text) |
| `--bone` (`--text`) | `#F7EFE6` | body text, your stars, card faces, tickets, balloons |
| `--ash` (`--muted`) | `#BCAAB9` | secondary text |
| `--crimson` (`--pick`) | `#D1173A` | the pick, the primary action, hearts; never text on dark |
| `--crimson-hot` | `#FF2E4F` | light only: spotlight, bursts, reason lines |
| `--crimson-text` (`--pick-text`) | `#FF5C72` | crimson words on dark, focus ring |
| `--rose` | `#FF8FB1` | highlights |
| `--quantum` / `--quantum-text` (`--link`) | `#7B4DFF` / `#B9A2FF` | the graph: tags, studios, PageRank; clubs; links |
| `--club` | `#4A2BB8` | clubs printed on bone |
| `--on-bone` / `--on-bone-muted` | `#1A0E18` / `#5E4A58` | text on bone |
| `--good`, `--cold` (`--bad`) | `#7FE0B0`, `#74D4E6` | verified; a game that pulls away (negative contribution) |

Two accents with fixed jobs: crimson is "the pick and what to do next", violet is "the graph".
Contrast (WCAG 2.1, computed): Bone ≥ 15.3:1, Ash ≥ 7.9:1, Crimson text ≥ 5.8:1, Quantum text
≥ 8.0:1, Rose ≥ 8.1:1 on every dark surface; ink on bone 16.5:1, muted ink on bone 7.1:1, crimson on
bone 4.7:1, club on bone 7.9:1; bone on the crimson button 4.7:1.

### Closeness

c = √(s / s_max), where s is a game's score and s_max the best score among games you do not own
(`web/src/lib/sky.ts`). Tiers, closest first:

| c | Tier | Plain words |
| --- | --- | --- |
| ≥ 0.9 | Twin star | about as close to your taste as a game gets here |
| ≥ 0.7 | Close orbit | close to your taste |
| ≥ 0.5 | Same constellation | shares a lot with your games |
| ≥ 0.3 | Neighbouring sky | some overlap with your games |
| < 0.3 | Distant light | little overlap with your games |

Colour modes (Settings, remembered; Starfall's saved choices map across), interpolated in OKLab from
distant to closest:

| Mode | Stops |
| --- | --- |
| Crimson and violet (default) | indigo, violet, orchid, rose, crimson |
| Crimson | maroon, deep crimson, crimson, pale rose (lightness rising) |
| Star temperature | red, orange, yellow, white, blue-white |

## Cards

The ten picks are a hand (`web/src/lib/cards.ts`). Rank 1 is the **Ace**, then 2 to 10. A pick's
score is exactly its EASE^R (co-play) part plus its PageRank (graph) part, summed over your games,
so the suit is computed, not chosen:

| Suit | When | Colour |
| --- | --- | --- |
| Hearts ♥ | the co-play part is at least the graph part: players in common carried it | crimson |
| Clubs ♣ | the graph part is larger: tags, studios and publishers carried it | violet |

Screen readers hear "Ace of hearts: XCOM 2, Twin star". The pick panel says how much of the score
the suit's part carried. Picks kept for variety say so in words.

## Type

| Role | Font (OFL, self-hosted) | Use |
| --- | --- | --- |
| Poster | Anton 400 | the wordmark, view and panel titles, section labels, card indices, numbers that matter; capitals |
| Names | Prata 400 | game titles, starter hands |
| Interface | Josefin Sans 400–700 (and italic) | everything you read, sentence case |
| Players | Comic Relief 400/700 | what players wrote, in speech balloons |
| Code | JetBrains Mono 500 | equations and source paths only |

Anton and Comic Relief are Latin subsets in `web/src/assets/fonts/` with their licences; the rest
come from Fontsource. Scale: 13, 14.5, 16, 20, 27, 36 px; the wordmark is 132 px at most on the title
screen and 27 px in the bar.

**Wordmark.** WHY in crimson, FINDER in bone, Anton capitals slanted 8°, with two hard offset shadows
(deep crimson, then violet at 40%), like a poster printed slightly out of register. On the title screen
a crimson ribbon with forked ends sits beneath it: "Find your next game. Know why."

## Frames and shapes

- **Panels:** square, velvet, a 1 px seam and a 56 px crimson rule on the top edge. Data panels get a
  longer rule and a corner of crimson halftone.
- **Cards:** bone, 12 px corners, an inner rule 6 px in, corner indices (rank over suit; the bottom
  one turned upside down), and a hard 8 px shadow in the suit's colour. The pick card holds the Steam
  art as its picture with the closeness tier stamped across its corner.
- **Buttons:** slanted plates (−10°). Primary: crimson with a bone offset (an ink offset on bone).
  Ghost: words with a crimson underline.
- **Inputs:** bone with a crimson offset. The title-screen search is an admission ticket: a stub with a
  four-pointed star, a dashed perforation and "Admit one" along the edge.
- **Speech balloons** for player quotes: bone, ink text, a tail at the lower left, a violet offset.
- **Terms** both communities use: violet tickets with a dashed edge.
- **Markers and bullets:** four-pointed stars. Halftone dots for texture, never behind text.

## Layout

- **Title screen:** a centred poster on the stage: wordmark and ribbon, one paragraph, the ticket
  search, and four starter hands fanned like cards. A spotlight falls from the top of the sky; a pool
  of dark sits behind the words so no star is ever under text. On phones the hands sit in a 2 × 2 grid.
- **Discover with results:** Your sky and Your hand on the left (340 px), the sky in the centre, the
  pick card on the right (430 px). Below 1180 px the pick moves under the sky; on phones everything
  stacks under a 46vh sky.

## Components

| Component | Notes |
| --- | --- |
| Search | Combobox; the ticket on the title screen, a bone field in Your sky; adds a twinkle and a rose ring on the star |
| Your sky | Your games with hours (the weight), remove, "Find my next game" |
| Describe | "like Portal 2, co-op, under $20": titles join your sky, tags, price and years become filters (violet ticket chips you can remove), unknown words are said back; on the title screen it deals at once |
| Your hand | Ranked list of ten mini cards (rank and suit on bone), title, closeness star and tier, "picked for variety"; rows are dealt in as each card lands; a suit key beneath |
| Pick card | Bone card face: indices, Steam art (fallback plate), stamped tier, title, studio, year, price; then View on Steam; closeness scale; which suit and how much it carried; Because you love (exact shares, crimson co-play and violet graph parts); Players who also played X say (balloons); Other players say; Both communities talk about; What would change it; How it connects to your games |
| Settings | Star colours, sound and volume, impact effects |
| Inspect card | Click any star: a small bone card with title, studio, price, tags, Add to your sky |

## Motion (ADR-0016, ADR-0017, ADR-0018)

| Element | Motion | Reduced motion |
| --- | --- | --- |
| Sky | three parallax layers, twinkle, a crimson and violet nebula with halftone corners; a swaying spotlight on the title screen; the camera springs to frame what matters | static, jumps |
| The deal | per card, the 10 to the Ace: a spotlight cone and a turning four-pointed star find the spot; the card falls from the upper right, turning over (crimson back, bone face) with a streak; it bursts into its star: bone, halftone and violet shockwaves, shards, a short shake | cards appear in place |
| Impact frame | top three only: one inverted frame (bone, ink speed lines, a halftone ring), one ink frame with crimson lines, then a crimson bloom; at most three a second | none |
| The Ace | hangs in the spotlight before it falls, lands hardest, then a jagged crimson burst with "AHA!" pops in and confetti falls over the stage | none |
| Recolour | after the Ace lands, every star takes its closeness colour, rippling out from your stars | instant |
| Reasons | lines draw in, then light travels from your game to the pick | appear; no particles |
| Panels | rows are dealt in; the pick card turns over into place and its tier is stamped on | none |

The loop runs at full rate only while something moves and idles at about 20 fps for the twinkle;
it stops when the tab is hidden.

## Sound

Synthesized in the browser (`web/src/lib/sfx.ts`): a card flick as each card is dealt, a falling
whoosh (noise through a falling band-pass), the impact (sine thump, noise crack, a bell from a D major
pentatonic, with the Ace on the root an octave down), a brass "ta-da" and cymbal for the Ace, a lock-on
glissando, select (a card slide and a chime) and add (a twinkle). On by default; starts on the first
click or key; mute and volume are remembered.

## Accessibility

- Every star a card lands on has a keyboard button; the hand is the full alternative to the sky.
- Focus ring 2 px crimson text colour, offset 2 px (crimson on bone).
- Colour never carries meaning alone: tiers and suits are named, negative contributions have a minus sign.
- The deal can be skipped with Esc, Space, Enter, a click or the Skip button.
- Target: axe 0 violations on every view and the settings dialog (NFR-09).

## Logo

A Y-shaped constellation ("why"): two violet-joined bone stars and a centre star, with a crimson
four-pointed star below it (the pick), on ink with a corner of halftone. Wordmark: see Type.
