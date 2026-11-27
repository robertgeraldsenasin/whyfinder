# Labelling guide: review retrieval (#33)

When Whyfinder explains a pick, it looks for something the pick has in common with a game you
liked (a shared tag such as *Horror*, or a word both games' players use) and then searches the
pick's own reviews for a player who talks about it. That quote goes into the explanation. These
labels measure how well that search works.

The sheet is `data/labels/retrieval.csv`. It has 150 queries. Each query is one game and one
aspect, and it lists all 12 reviews the demo holds for that game, in their original order, not
ranked. You grade every review for the aspect. Because every review gets a grade, the numbers do
not depend on which search happened to show what.

## The grades

| Grade | Meaning | Would it work as the quote "Players of this game mention *aspect*"? |
| --- | --- | --- |
| 2 | The review talks about the aspect. | Yes. |
| 1 | It touches the aspect in passing, or only implies it. | Weakly. |
| 0 | It is not about the aspect. | No. |

Judge only the text in front of you. What you know about the game doesn't count: if a review of
a horror game only praises the pizza mascots, it isn't about horror.

## Examples from the sheet

**Five Nights at Freddy's / Horror**

- "I love the horror factor and the suspense that this game brings when you least expect the
  animatronics and their jumpscares." → **2**
- "This game is perfect if you want a good scare, big thanks to Scott for making these awesome
  games." → **2**. The word isn't there, but being scared is what the aspect is about.
- "Thx Scott Cawthon for this great game of mystery, horror, and fun." → **1**. It names horror
  in a list and says nothing about it.
- "Scott Cawthon, The creator of the Five Nights Series, was very clever to put in a power
  system." → **0**

**The Walking Dead: Season 2 / Story Rich**

- "A lot of things that made Season 1 good are back in this season: amazing story, great
  characters and an emotional ending." → **2**
- "Gorgeous art, interesting story and characters as well as beautiful music and voice acting
  made this a pleasure to play." → **1**. The story is one item among five.
- "I love Clem and it's quite interesting to see how a young but brave girl behaves in the
  apocalypse." → **1**. It's about a character, which is part of the story, but only implies it.

**Emily is Away / Singleplayer**

Tags that describe a game's format (*Singleplayer*, *Indie*, *Early Access*, *Multiplayer*) are
the hard ones. Give a 2 only when the review talks about that format: playing alone, a solo
campaign, being made by a small team. "It is a fun and sad game." → **0**. Expect many queries
like this to have nothing above 0. That's a real result, not a mistake.

## Who grades what

- **Labeller A** grades every row in the `label_a` column.
- **Labeller B** grades queries 1 to 30 only, in the `label_b` column, without looking at
  `label_a`. Hide that column first. These 360 double grades give Cohen's kappa, which says how
  far the grades can be trusted.

Expect about 1,800 grades for A and 360 for B, a few seconds each, so roughly an evening for A
and half an hour for B. Breaks are fine; the score command can check work in progress.

## Using Google Sheets

Import the CSV with *File > Import > Upload*, choosing *Replace current sheet*. Don't sort or
delete rows, and keep the columns in the same order. When you're done, use *File > Download >
Comma-separated values*, save it over `data/labels/retrieval.csv`, and commit it.

## Scoring

```bash
uv run whyfinder rag labels score --partial   # while grading: scores the finished queries
uv run whyfinder rag labels score             # when done; fails if a grade is missing
```

The report goes to `results/validation/retrieval-labels.json`. It holds kappa (plain, and with
linear weights for the ordered grades), and Recall@5 and nDCG@5 for three rankings of each
query's reviews: BM25 alone, the LSA vectors alone, and the two fused by reciprocal rank, which
is what the API serves. A review counts as relevant for recall at grade 1 or more; nDCG uses the
grade itself (gain 2^grade − 1). Queries where nothing scored above 0 are left out of the
averages, and the report counts them.

Don't regenerate the sheet once grading has started. `rag labels pool` refuses to overwrite a
sheet that already has grades, unless you pass `--force`.
