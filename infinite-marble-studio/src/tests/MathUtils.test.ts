import { describe, expect, it } from 'vitest';
import {
  approxEqual,
  circularDistance,
  clamp,
  degToRad,
  isFiniteNumber,
  isNearlyInteger,
  isPositiveInteger,
  lerp,
  modulo,
  periodicSine,
  radToDeg,
  roundTo,
  smoothstep,
} from '../core/MathUtils';
import { PeriodicNoise } from '../core/PeriodicNoise';
import { PerformanceMonitor, getPerformanceRecommendations } from '../core/PerformanceMonitor';
import { History } from '../core/History';
import { debounce } from '../core/Debounce';
import { vi } from 'vitest';

describe('MathUtils', () => {
  it('modulo funciona com valores negativos', () => {
    expect(modulo(-0.25, 1)).toBeCloseTo(0.75);
    expect(modulo(-1, 1)).toBe(0);
    expect(modulo(2.5, 1)).toBeCloseTo(0.5);
    expect(modulo(-7, 3)).toBe(2);
    expect(modulo(0, 1)).toBe(0);
  });

  it('clamp, lerp, smoothstep, graus', () => {
    expect(clamp(5, 0, 1)).toBe(1);
    expect(clamp(-5, 0, 1)).toBe(0);
    expect(lerp(0, 10, 0.25)).toBe(2.5);
    expect(smoothstep(0, 1, 0.5)).toBeCloseTo(0.5);
    expect(radToDeg(degToRad(90))).toBeCloseTo(90);
    expect(roundTo(1.23456, 2)).toBe(1.23);
  });

  it('predicados numéricos', () => {
    expect(isFiniteNumber(1)).toBe(true);
    expect(isFiniteNumber(Number.NaN)).toBe(false);
    expect(isPositiveInteger(3)).toBe(true);
    expect(isPositiveInteger(0)).toBe(false);
    expect(isPositiveInteger(1.5)).toBe(false);
    expect(isNearlyInteger(240.0000000001)).toBe(true);
    expect(isNearlyInteger(240.3)).toBe(false);
    expect(approxEqual(1, 1 + 1e-9)).toBe(true);
  });

  it('distância circular e seno periódico', () => {
    expect(circularDistance(0.95, 0.05)).toBeCloseTo(0.1);
    expect(periodicSine(0, 3)).toBeCloseTo(periodicSine(1, 3), 10);
  });
});

describe('PeriodicNoise', () => {
  it('é periódico com período 1 e determinístico', () => {
    const a = new PeriodicNoise(42, 6);
    const b = new PeriodicNoise(42, 6);
    for (const t of [0, 0.1, 0.33, 0.5, 0.77]) {
      expect(a.sample(t)).toBeCloseTo(a.sample(t + 1), 12);
      expect(a.sample(t)).toBe(b.sample(t));
    }
    expect(a.sample(0)).toBeCloseTo(a.sample(1 - 1e-9), 6);
    const c = new PeriodicNoise(43, 6);
    expect([0.1, 0.3, 0.6].some((t) => c.sample(t) !== a.sample(t))).toBe(true);
  });
});

describe('PerformanceMonitor', () => {
  it('calcula média, mínimo e máximo na janela de 60 frames', () => {
    const monitor = new PerformanceMonitor(60);
    let t = 0;
    monitor.recordFrame(t);
    for (let i = 0; i < 120; i++) {
      t += i % 2 === 0 ? 10 : 30;
      monitor.recordFrame(t);
    }
    const s = monitor.getSnapshot();
    expect(s.sampleCount).toBe(60);
    expect(s.fps).toBeCloseTo(50, 5);
    expect(s.maxFps).toBeCloseTo(100, 5);
    expect(s.minFps).toBeCloseTo(1000 / 30, 5);
    expect(s.level).toBe('good');
  });

  it('classifica níveis e recomenda ajustes', () => {
    const monitor = new PerformanceMonitor(10);
    for (let i = 0; i <= 10; i++) monitor.recordFrame(i * 60);
    expect(monitor.getSnapshot().level).toBe('critical');
    const tips = getPerformanceRecommendations(
      {
        marbleCount: 200,
        shadowsEnabled: true,
        trackSegments: 400,
        shadowResolution: 2048,
        pixelRatio: 2,
      },
      'critical',
    );
    expect(tips.length).toBeGreaterThanOrEqual(5);
    expect(tips[0]).toContain('150');
  });
});

describe('History', () => {
  it('desfaz e refaz com limite de 50 passos', () => {
    const history = new History<number>(0, 50);
    for (let i = 1; i <= 60; i++) history.push(i);
    expect(history.undoDepth).toBe(50);
    expect(history.undo()).toBe(59);
    expect(history.redo()).toBe(60);
    for (let i = 0; i < 50; i++) history.undo();
    expect(history.present).toBe(10);
    expect(history.undo()).toBeNull();
  });

  it('push após undo descarta o refazer e ignora estados iguais', () => {
    const history = new History<string>('a');
    history.push('b');
    history.undo();
    expect(history.canRedo).toBe(true);
    history.push('c');
    expect(history.canRedo).toBe(false);
    expect(history.push('c')).toBe(false);
  });
});

describe('debounce', () => {
  it('agrupa chamadas e permite flush', () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const d = debounce(fn, 100);
    d(1);
    d(2);
    expect(d.pending).toBe(true);
    vi.advanceTimersByTime(99);
    expect(fn).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(fn).toHaveBeenCalledWith(2);
    d(3);
    d.flush();
    expect(fn).toHaveBeenLastCalledWith(3);
    d(4);
    d.cancel();
    vi.advanceTimersByTime(200);
    expect(fn).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });
});
