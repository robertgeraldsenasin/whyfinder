<script lang="ts">
  /**
   * The wordmark: WHYFINDER in Prata capitals with gold double hairlines cut through the Y and the
   * D, like a star's trail crossing the name. `line` adds the spaced line beneath, game-title style.
   */
  let { size = 26, line = '' }: { size?: number | string; line?: string } = $props();
  const letters = 'WHYFINDER'.split('');
  const cut = new Set([2, 6]);
</script>

<span class="mark" style:--size={typeof size === 'number' ? `${size}px` : size}>
  <span class="word" aria-hidden="true">
    {#each letters as ch, k (k)}<span class:cut={cut.has(k)}>{ch}</span>{/each}
  </span>
  <span class="sr-only">Whyfinder</span>
  {#if line}
    <span class="line" aria-hidden="true">{line}</span>
  {/if}
</span>

<style>
  .mark {
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    line-height: 1;
  }
  .word {
    font-family: var(--font-display);
    font-size: var(--size);
    letter-spacing: 0.09em;
    margin-right: -0.09em;
    color: var(--starlight);
    white-space: nowrap;
  }
  .cut {
    position: relative;
    display: inline-block;
  }
  .cut::after {
    content: '';
    position: absolute;
    left: 34%;
    top: 46%;
    width: 0.11em;
    height: 0.6em;
    border-left: max(1px, 0.02em) solid var(--gold);
    border-right: max(1px, 0.02em) solid var(--gold);
    transform: skewX(-38deg);
    transform-origin: bottom;
  }
  .line {
    margin-top: 0.55em;
    font-family: var(--font-display);
    font-size: calc(var(--size) * 0.26);
    letter-spacing: 0.62em;
    margin-right: -0.62em;
    color: var(--gold);
    white-space: nowrap;
  }
</style>
