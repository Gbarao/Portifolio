import { Color, Matrix4, Quaternion, Vector3 } from 'three';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  MarbleKinematics,
  computeAutoSpinCycles,
  computeMarbleU,
  computePhaseOffset,
  computeRestHeight,
} from '../marbles/MarbleKinematics';
import { generateMarbleColors, generateMarbleScales } from '../marbles/MarbleColorPalette';
import { MarbleSystem } from '../marbles/MarbleSystem';
import { PathModel } from '../path/PathModel';
import { createDefaultProject } from '../presets/DefaultPresets';
import { END_EPSILON } from './helpers';

function setup(overrides: Partial<ReturnType<typeof createDefaultProject>['marbles']> = {}) {
  const project = createDefaultProject();
  Object.assign(project.marbles, overrides);
  const path = new PathModel(project.path);
  const kinematics = new MarbleKinematics(path, project.marbles, project.track, project.seed);
  return { project, path, kinematics };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('Fase e parametrização', () => {
  it('phaseOffset = index / count na distribuição uniforme', () => {
    expect(computePhaseOffset(0, 24, 0)).toBe(0);
    expect(computePhaseOffset(6, 24, 0)).toBe(0.25);
    expect(computePhaseOffset(23, 24, 0)).toBeCloseTo(23 / 24, 12);
  });

  it('phaseOffset com espaçamento fixo envolve em [0, 1)', () => {
    expect(computePhaseOffset(3, 10, 0.1)).toBeCloseTo(0.3, 12);
    expect(computePhaseOffset(15, 20, 0.1)).toBeCloseTo(0.5, 12);
    expect(computePhaseOffset(1, 0, 0)).toBe(0);
  });

  it('u = modulo(dir × t × ciclos + fase + fase global, 1)', () => {
    expect(computeMarbleU(0.25, 0.5, 2, 1, 0)).toBeCloseTo(0, 12);
    expect(computeMarbleU(0.25, 0, 1, -1, 0)).toBeCloseTo(0.75, 12);
    expect(computeMarbleU(0.5, 0.1, 1, 1, 0.2)).toBeCloseTo(0.8, 12);
  });

  it('altura de repouso: sobre o tubo e entre os trilhos', () => {
    expect(
      computeRestHeight({ style: 'tube', radius: 0.3, railDistance: 1, railRadius: 0.15 }, 0.15),
    ).toBeCloseTo(0.45);
    expect(
      computeRestHeight(
        { style: 'dualRail', radius: 0.3, railDistance: 0.5, railRadius: 0.06 },
        0.2,
      ),
    ).toBeCloseTo(Math.sqrt(0.26 ** 2 - 0.25 ** 2));
    expect(
      computeRestHeight(
        { style: 'dualRail', radius: 0.3, railDistance: 1, railRadius: 0.15 },
        0.15,
      ),
    ).toBe(0);
  });

  it('rotações automáticas são inteiras', () => {
    const spins = computeAutoSpinCycles(1, 33.2, 0.15);
    expect(Number.isInteger(spins)).toBe(true);
    expect(spins).toBe(Math.round(33.2 / (2 * Math.PI * 0.15)));
    expect(computeAutoSpinCycles(1, 10, 0)).toBe(0);
  });
});

describe('Cores e escalas', () => {
  it('mesma seed → mesmas cores; seeds diferentes → cores diferentes', () => {
    const settings = { palette: 'rainbow' as const, count: 24, customColors: [] };
    expect(generateMarbleColors(settings, 5)).toEqual(generateMarbleColors(settings, 5));
    expect(generateMarbleColors(settings, 5)).not.toEqual(generateMarbleColors(settings, 6));
    const neon = { palette: 'neon' as const, count: 12, customColors: [] };
    expect(generateMarbleColors(neon, 1)).toEqual(generateMarbleColors(neon, 1));
    expect(generateMarbleColors(neon, 1)).not.toEqual(generateMarbleColors(neon, 3));
  });

  it('paleta custom aplica as cores em sequência', () => {
    const colors = generateMarbleColors(
      { palette: 'custom', count: 5, customColors: [0x111111, 0xeeeeee] },
      9,
    );
    expect(colors).toEqual([0x111111, 0xeeeeee, 0x111111, 0xeeeeee, 0x111111]);
  });

  it('escala individual limitada a ±10%', () => {
    const scales = generateMarbleScales(100, 0.5, 3);
    for (const s of scales) {
      expect(s).toBeGreaterThanOrEqual(0.9);
      expect(s).toBeLessThanOrEqual(1.1);
    }
    expect(generateMarbleScales(10, 0.05, 3)).toEqual(generateMarbleScales(10, 0.05, 3));
  });
});

describe('MarbleKinematics', () => {
  it('todas as bolinhas retornam exatamente ao ponto inicial', () => {
    for (const cycles of [1, 2, 3]) {
      const { kinematics } = setup({
        cycleCount: cycles,
        pulseAmount: 0.2,
        pulseCycles: 2,
        hueShiftCycles: 1,
      });
      const p0 = new Vector3();
      const p1 = new Vector3();
      const q0 = new Quaternion();
      const q1 = new Quaternion();
      const c0 = new Color();
      const c1 = new Color();
      for (let i = 0; i < kinematics.count; i++) {
        const s0 = kinematics.evaluate(i, 0, p0, q0);
        const s1 = kinematics.evaluate(i, 1 - END_EPSILON, p1, q1);
        expect(p0.distanceTo(p1)).toBeLessThan(0.001);
        expect(q0.angleTo(q1)).toBeLessThan(0.01);
        expect(Math.abs(s0 - s1)).toBeLessThan(0.001);
        kinematics.evaluateColor(i, 0, c0);
        kinematics.evaluateColor(i, 1 - END_EPSILON, c1);
        expect(Math.abs(c0.r - c1.r) + Math.abs(c0.g - c1.g) + Math.abs(c0.b - c1.b)).toBeLessThan(
          2 / 255,
        );
      }
    }
  });

  it('direção negativa percorre a curva em sentido oposto', () => {
    const { kinematics: forward } = setup({ direction: 1 });
    const { kinematics: backward } = setup({ direction: -1 });
    expect(forward.getU(0, 0.1)).toBeCloseTo(0.1, 12);
    expect(backward.getU(0, 0.1)).toBeCloseTo(0.9, 12);
  });
});

describe('MarbleSystem (InstancedMesh)', () => {
  it('usa um único InstancedMesh com uma instância por bolinha', () => {
    const { project, kinematics } = setup({ count: 40 });
    const system = new MarbleSystem(kinematics, project.marbles);
    expect(system.mesh.isInstancedMesh).toBe(true);
    expect(system.mesh.count).toBe(40);
    system.dispose();
  });

  it('não aloca objetos no loop de animação e atualiza a matriz uma vez por frame', () => {
    const { project, kinematics } = setup({ count: 50, hueShiftCycles: 1 });
    const system = new MarbleSystem(kinematics, project.marbles);
    const scratchBefore = system.scratch;
    const arrayBefore = system.mesh.instanceMatrix.array;
    const spies = [
      vi.spyOn(Vector3.prototype, 'clone'),
      vi.spyOn(Quaternion.prototype, 'clone'),
      vi.spyOn(Matrix4.prototype, 'clone'),
      vi.spyOn(Color.prototype, 'clone'),
    ];
    const versionBefore = system.mesh.instanceMatrix.version;
    for (let frame = 0; frame < 120; frame++) system.update(frame / 120);
    for (const spy of spies) expect(spy).not.toHaveBeenCalled();
    expect(system.mesh.instanceMatrix.version - versionBefore).toBe(120);
    expect(system.mesh.instanceMatrix.array).toBe(arrayBefore);
    system.scratch.forEach((obj, i) => expect(obj).toBe(scratchBefore[i]));
    system.dispose();
  });

  it('matriz de instância corresponde à cinemática e é finita', () => {
    const { project, kinematics } = setup({ count: 8 });
    const system = new MarbleSystem(kinematics, project.marbles);
    system.update(0.37);
    const m = new Matrix4();
    const p = new Vector3();
    const q = new Quaternion();
    const expected = new Vector3();
    for (let i = 0; i < 8; i++) {
      system.mesh.getMatrixAt(i, m);
      p.setFromMatrixPosition(m);
      kinematics.evaluate(i, 0.37, expected, q);
      expect(p.distanceTo(expected)).toBeLessThan(1e-5);
    }
    for (const v of system.mesh.instanceMatrix.array) expect(Number.isFinite(v)).toBe(true);
    system.dispose();
  });

  it('dispose libera geometria, material e buffers', () => {
    const { project, kinematics } = setup();
    const system = new MarbleSystem(kinematics, project.marbles);
    const geometrySpy = vi.spyOn(system.mesh.geometry, 'dispose');
    const materialSpy = vi.spyOn(system.mesh.material, 'dispose');
    system.dispose();
    expect(geometrySpy).toHaveBeenCalledTimes(1);
    expect(materialSpy).toHaveBeenCalledTimes(1);
  });

  it('setKinematics exige a mesma quantidade de instâncias', () => {
    const a = setup({ count: 10 });
    const b = setup({ count: 12 });
    const system = new MarbleSystem(a.kinematics, a.project.marbles);
    expect(() => system.setKinematics(b.kinematics, b.project.marbles)).toThrow();
    system.setKinematics(setup({ count: 10, palette: 'neon' }).kinematics, a.project.marbles);
    system.dispose();
  });
});
