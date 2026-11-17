/** Viewer settings, kept in this browser only. */
import type { Palette } from './sky';

export type Flashes = 'full' | 'reduced' | 'off';

const KEY = 'whyfinder.settings.v1';

interface Saved {
  palette: Palette;
  sound: boolean;
  volume: number;
  flashes: Flashes;
}

const DEFAULTS: Saved = { palette: 'gold-violet', sound: true, volume: 0.6, flashes: 'full' };

function read(): Saved {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? 'null') as Partial<Saved> | null;
    if (!raw) return { ...DEFAULTS };
    return {
      palette: (['gold-violet', 'gold', 'spectrum'] as const).includes(raw.palette as Palette)
        ? (raw.palette as Palette)
        : DEFAULTS.palette,
      sound: typeof raw.sound === 'boolean' ? raw.sound : DEFAULTS.sound,
      volume: typeof raw.volume === 'number' && raw.volume >= 0 && raw.volume <= 1 ? raw.volume : DEFAULTS.volume,
      flashes: (['full', 'reduced', 'off'] as const).includes(raw.flashes as Flashes) ? (raw.flashes as Flashes) : DEFAULTS.flashes,
    };
  } catch {
    return { ...DEFAULTS };
  }
}

class Settings {
  palette = $state<Palette>(DEFAULTS.palette);
  sound = $state(DEFAULTS.sound);
  volume = $state(DEFAULTS.volume);
  flashes = $state<Flashes>(DEFAULTS.flashes);

  load(): void {
    Object.assign(this, read());
  }

  save(): void {
    try {
      const saved: Saved = { palette: this.palette, sound: this.sound, volume: this.volume, flashes: this.flashes };
      localStorage.setItem(KEY, JSON.stringify(saved));
    } catch {
      /* storage can be unavailable */
    }
  }
}

export const settings = new Settings();
