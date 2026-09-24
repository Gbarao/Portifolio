import { describe, expect, it } from 'vitest';
import {
  LoopClock,
  computeAnimationTime,
  computeTotalFrames,
  frameToNormalizedTime,
} from '../core/LoopClock';

function fakeClock(durationSeconds = 8, fps = 30) {
  let now = 1000;
  const clock = new LoopClock({ durationSeconds, fps, now: () => now });
  return {
    clock,
    advance(ms: number) {
      now += ms;
    },
  };
}

describe('LoopClock', () => {
  it('totalFrames = durationSeconds × fps', () => {
    expect(computeTotalFrames(8, 30)).toBe(240);
    expect(computeTotalFrames(8, 60)).toBe(480);
    expect(new LoopClock({ durationSeconds: 8, fps: 60 }).totalFrames).toBe(480);
  });

  it('normalizedTime sempre ∈ [0, 1) no preview', () => {
    const { clock, advance } = fakeClock();
    for (let i = 0; i < 2000; i++) {
      advance(37.3);
      const t = clock.getNormalizedTime();
      expect(t).toBeGreaterThanOrEqual(0);
      expect(t).toBeLessThan(1);
    }
  });

  it('modo export usa frameIndex/totalFrames e nunca atinge 1', () => {
    const clock = new LoopClock({ durationSeconds: 8, fps: 30 });
    clock.beginExport(30);
    expect(clock.mode).toBe('export');
    const values: number[] = [];
    for (let i = 0; i < 240; i++) {
      clock.setFrameIndex(i);
      values.push(clock.getNormalizedTime());
    }
    expect(values[0]).toBe(0);
    expect(values[239]).toBeCloseTo(239 / 240, 12);
    expect(Math.max(...values)).toBeLessThan(1);
    // O frame totalFrames seria duplicado do frame 0: envolve para 0.
    clock.setFrameIndex(240);
    expect(clock.getNormalizedTime()).toBe(0);
    clock.endExport();
    expect(clock.mode).toBe('preview');
  });

  it('transição do último frame para o primeiro é suave (mesmo passo)', () => {
    const total = 240;
    const step = frameToNormalizedTime(1, total) - frameToNormalizedTime(0, total);
    const wrapStep = 1 - frameToNormalizedTime(total - 1, total) + frameToNormalizedTime(0, total);
    expect(wrapStep).toBeCloseTo(step, 12);
  });

  it('preview e export retornam valores idênticos para o mesmo frame', () => {
    for (const fps of [30, 60]) {
      const exporter = new LoopClock({ durationSeconds: 8, fps });
      exporter.beginExport(fps);
      for (let k = 0; k < 8 * fps; k += 7) {
        const { clock: preview, advance } = fakeClock(8, fps);
        advance((k / fps) * 1000 + 0.4);
        exporter.setFrameIndex(k);
        expect(preview.getFrameIndex()).toBe(k);
        // Igualdade exata (bit a bit): mesma função de conversão.
        expect(preview.getNormalizedTime()).toBe(exporter.getNormalizedTime());
      }
    }
  });

  it('pause congela, play retoma sem salto e reset volta ao início', () => {
    const { clock, advance } = fakeClock();
    advance(1000);
    clock.pause();
    const paused = clock.getElapsedSeconds();
    advance(5000);
    expect(clock.getElapsedSeconds()).toBeCloseTo(paused, 9);
    clock.play();
    advance(500);
    expect(clock.getElapsedSeconds()).toBeCloseTo(paused + 0.5, 9);
    clock.reset();
    expect(clock.getElapsedSeconds()).toBe(0);
    expect(clock.toggle()).toBe(false);
    expect(clock.isPlaying).toBe(false);
  });

  it('velocidade de preview entre 0.25× e 2× sem acumular delta', () => {
    const { clock, advance } = fakeClock();
    clock.setSpeed(2);
    advance(1000);
    expect(clock.getElapsedSeconds()).toBeCloseTo(2, 9);
    clock.setSpeed(10);
    expect(clock.previewSpeed).toBe(2);
    clock.setSpeed(0.01);
    expect(clock.previewSpeed).toBe(0.25);
  });

  it('seek e configure preservam a posição normalizada', () => {
    const { clock } = fakeClock(8, 30);
    clock.pause();
    clock.seekNormalized(0.5);
    expect(clock.getNormalizedTime()).toBeCloseTo(0.5, 9);
    clock.configure(16, 60);
    expect(clock.getNormalizedTime()).toBeCloseTo(0.5, 9);
    expect(clock.totalFrames).toBe(960);
    clock.snapToFrames = false;
    clock.seekNormalized(0.123456);
    expect(clock.getNormalizedTime()).toBeCloseTo(0.123456, 9);
  });

  it('computeAnimationTime repete a coreografia um número inteiro de vezes', () => {
    expect(computeAnimationTime(0.5, 2)).toBeCloseTo(0, 12);
    expect(computeAnimationTime(0.25, 2)).toBeCloseTo(0.5, 12);
    expect(computeAnimationTime(1 - 1e-9, 3)).toBeGreaterThan(0.99);
  });
});
