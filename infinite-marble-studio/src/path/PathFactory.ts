import { CatmullRomCurve3, Vector3 } from 'three';
import { TAU, roundTo } from '../core/MathUtils';
import { SeededRandom } from '../core/SeededRandom';
import type { CurveType, PathPresetId, PathSettings, Vec3Like } from '../presets/PresetSchema';
import { validatePathPoints } from './PathValidator';

export const FIT_RADIUS = 5;

export const PATH_PRESET_LABELS: Record<PathPresetId, string> = {
  circle: 'Círculo',
  figureEight: 'Figura de oito',
  wave3d: 'Onda 3D',
  toroidalSpiral: 'Espiral toroidal',
  torusKnot: 'Torus knot (3,2)',
  sTrack: 'Pista em S',
  stackedCircuit: 'Circuito empilhado',
  custom: 'Percurso personalizado',
};

export type BuiltInPathPresetId = Exclude<PathPresetId, 'custom'>;

export const BUILT_IN_PATH_PRESETS: readonly BuiltInPathPresetId[] = [
  'circle',
  'figureEight',
  'wave3d',
  'toroidalSpiral',
  'torusKnot',
  'sTrack',
  'stackedCircuit',
];

function sample(count: number, fn: (theta: number) => Vec3Like): Vec3Like[] {
  const points: Vec3Like[] = [];
  for (let i = 0; i < count; i++) points.push(fn((TAU * i) / count));
  return points;
}

const RAW_PRESETS: Record<BuiltInPathPresetId, () => Vec3Like[]> = {
  // Círculo perfeito no plano XY.
  circle: () => sample(24, (t) => ({ x: 5 * Math.cos(t), y: 5 * Math.sin(t), z: 0 })),

  // Lemniscata de Bernoulli no plano XZ; a elevação em Y cria um viaduto no cruzamento.
  figureEight: () =>
    sample(40, (t) => {
      const s = Math.sin(t);
      const c = Math.cos(t);
      const d = 1 + s * s;
      return { x: (6 * c) / d, y: 1.3 * s, z: (6 * s * c) / d };
    }),

  // Onda senoidal com número inteiro de cristas ao redor de um anel.
  wave3d: () =>
    sample(48, (t) => {
      const r = 5 + 0.5 * Math.cos(2 * t);
      return { x: r * Math.cos(t), y: 1.4 * Math.sin(3 * t), z: r * Math.sin(t) };
    }),

  // Hélice enrolada sobre um toro (8 voltas).
  toroidalSpiral: () =>
    sample(112, (t) => {
      const q = 8;
      const r = 4 + 1.4 * Math.cos(q * t);
      return { x: r * Math.cos(t), y: 1.4 * Math.sin(q * t), z: r * Math.sin(t) };
    }),

  // Nó (3,2): 3 voltas ao redor do eixo, 2 pelo interior do toro.
  torusKnot: () =>
    sample(72, (t) => {
      const u = 3 * t;
      const w = (2 * u) / 3;
      const r = 2 + Math.cos(w);
      return { x: 1.8 * r * Math.cos(u), y: 1.8 * Math.sin(w), z: 1.8 * r * Math.sin(u) };
    }),

  // S vertical na frente, S espelhado atrás: forma fechada e suave.
  sTrack: () =>
    sample(40, (t) => ({ x: 2.4 * Math.sin(2 * t), y: 5 * Math.cos(t), z: 1.8 * Math.sin(t) })),

  // Duas voltas descendo por fora e duas subindo por dentro.
  stackedCircuit: () =>
    sample(120, (t) => {
      const turns = 4;
      const r = 3.5 + 1.1 * Math.sin(t);
      return { x: r * Math.cos(turns * t), y: 3.6 * Math.cos(t), z: r * Math.sin(turns * t) };
    }),
};

export interface AutoFitOptions {
  radius?: number;
  closed?: boolean;
  curveType?: CurveType;
  tension?: number;
}

/**
 * Centraliza o trajeto em (0,0,0) pelo bounding box da curva amostrada e escala para caber
 * em uma esfera de raio `radius` (padrão 5).
 */
export function autoFitPath(points: readonly Vec3Like[], options: AutoFitOptions = {}): Vec3Like[] {
  const radius = options.radius ?? FIT_RADIUS;
  if (points.length < 2) return points.map((p) => ({ ...p }));
  const curve = new CatmullRomCurve3(
    points.map((p) => new Vector3(p.x, p.y, p.z)),
    options.closed ?? true,
    options.curveType ?? 'centripetal',
    options.tension ?? 0.5,
  );
  const samples = curve.getSpacedPoints(512);
  const min = new Vector3(Infinity, Infinity, Infinity);
  const max = new Vector3(-Infinity, -Infinity, -Infinity);
  for (const s of samples) {
    min.min(s);
    max.max(s);
  }
  const center = min.add(max).multiplyScalar(0.5);
  let maxDistance = 0;
  for (const s of samples) maxDistance = Math.max(maxDistance, s.distanceTo(center));
  const scale = maxDistance > 1e-9 ? radius / maxDistance : 1;
  return points.map((p) => ({
    x: roundTo((p.x - center.x) * scale, 4),
    y: roundTo((p.y - center.y) * scale, 4),
    z: roundTo((p.z - center.z) * scale, 4),
  }));
}

/** Alias com o nome exigido pela especificação. */
export const AutoFitPath = autoFitPath;

export function createPresetPoints(id: BuiltInPathPresetId): Vec3Like[] {
  return autoFitPath(RAW_PRESETS[id]());
}

export interface RandomPathResult {
  points: Vec3Like[];
  attempts: number;
}

/**
 * Gera um trajeto fechado aleatório (8–20 pontos) a partir da seed. Cada tentativa é validada
 * em modo estrito (distância mínima 0.5, ângulo máximo 120°, limites de tamanho, valores finitos).
 */
export function randomizePath(seed: number, maxAttempts = 64): RandomPathResult {
  const rng = SeededRandom.derived(seed, 'path');
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const count = rng.nextInt(8, 21);
    const baseRadius = rng.nextFloat(3, 5);
    const heightAmplitude = rng.nextFloat(0.4, 2.2);
    const harmonic = rng.nextInt(1, 4);
    const heightPhase = rng.nextFloat(0, TAU);
    const step = TAU / count;
    const raw: Vec3Like[] = [];
    for (let i = 0; i < count; i++) {
      const theta = i * step + rng.nextFloat(-0.25, 0.25) * step;
      const r = baseRadius * rng.nextFloat(0.65, 1.2);
      const y =
        heightAmplitude * Math.sin(harmonic * theta + heightPhase) + rng.nextFloat(-0.5, 0.5);
      raw.push({ x: r * Math.cos(theta), y, z: r * Math.sin(theta) });
    }
    const fitted = autoFitPath(raw);
    const result = validatePathPoints(fitted, true, { strict: true });
    if (result.valid) return { points: fitted, attempts: attempt };
  }
  return { points: createPresetPoints('wave3d'), attempts: maxAttempts };
}

export function createPathSettings(id: PathPresetId, seed: number): PathSettings {
  const points = id === 'custom' ? randomizePath(seed).points : createPresetPoints(id);
  return { preset: id, points, closed: true, curveType: 'centripetal', tension: 0.5 };
}
