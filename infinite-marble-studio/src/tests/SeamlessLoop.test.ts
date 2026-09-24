import { describe, expect, it } from 'vitest';
import { CAMERA_MODE_DEFAULTS } from '../camera/CameraFactory';
import { computeTotalFrames, frameToNormalizedTime } from '../core/LoopClock';
import { BUILT_IN_PRESETS, createDefaultProject } from '../presets/DefaultPresets';
import type { CameraMode, ScenePreset } from '../presets/PresetSchema';
import {
  SceneEvaluator,
  captureSceneState,
  type SceneStateSnapshot,
} from '../scene/SceneStateCapture';
import { END_EPSILON, expectAllFinite, maxAbsDiff, maxQuaternionAngle } from './helpers';

function expectSameState(a: SceneStateSnapshot, b: SceneStateSnapshot): void {
  expect(maxAbsDiff(a.marblePositions, b.marblePositions)).toBeLessThan(0.001);
  expect(maxQuaternionAngle(a.marbleQuaternions, b.marbleQuaternions)).toBeLessThan(0.01);
  expect(maxAbsDiff(a.marbleScales, b.marbleScales)).toBeLessThan(0.001);
  expect(maxAbsDiff(a.marbleColors, b.marbleColors)).toBeLessThanOrEqual(2);
  expect(maxAbsDiff(a.cameraPosition, b.cameraPosition)).toBeLessThan(0.001);
  expect(maxAbsDiff(a.cameraTarget, b.cameraTarget)).toBeLessThan(0.001);
  expect(maxAbsDiff(a.cameraUp, b.cameraUp)).toBeLessThan(0.001);
  expect(Math.abs(a.cameraFov - b.cameraFov)).toBeLessThan(0.001);
  expect(Math.abs(a.lights.main - b.lights.main)).toBeLessThan(0.01);
  expect(Math.abs(a.lights.rim - b.lights.rim)).toBeLessThan(0.01);
  expect(Math.abs(a.lights.fill - b.lights.fill)).toBeLessThan(0.01);
  expect(Math.abs(a.lights.ambient - b.lights.ambient)).toBeLessThan(0.01);
}

/** Projeto com todas as animações periódicas ligadas. */
function animatedProject(mode: CameraMode): ScenePreset {
  const project = createDefaultProject();
  Object.assign(project.camera, CAMERA_MODE_DEFAULTS[mode], {
    mode,
    cycleCount: 2,
    swayAmount: 0.4,
  });
  Object.assign(project.marbles, {
    cycleCount: 2,
    hueShiftCycles: 1,
    pulseAmount: 0.15,
    pulseCycles: 3,
    scaleVariation: 0.08,
    pattern: 'striped',
  });
  Object.assign(project.lighting, { pulseAmount: 0.3, pulseCycles: 2 });
  project.loop.cycleCount = 2;
  return project;
}

describe('Loop perfeito: estado em t=0 igual a t=1−ε', () => {
  it('exemplo da especificação (t=0 vs t=0.9999…)', () => {
    const project = createDefaultProject();
    const state0 = captureSceneState(project, 0);
    const state1 = captureSceneState(project, 1 - END_EPSILON);
    expectSameState(state0, state1);
  });

  it.each(['fixed', 'orbit', 'follow', 'rail', 'topView'] as CameraMode[])(
    'com todas as animações ligadas e câmera %s',
    (mode) => {
      const evaluator = new SceneEvaluator(animatedProject(mode));
      const a = evaluator.capture(0);
      const b = evaluator.capture(1 - END_EPSILON);
      expectSameState(a, b);
      expectAllFinite([
        ...a.marblePositions,
        ...a.marbleQuaternions,
        ...a.cameraPosition,
        ...a.cameraTarget,
      ]);
    },
  );

  it.each(BUILT_IN_PRESETS.map((p) => [p.name, p] as const))(
    'preset built-in "%s"',
    (_name, preset) => {
      const evaluator = new SceneEvaluator(preset);
      expectSameState(evaluator.capture(0), evaluator.capture(1 - END_EPSILON));
    },
  );
});

describe('Sem saltos na transição do último frame para o frame zero', () => {
  it.each(['orbit', 'follow', 'rail'] as CameraMode[])('câmera %s', (mode) => {
    const project = animatedProject(mode);
    const evaluator = new SceneEvaluator(project);
    const total = computeTotalFrames(project.loop.durationSeconds, project.output.fps);
    const first = evaluator.capture(frameToNormalizedTime(0, total));
    const second = evaluator.capture(frameToNormalizedTime(1, total));
    const last = evaluator.capture(frameToNormalizedTime(total - 1, total));
    const normalStep = maxAbsDiff(first.marblePositions, second.marblePositions);
    const wrapStep = maxAbsDiff(last.marblePositions, first.marblePositions);
    // O passo que fecha o loop tem o mesmo tamanho de um passo comum (sem "pop").
    expect(wrapStep).toBeLessThan(normalStep * 1.5 + 1e-6);
    const camStep = maxAbsDiff(first.cameraPosition, second.cameraPosition);
    const camWrap = maxAbsDiff(last.cameraPosition, first.cameraPosition);
    expect(camWrap).toBeLessThan(camStep * 1.5 + 1e-6);
  });
});

describe('Iluminação periódica', () => {
  it('intensidades repetem com período 1', () => {
    const evaluator = new SceneEvaluator(animatedProject('fixed'));
    for (const t of [0.1, 0.35, 0.8]) {
      const a = evaluator.capture(t);
      const b = evaluator.capture(t + 1 - END_EPSILON);
      expect(Math.abs(a.lights.main - b.lights.main)).toBeLessThan(0.01);
    }
    // loop.cycleCount = 2 e pulseCycles = 2: picos em t = 1/16 e vales em t = 3/16.
    const peak = evaluator.capture(1 / 16);
    const valley = evaluator.capture(3 / 16);
    expect(peak.lights.main).toBeGreaterThan(valley.lights.main + 1);
  });
});
