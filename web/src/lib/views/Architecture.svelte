<script lang="ts">
  /**
   * Architecture: the system as a live diagram. Offline numbers come from data/stats.json (the last
   * data run); browser timings come from the engine you are running right now.
   */
  import stats from '../../../../data/stats.json';
  import { int, ms, pct, source } from '../format';
  import { app } from '../state.svelte';

  type Status = 'live' | 'built' | 'planned';
  interface Node {
    id: string;
    lane: number;
    col: number;
    title: string;
    detail: string;
    status: Status;
    milestone?: string;
    about: string;
    files: string[];
  }

  const s = stats;
  const timings = $derived(app.result?.timings);
  const ready = $derived(app.ready);

  const nodes = $derived<Node[]>([
    { id: 'ucsd', lane: 0, col: 0, title: 'UCSD Steam data', detail: '1.3 GB · never committed', status: 'built', about: 'Version 2 reviews (dated, with hours played) and game metadata from the McAuley Lab. Downloaded by script on GitHub’s runners; the dataset papers are cited in CITATION.cff.', files: ['src/whyfinder/data/sources.py'] },
    { id: 'fetch', lane: 0, col: 1, title: 'fetch', detail: 'SHA-256 verified', status: 'built', about: 'Downloads with retries and backoff; every byte is checked against data/checksums.txt, so a rebuild can never silently use different data.', files: ['src/whyfinder/data/fetch.py', 'data/checksums.txt'] },
    { id: 'parse', lane: 0, col: 2, title: 'parse', detail: `${int(s.parse.reviews.lines)} lines`, status: 'built', about: 'Streams the Python-literal files line by line with ast.literal_eval in a bounded process pool; malformed lines are counted (limit 0.1%).', files: ['src/whyfinder/data/parse.py'] },
    { id: 'clean', lane: 0, col: 3, title: 'clean', detail: `${int(s.clean.users)} users`, status: 'built', about: `Hashes usernames (salted SHA-256), dedupes (user, game) keeping the most hours (${int(s.clean.duplicates_removed)} duplicates), clips hours at the 99.9th percentile. Date coverage ${pct(s.clean.date_coverage, 1)}, hours coverage ${pct(s.clean.hours_coverage, 1)}.`, files: ['src/whyfinder/data/clean.py', 'src/whyfinder/data/contracts.py'] },
    { id: 'kcore', lane: 0, col: 4, title: `${s.kcore.k}-core`, detail: `${int(s.kcore.rows_out)} pairs`, status: 'built', about: `Repeatedly drops users and games with fewer than ${s.kcore.k} interactions (${s.kcore.passes} passes). Property-tested against a one-at-a-time reference on random graphs.`, files: ['src/whyfinder/data/kcore.py'] },
    { id: 'split', lane: 0, col: 5, title: 'time split', detail: `T1 ${s.split.t1}`, status: 'built', about: `Global time cut-offs: train ${int(s.split.rows.train)}, validation ${int(s.split.rows.valid)}, test ${int(s.split.rows.test)} (sealed until release), cold-start ${int(s.split.rows.cold)}. No test row predates T2.`, files: ['src/whyfinder/data/split.py', 'data/split.json'] },
    { id: 'slice', lane: 0, col: 6, title: 'demo slice', detail: '500 games · G', status: 'built', about: 'The 500 most-played games with their co-play Gram matrix G = XᵀX (train only), tags, developers, publishers and a deterministic star-map layout. Aggregates only: no user rows, no review text.', files: ['src/whyfinder/export/demo.py'] },

    { id: 'py', lane: 1, col: 2, title: 'Python core', detail: '5 algorithms + oracles', status: 'built', about: 'The source of truth. Every algorithm is hand-written and checked against an oracle: numpy’s inverse for EASE^R, power iteration for PageRank, brute-force determinants for DPP.', files: ['src/whyfinder/core/ease.py', 'src/whyfinder/graph/ppr.py', 'src/whyfinder/rerank/dpp.py', 'src/whyfinder/explain/counterfactual.py'] },
    { id: 'goldens', lane: 1, col: 4, title: 'goldens', detail: 'TS = Python ± 1e-9', status: 'built', about: '`whyfinder export model` runs the Python core on the slice and records B and Π rows, scores, picks, variety flags, attributions and counterfactual sets. Vitest fails CI if the browser engine drifts.', files: ['src/whyfinder/export/model.py', 'web/src/engine/engine.test.ts'] },
    { id: 'gate', lane: 1, col: 6, title: 'quality gate', detail: 'bootstrap CI', status: 'planned', milestone: 'M1', about: 'Every PR that touches a model is scored against main on a validation subsample; a significant regression blocks the merge. The sealed test set is scored only at release.', files: ['docs/spec/07_EVALUATION.md'] },

    { id: 'worker', lane: 2, col: 0, title: 'Web Worker', detail: ready ? `ready in ${ms(ready.timings.gram + ready.timings.ease + ready.timings.graph)}` : 'starting', status: 'live', about: 'The engine runs off the main thread, so animations never wait for maths.', files: ['web/src/engine/worker.ts'] },
    { id: 'ease', lane: 2, col: 1, title: 'EASE^R', detail: ready ? `solve ${ms(ready.timings.ease)}` : '…', status: 'live', about: 'Closed-form item-item model: one Cholesky factorisation of G + λI on your device.', files: ['web/src/engine/ease.ts'] },
    { id: 'push', lane: 2, col: 2, title: 'graph + push', detail: ready ? `${int(ready.nodes)} nodes` : '…', status: 'live', about: 'Personalized PageRank from each of your games by forward push, over games, tags, developers and publishers.', files: ['web/src/engine/graph.ts', 'web/src/engine/ppr.ts'] },
    { id: 'blend', lane: 2, col: 3, title: 'blend + score', detail: timings ? ms(timings.score + timings.pi) : 'waiting for games', status: 'live', about: 'M = β·B/c_B + (1−β)·Π/c_Π; your score is a sum over your games, which is what makes every reason exact.', files: ['web/src/engine/blend.ts'] },
    { id: 'dpp', lane: 2, col: 4, title: 'DPP re-rank', detail: '100 → 10', status: 'live', about: 'Greedy MAP on a determinantal point process keeps the top 10 relevant and varied; picks it adds for variety are flagged.', files: ['web/src/engine/dpp.ts', 'web/src/engine/pipeline.ts'] },
    { id: 'explain', lane: 2, col: 5, title: 'explain', detail: timings ? `${app.result?.explanations.reduce((n, e) => n + e.counterfactual.runs, 0) ?? 0} re-runs` : '…', status: 'live', about: 'Exact attributions per pick, the smallest counterfactual found by re-running the whole pipeline, and "related by" paths through the graph.', files: ['web/src/engine/explain.ts'] },
    { id: 'ui', lane: 2, col: 6, title: 'Star Atlas UI', detail: 'Svelte · Pages', status: 'live', about: 'Svelte + TypeScript on GitHub Pages. The map is the stage; the reasons sit on solid panels. Both themes are tested with axe.', files: ['web/src/lib/components/Atlas.svelte'] },

    { id: 'ials', lane: 3, col: 1, title: 'iALS rival', detail: 'must be matched', status: 'planned', milestone: 'M1', about: 'A latent-factor model the glass-box blend has to match on NDCG@10, so explainability isn’t bought with accuracy.', files: ['docs/spec/04_ALGORITHMS.md'] },
    { id: 'rag', lane: 3, col: 3, title: 'grounded RAG', detail: 'BM25 + HNSW', status: 'planned', milestone: 'M3', about: 'Hybrid retrieval over reviews and a local LLM that may only voice the computed reasons; a deterministic claim checker rejects anything it can’t verify.', files: ['docs/spec/06_RAG.md'] },
    { id: 'api', lane: 3, col: 5, title: 'FastAPI', detail: '/recommend · /explain', status: 'planned', milestone: 'M4', about: 'The full 8,000-game model behind a small API with an OpenAPI contract, for queries beyond the demo slice.', files: ['docs/spec/12_API.md'] },
  ]);

  const LANES = ['Offline data · Python on GitHub Actions', 'Model build · Python core (source of truth)', 'Your browser · live engine', 'Planned'];
  const COLS = 7;
  const W = 1280;
  const LANE_H = 118;
  const NODE_W = 150;
  const NODE_H = 58;
  const pos = (n: Node) => ({ x: 24 + n.col * ((W - 48 - NODE_W) / (COLS - 1)), y: 44 + n.lane * LANE_H });

  const edges: [string, string][] = [
    ['ucsd', 'fetch'], ['fetch', 'parse'], ['parse', 'clean'], ['clean', 'kcore'], ['kcore', 'split'], ['split', 'slice'],
    ['slice', 'py'], ['py', 'goldens'], ['goldens', 'gate'],
    ['worker', 'ease'], ['ease', 'push'], ['push', 'blend'], ['blend', 'dpp'], ['dpp', 'explain'], ['explain', 'ui'],
    ['slice', 'worker'], ['goldens', 'dpp'],
  ];
  const byId = $derived(new Map(nodes.map((n) => [n.id, n])));

  let chosen = $state('worker');
  let active = $state<string | null>(null);
  let replaying = $state<string | null>(null);

  async function replay(kind: 'request' | 'build'): Promise<void> {
    if (kind === 'request' && !app.result && app.history.length === 0) {
      const g = app.slice?.games ?? [];
      app.history = ['Portal 2', 'Half-Life 2', 'Undertale'].map((t) => ({ index: g.findIndex((x) => x.title === t), hours: 20 })).filter((h) => h.index >= 0);
    }
    if (kind === 'request') await app.find();
    const path = kind === 'request' ? ['worker', 'ease', 'push', 'blend', 'dpp', 'explain', 'ui'] : ['ucsd', 'fetch', 'parse', 'clean', 'kcore', 'split', 'slice', 'py', 'goldens'];
    replaying = kind;
    for (const id of path) {
      active = id;
      chosen = id;
      await new Promise((r) => setTimeout(r, app.reducedMotion ? 350 : 520));
    }
    active = null;
    replaying = null;
  }

  $effect(() => {
    app.scene = { focus: [], history: app.history.map((h) => h.index), picks: [], selected: null, lines: [], glow: null, hubs: [], hubGlow: null, dim: 0.75, key: 'architecture' };
  });

  const detail = $derived(byId.get(chosen)!);
</script>

<div class="arch">
  <section class="panel hud diagram" aria-labelledby="arch-title">
    <div class="head">
      <div>
        <p class="micro">System architecture</p>
        <h2 id="arch-title">From 7.8 million reviews to a reason you can check</h2>
      </div>
      <div class="actions">
        <button class="btn primary" disabled={!!replaying || !app.ready} onclick={() => replay('request')}>Replay a request</button>
        <button class="btn" disabled={!!replaying} onclick={() => replay('build')}>Replay the build</button>
      </div>
    </div>
    <svg viewBox={`0 0 ${W} ${44 + LANES.length * LANE_H - 30}`} role="group" aria-label="System diagram: select a component for details">
      {#each LANES as lane, l (lane)}
        <text class="lane" x="24" y={30 + l * LANE_H}>{lane.toUpperCase()}</text>
        <line class="rule" x1="24" x2={W - 24} y1={36 + l * LANE_H} y2={36 + l * LANE_H} />
      {/each}
      {#each edges as [a, b] (`${a}-${b}`)}
        {@const p = pos(byId.get(a)!)}
        {@const q = pos(byId.get(b)!)}
        {@const same = byId.get(a)!.lane === byId.get(b)!.lane}
        <path
          class="edge"
          class:dashed={byId.get(b)!.status === 'planned' || !same}
          class:hot={active === b}
          d={same
            ? `M ${p.x + NODE_W} ${p.y + NODE_H / 2} L ${q.x} ${q.y + NODE_H / 2}`
            : `M ${p.x + NODE_W / 2} ${p.y + NODE_H} C ${p.x + NODE_W / 2} ${p.y + NODE_H + 40}, ${q.x + NODE_W / 2} ${q.y - 40}, ${q.x + NODE_W / 2} ${q.y}`}
        />
      {/each}
      {#each nodes as n (n.id)}
        {@const p = pos(n)}
        <g
          class="node {n.status}"
          class:chosen={chosen === n.id}
          class:active={active === n.id}
          transform={`translate(${p.x} ${p.y})`}
          role="button"
          tabindex="0"
          onclick={() => (chosen = n.id)}
          onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), (chosen = n.id))}
        >
          <rect width={NODE_W} height={NODE_H} rx="9" />
          <text class="t" x="12" y="24">{n.title}</text>
          <text class="d" x="12" y="43">{n.detail.length > 21 ? `${n.detail.slice(0, 20)}…` : n.detail}</text>
          {#if n.milestone}<text class="m" x={NODE_W - 10} y="18" text-anchor="end">{n.milestone}</text>{/if}
          {#if n.status === 'live'}<circle class="dot" cx={NODE_W - 12} cy="14" r="3" />{/if}
        </g>
      {/each}
    </svg>
    <p class="legend micro">
      <span class="sw live"></span> live in your browser <span class="sw built"></span> built and tested <span class="sw planned"></span> planned
    </p>
    <p class="ci">
      Every pull request runs ruff, mypy --strict, import-linter, pytest (coverage ≥ 85%), svelte-check, the Vitest goldens
      (the browser engine must equal the Python core) and Playwright + axe in both themes.
    </p>
  </section>

  <aside class="panel detail" aria-live="polite">
    {#key chosen}
      <div class="fade">
        <p class="micro">{detail.status === 'planned' ? `Planned · ${detail.milestone}` : detail.status === 'live' ? 'Live · running in this tab' : 'Built · tested in CI'}</p>
        <h3>{detail.title}</h3>
        <p class="numbers mono">{detail.detail}</p>
        <p>{detail.about}</p>
        <ul>
          {#each detail.files as f (f)}<li><a href={source(f)} target="_blank" rel="noreferrer" class="mono">{f}</a></li>{/each}
        </ul>
      </div>
    {/key}
  </aside>
</div>

<style>
  .arch {
    position: relative;
    z-index: 2;
    display: grid;
    grid-template-columns: minmax(0, 1fr) 320px;
    gap: var(--space-5);
    padding: 0 var(--space-5) var(--space-5);
    align-items: start;
  }
  .diagram,
  .detail {
    pointer-events: auto;
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: var(--space-4);
    flex-wrap: wrap;
    margin-bottom: var(--space-3);
  }
  .head h2 {
    font-size: var(--text-xl);
  }
  .actions {
    display: flex;
    gap: var(--space-2);
  }
  svg {
    width: 100%;
    height: auto;
    display: block;
  }
  .lane {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.08em;
    fill: var(--muted);
  }
  .rule {
    stroke: var(--line);
    stroke-width: 1;
  }
  .edge {
    fill: none;
    stroke: var(--line);
    stroke-width: 1.5;
    transition: stroke var(--dur-fast);
  }
  .edge.dashed {
    stroke-dasharray: 4 5;
  }
  .edge.hot {
    stroke: var(--pick);
    stroke-width: 2.5;
  }
  .node {
    cursor: pointer;
    outline: none;
  }
  .node rect {
    fill: var(--surface);
    stroke: var(--line);
    stroke-width: 1;
    transition:
      stroke var(--dur-fast),
      fill var(--dur-fast);
  }
  .node.live rect {
    stroke: color-mix(in srgb, var(--link) 70%, transparent);
  }
  .node.planned rect {
    stroke-dasharray: 4 4;
    fill: transparent;
  }
  .node:hover rect,
  .node.chosen rect {
    fill: var(--raised);
  }
  .node.chosen rect,
  .node:focus-visible rect {
    stroke: var(--pick);
    stroke-width: 2;
  }
  .node.active rect {
    stroke: var(--pick);
    stroke-width: 2.5;
    fill: color-mix(in srgb, var(--pick) 14%, var(--surface));
  }
  .t {
    font-family: var(--font-display);
    font-weight: 600;
    font-size: 15px;
    fill: var(--text);
  }
  .d {
    font-family: var(--font-mono);
    font-size: 10.5px;
    fill: var(--muted);
  }
  .m {
    font-family: var(--font-mono);
    font-size: 10px;
    fill: var(--muted);
  }
  .dot {
    fill: var(--link);
  }
  .legend {
    margin: var(--space-3) 0 0;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
    text-transform: none;
    letter-spacing: 0.02em;
  }
  .ci {
    margin: var(--space-2) 0 0;
    font-size: var(--text-sm);
    color: var(--muted);
  }
  .sw {
    display: inline-block;
    width: 14px;
    height: 9px;
    border-radius: 3px;
    border: 1px solid var(--line);
    margin-left: 6px;
  }
  .sw.live {
    border-color: var(--link);
    margin-left: 0;
  }
  .sw.planned {
    border-style: dashed;
  }
  .detail {
    position: sticky;
    top: var(--space-4);
  }
  .fade {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    animation: rise var(--dur-fast) var(--ease-out);
  }
  .fade p {
    margin: 0;
    font-size: var(--text-sm);
  }
  .fade p.micro {
    font-size: var(--text-xs);
  }
  h3 {
    font-size: var(--text-lg);
  }
  .numbers {
    color: var(--link);
  }
  ul {
    margin: 0;
    padding-left: 18px;
    font-size: var(--text-xs);
  }
  @media (max-width: 1100px) {
    .arch {
      grid-template-columns: minmax(0, 1fr);
    }
    svg {
      min-width: 760px;
    }
    .diagram {
      overflow-x: auto;
    }
  }
</style>
