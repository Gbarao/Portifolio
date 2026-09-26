import { describe, expect, it } from 'vitest';
import { computeTotalFrames, frameToNormalizedTime } from '../core/LoopClock';
import {
  DEFAULT_PRESSURE_TIMING,
  createPressureState,
  elasticDecay,
  evaluatePressure,
  evaluateToolTravel,
  timeForPressure,
  validatePressureTiming,
  viscousDecay,
  type PressureMotion,
} from '../satisfying/animation/PressureCurve';
import { evaluateMacroCamera } from '../satisfying/camera/MacroCameraRig';
import { computeMeshVolume } from '../satisfying/deformation/MeshNormals';
import { indentationProfile, solveContactRadius } from '../satisfying/deformation/SqueezeDeformer';
import { buildSoftBlockMesh } from '../satisfying/geometry/SoftBlockGeometry';
import { createDefaultSatisfyingSettings } from '../satisfying/SatisfyingSettings';
import { SqueezeSimulation, pressureMotionFrom } from '../satisfying/SqueezeSimulation';

const ASPECT = 9 / 16;
const settings = createDefaultSatisfyingSettings();
const motion: PressureMotion = pressureMotionFrom(settings);

function simulate(t: number, seed = 1, s = settings): SqueezeSimulation {
  const sim = new SqueezeSimulation(s, seed);
  sim.deform(sim.evaluate(t, ASPECT));
  return sim;
}

describe('SoftBlockGeometry', () => {
  const mesh = buildSoftBlockMesh(settings.object);

  it('é fechada, soldada e orientada para fora (volume positivo ≈ caixa arredondada)', () => {
    const { width: w, height: h, depth: d } = settings.object;
    const r = mesh.radius;
    // Volume exato de uma caixa arredondada.
    const exact =
      (w - 2 * r) * (h - 2 * r) * (d - 2 * r) +
      2 * r * ((w - 2 * r) * (h - 2 * r) + (w - 2 * r) * (d - 2 * r) + (h - 2 * r) * (d - 2 * r)) +
      Math.PI * r * r * (w - 2 * r + (h - 2 * r) + (d - 2 * r)) +
      (4 / 3) * Math.PI * r ** 3;
    const volume = computeMeshVolume(mesh.positions, mesh.indices);
    expect(volume).toBeGreaterThan(0);
    expect(Math.abs(volume - exact) / exact).toBeLessThan(0.01);
    // Malha fechada: cada aresta pertence a exatamente dois triângulos.
    const edges = new Map<string, number>();
    for (let t = 0; t < mesh.indices.length; t += 3) {
      for (let e = 0; e < 3; e++) {
        const a = mesh.indices[t + e] as number;
        const b = mesh.indices[t + ((e + 1) % 3)] as number;
        const key = a < b ? `${a}-${b}` : `${b}-${a}`;
        edges.set(key, (edges.get(key) ?? 0) + 1);
      }
    }
    for (const count of edges.values()) expect(count).toBe(2);
  });

  it('base apoiada no chão e topo na altura configurada', () => {
    let minY = Infinity;
    let maxY = -Infinity;
    for (let i = 1; i < mesh.positions.length; i += 3) {
      minY = Math.min(minY, mesh.positions[i] as number);
      maxY = Math.max(maxY, mesh.positions[i] as number);
    }
    expect(minY).toBeCloseTo(0, 6);
    expect(maxY).toBeCloseTo(settings.object.height, 6);
  });
});

describe('Curva de pressão', () => {
  it('cronograma padrão é válido; fora de ordem é rejeitado', () => {
    expect(validatePressureTiming(DEFAULT_PRESSURE_TIMING)).toEqual([]);
    expect(
      validatePressureTiming({ ...DEFAULT_PRESSURE_TIMING, peak: 0.2 }).length,
    ).toBeGreaterThan(0);
    expect(
      validatePressureTiming({ ...DEFAULT_PRESSURE_TIMING, contact: Number.NaN }).length,
    ).toBeGreaterThan(0);
  });

  it('fases: repouso → contato → pico → hold → recuperação → repouso', () => {
    const at = (t: number) => evaluatePressure(t, DEFAULT_PRESSURE_TIMING, motion);
    expect(at(0).toolTravel).toBe(0);
    expect(at(0.02).indent + at(0.02).squash).toBe(0);
    expect(at(DEFAULT_PRESSURE_TIMING.contact).toolDepth).toBeCloseTo(0, 9);
    expect(at(DEFAULT_PRESSURE_TIMING.peak).pressure).toBeCloseTo(1, 6);
    expect(at(0.55).pressure).toBeGreaterThanOrEqual(1);
    expect(at(0.99).pressure).toBe(0);
    expect(at(0.99).toolTravel).toBe(0);
  });

  it('descida monotônica até o pico e valores sempre finitos', () => {
    let previous = -1;
    const state = createPressureState();
    for (let i = 0; i <= 2000; i++) {
      const t = i / 2000;
      const travel = evaluateToolTravel(t, DEFAULT_PRESSURE_TIMING, motion);
      expect(Number.isFinite(travel)).toBe(true);
      if (t <= DEFAULT_PRESSURE_TIMING.peak) {
        expect(travel).toBeGreaterThanOrEqual(previous - 1e-12);
        previous = travel;
      }
      evaluatePressure(t, DEFAULT_PRESSURE_TIMING, motion, state);
      for (const value of [state.indent, state.squash, state.toolDepth, state.pressure]) {
        expect(Number.isFinite(value)).toBe(true);
      }
      expect(state.indent).toBeGreaterThanOrEqual(0);
    }
  });

  it('contínua (sem saltos) inclusive na emenda do loop', () => {
    const n = 4000;
    let maxJump = 0;
    const a = createPressureState();
    const b = createPressureState();
    for (let i = 0; i < n; i++) {
      evaluatePressure(i / n, DEFAULT_PRESSURE_TIMING, motion, a);
      evaluatePressure((i + 1) / n, DEFAULT_PRESSURE_TIMING, motion, b);
      maxJump = Math.max(
        maxJump,
        Math.abs(a.indent - b.indent),
        Math.abs(a.squash - b.squash),
        Math.abs(a.toolTravel - b.toolTravel),
      );
    }
    expect(maxJump).toBeLessThan(0.01);
  });

  it('decaimentos começam em 1 e terminam em 0', () => {
    for (const x of [0, 0.5, 1]) {
      expect(viscousDecay(0, x)).toBe(1);
      expect(viscousDecay(1, x)).toBe(0);
      expect(elasticDecay(0, x)).toBe(1);
      expect(Math.abs(elasticDecay(1, x))).toBeLessThan(1e-12);
    }
  });

  it('timeForPressure encontra o instante da fração pedida', () => {
    for (const f of [0.25, 0.5, 0.75]) {
      const t = timeForPressure(f, DEFAULT_PRESSURE_TIMING, motion);
      expect(evaluatePressure(t, DEFAULT_PRESSURE_TIMING, motion).pressure).toBeCloseTo(f, 6);
    }
  });
});

describe('Indentação (Hertz + esfera)', () => {
  it('raio de contato satisfaz a relação de continuidade', () => {
    const R = 0.6;
    for (const indent of [0.01, 0.1, 0.3]) {
      const a = solveContactRadius(indent, R);
      const f = R - Math.sqrt(R * R - a * a) + (a * a) / (2 * R);
      expect(f).toBeCloseTo(indent, 8);
    }
    expect(solveContactRadius(0, R)).toBe(0);
  });

  it('perfil contínuo na borda do contato e decrescente para fora', () => {
    const R = 0.6;
    const indent = 0.3;
    const a = solveContactRadius(indent, R);
    const inside = indentationProfile(a - 1e-7, indent, a, R, 0.5);
    const outside = indentationProfile(a + 1e-7, indent, a, R, 0.5);
    expect(Math.abs(inside - outside)).toBeLessThan(1e-5);
    let previous = Infinity;
    for (let rho = 0; rho < 3; rho += 0.01) {
      const value = indentationProfile(rho, indent, a, R, 0.5);
      expect(Number.isFinite(value)).toBe(true);
      expect(value).toBeLessThanOrEqual(previous + 1e-12);
      previous = value;
    }
  });
});

describe('SqueezeSimulation', () => {
  const peak = DEFAULT_PRESSURE_TIMING.peak;

  it('nenhum vértice NaN/Infinity em todo o ciclo', () => {
    const sim = new SqueezeSimulation(settings, 7);
    for (let i = 0; i <= 40; i++) {
      sim.deform(sim.evaluate(i / 40, ASPECT));
      let invalid = 0;
      for (const value of sim.deformer.positions) if (!Number.isFinite(value)) invalid++;
      for (const value of sim.deformer.normals) if (!Number.isFinite(value)) invalid++;
      expect(invalid).toBe(0);
    }
  });

  it('deformação localizada: afunda sob a ferramenta, laterais expandem, base fica no chão', () => {
    const sim = simulate(peak);
    const rest = sim.mesh.positions;
    const out = sim.deformer.positions;
    let topCenterDrop = 0;
    let cornerDrop = Infinity;
    let maxSideOut = 0;
    let minY = Infinity;
    const H = settings.object.height;
    for (let v = 0; v < rest.length; v += 3) {
      const x = rest[v] as number;
      const y = rest[v + 1] as number;
      const z = rest[v + 2] as number;
      const drop = y - (out[v + 1] as number);
      if (y > H - 1e-3 && Math.hypot(x, z) < 0.05) topCenterDrop = Math.max(topCenterDrop, drop);
      if (y > H - 0.3 && Math.abs(x) > 0.9 && Math.abs(z) > 0.9)
        cornerDrop = Math.min(cornerDrop, drop);
      if (Math.abs(y - H * 0.6) < 0.08 && Math.abs(z) < 0.05 && x > 0.5) {
        maxSideOut = Math.max(maxSideOut, (out[v] as number) - x);
      }
      minY = Math.min(minY, out[v + 1] as number);
    }
    const depth = settings.pressure.strength * H;
    expect(topCenterDrop).toBeGreaterThan(depth * 0.9);
    // Não é escala global: os cantos do topo descem bem menos que o centro.
    expect(cornerDrop).toBeLessThan(topCenterDrop * 0.5);
    expect(maxSideOut).toBeGreaterThan(0.02);
    expect(minY).toBeGreaterThanOrEqual(0);
  });

  it('preserva o volume ao longo de todo o ciclo (± 2 %)', () => {
    const sim = new SqueezeSimulation(settings, 1);
    sim.deform(sim.evaluate(0, ASPECT));
    const restVolume = computeMeshVolume(sim.deformer.positions, sim.mesh.indices);
    let worst = 0;
    for (let i = 0; i < 100; i++) {
      sim.deform(sim.evaluate(i / 100, ASPECT));
      const volume = computeMeshVolume(sim.deformer.positions, sim.mesh.indices);
      worst = Math.max(worst, Math.abs(volume - restVolume) / restVolume);
    }
    expect(worst).toBeLessThan(0.02);
  });

  it('sem interpenetração com a esfera e sem gap no contato', () => {
    for (const t of [0.3, 0.4, peak, 0.55]) {
      const sim = new SqueezeSimulation(settings, 3);
      const state = sim.evaluate(t, ASPECT);
      sim.deform(state);
      const p = sim.deformer.positions;
      const { x, y, z, radius } = state.tool;
      let minDistance = Infinity;
      for (let v = 0; v < p.length; v += 3) {
        const d = Math.hypot(
          (p[v] as number) - x,
          (p[v + 1] as number) - y,
          (p[v + 2] as number) - z,
        );
        minDistance = Math.min(minDistance, d);
      }
      expect(minDistance).toBeGreaterThan(radius - 1e-4);
      // Em contato: a superfície toca a esfera.
      expect(minDistance).toBeLessThan(radius + 0.01);
    }
  });

  it('state(0) === state(1) e o bloco volta exatamente ao repouso', () => {
    const a = simulate(0);
    const b = simulate(0.999999999);
    const rest = simulate(0.02);
    let seam = 0;
    let restDiff = 0;
    for (let i = 0; i < a.deformer.positions.length; i++) {
      const value = a.deformer.positions[i] as number;
      seam = Math.max(seam, Math.abs(value - (b.deformer.positions[i] as number)));
      restDiff = Math.max(
        restDiff,
        Math.abs(value - (rest.deformer.positions[i] as number)),
        Math.abs(value - (a.mesh.positions[i] as number)),
      );
    }
    expect(seam).toBeLessThan(1e-5);
    expect(restDiff).toBe(0);
  });

  it('mesma seed → mesmo objeto; seeds diferentes → objetos diferentes', () => {
    const a = new SqueezeSimulation(settings, 42);
    const b = new SqueezeSimulation(settings, 42);
    const c = new SqueezeSimulation(settings, 43);
    expect(a.mesh.positions).toEqual(b.mesh.positions);
    expect(a.mesh.positions).not.toEqual(c.mesh.positions);
    const fa = simulate(0.45, 42);
    const fb = simulate(0.45, 42);
    expect(fa.deformer.positions).toEqual(fb.deformer.positions);
  });

  it('câmera macro retorna ao estado inicial e não produz valores inválidos', () => {
    const subject = settings.object;
    const start = evaluateMacroCamera(settings.camera, subject, ASPECT, 0);
    const end = evaluateMacroCamera(settings.camera, subject, ASPECT, 1);
    expect(end).toEqual(start);
    const total = computeTotalFrames(8, 30);
    for (let i = 0; i < total; i++) {
      const pose = evaluateMacroCamera(
        settings.camera,
        subject,
        ASPECT,
        frameToNormalizedTime(i, total),
      );
      for (const v of Object.values(pose)) expect(Number.isFinite(v)).toBe(true);
    }
  });
});
