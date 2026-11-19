<script lang="ts">
  /**
   * Under the hood: the same run you see in Discover, replayed stage by stage from the engine's own
   * traces. Nothing here is a mock-up: every number is what the worker computed for your history.
   */
  import type { Trace } from '../../engine/protocol';
  import GramHeatmap from '../hood/GramHeatmap.svelte';
  import { int, ms, num, pct, rank, source } from '../format';
  import { app, type SceneLine } from '../state.svelte';

  type Stage = { id: string; title: string; short: string; planned?: boolean };
  const STAGES: Stage[] = [
    { id: 'history', title: 'Your history becomes a vector', short: 'History to weights' },
    { id: 'ease', title: 'EASE^R: a closed-form co-play model', short: 'EASE^R' },
    { id: 'push', title: 'PageRank by forward push', short: 'Graph + push' },
    { id: 'blend', title: 'One additive blend', short: 'Blend' },
    { id: 'shortlist', title: 'Drop what you own, shortlist 100', short: 'Shortlist' },
    { id: 'dpp', title: 'DPP: variety without losing relevance', short: 'DPP variety' },
    { id: 'explain', title: 'Exact reasons, smallest counterfactual', short: 'Explain' },
    { id: 'words', title: 'Grounded words (arrives in M3)', short: 'Words', planned: true },
  ];

  let sub = $state(0);
  let playing = $state(false);
  let speed = $state(1);
  let seedPick = $state(0);
  let traces = $state.raw<Trace[]>([]);
  let neighbours = $state.raw<{ game: number; top: [number, number, number][] }[]>([]);
  let fetchedFor = '';

  const games = $derived(app.slice?.games ?? []);
  const result = $derived(app.result);
  const stage = $derived(STAGES[app.stage]);
  const params = $derived(app.model?.params);
  const history = $derived(result?.history ?? []);
  const trace = $derived(traces[Math.min(seedPick, traces.length - 1)] ?? null);
  const pickE = $derived(result?.explanations[app.selected] ?? null);

  const subs = $derived.by(() => {
    if (!result) return 1;
    if (stage.id === 'ease') return 24;
    if (stage.id === 'push') return trace?.trace.length ?? 1;
    if (stage.id === 'dpp') return result.steps.length || 1;
    if (stage.id === 'explain') return pickE?.counterfactual.trail.length ?? 1;
    return 1;
  });

  // Fetch traces for the current history once per result.
  $effect(() => {
    const r = app.result;
    const client = app.client;
    if (!r || !client || fetchedFor === app.resultFor) return;
    fetchedFor = app.resultFor;
    const seeds = r.history.map(([j]) => j);
    void client.trace(seeds).then((t) => (traces = t));
    void client.neighbours(seeds).then((n) => (neighbours = n));
  });

  // Reset the sub-step when the stage changes.
  let lastStage = -1;
  $effect(() => {
    if (app.stage !== lastStage) {
      lastStage = app.stage;
      sub = stage.id === 'ease' ? 0 : 0;
    }
  });

  // Player: advance sub-steps, then stages.
  $effect(() => {
    if (!playing) return;
    const id = setInterval(
      () => {
        if (sub < subs - 1) sub += 1;
        else if (app.stage < STAGES.length - 2) {
          app.stage += 1;
          sub = 0;
        } else playing = false;
      },
      (stage.id === 'ease' ? 70 : stage.id === 'history' || subs === 1 ? 2200 : 650) / speed,
    );
    return () => clearInterval(id);
  });

  // What the atlas shows for each stage.
  $effect(() => {
    const r = result;
    if (!r) return;
    const n = games.length;
    const hist = r.history.map(([j]) => j);
    const base = { history: hist, picks: [] as number[], selected: null as number | null, lines: [] as SceneLine[], glow: null as Float32Array | null, hubs: [] as number[], hubGlow: null as Map<number, number> | null, dim: 0.35 };
    const key = `hood:${app.resultFor}:${app.stage}`;
    if (stage.id === 'history') {
      app.scene = { ...base, focus: hist, key };
    } else if (stage.id === 'ease') {
      const glow = new Float32Array(n);
      const lines: SceneLine[] = [];
      const reveal = sub >= subs - 1;
      for (const row of neighbours) {
        const max = row.top[0]?.[1] || 1;
        for (const [i, w] of row.top.slice(0, 5)) {
          if (reveal) lines.push({ from: row.game, to: i, share: w / max, kind: 'neighbor' });
          glow[i] = Math.max(glow[i], reveal ? w / max : 0);
        }
      }
      app.scene = { ...base, focus: reveal ? [...hist, ...neighbours.flatMap((r) => r.top.slice(0, 5).map(([i]) => i))] : hist, lines, glow, key: `${key}:${reveal}` };
    } else if (stage.id === 'push' && trace) {
      const glow = new Float32Array(n);
      const hubGlow = new Map<number, number>();
      const p = trace.trace[Math.min(sub, trace.trace.length - 1)].p;
      let max = 1e-12;
      for (let v = 0; v < p.length; v++) if (v !== trace.seed) max = Math.max(max, p[v]);
      for (let v = 0; v < p.length; v++) {
        if (v === trace.seed) continue;
        const t = Math.sqrt(p[v] / max);
        if (t < 0.08) continue;
        if (v < n) glow[v] = t;
        else hubGlow.set(v, t);
      }
      const hubs = [...hubGlow.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12).map(([v]) => v);
      app.scene = { ...base, history: [trace.seed], focus: [trace.seed, ...trace.top.slice(0, 8).map(([i]) => i)], glow, hubs, hubGlow, dim: 0.5, key: `${key}:${trace.seed}` };
    } else if (stage.id === 'blend' || stage.id === 'shortlist') {
      const glow = new Float32Array(n);
      const list = stage.id === 'blend' ? r.topScores.slice(0, 20) : r.topScores;
      const max = list[0]?.[1] || 1;
      list.forEach(([i, s], t) => (glow[i] = stage.id === 'blend' ? Math.max(0.15, s / max) : t < 10 ? 1 : 0.35));
      app.scene = { ...base, focus: [...hist, ...list.slice(0, 20).map(([i]) => i)], glow, key };
    } else if (stage.id === 'dpp') {
      const steps = r.steps.slice(0, sub + 1);
      const picked = steps.map((s) => s.picked);
      const glow = new Float32Array(n);
      const gains = r.steps[Math.min(sub, r.steps.length - 1)]?.gains ?? [];
      const g0 = Math.max(...gains.map(([, g]) => g), 1e-12);
      for (const [i, g] of gains) if (!picked.includes(i)) glow[i] = Math.max(0.08, g / g0) * 0.8;
      app.scene = { ...base, picks: picked, selected: picked[picked.length - 1] ?? null, focus: [...hist, ...r.picks], glow, key: `${key}:${sub}` };
    } else {
      const e = pickE;
      if (!e) return;
      const total = e.attributions.reduce((s, a) => s + Math.abs(a.total), 0) || 1;
      const step = e.counterfactual.trail[Math.min(sub, e.counterfactual.trail.length - 1)];
      const removed = new Set(stage.id === 'explain' && step ? step[1] : []);
      const lines: SceneLine[] = e.attributions
        .filter((a) => !removed.has(a.game))
        .map((a) => ({ from: a.game, to: e.pick, share: Math.abs(a.total) / total, kind: a.total < 0 ? 'negative' : 'reason' }));
      app.scene = { ...base, history: hist.filter((j) => !removed.has(j)), picks: r.picks, selected: e.pick, lines, focus: [...hist, e.pick], dim: 0.3, key: `${key}:${app.selected}:${sub}` };
    }
  });

  function go(i: number): void {
    app.stage = Math.max(0, Math.min(STAGES.length - 1, i));
    sub = 0;
  }

  async function demo(): Promise<void> {
    const want = ['FTL: Faster Than Light', 'The Binding of Isaac', 'XCOM: Enemy Unknown'];
    const hours = [60, 90, 45];
    app.history = want
      .map((t, k) => ({ index: games.findIndex((g) => g.title === t), hours: hours[k] }))
      .filter((h) => h.index >= 0);
    await app.find();
  }

  $effect(() => {
    if (app.stale && !app.running) void app.find();
  });

  const blendMax = $derived(Math.max(...(result?.parts ?? []).map(([, a, b]) => Math.abs(a) + Math.abs(b)), 1e-12));
</script>

<div class="hood">
  <nav class="panel rail" aria-label="Pipeline stages">
    <p class="micro">The pipeline, on your history</p>
    <ol>
      {#each STAGES as s, i (s.id)}
        <li>
          <button class:active={app.stage === i} class:planned={s.planned} aria-current={app.stage === i ? 'step' : undefined} onclick={() => go(i)}>
            <span class="num mono">{i + 1}</span>
            <span>{s.short}</span>
            {#if s.planned}<span class="chip">M3</span>{/if}
          </button>
        </li>
      {/each}
    </ol>
    {#if result}
      <p class="micro run">
        Last run took {ms(result.timings.score)} to score, {ms(result.timings.pi)} for PageRank rows and {ms(result.timings.explain)} to explain.
      </p>
    {/if}
  </nav>

  <div class="stage" data-stage>
    {#if !result}
      <div class="panel empty">
        <p>Under the hood replays the engine's real computation on <em>your</em> games.</p>
        <button class="btn primary" onclick={demo} disabled={!app.ready}>Run it on FTL, Isaac and XCOM</button>
        <button class="btn ghost" onclick={() => app.go('discover')}>Or pick your own games</button>
      </div>
    {/if}
  </div>

  {#if result && params}
    <section class="panel hud detail" aria-labelledby="stage-title" aria-live="polite">
      <p class="micro">Stage {app.stage + 1} of {STAGES.length}</p>
      <h2 id="stage-title">{stage.title}</h2>
      {#key app.stage}
        <div class="body">
          {#if stage.id === 'history'}
            <p>The model never trains on you. Your games become a weight vector, one entry per game, and that is all it sees.</p>
            <p class="eq mono">x<sub>j</sub> = 1 + α·ln(1 + h<sub>j</sub>/ε) &nbsp; (α = {params.confidence.alpha}, ε = {params.confidence.eps})</p>
            <table>
              <thead><tr><th>Game</th><th>Hours</th><th>x<sub>j</sub></th></tr></thead>
              <tbody>
                {#each history as [j, x] (j)}
                  <tr><td>{games[j].title}</td><td class="mono">{app.history.find((h) => h.index === j)?.hours ?? '—'}</td><td class="mono">{num(x)}</td></tr>
                {/each}
              </tbody>
            </table>
            <p class="cost micro">Cost O(|H|). Source: <a href={source('src/whyfinder/core/blend.py')}>core/blend.py</a>, <a href={source('web/src/engine/blend.ts')}>engine/blend.ts</a></p>
          {:else if stage.id === 'ease'}
            <p>Two games are similar when the same players review both. EASE^R turns those co-play counts into item-item weights in one closed-form solve, with no training loop.</p>
            <p class="eq mono">P = (G + λI)<sup>−1</sup>, &nbsp;B<sub>ij</sub> = −P<sub>ij</sub> / P<sub>jj</sub>, &nbsp;B<sub>jj</sub> = 0 &nbsp; (λ = {params.lambda})</p>
            <GramHeatmap sweep={sub / (subs - 1)} rows={history.map(([j]) => j)} />
            <p class="micro">
              {sub < subs - 1 ? `Replaying the Cholesky sweep: column ${Math.round((sub / (subs - 1)) * games.length)} of ${games.length}` : `Solved on your device in ${ms(app.ready?.timings.ease ?? 0)}, from ${int(app.slice?.users ?? 0)} players behind G`}
            </p>
            {#if sub >= subs - 1}
              {#each neighbours as row (row.game)}
                <p class="nb"><strong>{games[row.game].title}</strong> → {row.top.slice(0, 3).map(([i, w]) => `${games[i].title} (${num(w, 4)})`).join(', ')}</p>
              {/each}
            {/if}
            <p class="cost micro">Cost O(n³) once (n = {games.length}). Matches Python to 1e-9 in CI. Source: <a href={source('src/whyfinder/core/ease.py')}>core/ease.py</a>, <a href={source('web/src/engine/ease.ts')}>engine/ease.ts</a></p>
          {:else if stage.id === 'push'}
            <p>
              A second view of similarity: a graph of games, tags, developers and publishers ({int(app.ready?.nodes ?? 0)} nodes, {int(app.ready?.edges ?? 0)} edges).
              A random walk that restarts at your game settles on games nearby. Forward push computes it locally, round by round.
            </p>
            <p class="eq mono">π<sub>g</sub> = α·e<sub>g</sub> + (1−α)·π<sub>g</sub>P <br />|π − p| ≤ ε·d(v), ε = {params.pushEps}</p>
            {#if traces.length > 1}
              <div class="seeds" role="group" aria-label="Seed game">
                {#each traces as t, k (t.seed)}
                  <button class="chip" class:link={k === seedPick} onclick={() => ((seedPick = k), (sub = 0))}>{games[t.seed].title}</button>
                {/each}
              </div>
            {/if}
            {#if trace}
              {@const r = trace.trace[Math.min(sub, trace.trace.length - 1)]}
              <p class="micro">Round {Math.min(sub, trace.rounds - 1) + 1} of {trace.rounds}: {int(r.active)} nodes pushed, {pct(r.settled, 1)} settled, {pct(r.residual, 1)} residual</p>
              <div class="spark" aria-hidden="true">
                {#each trace.trace as t, k (k)}
                  <span class:on={k <= sub} style:height={`${Math.max(4, t.settled * 100)}%`}></span>
                {/each}
              </div>
              <p class="micro">{int(trace.pushes)} pushes in total. Nearest games from {games[trace.seed].title}:</p>
              <ol class="toplist">
                {#each trace.top.slice(0, 5) as [i, v] (i)}<li>{games[i].title} <span class="mono">{num(v, 5)}</span></li>{/each}
              </ol>
            {/if}
            <p class="cost micro">Cost O(1/(αε)) per seed, independent of graph size. Source: <a href={source('src/whyfinder/graph/ppr.py')}>graph/ppr.py</a>, <a href={source('web/src/engine/ppr.ts')}>engine/ppr.ts</a></p>
          {:else if stage.id === 'blend'}
            <p>Both models are linear in your history, so one blended matrix keeps every reason exact. Move β to trade co-play for graph.</p>
            <p class="eq mono">M = β·B/c<sub>B</sub> + (1−β)·Π/c<sub>Π</sub>, &nbsp; s = Σ<sub>j</sub> x<sub>j</sub>·M<sub>j·</sub></p>
            <label class="slider">
              <span class="micro">β = {app.beta.toFixed(2)}</span>
              <input type="range" min="0" max="1" step="0.05" bind:value={app.beta} aria-label="Blend weight beta" />
            </label>
            <ul class="stack">
              {#each result.parts.slice(0, 10) as [i, a, b] (i)}
                <li>
                  <span class="who">{games[i].title}</span>
                  <span class="bars" aria-label={`EASE ${num(a)}, PageRank ${num(b)}`}>
                    <span class="e" style:width={`${(Math.max(0, a) / blendMax) * 100}%`}></span><span class="p" style:width={`${(Math.max(0, b) / blendMax) * 100}%`}></span>
                  </span>
                </li>
              {/each}
            </ul>
            <p class="legend micro"><span class="key e"></span> EASE^R part <span class="key p"></span> PageRank part</p>
            <p class="micro">c<sub>B</sub> = {num(app.model?.cB ?? 0, 5)}, c<sub>Π</sub> = {num(app.model?.cPi ?? 0, 5)} (99th percentile, from the Python build)</p>
            {#if app.verified}
              <p class="micro ok">✓ Recomputed here from all {games.length} PageRank rows in {app.verified.seconds.toFixed(1)} s: c<sub>Π</sub> = {num(app.verified.cPi, 5)}, c<sub>B</sub> = {num(app.verified.cB, 5)}</p>
            {:else}
              <button class="btn" onclick={() => app.verify()} disabled={!!app.progress}>{app.progress?.phase === 'pi' ? `Computing ${app.progress.done}/${app.progress.total} rows…` : 'Verify the constants in your browser'}</button>
            {/if}
            <p class="cost micro">Cost O(|H|·K) per request. Source: <a href={source('src/whyfinder/core/blend.py')}>core/blend.py</a>, <a href={source('web/src/engine/blend.ts')}>engine/blend.ts</a></p>
          {:else if stage.id === 'shortlist'}
            <p>Games you already have are removed; the rest are ranked by score (ties by game ID) and the best {params.candidates} go on to re-ranking.</p>
            <div class="spark wide" aria-hidden="true">
              {#each result.topScores as [i, s], k (i)}
                <span class:on={k < 10} style:height={`${Math.max(3, (s / (result.topScores[0][1] || 1)) * 100)}%`}></span>
              {/each}
            </div>
            <p class="micro">{result.topScores.length} candidates. Crimson marks the top 10 by score alone.</p>
            <p class="cost micro">Filters by tag, price and year arrive with natural-language queries (M3, FR-23). Source: <a href={source('src/whyfinder/rerank/pipeline.py')}>rerank/pipeline.py</a></p>
          {:else if stage.id === 'dpp'}
            <p>Ten copies of the same game is a bad list. A determinantal point process picks games that are relevant <em>and</em> different, one greedy step at a time.</p>
            <p class="eq mono">L = Diag(q)·S·Diag(q), q<sub>i</sub> = e<sup>θŝ<sub>i</sub></sup><br />pick argmax d<sub>i</sub>² = det L<sub>Y∪i</sub> / det L<sub>Y</sub></p>
            <label class="slider">
              <span class="micro">θ = {app.theta.toFixed(1)} (higher = relevance matters more)</span>
              <input type="range" min="0" max="6" step="0.5" bind:value={app.theta} aria-label="DPP relevance weight theta" />
            </label>
            {#if result.steps.length}
              {@const st = result.steps[Math.min(sub, result.steps.length - 1)]}
              <p class="micro">Step {Math.min(sub, result.steps.length - 1) + 1} of {result.steps.length}: picked <strong class="pickname">{games[st.picked].title}</strong>{result.variety[Math.min(sub, result.steps.length - 1)] ? ', picked for variety' : ''}</p>
              <ul class="stack">
                {#each [...st.gains].sort((a, b) => b[1] - a[1]).slice(0, 8) as [i, g] (i)}
                  <li>
                    <span class="who" class:chosen={i === st.picked}>{games[i].title}</span>
                    <span class="bars"><span class="g" class:pick={i === st.picked} style:width={`${(g / (st.gains.reduce((m, x) => Math.max(m, x[1]), 1e-12))) * 100}%`}></span></span>
                  </li>
                {/each}
              </ul>
            {/if}
            <p class="cost micro">Cost O(N·k²) = {params.candidates}·{params.k}². Source: <a href={source('src/whyfinder/rerank/dpp.py')}>rerank/dpp.py</a>, <a href={source('web/src/engine/dpp.ts')}>engine/dpp.ts</a></p>
          {:else if stage.id === 'explain' && pickE}
            <div class="seeds" role="group" aria-label="Pick">
              {#each result.picks as p, t (p)}
                <button class="chip" class:link={t === app.selected} onclick={() => ((app.selected = t), (sub = 0))} aria-label={`Pick ${t + 1}: ${games[p].title}`}>{rank(t)}</button>
              {/each}
            </div>
            <p><strong>{games[pickE.pick].title}</strong> scored {num(pickE.score)}. Because the score is a sum over your games, each game's share is exact.</p>
            <table>
              <thead><tr><th>Your game</th><th>EASE^R</th><th>PageRank</th><th>Total</th></tr></thead>
              <tbody>
                {#each pickE.attributions as a (a.game)}
                  <tr><td>{games[a.game].title}</td><td class="mono">{num(a.ease)}</td><td class="mono">{num(a.ppr)}</td><td class="mono">{num(a.total)}</td></tr>
                {/each}
              </tbody>
            </table>
            <p class="micro ok">Σ = {num(pickE.attributions.reduce((s, a) => s + a.total, 0))} = score, |Δ| = {Math.abs(pickE.attributions.reduce((s, a) => s + a.total, 0) - pickE.score).toExponential(1)}</p>
            <p class="micro">Counterfactual search: remove games in order of contribution, re-run the whole pipeline, then prune.</p>
            <ol class="trail">
              {#each pickE.counterfactual.trail as [action, tried, shown], k (k)}
                <li class:on={k <= sub} class:now={k === sub}>
                  <span class="mono">{action === 'remove' ? 'remove' : 'prune'}</span>
                  {tried.map((j) => games[j].title).join(' + ')}
                  <span class="verdict" class:gone={!shown}>{shown ? 'still in top 10' : 'pick gone'}</span>
                </li>
              {/each}
            </ol>
            <p class="cost micro">{pickE.counterfactual.runs} pipeline runs. Valid and irreducible (ADR-0012). Source: <a href={source('src/whyfinder/explain/counterfactual.py')}>explain/counterfactual.py</a>, <a href={source('web/src/engine/explain.ts')}>engine/explain.ts</a></p>
          {:else if stage.id === 'words'}
            <p>In M3 a local LLM will put these exact reasons into sentences, quoting real reviews. It may only say what the model computed:</p>
            <ol class="plan">
              <li>Retrieve review passages for the shared aspects: BM25 + a hand-written HNSW index, fused by RRF.</li>
              <li>The LLM writes claims as JSON; each cites an attribution or a quoted review span.</li>
              <li>A deterministic checker rejects absent attributions, wrong percentages and non-verbatim quotes; one retry, then a template.</li>
            </ol>
            <p class="cost micro">Planned for M3 (Jan 2 to 13). See docs/spec/06_RAG.md.</p>
          {/if}
        </div>
      {/key}
    </section>

    <div class="player panel" role="group" aria-label="Playback">
      <button class="btn ghost" onclick={() => (sub > 0 ? (sub -= 1) : go(app.stage - 1))} aria-label="Previous step">◀</button>
      <button class="btn primary" onclick={() => (playing = !playing)} aria-pressed={playing}>{playing ? 'Pause' : 'Play the run'}</button>
      <button class="btn ghost" onclick={() => (sub < subs - 1 ? (sub += 1) : go(app.stage + 1))} aria-label="Next step">▶</button>
      <label class="micro speed">
        Speed
        <select bind:value={speed} aria-label="Playback speed">
          <option value={0.5}>0.5×</option>
          <option value={1}>1×</option>
          <option value={2}>2×</option>
        </select>
      </label>
      {#if subs > 1}
        <input class="scrub" type="range" min="0" max={subs - 1} bind:value={sub} aria-label="Step within this stage" />
      {/if}
    </div>
  {/if}
</div>

<style>
  .hood {
    position: relative;
    z-index: 2;
    display: grid;
    grid-template-columns: 230px minmax(0, 1fr) 420px;
    grid-template-rows: minmax(0, 1fr) auto;
    grid-template-areas: 'rail stage detail' 'rail player detail';
    gap: var(--space-4) var(--space-5);
    height: calc(100dvh - 64px);
    padding: 0 var(--space-5) var(--space-5);
    pointer-events: none;
  }
  .rail,
  .detail,
  .player,
  .empty {
    pointer-events: auto;
  }
  .rail {
    grid-area: rail;
    align-self: start;
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  .rail ol {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .rail button {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border-radius: 0;
    border: 1px solid transparent;
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    text-align: left;
    font-size: var(--text-sm);
  }
  .rail button:hover {
    color: var(--text);
    background: var(--raised);
  }
  .rail button.active {
    color: var(--text);
    background: var(--raised);
    border-color: var(--line);
  }
  .rail button.planned {
    border-style: dashed;
    border-color: var(--line);
  }
  .num {
    width: 20px;
    height: 27px;
    display: grid;
    place-items: center;
    border-radius: 3px;
    border: var(--border);
    font-family: var(--font-poster);
    font-size: 13px;
    transition: transform var(--dur-fast) var(--ease-pop);
  }
  .active .num {
    border-color: var(--bone);
    background: var(--bone);
    color: var(--crimson);
    transform: rotate(-6deg);
    box-shadow: 2px 2px 0 var(--crimson);
  }
  .run {
    margin: 0;
    font-size: 10px;
  }
  .stage {
    grid-area: stage;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .empty {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    align-items: center;
    max-width: 420px;
    text-align: center;
  }
  .empty p {
    margin: 0;
  }
  .detail {
    grid-area: detail;
    overflow-y: auto;
    scrollbar-width: thin;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  .detail h2 {
    font-size: var(--text-xl);
  }
  .body {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    animation: rise var(--dur-fast) var(--ease-out);
  }
  .body p {
    margin: 0;
    font-size: var(--text-sm);
  }
  .body p.micro {
    font-size: var(--text-xs);
  }
  .eq {
    background: var(--bg);
    border: var(--border);
    border-radius: 0;
    padding: 8px 10px;
    font-size: 12px !important;
    color: var(--text);
    overflow-x: auto;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--text-sm);
  }
  th {
    text-align: left;
    font-size: var(--text-xs);
    font-weight: 500;
    color: var(--muted);
    border-bottom: var(--border);
    padding: 4px 6px 4px 0;
  }
  td {
    padding: 5px 6px 5px 0;
    border-bottom: 1px solid color-mix(in srgb, var(--line) 50%, transparent);
  }
  td.mono {
    font-size: 12px;
    white-space: nowrap;
  }
  .cost {
    border-top: var(--border);
    padding-top: var(--space-2);
  }
  .nb {
    font-size: var(--text-xs) !important;
    color: var(--muted);
  }
  .nb strong {
    color: var(--text);
  }
  .seeds {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .seeds .chip {
    cursor: pointer;
    background: transparent;
  }
  .spark {
    display: flex;
    align-items: flex-end;
    gap: 2px;
    height: 48px;
  }
  .spark span {
    flex: 1;
    background: var(--raised);
    border-radius: 2px 2px 0 0;
    transition: background var(--dur-fast);
  }
  .spark span.on {
    background: var(--link);
  }
  .spark.wide span {
    gap: 1px;
  }
  .spark.wide span.on {
    background: var(--pick);
  }
  .spark.wide span:not(.on) {
    background: color-mix(in srgb, var(--link) 40%, transparent);
  }
  .toplist,
  .plan {
    margin: 0;
    padding-left: 20px;
    font-size: var(--text-sm);
  }
  .toplist .mono {
    color: var(--muted);
    font-size: 11px;
  }
  .slider {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .stack {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .stack li {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr);
    gap: 10px;
    align-items: center;
    font-size: var(--text-sm);
  }
  .who {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .who.chosen,
  .pickname {
    color: var(--pick-text);
  }
  .bars {
    display: flex;
    height: 8px;
    background: var(--ink);
    overflow: hidden;
    transform: skewX(-20deg);
  }
  .bars .e {
    background: var(--crimson);
    transition: width 300ms var(--ease-out);
  }
  .bars .p {
    background: var(--quantum);
    transition: width 300ms var(--ease-out);
  }
  .bars .g {
    background: var(--quantum);
    transition: width 300ms var(--ease-out);
  }
  .bars .g.pick {
    background: var(--crimson);
  }
  .legend {
    display: flex;
    gap: 6px;
    align-items: center;
  }
  .key {
    display: inline-block;
    width: 14px;
    height: 8px;
    transform: skewX(-20deg);
    margin-left: 8px;
  }
  .key.e {
    background: var(--crimson);
    margin-left: 0;
  }
  .key.p {
    background: var(--quantum);
  }
  .ok {
    color: var(--good);
  }
  .trail {
    margin: 0;
    padding-left: 20px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: var(--text-sm);
  }
  .trail li {
    opacity: 0.4;
    transition: opacity var(--dur-fast);
  }
  .trail li.on {
    opacity: 1;
  }
  .trail li.now {
    color: var(--text);
  }
  .trail .mono {
    font-size: 11px;
    color: var(--muted);
    margin-right: 4px;
  }
  .verdict {
    font-family: var(--font-mono);
    font-size: 10px;
    margin-left: 6px;
    color: var(--muted);
  }
  .verdict.gone {
    color: var(--pick-text);
  }
  .player {
    grid-area: player;
    justify-self: center;
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: 8px 12px;
    flex-wrap: wrap;
  }
  .speed {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .speed select {
    background: var(--bg);
    border: var(--border);
    border-radius: 0;
    padding: 2px 6px;
  }
  .scrub {
    width: 160px;
  }
  @media (max-width: 1100px) {
    .hood {
      grid-template-columns: minmax(0, 1fr);
      grid-template-areas: 'rail' 'stage' 'player' 'detail';
      grid-template-rows: auto 46vh auto auto;
      height: auto;
    }
    .rail ol {
      flex-direction: row;
      flex-wrap: wrap;
    }
    .rail button {
      width: auto;
    }
  }
</style>
