import { roundTo } from '../../core/MathUtils';
import { SeededRandom, normalizeSeed } from '../../core/SeededRandom';
import {
  SATISFYING_LIGHTING_PRESETS,
  createSatisfyingLighting,
} from '../lighting/SatisfyingLighting';
import { withMaterialPreset } from '../materials/SatisfyingMaterials';
import { MATERIAL_TYPES } from '../SatisfyingSchema';
import type {
  SatisfyingLightingId,
  SatisfyingMaterialId,
  SatisfyingSettings,
  ToolFinishId,
} from '../SatisfyingSettings';

/** Categorias que uma variação pode alterar. */
export type SqueezeVariationCategory =
  | 'shape'
  | 'material'
  | 'color'
  | 'pressure'
  | 'deformation'
  | 'camera'
  | 'lighting'
  | 'background';

export const SQUEEZE_VARIATION_CATEGORIES: readonly SqueezeVariationCategory[] = [
  'shape',
  'material',
  'color',
  'pressure',
  'deformation',
  'camera',
  'lighting',
  'background',
];

export const MIN_VARIATION_CATEGORIES = 3;

export const MATERIAL_LABELS: Record<SatisfyingMaterialId, string> = {
  softRubber: 'Soft Rubber',
  glossyGel: 'Glossy Gel',
  slime: 'Slime',
  foam: 'Foam',
  silicone: 'Silicone',
  wax: 'Wax',
  softPlastic: 'Soft Plastic',
  butter: 'Butter-like',
  candy: 'Candy',
};

export const LIGHTING_LABELS: Record<SatisfyingLightingId, string> = {
  cleanStudio: 'Clean Studio',
  softWhite: 'Soft White',
  pastel: 'Pastel',
  candy: 'Candy',
  darkPremium: 'Dark Premium',
  neon: 'Neon',
  warmProduct: 'Warm Product',
  monochrome: 'Monochrome',
};

/** Paleta curada de cores de objeto (saturadas, agradáveis em vídeo). */
export const OBJECT_COLORS: readonly { name: string; color: number }[] = [
  { name: 'Rosa chiclete', color: 0xff5c9a },
  { name: 'Coral', color: 0xff6f59 },
  { name: 'Amarelo manteiga', color: 0xffc53d },
  { name: 'Laranja pêssego', color: 0xff9a4d },
  { name: 'Azul céu', color: 0x3d86ff },
  { name: 'Azul-petróleo', color: 0x18a7b5 },
  { name: 'Menta', color: 0x6fd9bd },
  { name: 'Verde limão', color: 0x9bd94a },
  { name: 'Lavanda', color: 0xa98bff },
  { name: 'Uva', color: 0x7a3cff },
  { name: 'Vermelho bala', color: 0xf0245e },
  { name: 'Grafite', color: 0x2b2b33 },
];

/** Fundos de estúdio (parede + piso). */
export const BACKGROUNDS: readonly { name: string; wall: number; floor: number; dark: boolean }[] =
  [
    { name: 'Rosa claro', wall: 0xefc3d5, floor: 0xf9e3ec, dark: false },
    { name: 'Creme', wall: 0xf4e2b8, floor: 0xfbf1da, dark: false },
    { name: 'Azul névoa', wall: 0xcfe0f7, floor: 0xe9f1fc, dark: false },
    { name: 'Menta suave', wall: 0xc9efe3, floor: 0xe6f8f1, dark: false },
    { name: 'Lilás', wall: 0xdcd3f2, floor: 0xf0ebfb, dark: false },
    { name: 'Pêssego', wall: 0xf8d2c0, floor: 0xfde9df, dark: false },
    { name: 'Branco estúdio', wall: 0xe6e6ea, floor: 0xf5f5f7, dark: false },
    { name: 'Grafite', wall: 0x141418, floor: 0x1d1d23, dark: true },
    { name: 'Azul-noite', wall: 0x0f1424, floor: 0x161c30, dark: true },
  ];

const DARK_LIGHTING: readonly SatisfyingLightingId[] = ['darkPremium', 'neon', 'monochrome'];
const LIGHT_LIGHTING: readonly SatisfyingLightingId[] = [
  'cleanStudio',
  'softWhite',
  'pastel',
  'candy',
  'warmProduct',
];
const TOOL_FINISHES: readonly ToolFinishId[] = ['ceramic', 'ceramic', 'satinMetal', 'glass'];
const TOOL_COLORS: readonly number[] = [0xffffff, 0xf7f5f2, 0xe8e2f5, 0xd9dde4];

export interface SqueezeVariationOptions {
  /** Categorias fixas; se ausente, sorteia de 3 a 5 categorias. */
  categories?: readonly SqueezeVariationCategory[];
}

export interface SqueezeVariationResult {
  settings: SatisfyingSettings;
  seed: number;
  categories: SqueezeVariationCategory[];
  changes: string[];
}

const fmt = (value: number, decimals = 2): string => roundTo(value, decimals).toFixed(decimals);

function isDarkBackground(settings: SatisfyingSettings): boolean {
  const c = settings.background.color;
  const luminance = 0.2126 * ((c >> 16) & 255) + 0.7152 * ((c >> 8) & 255) + 0.0722 * (c & 255);
  return luminance < 90;
}

/**
 * Nova variação determinística do squeeze (mesma seed + mesma base = mesmo resultado).
 * Altera pelo menos três categorias e devolve um relatório legível.
 */
export function createSqueezeVariation(
  base: SatisfyingSettings,
  seed: number,
  options: SqueezeVariationOptions = {},
): SqueezeVariationResult {
  const s = normalizeSeed(seed);
  const rng = SeededRandom.derived(s, 'squeezeVariation');
  let categories: SqueezeVariationCategory[];
  if (options.categories && options.categories.length > 0) {
    categories = SQUEEZE_VARIATION_CATEGORIES.filter((c) => options.categories?.includes(c));
  } else {
    const count = rng.nextInt(MIN_VARIATION_CATEGORIES, 6);
    const picked = rng.shuffle([...SQUEEZE_VARIATION_CATEGORIES]).slice(0, count);
    categories = SQUEEZE_VARIATION_CATEGORIES.filter((c) => picked.includes(c));
  }
  const settings = structuredClone(base);
  const changes: string[] = [];
  // Um gerador por categoria: mudar uma não altera o sorteio das outras.
  const r = (category: string): SeededRandom => SeededRandom.derived(s, `squeeze:${category}`);

  for (const category of categories) {
    const g = r(category);
    switch (category) {
      case 'shape': {
        const width = roundTo(g.nextFloat(1.8, 2.6), 2);
        const depth = roundTo(width * g.nextFloat(0.85, 1.15), 2);
        const height = roundTo(g.nextFloat(1.15, 2), 2);
        const roundness = roundTo(g.nextFloat(0.25, 0.62), 2);
        settings.object = { ...settings.object, width, height, depth, roundness };
        changes.push(
          `Proporções do bloco: ${fmt(width)} × ${fmt(height)} × ${fmt(depth)} (arredondamento ${fmt(roundness)})`,
        );
        break;
      }
      case 'material': {
        const type = g.pick(MATERIAL_TYPES);
        settings.material = withMaterialPreset(settings.material, type);
        changes.push(`Material ${MATERIAL_LABELS[type]}`);
        break;
      }
      case 'color': {
        const choice = g.pick(OBJECT_COLORS.filter((c) => c.color !== settings.material.color));
        settings.material.color = choice.color;
        settings.material.attenuationColor = choice.color;
        changes.push(`Cor do objeto: ${choice.name}`);
        break;
      }
      case 'pressure': {
        const strength = roundTo(g.nextFloat(0.3, 0.5), 2);
        const toolRadius = roundTo(g.nextFloat(0.5, 0.85), 2);
        const finish = g.pick(TOOL_FINISHES);
        settings.pressure = {
          ...settings.pressure,
          strength,
          toolRadius,
          toolFinish: finish,
          toolColor: g.pick(TOOL_COLORS),
          offsetX: roundTo(g.nextBool(0.35) ? g.nextFloat(-0.18, 0.18) : 0, 2),
          offsetZ: roundTo(g.nextBool(0.35) ? g.nextFloat(-0.18, 0.18) : 0, 2),
          creep: roundTo(g.nextFloat(0, 0.12), 2),
        };
        changes.push(`Pressão: força ${fmt(strength)}, esfera r=${fmt(toolRadius)} (${finish})`);
        break;
      }
      case 'deformation': {
        const d = {
          ...settings.deformation,
          softness: roundTo(g.nextFloat(0.25, 0.55), 2),
          viscosity: roundTo(g.nextFloat(0, 0.9), 2),
          elasticity: roundTo(g.nextFloat(0.1, 0.95), 2),
          locality: roundTo(g.nextFloat(0.4, 0.75), 2),
          falloff: roundTo(g.nextFloat(0.4, 0.8), 2),
          bulgeHeight: roundTo(g.nextFloat(0.5, 0.7), 2),
        };
        settings.deformation = d;
        changes.push(
          `Deformação: maciez ${fmt(d.softness)}, viscosidade ${fmt(d.viscosity)}, rebote ${fmt(d.elasticity)}`,
        );
        break;
      }
      case 'camera': {
        const side = g.nextBool() ? 1 : -1;
        const c = {
          ...settings.camera,
          fov: Math.round(g.nextFloat(24, 36)),
          elevation: roundTo(g.nextFloat(12, 32), 1),
          azimuth: Math.round(side * g.nextFloat(15, 40)),
          orbitAmplitude: roundTo(g.nextFloat(0, 5), 1),
          targetHeight: roundTo(g.nextFloat(0.75, 1), 2),
        };
        settings.camera = c;
        changes.push(
          `Câmera: FOV ${c.fov}°, elevação ${fmt(c.elevation, 1)}°, ângulo ${c.azimuth}°`,
        );
        break;
      }
      case 'background': {
        // A iluminação (processada antes, ordem canônica) decide claro × escuro.
        const wantDark = DARK_LIGHTING.includes(settings.lighting.preset);
        const choice = g.pick(
          BACKGROUNDS.filter((b) => b.dark === wantDark && b.wall !== settings.background.color),
        );
        settings.background = {
          ...settings.background,
          color: choice.wall,
          floorColor: choice.floor,
          contactShadow: choice.dark ? 0.7 : 0.55,
        };
        changes.push(`Fundo: ${choice.name}`);
        break;
      }
      case 'lighting': {
        const dark = categories.includes('background')
          ? g.nextBool(0.2)
          : isDarkBackground(settings);
        const pool = (dark ? DARK_LIGHTING : LIGHT_LIGHTING).filter(
          (id) => id !== settings.lighting.preset,
        );
        const id = g.pick(pool.length > 0 ? pool : dark ? DARK_LIGHTING : LIGHT_LIGHTING);
        settings.lighting = createSatisfyingLighting(id);
        changes.push(`Iluminação ${LIGHTING_LABELS[id]}`);
        break;
      }
    }
  }
  return { settings, seed: s, categories, changes };
}

/** Relatório no formato pedido: "VARIATION #seed / Changed: …". */
export function formatSqueezeVariationReport(result: SqueezeVariationResult): string {
  return [`VARIATION #${result.seed}`, '', 'Changed:', ...result.changes.map((c) => `- ${c}`)].join(
    '\n',
  );
}

/** Garante que os presets de luz citados existem (usado em testes). */
export const KNOWN_LIGHTING_IDS = Object.keys(
  SATISFYING_LIGHTING_PRESETS,
) as SatisfyingLightingId[];
