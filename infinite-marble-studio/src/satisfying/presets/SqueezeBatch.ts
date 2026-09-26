import { MAX_SEED, normalizeSeed } from '../../core/SeededRandom';
import type { ScenePreset } from '../../presets/PresetSchema';
import { createDefaultSatisfyingSettings } from '../SatisfyingSettings';
import {
  SQUEEZE_VARIATION_CATEGORIES,
  createSqueezeVariation,
  formatSqueezeVariationReport,
} from './SqueezeVariation';

export const MAX_BATCH_AMOUNT = 200;

export interface SqueezeBatchItem {
  name: string;
  project: ScenePreset;
  report: string;
}

/** Nome reproduzível de um item do lote. */
export function batchItemName(seed: number): string {
  return `squeeze-${normalizeSeed(seed)}`;
}

/**
 * Lote reproduzível: seeds consecutivas a partir de `seedStart`, cada uma gerando uma
 * variação completa (todas as categorias) a partir da base. Mesma entrada = mesmo lote.
 */
export function createSqueezeBatch(
  base: ScenePreset,
  seedStart: number,
  amount: number,
): SqueezeBatchItem[] {
  const count = Math.max(1, Math.min(MAX_BATCH_AMOUNT, Math.floor(amount)));
  const start = normalizeSeed(seedStart);
  const items: SqueezeBatchItem[] = [];
  for (let i = 0; i < count; i++) {
    const seed = (start + i) % (MAX_SEED + 1);
    const variation = createSqueezeVariation(
      base.satisfying ?? createDefaultSatisfyingSettings(),
      seed,
      { categories: SQUEEZE_VARIATION_CATEGORIES },
    );
    const project = structuredClone(base);
    project.name = batchItemName(seed);
    project.seed = seed;
    project.generator = 'satisfying';
    project.satisfying = variation.settings;
    project.description = formatSqueezeVariationReport(variation);
    items.push({ name: project.name, project, report: project.description });
  }
  return items;
}
