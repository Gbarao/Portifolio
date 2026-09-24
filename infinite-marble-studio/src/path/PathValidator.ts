import { MAX_PATH_POINTS, MIN_PATH_POINTS, type Vec3Like } from '../presets/PresetSchema';

export interface PathValidationOptions {
  /** Distância mínima entre pontos de controle (padrão 0.5). */
  minPointDistance?: number;
  /** Ângulo máximo de desvio entre segmentos consecutivos, em graus (padrão 120). */
  maxTurnAngleDeg?: number;
  /** Tamanho máximo do bounding box (padrão 50). */
  maxExtent?: number;
  /** Extensão mínima exigida em pelo menos dois eixos (padrão 0.1). */
  minExtent?: number;
  /** Modo estrito (randomizador): proximidade e ângulos viram erros. */
  strict?: boolean;
}

export interface PathValidationResult {
  valid: boolean;
  closed: boolean;
  exportable: boolean;
  errors: string[];
  warnings: string[];
}

const DUPLICATE_EPSILON = 1e-4;

function distance(a: Vec3Like, b: Vec3Like): number {
  return Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
}

/** Ângulo (graus) entre as direções (b - a) e (c - b). 0 = seguir reto. */
export function turnAngleDeg(a: Vec3Like, b: Vec3Like, c: Vec3Like): number {
  const ux = b.x - a.x;
  const uy = b.y - a.y;
  const uz = b.z - a.z;
  const vx = c.x - b.x;
  const vy = c.y - b.y;
  const vz = c.z - b.z;
  const lu = Math.hypot(ux, uy, uz);
  const lv = Math.hypot(vx, vy, vz);
  if (lu === 0 || lv === 0) return 0;
  const cos = Math.min(1, Math.max(-1, (ux * vx + uy * vy + uz * vz) / (lu * lv)));
  return (Math.acos(cos) * 180) / Math.PI;
}

export function computeBounds(points: readonly Vec3Like[]): { min: Vec3Like; max: Vec3Like } {
  const min = { x: Infinity, y: Infinity, z: Infinity };
  const max = { x: -Infinity, y: -Infinity, z: -Infinity };
  for (const p of points) {
    min.x = Math.min(min.x, p.x);
    min.y = Math.min(min.y, p.y);
    min.z = Math.min(min.z, p.z);
    max.x = Math.max(max.x, p.x);
    max.y = Math.max(max.y, p.y);
    max.z = Math.max(max.z, p.z);
  }
  return { min, max };
}

export function validatePathPoints(
  points: readonly Vec3Like[],
  closed: boolean,
  options: PathValidationOptions = {},
): PathValidationResult {
  const minDistance = options.minPointDistance ?? 0.5;
  const maxTurn = options.maxTurnAngleDeg ?? 120;
  const maxExtent = options.maxExtent ?? 50;
  const minExtent = options.minExtent ?? 0.1;
  const strict = options.strict ?? false;
  const errors: string[] = [];
  const warnings: string[] = [];
  const soft = (message: string): void => {
    (strict ? errors : warnings).push(message);
  };

  const n = points.length;
  if (n < MIN_PATH_POINTS) {
    errors.push(`A curva precisa de pelo menos ${MIN_PATH_POINTS} pontos (atual: ${n}).`);
  }
  if (n > MAX_PATH_POINTS) {
    errors.push(`A curva aceita no máximo ${MAX_PATH_POINTS} pontos (atual: ${n}).`);
  }

  let finite = true;
  points.forEach((p, i) => {
    if (!Number.isFinite(p.x) || !Number.isFinite(p.y) || !Number.isFinite(p.z)) {
      errors.push(`Ponto ${i} possui coordenada inválida (NaN ou Infinity).`);
      finite = false;
    }
  });

  if (finite && n >= 2) {
    const segmentCount = closed ? n : n - 1;
    for (let i = 0; i < segmentCount; i++) {
      const a = points[i] as Vec3Like;
      const j = (i + 1) % n;
      const b = points[j] as Vec3Like;
      const d = distance(a, b);
      if (d < DUPLICATE_EPSILON) {
        errors.push(`Pontos ${i} e ${j} são duplicados consecutivos.`);
      } else if (d < minDistance) {
        soft(`Pontos ${i} e ${j} estão muito próximos (${d.toFixed(2)} < ${minDistance}).`);
      }
    }

    // Pontos não adjacentes muito próximos indicam trechos que se cruzam.
    for (let i = 0; i < n; i++) {
      for (let j = i + 2; j < n; j++) {
        if (closed && i === 0 && j === n - 1) continue;
        const d = distance(points[i] as Vec3Like, points[j] as Vec3Like);
        if (d < minDistance) {
          soft(`Pontos ${i} e ${j} (não adjacentes) estão muito próximos (${d.toFixed(2)}).`);
        }
      }
    }

    if (n >= 3) {
      const start = closed ? 0 : 1;
      const end = closed ? n : n - 1;
      for (let i = start; i < end; i++) {
        const prev = points[(i - 1 + n) % n] as Vec3Like;
        const curr = points[i] as Vec3Like;
        const next = points[(i + 1) % n] as Vec3Like;
        const angle = turnAngleDeg(prev, curr, next);
        if (angle > maxTurn) {
          soft(`Curva abrupta no ponto ${i} (${angle.toFixed(0)}° > ${maxTurn}°).`);
        }
      }
    }

    const { min, max } = computeBounds(points);
    const extents = [max.x - min.x, max.y - min.y, max.z - min.z];
    const largest = Math.max(...extents);
    if (largest > maxExtent) {
      errors.push(`O trajeto excede ${maxExtent} unidades (${largest.toFixed(1)}).`);
    }
    if (extents.filter((e) => e >= minExtent).length < 2) {
      errors.push(`Trajeto degenerado: precisa de pelo menos ${minExtent} unidade em dois eixos.`);
    }
  }

  if (!closed) {
    warnings.push('Curva aberta: a exportação exige curva fechada.');
  }

  const valid = errors.length === 0;
  return { valid, closed, exportable: valid && closed, errors, warnings };
}
