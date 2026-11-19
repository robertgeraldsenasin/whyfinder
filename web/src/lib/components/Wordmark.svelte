<script lang="ts">
  /**
   * The wordmark (ADR-0018): WHY in crimson, FINDER in bone, Anton capitals slanted like a poster,
   * with two hard offset shadows (deep crimson, then violet), as if the print slipped. `ribbon` adds
   * the crimson ribbon beneath it on the title screen.
   */
  let { size = 26, ribbon = '' }: { size?: number | string; ribbon?: string } = $props();
</script>

<span class="mark" style:--size={typeof size === 'number' ? `${size}px` : size}>
  <span class="word" aria-hidden="true"><span class="why">Why</span>finder</span>
  <span class="sr-only">Whyfinder</span>
  {#if ribbon}
    <span class="ribbon">{ribbon}</span>
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
    display: inline-block;
    font-family: var(--font-poster);
    font-weight: 400;
    font-size: var(--size);
    line-height: 0.86;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    color: var(--bone);
    white-space: nowrap;
    transform: skewX(-8deg);
    --off: max(1px, calc(var(--size) * 0.045));
    text-shadow:
      var(--off) var(--off) 0 var(--crimson-deep),
      calc(var(--off) * 2) calc(var(--off) * 2) 0 rgb(123 77 255 / 0.4);
  }
  .why {
    color: var(--crimson-hot);
    text-shadow:
      var(--off) var(--off) 0 #3d0412,
      calc(var(--off) * 2) calc(var(--off) * 2) 0 rgb(123 77 255 / 0.4);
  }
  .ribbon {
    margin-top: calc(var(--size) * 0.2);
    padding: 9px 46px 7px;
    background: var(--crimson);
    color: var(--bone);
    font-family: var(--font-poster);
    font-size: clamp(14px, calc(var(--size) * 0.15), 19px);
    letter-spacing: 0.16em;
    text-transform: uppercase;
    white-space: nowrap;
    clip-path: polygon(0 0, 100% 0, calc(100% - 16px) 50%, 100% 100%, 0 100%, 16px 50%);
  }
  @media (max-width: 520px) {
    .ribbon {
      padding: 8px 30px 6px;
      letter-spacing: 0.1em;
    }
  }
</style>
