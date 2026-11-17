# 11 · Design system: "Starfall"

Whyfinder is a night sky. Every star is a game, placed by the players it shares with other games.
Your games are white stars; when you ask for picks, ten new stars fall from the sky and strike
where they sit, and the lines between your stars and a pick are the exact reasons. The sky carries
the spectacle; the reading panels stay solid and calm. Decision record: [ADR-0017](../decisions/ADR-0017-starfall.md)
(motion: ADR-0016).

Tokens: [`docs/design/tokens.css`](../design/tokens.css). Logo: [`docs/design/logo.svg`](../design/logo.svg).

## Principles

1. **The metaphor carries meaning.** Lines exist only where an attribution exists, and line weight is
   the contribution share. Star colour is closeness to your taste. Nothing decorative pretends to be data.
2. **One moment of spectacle.** The starfall is the memorable moment. Everything around it is quiet:
   solid panels, sentence-case labels, no glow behind text.
3. **Evidence from people, not only numbers.** Each pick shows the game itself (Steam art and store
   link), what its players say and the words both communities use, next to the exact shares.
4. **Human words.** Plain verbs, sentence case, no jargon on Discover. The technical story lives in
   Under the hood and Architecture.
5. **Respect the viewer.** Flashes are capped, effects and sound can be turned down or off, and reduced
   motion turns every effect off.

## Colour

| Token | Hex | Use |
| --- | --- | --- |
| `--midnight` (`--bg`) | `#070B1E` | the sky, the page |
| `--deep` (`--surface`) | `#0D1433` | panels (97% opaque) |
| `--raised` | `#151D49` | hover, selected rows |
| `--line` | `#273068` | borders, rules (non-text) |
| `--starlight` (`--text`) | `#F5F2FF` | body text, your stars |
| `--dust` (`--muted`) | `#A9AED3` | secondary text |
| `--gold` (`--pick`) | `#F2C14E` | picks, primary action, focus ring, the co-play part of a reason |
| `--violet` / `--violet-text` (`--link`) | `#8E6BF0` / `#B8A4FF` | the graph: tags, studios, PageRank glow; links |
| `--good`, `--bad` | `#7FE0B0`, `#FF8F8F` | verified, negative contributions |

Two accents with fixed jobs: gold is "the pick and what to do next", violet is "the graph". Contrast
(WCAG 2.1, computed): Starlight ≥ 14.6:1, Dust ≥ 7.4:1, Gold ≥ 9.6:1, violet text ≥ 7.5:1 on every
surface; text on the gold button is 11.1:1. Raw `--violet` is never used for text.

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

Colour modes (Settings, remembered), interpolated in OKLab from distant to closest:

| Mode | Stops |
| --- | --- |
| Gold and violet (default) | indigo, violet, lavender, warm white, gold |
| Gold | bronze, deep gold, gold, pale gold |
| Star temperature | red, orange, yellow, white, blue-white |

## Type

| Role | Font (OFL, self-hosted) | Use |
| --- | --- | --- |
| Display | Bodoni Moda italic 500/700 | wordmark, headings, game titles, quotes, rank numerals |
| Body and UI | Hanken Grotesk 400–700 | everything else, sentence case, tabular figures |
| Code | JetBrains Mono 500 | equations and source paths only |

Scale (a perfect fourth): 12.5, 14, 15.5, 20, 27, 36 px; hero 40–68 px. No tracked capitals, no
middle-dot meta strings, no arrows appended to buttons.

## Layout

- Title screen: the hero (headline, one paragraph, a large search, four starter skies) on the left;
  the sky on the right. On phones the sky sits above the hero.
- Discover with results: "Your sky" and "Where the stars fell" on the left (340 px), the sky in the
  centre, the pick on the right (420 px). Below 1180 px the pick moves under the sky; on phones
  everything stacks under a 46vh sky.
- Radius: 14 px panels, 12 px rows, pills for buttons, chips and the search.

## Components

| Component | Notes |
| --- | --- |
| Search | Combobox; hero size on the title screen, compact in Your sky; adds a twinkle sound and a violet ring on the star |
| Your sky | Your games with hours (the weight), remove, "Find my next game" |
| Where the stars fell | Ranked list; rows appear as each star lands; rank numeral, title, closeness dot and tier, "picked for variety" |
| Pick panel | Steam header art (fallback plate) with the tier, title, studio, year, price; View on Steam; closeness scale; Because you love (exact shares, gold co-play and violet graph parts); Players who also played X say; Other players say; Both communities talk about; What would change it; How it connects to your games |
| Settings | Star colours, sound and volume, impact effects |
| Inspect card | Click any star: title, studio, price, tags, Add to your sky |

## Motion (ADR-0016, ADR-0017)

| Element | Motion | Reduced motion |
| --- | --- | --- |
| Sky | three parallax layers, twinkle, a milky band and nebula; the camera springs to frame what matters | static, jumps |
| Starfall | per pick, #10 to #1: beam and reticle lock on, an accelerating streak, impact (shockwaves, embers, crater glow, shake); #1 hangs before it falls and lands hardest | picks appear in place |
| Impact frame | top three only: one inverted frame with speed lines rushing in, one dark frame with gold lines, then a bloom; at most three a second | none |
| Recolour | after #1 lands, every star takes its closeness colour, rippling out from your stars | instant |
| Reasons | lines draw in, then light travels from your game to the pick | appear; no particles |
| Panels | rows land with a flash of brightness; the pick panel rises in | none |

The loop runs at full rate only while something moves and idles at about 20 fps for the twinkle;
it stops when the tab is hidden.

## Sound

Synthesized in the browser (`web/src/lib/sfx.ts`): falling whoosh (noise through a falling band-pass),
impact (sine thump, noise crack, a bell from a D major pentatonic, with #1 on the root an octave
down), lock-on glissando, select chime, add twinkle. On by default; starts on the first click or key;
mute and volume are remembered.

## Accessibility

- Every star a pick lands on has a keyboard button; the ranked list is the full alternative to the sky.
- Focus ring 2 px gold, offset 2 px.
- Colour never carries meaning alone: tiers are named, negative contributions have a minus sign.
- The starfall can be skipped with Esc, Space, Enter, a click or the Skip button.
- Target: axe 0 violations on every view and the settings dialog (NFR-09).

## Logo

A Y-shaped constellation ("why"): two violet-joined white stars and a centre star, with a gold
four-point star below it (the pick). Wordmark "Whyfinder" in Bodoni Moda italic 700.
