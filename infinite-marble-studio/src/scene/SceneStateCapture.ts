import { Color, Quaternion, Vector3 } from 'three';
import { createCameraPose } from '../camera/CameraRig';
import type { ScenePreset } from '../presets/PresetSchema';
import {
  createLightIntensities,
  evaluateLightIntensities,
  type LightIntensities,
} from './LightingManager';
import { Simulation } from './Simulation';

/** Estado numérico completo de um frame (sem WebGL): base dos testes de loop e determinismo. */
export interface SceneStateSnapshot {
  normalizedTime: number;
  animationTime: number;
  marblePositions: number[];
  marbleQuaternions: number[];
  marbleScales: number[];
  /** Cores em 8 bits sRGB (0–255), para comparação com tolerância RGBA. */
  marbleColors: number[];
  cameraPosition: number[];
  cameraTarget: number[];
  cameraUp: number[];
  cameraFov: number;
  cameraTilt: number;
  lights: LightIntensities;
}

export class SceneEvaluator {
  readonly simulation: Simulation;
  private readonly project: ScenePreset;

  constructor(project: ScenePreset) {
    this.project = structuredClone(project);
    this.simulation = new Simulation(this.project);
  }

  capture(normalizedTime: number): SceneStateSnapshot {
    const sim = this.simulation;
    const t = sim.animationTime(normalizedTime);
    const k = sim.kinematics;
    const position = new Vector3();
    const quaternion = new Quaternion();
    const color = new Color();
    const marblePositions: number[] = [];
    const marbleQuaternions: number[] = [];
    const marbleScales: number[] = [];
    const marbleColors: number[] = [];
    for (let i = 0; i < k.count; i++) {
      const scale = k.evaluate(i, t, position, quaternion);
      marblePositions.push(position.x, position.y, position.z);
      marbleQuaternions.push(quaternion.x, quaternion.y, quaternion.z, quaternion.w);
      marbleScales.push(scale * this.project.marbles.radius);
      k.evaluateColor(i, t, color);
      const hex = color.getHex();
      marbleColors.push((hex >> 16) & 255, (hex >> 8) & 255, hex & 255);
    }
    const pose = createCameraPose();
    sim.evaluateCamera(t, pose);
    return {
      normalizedTime,
      animationTime: t,
      marblePositions,
      marbleQuaternions,
      marbleScales,
      marbleColors,
      cameraPosition: pose.position.toArray(),
      cameraTarget: pose.target.toArray(),
      cameraUp: pose.up.toArray(),
      cameraFov: pose.fov,
      cameraTilt: pose.tilt,
      lights: evaluateLightIntensities(this.project.lighting, t, createLightIntensities()),
    };
  }
}

export function captureSceneState(
  project: ScenePreset,
  normalizedTime: number,
): SceneStateSnapshot {
  return new SceneEvaluator(project).capture(normalizedTime);
}
