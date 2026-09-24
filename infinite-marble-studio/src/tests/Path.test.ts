import { Vector3 } from 'three';
import { describe, expect, it } from 'vitest';
import {
  AutoFitPath,
  BUILT_IN_PATH_PRESETS,
  FIT_RADIUS,
  autoFitPath,
  createPathSettings,
  createPresetPoints,
  randomizePath,
} from '../path/PathFactory';
import { PathModel } from '../path/PathModel';
import { computeBounds, validatePathPoints } from '../path/PathValidator';
import { END_EPSILON } from './helpers';

const model = (id: (typeof BUILT_IN_PATH_PRESETS)[number], bank = 0): PathModel =>
  new PathModel(createPathSettings(id, 1), { bankAngleDeg: bank });

describe('Presets de trajeto', () => {
  it.each(BUILT_IN_PATH_PRESETS)('%s é fechado, válido e sem avisos', (id) => {
    const points = createPresetPoints(id);
    const result = validatePathPoints(points, true);
    expect(result.valid).toBe(true);
    expect(result.closed).toBe(true);
    expect(result.warnings).toEqual([]);
  });

  it.each(BUILT_IN_PATH_PRESETS)('%s não tem salto entre getPointAt(0) e getPointAt(1−ε)', (id) => {
    const path = model(id);
    const a = path.curve.getPointAt(0, new Vector3());
    const b = path.curve.getPointAt(1 - END_EPSILON, new Vector3());
    const c = path.curve.getPointAt(0.9999, new Vector3());
    expect(a.distanceTo(b)).toBeLessThan(0.001);
    // 0.9999 está a 0.01% do comprimento: distância proporcional, sem salto.
    expect(a.distanceTo(c)).toBeLessThan(path.length * 1e-4 * 1.5);
  });

  it.each(BUILT_IN_PATH_PRESETS)('%s produz posições finitas e cabe na esfera de raio 5', (id) => {
    const path = model(id);
    const p = new Vector3();
    for (let i = 0; i <= 500; i++) {
      path.getPointAt(i / 500, p);
      expect(Number.isFinite(p.x) && Number.isFinite(p.y) && Number.isFinite(p.z)).toBe(true);
    }
    expect(path.boundingSphere.radius).toBeLessThanOrEqual(FIT_RADIUS + 0.05);
    expect(path.length).toBeGreaterThan(10);
  });
});

describe('Randomizar trajeto', () => {
  it('é determinístico para a mesma seed', () => {
    expect(randomizePath(1234).points).toEqual(randomizePath(1234).points);
  });

  it('seeds diferentes produzem trajetos diferentes', () => {
    expect(randomizePath(1).points).not.toEqual(randomizePath(2).points);
  });

  it('gera 8–20 pontos respeitando todas as restrições em modo estrito', () => {
    for (let seed = 0; seed < 60; seed++) {
      const { points } = randomizePath(seed * 7919 + 13);
      expect(points.length).toBeGreaterThanOrEqual(8);
      expect(points.length).toBeLessThanOrEqual(20);
      const result = validatePathPoints(points, true, { strict: true });
      expect(result.errors).toEqual([]);
      const { min, max } = computeBounds(points);
      expect(Math.max(max.x - min.x, max.y - min.y, max.z - min.z)).toBeLessThanOrEqual(50);
    }
  });

  it('createPathSettings("custom") usa o randomizador com curva fechada centrípeta', () => {
    const settings = createPathSettings('custom', 77);
    expect(settings.closed).toBe(true);
    expect(settings.curveType).toBe('centripetal');
    expect(settings.points).toEqual(randomizePath(77).points);
  });
});

describe('AutoFitPath', () => {
  it('centraliza em (0,0,0) e escala para raio 5', () => {
    const shifted = createPresetPoints('wave3d').map((p) => ({
      x: p.x * 3 + 20,
      y: p.y * 3 - 7,
      z: p.z * 3 + 4,
    }));
    const fitted = AutoFitPath(shifted);
    const path = new PathModel({
      points: fitted,
      closed: true,
      curveType: 'centripetal',
      tension: 0.5,
    });
    const center = path.boundingBox.getCenter(new Vector3());
    expect(center.length()).toBeLessThan(0.01);
    expect(path.boundingSphere.radius).toBeCloseTo(FIT_RADIUS, 1);
    expect(autoFitPath(fitted)).toEqual(fitted);
  });
});

describe('PathFrames', () => {
  it.each(BUILT_IN_PATH_PRESETS)('%s: frames ortonormais, contínuos e sem inversão', (id) => {
    const path = model(id);
    const t = new Vector3();
    const u = new Vector3();
    const s = new Vector3();
    const prevUp = new Vector3();
    for (let i = 0; i <= 400; i++) {
      path.getFrameAt(i / 400, t, u, s);
      expect(t.length()).toBeCloseTo(1, 6);
      expect(u.length()).toBeCloseTo(1, 6);
      expect(Math.abs(t.dot(u))).toBeLessThan(1e-6);
      expect(s.clone().sub(new Vector3().crossVectors(u, t)).length()).toBeLessThan(1e-6);
      if (i > 0) expect(u.dot(prevUp)).toBeGreaterThan(0.9);
      prevUp.copy(u);
    }
  });

  it.each(BUILT_IN_PATH_PRESETS)('%s: frame(0) ≈ frame(1−ε) no fechamento', (id) => {
    const path = model(id);
    const t0 = new Vector3();
    const u0 = new Vector3();
    const s0 = new Vector3();
    const t1 = new Vector3();
    const u1 = new Vector3();
    const s1 = new Vector3();
    path.getFrameAt(0, t0, u0, s0);
    path.getFrameAt(1 - END_EPSILON, t1, u1, s1);
    expect(t0.distanceTo(t1)).toBeLessThan(1e-3);
    expect(u0.distanceTo(u1)).toBeLessThan(1e-3);
    expect(s0.distanceTo(s1)).toBeLessThan(1e-3);
  });

  it('bankAngle gira o "up" em torno da tangente', () => {
    const a = model('wave3d', 0);
    const b = model('wave3d', 90);
    const t = new Vector3();
    const ua = new Vector3();
    const ub = new Vector3();
    const s = new Vector3();
    a.getFrameAt(0.3, t, ua, s);
    b.getFrameAt(0.3, t, ub, s);
    expect(Math.abs(ua.dot(ub))).toBeLessThan(1e-3);
  });

  it('curvas horizontais têm "up" alinhado a +Y', () => {
    const path = model('wave3d');
    const t = new Vector3();
    const u = new Vector3();
    const s = new Vector3();
    let sum = 0;
    for (let i = 0; i < 100; i++) {
      path.getFrameAt(i / 100, t, u, s);
      sum += u.y;
    }
    expect(sum / 100).toBeGreaterThan(0.8);
  });
});
