import { describe, expect, it } from 'vitest';
import { PathEditor } from '../path/PathEditor';
import { turnAngleDeg, validatePathPoints } from '../path/PathValidator';
import type { Vec3Like } from '../presets/PresetSchema';

const square: Vec3Like[] = [
  { x: 3, y: 0, z: 0 },
  { x: 0, y: 0, z: 3 },
  { x: -3, y: 0, z: 0 },
  { x: 0, y: 0, z: -3 },
];

describe('PathValidator', () => {
  it('aceita curva fechada simples com 4 pontos', () => {
    const result = validatePathPoints(square, true);
    expect(result.valid).toBe(true);
    expect(result.exportable).toBe(true);
    expect(result.errors).toEqual([]);
  });

  it('curva com menos de 4 pontos é inválida', () => {
    const result = validatePathPoints(square.slice(0, 3), true);
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toContain('pelo menos 4');
  });

  it('rejeita pontos duplicados consecutivos (inclusive o fechamento)', () => {
    const dup = [...square, { ...square[0]! }];
    const result = validatePathPoints(dup, true);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes('duplicados'))).toBe(true);
    const mid = [square[0]!, { ...square[0]! }, square[1]!, square[2]!, square[3]!];
    expect(validatePathPoints(mid, true).valid).toBe(false);
  });

  it('rejeita NaN e Infinity', () => {
    const bad = square.map((p, i) => (i === 2 ? { ...p, y: Number.NaN } : p));
    expect(validatePathPoints(bad, true).errors[0]).toContain('NaN');
    const inf = square.map((p, i) => (i === 1 ? { ...p, x: Infinity } : p));
    expect(validatePathPoints(inf, true).valid).toBe(false);
  });

  it('rejeita trajetos grandes demais e degenerados', () => {
    const huge = square.map((p) => ({ x: p.x * 20, y: p.y, z: p.z * 20 }));
    expect(validatePathPoints(huge, true).errors.some((e) => e.includes('excede'))).toBe(true);
    const line = [0, 1, 2, 3].map((i) => ({ x: i, y: 0, z: 0 }));
    expect(validatePathPoints(line, true).errors.some((e) => e.includes('degenerado'))).toBe(true);
  });

  it('avisa sobre curva aberta, ângulos abruptos e pontos próximos', () => {
    expect(validatePathPoints(square, false).warnings[0]).toContain('aberta');
    expect(validatePathPoints(square, false).exportable).toBe(false);
    const zigzag: Vec3Like[] = [
      { x: 0, y: 0, z: 0 },
      { x: 4, y: 0, z: 0 },
      { x: 0.3, y: 0, z: 0.4 },
      { x: 0, y: 0, z: 4 },
    ];
    const soft = validatePathPoints(zigzag, true);
    expect(soft.valid).toBe(true);
    expect(soft.warnings.some((w) => w.includes('abrupta'))).toBe(true);
    const strict = validatePathPoints(zigzag, true, { strict: true });
    expect(strict.valid).toBe(false);
    const close = [...square.slice(0, 2), { x: 0.1, y: 0, z: 3 }, ...square.slice(2)];
    expect(validatePathPoints(close, true).warnings.some((w) => w.includes('próximos'))).toBe(true);
  });

  it('turnAngleDeg mede o desvio de direção', () => {
    expect(
      turnAngleDeg({ x: 0, y: 0, z: 0 }, { x: 1, y: 0, z: 0 }, { x: 2, y: 0, z: 0 }),
    ).toBeCloseTo(0);
    expect(
      turnAngleDeg({ x: 0, y: 0, z: 0 }, { x: 1, y: 0, z: 0 }, { x: 1, y: 1, z: 0 }),
    ).toBeCloseTo(90);
  });
});

describe('PathEditor', () => {
  it('adiciona, duplica, move e remove pontos sem mutar a lista original', () => {
    const added = PathEditor.addPoint(square, 0, true);
    expect(added.points).toHaveLength(5);
    expect(added.selectedIndex).toBe(1);
    expect(added.points[1]).toEqual({ x: 1.5, y: 0, z: 1.5 });
    expect(square).toHaveLength(4);

    const duplicated = PathEditor.duplicatePoint(square, 3, true);
    expect(duplicated.points).toHaveLength(5);
    expect(validatePathPoints(duplicated.points, true).errors).toEqual([]);

    const moved = PathEditor.setCoordinate(square, 2, 'y', 1.25);
    expect(moved.points[2]!.y).toBe(1.25);

    expect(() => PathEditor.removePoint(square, 0)).toThrow('pelo menos 4');
    expect(PathEditor.removePoint(added.points, 1).points).toEqual(square);
    expect(() => PathEditor.setCoordinate(square, 9, 'x', 1)).toThrow();
    expect(() => PathEditor.setCoordinate(square, 0, 'x', Number.NaN)).toThrow();
  });

  it('adiciona ponto em curva aberta no último índice sem duplicar', () => {
    const result = PathEditor.addPoint(square, 3, false);
    expect(validatePathPoints(result.points, false).valid).toBe(true);
  });
});
