import { roundTo } from '../core/MathUtils';
import { MAX_PATH_POINTS, MIN_PATH_POINTS, type Vec3Like } from '../presets/PresetSchema';

export type Axis = 'x' | 'y' | 'z';

export interface EditResult {
  points: Vec3Like[];
  /** Índice a selecionar após a operação. */
  selectedIndex: number | null;
}

const clonePoints = (points: readonly Vec3Like[]): Vec3Like[] => points.map((p) => ({ ...p }));

const round = (p: Vec3Like): Vec3Like => ({
  x: roundTo(p.x, 4),
  y: roundTo(p.y, 4),
  z: roundTo(p.z, 4),
});

/** Operações puras de edição de pontos de controle (retornam novas listas). */
export const PathEditor = {
  /** Insere um ponto no meio do segmento entre `afterIndex` e o próximo. */
  addPoint(points: readonly Vec3Like[], afterIndex: number | null, closed: boolean): EditResult {
    if (points.length >= MAX_PATH_POINTS) {
      throw new Error(`Limite de ${MAX_PATH_POINTS} pontos atingido.`);
    }
    const next = clonePoints(points);
    const n = next.length;
    const i = afterIndex === null ? n - 1 : Math.min(Math.max(0, afterIndex), n - 1);
    const a = next[i] as Vec3Like;
    const bIndex = i + 1 < n ? i + 1 : closed ? 0 : i - 1;
    const b = next[bIndex] as Vec3Like;
    const mid = round({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, z: (a.z + b.z) / 2 });
    if (bIndex === i - 1) mid.x += 0.5;
    next.splice(i + 1, 0, mid);
    return { points: next, selectedIndex: i + 1 };
  },

  removePoint(points: readonly Vec3Like[], index: number): EditResult {
    if (points.length <= MIN_PATH_POINTS) {
      throw new Error(`A curva precisa de pelo menos ${MIN_PATH_POINTS} pontos.`);
    }
    if (index < 0 || index >= points.length) throw new Error(`Ponto ${index} não existe.`);
    const next = clonePoints(points);
    next.splice(index, 1);
    return { points: next, selectedIndex: Math.min(index, next.length - 1) };
  },

  /** Duplica o ponto, deslocando a cópia em direção ao vizinho para não criar duplicata. */
  duplicatePoint(points: readonly Vec3Like[], index: number, closed: boolean): EditResult {
    if (points.length >= MAX_PATH_POINTS) {
      throw new Error(`Limite de ${MAX_PATH_POINTS} pontos atingido.`);
    }
    if (index < 0 || index >= points.length) throw new Error(`Ponto ${index} não existe.`);
    const next = clonePoints(points);
    const a = next[index] as Vec3Like;
    const neighbor = next[index + 1 < next.length ? index + 1 : closed ? 0 : index - 1] as Vec3Like;
    const dx = neighbor.x - a.x;
    const dy = neighbor.y - a.y;
    const dz = neighbor.z - a.z;
    const length = Math.hypot(dx, dy, dz);
    const copy =
      length > 1e-6
        ? round({ x: a.x + dx * 0.3, y: a.y + dy * 0.3, z: a.z + dz * 0.3 })
        : round({ x: a.x + 0.5, y: a.y, z: a.z });
    next.splice(index + 1, 0, copy);
    return { points: next, selectedIndex: index + 1 };
  },

  movePoint(points: readonly Vec3Like[], index: number, position: Vec3Like): EditResult {
    if (index < 0 || index >= points.length) throw new Error(`Ponto ${index} não existe.`);
    const next = clonePoints(points);
    next[index] = round(position);
    return { points: next, selectedIndex: index };
  },

  setCoordinate(points: readonly Vec3Like[], index: number, axis: Axis, value: number): EditResult {
    if (!Number.isFinite(value)) throw new Error('Coordenada inválida.');
    const current = points[index];
    if (!current) throw new Error(`Ponto ${index} não existe.`);
    return PathEditor.movePoint(points, index, { ...current, [axis]: value });
  },
};
