import { describe, expect, it } from 'vitest';
import {
  CAMERA_MODE_DEFAULTS,
  createCameraRig,
  isAnimatedCameraMode,
} from '../camera/CameraFactory';
import { computeFitDistance, createCameraPose } from '../camera/CameraRig';
import { MarbleKinematics } from '../marbles/MarbleKinematics';
import { PathModel } from '../path/PathModel';
import { createDefaultProject } from '../presets/DefaultPresets';
import type { CameraMode } from '../presets/PresetSchema';
import { END_EPSILON, expectAllFinite } from './helpers';

const MODES: CameraMode[] = ['fixed', 'orbit', 'follow', 'rail', 'topView'];

function rigFor(
  mode: CameraMode,
  extra: Partial<ReturnType<typeof createDefaultProject>['camera']> = {},
) {
  const project = createDefaultProject();
  Object.assign(project.camera, CAMERA_MODE_DEFAULTS[mode], { mode }, extra);
  const path = new PathModel(project.path);
  const kinematics = new MarbleKinematics(path, project.marbles, project.track, project.seed);
  return createCameraRig({
    path,
    kinematics,
    marbles: project.marbles,
    settings: project.camera,
    aspect: 1080 / 1920,
    seed: project.seed,
  });
}

describe('Enquadramento automático', () => {
  it('retrato (9:16) exige mais distância que paisagem (16:9)', () => {
    const portrait = computeFitDistance(5, 50, 9 / 16, 0.1);
    const landscape = computeFitDistance(5, 50, 16 / 9, 0.1);
    expect(portrait).toBeGreaterThan(landscape);
    expect(landscape).toBeCloseTo((5 * 1.1) / Math.sin((50 * Math.PI) / 360), 6);
  });
});

describe.each(MODES)('Câmera %s', (mode) => {
  it('produz pose finita', () => {
    const rig = rigFor(mode);
    expect(rig.mode).toBe(mode);
    const pose = createCameraPose();
    for (let i = 0; i < 50; i++) {
      rig.evaluate(i / 50, pose);
      expectAllFinite([...pose.position.toArray(), ...pose.target.toArray(), ...pose.up.toArray()]);
      expect(pose.position.distanceTo(pose.target)).toBeGreaterThan(0.01);
    }
  });

  it('retorna exatamente ao estado inicial no fim do loop', () => {
    for (const cycleCount of [1, 2]) {
      const rig = rigFor(mode, { cycleCount, swayAmount: 0.5 });
      const a = createCameraPose();
      const b = createCameraPose();
      rig.evaluate(0, a);
      rig.evaluate(1 - END_EPSILON, b);
      expect(a.position.distanceTo(b.position)).toBeLessThan(0.001);
      expect(a.target.distanceTo(b.target)).toBeLessThan(0.001);
      expect(a.up.distanceTo(b.up)).toBeLessThan(0.001);
      expect(a.fov).toBe(b.fov);
    }
  });

  it('é uma função pura do tempo (mesma entrada, mesma saída)', () => {
    const rig = rigFor(mode);
    const a = createCameraPose();
    const b = createCameraPose();
    rig.evaluate(0.42, a);
    rig.evaluate(0.9, b);
    rig.evaluate(0.42, b);
    expect(b.position.toArray()).toEqual(a.position.toArray());
  });
});

describe('Comportamentos específicos', () => {
  it('órbita percorre um círculo ao redor do alvo', () => {
    const rig = rigFor('orbit', { autoFrame: false, distance: 10, height: 2 });
    const pose = createCameraPose();
    rig.evaluate(0.25, pose);
    expect(Math.hypot(pose.position.x, pose.position.z)).toBeCloseTo(10, 6);
    expect(pose.position.y).toBeCloseTo(2, 6);
  });

  it('visão superior olha para baixo com up = −Z', () => {
    const rig = rigFor('topView', { autoFrame: false, distance: 20 });
    const pose = createCameraPose();
    rig.evaluate(0.5, pose);
    expect(pose.position.y).toBeCloseTo(20, 6);
    expect(pose.up.toArray()).toEqual([0, 0, -1]);
  });

  it('modos animados exigem ciclos inteiros', () => {
    expect(isAnimatedCameraMode('orbit')).toBe(true);
    expect(isAnimatedCameraMode('fixed')).toBe(false);
  });
});
