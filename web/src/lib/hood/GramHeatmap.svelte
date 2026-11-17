<script lang="ts">
  /** G = XᵀX as an image (games in Hilbert order of their map position), with a replay of the
   *  Cholesky sweep and your games' rows marked. */
  import { app } from '../state.svelte';

  let { sweep = 1, rows = [] as number[] }: { sweep?: number; rows?: number[] } = $props();
  let canvas: HTMLCanvasElement;
  let image: ImageData | null = null;

  $effect(() => {
    const ready = app.ready;
    if (!ready || !canvas) return;
    const n = Math.round(Math.sqrt(ready.gramImage.length));
    const css = getComputedStyle(document.documentElement);
    const hex = css.getPropertyValue('--link').trim();
    const bg = css.getPropertyValue('--bg').trim();
    const rgb = (h: string) => [1, 3, 5].map((k) => parseInt(h.slice(k, k + 2), 16));
    const [r, g, b] = rgb(hex.length === 7 ? hex : '#7dd3e3');
    const [r0, g0, b0] = rgb(bg.length === 7 ? bg : '#0a0f1f');
    image = new ImageData(n, n);
    for (let k = 0; k < n * n; k++) {
      const t = ready.gramImage[k] / 255;
      image.data[4 * k] = r0 + (r - r0) * t;
      image.data[4 * k + 1] = g0 + (g - g0) * t;
      image.data[4 * k + 2] = b0 + (b - b0) * t;
      image.data[4 * k + 3] = 255;
    }
    canvas.width = n;
    canvas.height = n;
  });

  $effect(() => {
    void sweep;
    void rows;
    const ready = app.ready;
    const ctx = canvas?.getContext('2d');
    if (!ctx || !image || !ready) return;
    const n = image.width;
    ctx.putImageData(image, 0, 0);
    const css = getComputedStyle(document.documentElement);
    if (sweep < 1) {
      const x = Math.round(sweep * n);
      ctx.fillStyle = css.getPropertyValue('--bg').trim();
      ctx.globalAlpha = 0.72;
      ctx.fillRect(x, x, n - x, n - x);
      ctx.globalAlpha = 1;
      ctx.fillStyle = css.getPropertyValue('--pick').trim();
      ctx.fillRect(x, x, 2, n - x);
    }
    ctx.fillStyle = css.getPropertyValue('--pick').trim();
    for (const game of rows) {
      const y = ready.gramOrder.indexOf(game);
      ctx.globalAlpha = 0.85;
      ctx.fillRect(0, y - 1, n, 2);
    }
    ctx.globalAlpha = 1;
  });
</script>

<figure>
  <canvas bind:this={canvas} aria-hidden="true"></canvas>
  <span class="sr-only">Heat map of the co-play matrix G for 500 games; your games' rows are marked in amber.</span>
  <figcaption class="micro">G = XᵀX. Brighter means more shared players; gold marks your games.</figcaption>
</figure>

<style>
  figure {
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  canvas {
    width: 100%;
    aspect-ratio: 1;
    image-rendering: pixelated;
    border-radius: 6px;
    border: var(--border);
  }
</style>
