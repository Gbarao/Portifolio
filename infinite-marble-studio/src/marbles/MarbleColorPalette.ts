import { Color } from 'three';
import { SeededRandom } from '../core/SeededRandom';
import type { MarbleSettings, PaletteId } from '../presets/PresetSchema';

export const PALETTE_LABELS: Record<PaletteId, string> = {
  rainbow: 'Rainbow',
  metal: 'Metal',
  pastels: 'Pastéis',
  neon: 'Neon',
  custom: 'Custom',
};

/** Cores sRGB (hex) das paletas fixas. */
export const PALETTE_SWATCHES: Record<
  Exclude<PaletteId, 'rainbow' | 'custom'>,
  readonly number[]
> = {
  metal: [0xd9d9de, 0xd4af37, 0xb87333, 0xcd7f32, 0x6b6f75, 0xf2f2f5],
  pastels: [0xffb3ba, 0xffdfba, 0xffffba, 0xbaffc9, 0xbae1ff, 0xd7baff],
  neon: [0xff1fe6, 0x00f0ff, 0x39ff14, 0xfff01f, 0xff3131, 0x7b2fff],
};

export const DEFAULT_CUSTOM_COLORS: readonly number[] = [0xff6b6b, 0xffd93d, 0x6bcb77, 0x4d96ff];

/**
 * Gera as cores base (hex sRGB) de cada bolinha. Determinístico: depende apenas da paleta,
 * da quantidade, das cores custom e da seed.
 */
export function generateMarbleColors(
  settings: Pick<MarbleSettings, 'palette' | 'count' | 'customColors'>,
  seed: number,
): number[] {
  const rng = SeededRandom.derived(seed, 'marbleColors');
  const count = Math.max(0, Math.floor(settings.count));
  const colors: number[] = [];

  if (settings.palette === 'rainbow') {
    const hueOffset = rng.next();
    const color = new Color();
    for (let i = 0; i < count; i++) {
      color.setHSL((hueOffset + i / Math.max(1, count)) % 1, 0.85, 0.55);
      colors.push(color.getHex());
    }
    return colors;
  }

  if (settings.palette === 'custom') {
    const list = settings.customColors.length > 0 ? settings.customColors : DEFAULT_CUSTOM_COLORS;
    for (let i = 0; i < count; i++) colors.push(list[i % list.length] as number);
    return colors;
  }

  // Paletas fixas: ordem embaralhada pela seed e distribuição cíclica (ritmo regular).
  const order = rng.shuffle([...PALETTE_SWATCHES[settings.palette]]);
  for (let i = 0; i < count; i++) colors.push(order[i % order.length] as number);
  return colors;
}

/** Escala base por instância: 1 ± variation (máx. ±10%), derivada da seed. */
export function generateMarbleScales(count: number, variation: number, seed: number): Float32Array {
  const rng = SeededRandom.derived(seed, 'marbleScales');
  const v = Math.min(0.1, Math.max(0, variation));
  const scales = new Float32Array(Math.max(0, count));
  for (let i = 0; i < scales.length; i++) scales[i] = 1 + rng.nextFloat(-v, v);
  return scales;
}
