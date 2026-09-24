import { Color } from 'three';
import { CAMERA_MODE_DEFAULTS, CAMERA_MODE_LABELS } from '../camera/CameraFactory';
import { SeededRandom } from '../core/SeededRandom';
import { PALETTE_LABELS } from '../marbles/MarbleColorPalette';
import {
  BUILT_IN_PATH_PRESETS,
  PATH_PRESET_LABELS,
  createPresetPoints,
  randomizePath,
} from '../path/PathFactory';
import { computeBounds } from '../path/PathValidator';
import { LIGHTING_PRESET_LABELS, createLightingPreset } from './DefaultPresets';
import type {
  CameraMode,
  LightingPresetId,
  PaletteId,
  PathPresetId,
  ScenePreset,
  Vec3Like,
} from './PresetSchema';

export type VariationCategory =
  'path' | 'marbles' | 'palette' | 'camera' | 'lighting' | 'material' | 'speed' | 'background';

export const ALL_VARIATION_CATEGORIES: readonly VariationCategory[] = [
  'path',
  'marbles',
  'palette',
  'camera',
  'lighting',
  'material',
  'speed',
  'background',
];

export const APPEARANCE_CATEGORIES: readonly VariationCategory[] = [
  'palette',
  'material',
  'lighting',
  'background',
];

/** Inclinação sugerida por preset de trajeto (curvas verticais planas). */
export const PATH_PRESET_BANK: Partial<Record<PathPresetId, number>> = { circle: -90 };

export interface VariationOptions {
  /** Categorias fixas. Sem valor: sorteia de 3 a 5 categorias. */
  categories?: readonly VariationCategory[];
  /** Força trajeto aleatório (Randomizar trajeto). */
  forceRandomPath?: boolean;
  /** Modos de câmera permitidos no sorteio (padrão: todos). */
  cameraModes?: readonly CameraMode[];
}

export const ALL_CAMERA_MODES: readonly CameraMode[] = [
  'fixed',
  'orbit',
  'follow',
  'rail',
  'topView',
];

/** Enquadramentos que mostram a cena inteira (usados no modo simples). */
export const OVERVIEW_CAMERA_MODES: readonly CameraMode[] = ['fixed', 'orbit', 'topView'];

export interface VariationResult {
  project: ScenePreset;
  categories: VariationCategory[];
  changes: string[];
}

const hex = (value: number): string => `#${value.toString(16).padStart(6, '0')}`;

function pickDifferent<T>(rng: SeededRandom, options: readonly T[], current: T): T {
  const candidates = options.filter((o) => o !== current);
  return rng.pick(candidates.length > 0 ? candidates : options);
}

function randomColor(
  rng: SeededRandom,
  saturation: [number, number],
  lightness: [number, number],
): number {
  return new Color()
    .setHSL(rng.next(), rng.nextFloat(...saturation), rng.nextFloat(...lightness))
    .getHex();
}

type Mutator = (
  project: ScenePreset,
  rng: SeededRandom,
  seed: number,
  options: VariationOptions,
) => string;

const CAMERA_DISTANCE = 14;

/**
 * Elevação (graus) que mostra bem o trajeto: trajetos achatados pedem câmera mais alta,
 * trajetos verticais pedem câmera mais baixa.
 */
export function suggestCameraElevation(points: readonly Vec3Like[]): number {
  const { min, max } = computeBounds(points);
  const horizontal = Math.max(max.x - min.x, max.z - min.z, 1e-6);
  const ratio = (max.y - min.y) / horizontal;
  if (ratio < 0.5) return 42;
  if (ratio > 1.2) return 14;
  return 28;
}

/** Posiciona câmeras fixa/órbita no azimute dado com elevação adequada ao trajeto. */
function placeCamera(project: ScenePreset, azimuth: number, jitterDeg = 0): void {
  const elevation = ((suggestCameraElevation(project.path.points) + jitterDeg) * Math.PI) / 180;
  const round = (v: number): number => Number(v.toFixed(2));
  const horizontal = CAMERA_DISTANCE * Math.cos(elevation);
  const height = CAMERA_DISTANCE * Math.sin(elevation);
  project.camera.position = {
    x: round(horizontal * Math.sin(azimuth)),
    y: round(height),
    z: round(horizontal * Math.cos(azimuth)),
  };
  project.camera.height = round(Math.min(10, height));
}

const MUTATORS: Record<VariationCategory, Mutator> = {
  path(project, rng, seed, options) {
    const before = project.path.preset;
    const choices: PathPresetId[] = [...BUILT_IN_PATH_PRESETS, 'custom'];
    const next = options.forceRandomPath ? 'custom' : pickDifferent(rng, choices, before);
    project.path.points = next === 'custom' ? randomizePath(seed).points : createPresetPoints(next);
    project.path.preset = next;
    project.path.closed = true;
    project.track.bankAngle = PATH_PRESET_BANK[next] ?? 0;
    // Mantém o azimute atual e ajusta a elevação ao formato do novo trajeto.
    const { position } = project.camera;
    placeCamera(project, Math.atan2(position.x, position.z));
    return `Trajeto: ${PATH_PRESET_LABELS[before]} → ${PATH_PRESET_LABELS[next]}${
      next === 'custom' ? ` (seed ${seed})` : ''
    }`;
  },
  marbles(project, rng) {
    const before = project.marbles.count;
    const next = pickDifferent(rng, [12, 18, 24, 30, 36, 48, 60, 72], before);
    project.marbles.count = next;
    project.marbles.spacing = 0;
    project.marbles.radius = Number(rng.nextFloat(0.12, 0.26).toFixed(2));
    project.camera.followMarbleIndex = 0;
    return `Bolinhas: ${before} → ${next} (raio ${project.marbles.radius})`;
  },
  palette(project, rng) {
    const before = project.marbles.palette;
    const options: PaletteId[] = ['rainbow', 'metal', 'pastels', 'neon', 'custom'];
    const next = pickDifferent(rng, options, before);
    project.marbles.palette = next;
    if (next === 'custom') {
      const count = rng.nextInt(2, 5);
      project.marbles.customColors = Array.from({ length: count }, () =>
        randomColor(rng, [0.6, 0.95], [0.45, 0.65]),
      );
    }
    return `Paleta: ${PALETTE_LABELS[before]} → ${PALETTE_LABELS[next]}`;
  },
  camera(project, rng, _seed, options) {
    const before = project.camera.mode;
    const allowed = options.cameraModes?.length ? options.cameraModes : ALL_CAMERA_MODES;
    const next = pickDifferent(rng, allowed, before);
    Object.assign(project.camera, CAMERA_MODE_DEFAULTS[next]);
    project.camera.mode = next;
    project.camera.cycleCount = 1;
    project.camera.autoFrame = true;
    placeCamera(project, rng.nextFloat(-0.6, 0.6), rng.nextFloat(-5, 5));
    const cycles =
      next === 'orbit' || next === 'rail' ? ` (${project.camera.cycleCount} ciclo)` : '';
    return `Câmera: ${CAMERA_MODE_LABELS[before]} → ${CAMERA_MODE_LABELS[next]}${cycles}`;
  },
  lighting(project, rng) {
    const before = project.lighting.preset;
    const options: Exclude<LightingPresetId, 'custom'>[] = [
      'darkNeon',
      'cleanStudio',
      'pastel',
      'metallicGold',
      'woodenWarm',
    ];
    const next = pickDifferent(rng, options, before as Exclude<LightingPresetId, 'custom'>);
    project.lighting = createLightingPreset(next);
    return `Iluminação: ${LIGHTING_PRESET_LABELS[before]} → ${LIGHTING_PRESET_LABELS[next]}`;
  },
  material(project, rng) {
    const m = project.marbles;
    const beforeMetal = m.metalness;
    const beforeRough = m.roughness;
    m.metalness = Number(rng.nextFloat(0, 1).toFixed(2));
    m.roughness = Number(rng.nextFloat(0.05, 0.6).toFixed(2));
    project.track.color = randomColor(rng, [0.1, 0.5], [0.12, 0.6]);
    project.track.metalness = Number(rng.nextFloat(0, 1).toFixed(2));
    project.track.roughness = Number(rng.nextFloat(0.15, 0.7).toFixed(2));
    return `Material: metalness ${beforeMetal} → ${m.metalness}, roughness ${beforeRough} → ${m.roughness}, trilho ${hex(project.track.color)}`;
  },
  speed(project, rng) {
    const before = project.marbles.cycleCount;
    const next = pickDifferent(rng, [1, 2, 3], before);
    project.marbles.cycleCount = next;
    return `Velocidade: ${before} → ${next} volta(s) por ciclo`;
  },
  background(project, rng) {
    const b = project.background;
    const before = `${b.type} ${hex(b.colorMain)}`;
    const dark = rng.nextBool(0.65);
    b.type = rng.nextBool(0.7) ? 'gradient' : 'solid';
    b.gradientMode = rng.nextBool(0.5) ? 'vertical' : 'radial';
    b.colorMain = randomColor(rng, [0.3, 0.8], dark ? [0.08, 0.22] : [0.75, 0.92]);
    b.colorSecondary = randomColor(rng, [0.2, 0.7], dark ? [0.01, 0.06] : [0.85, 0.97]);
    b.fogColor = b.colorSecondary;
    return `Fundo: ${before} → ${b.type} ${hex(b.colorMain)}`;
  },
};

/**
 * Gera uma variação determinística do projeto: mesma seed + mesmo projeto = mesmo resultado.
 * Sem categorias explícitas, altera de 3 a 5 categorias sorteadas.
 */
export function createVariation(
  base: ScenePreset,
  seed: number,
  options: VariationOptions = {},
): VariationResult {
  const rng = SeededRandom.derived(seed, 'variation');
  const project = structuredClone(base);
  project.seed = seed;
  const picked = options.categories
    ? [...options.categories]
    : rng.shuffle([...ALL_VARIATION_CATEGORIES]).slice(0, rng.nextInt(3, 6));
  // Ordem canônica: o trajeto é definido antes da câmera, que depende do formato dele.
  const categories = ALL_VARIATION_CATEGORIES.filter((c) => picked.includes(c));
  const changes = categories.map((category) =>
    MUTATORS[category](project, SeededRandom.derived(seed, `variation:${category}`), seed, options),
  );
  return { project, categories, changes };
}

export function formatVariationReport(changes: readonly string[]): string {
  return ['Mudanças realizadas:', ...changes.map((c) => `- ${c}`)].join('\n');
}
