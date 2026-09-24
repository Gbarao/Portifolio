import { Vector3 } from 'three';
import { degToRad } from '../core/MathUtils';
import { PeriodicNoise } from '../core/PeriodicNoise';
import { deriveSeed } from '../core/SeededRandom';
import type { MarbleKinematics } from '../marbles/MarbleKinematics';
import type { PathModel } from '../path/PathModel';
import type { CameraMode, CameraSettings, MarbleSettings } from '../presets/PresetSchema';

/** Estado completo da câmera em um instante (dados puros). */
export interface CameraPose {
  position: Vector3;
  target: Vector3;
  up: Vector3;
  fov: number;
  /** Inclinação adicional (radianos) aplicada após o lookAt. */
  tilt: number;
}

export function createCameraPose(): CameraPose {
  return {
    position: new Vector3(),
    target: new Vector3(),
    up: new Vector3(0, 1, 0),
    fov: 50,
    tilt: 0,
  };
}

export interface CameraRigContext {
  path: PathModel;
  kinematics: MarbleKinematics;
  marbles: MarbleSettings;
  settings: CameraSettings;
  /** Proporção da resolução de saída (largura / altura). */
  aspect: number;
  seed: number;
}

export interface CameraRig {
  readonly mode: CameraMode;
  /** Calcula a pose para o tempo de animação t ∈ [0, 1). Função pura de t. */
  evaluate(animationTime: number, out: CameraPose): void;
}

/**
 * Distância mínima para enquadrar uma esfera de raio `radius`, considerando o menor FOV
 * (vertical ou horizontal derivado da proporção) e uma margem relativa.
 */
export function computeFitDistance(
  radius: number,
  fovDeg: number,
  aspect: number,
  margin: number,
): number {
  const vFov = degToRad(fovDeg);
  const hFov = 2 * Math.atan(Math.tan(vFov / 2) * aspect);
  const limiting = Math.min(vFov, hFov);
  return (radius * (1 + margin)) / Math.sin(limiting / 2);
}

/** Amostra frames suavizados por janela simétrica em u (determinístico e periódico). */
export class SmoothedFrameSampler {
  private readonly point = new Vector3();
  private readonly tangent = new Vector3();
  private readonly up = new Vector3();
  private readonly side = new Vector3();

  constructor(
    private readonly path: PathModel,
    private readonly sampleCount = 9,
  ) {}

  sample(
    u: number,
    window: number,
    outPosition: Vector3,
    outTangent: Vector3,
    outUp: Vector3,
    outSide: Vector3,
  ): void {
    const k = window > 0 ? this.sampleCount : 1;
    outPosition.set(0, 0, 0);
    outTangent.set(0, 0, 0);
    outUp.set(0, 0, 0);
    for (let j = 0; j < k; j++) {
      const offset = k === 1 ? 0 : window * ((2 * j) / (k - 1) - 1);
      const uu = this.path.wrapU(u + offset);
      this.path.getPointAt(uu, this.point);
      this.path.getFrameAt(uu, this.tangent, this.up, this.side);
      outPosition.add(this.point);
      outTangent.add(this.tangent);
      outUp.add(this.up);
    }
    outPosition.multiplyScalar(1 / k);
    outTangent.normalize();
    outUp.addScaledVector(outTangent, -outUp.dot(outTangent)).normalize();
    outSide.crossVectors(outUp, outTangent).normalize();
  }
}

/** Base comum: snapshot das configurações, FOV, inclinação e balanço periódico opcional. */
export abstract class BaseCameraRig implements CameraRig {
  abstract readonly mode: CameraMode;
  protected readonly settings: CameraSettings;
  protected readonly marbles: MarbleSettings;
  private readonly swayNoise: [PeriodicNoise, PeriodicNoise, PeriodicNoise];

  constructor(protected readonly context: CameraRigContext) {
    this.settings = structuredClone(context.settings);
    this.marbles = structuredClone(context.marbles);
    this.swayNoise = [
      new PeriodicNoise(deriveSeed(context.seed, 'swayX'), 6),
      new PeriodicNoise(deriveSeed(context.seed, 'swayY'), 6),
      new PeriodicNoise(deriveSeed(context.seed, 'swayZ'), 6),
    ];
  }

  evaluate(animationTime: number, out: CameraPose): void {
    this.evaluatePose(animationTime, out);
    const sway = this.settings.swayAmount;
    if (sway > 0) {
      const [nx, ny, nz] = this.swayNoise;
      out.position.x += nx.sample(animationTime) * sway * 0.6;
      out.position.y += ny.sample(animationTime) * sway * 0.6;
      out.position.z += nz.sample(animationTime) * sway * 0.6;
    }
    out.fov = this.settings.fov;
    out.tilt = degToRad(this.settings.tilt);
  }

  protected abstract evaluatePose(animationTime: number, out: CameraPose): void;

  /** Distância de enquadramento automático do trajeto a partir do alvo configurado. */
  protected fitDistance(): number {
    const { path, aspect } = this.context;
    const s = this.settings;
    const sphere = path.boundingSphere;
    const offset = Math.hypot(
      sphere.center.x - s.target.x,
      sphere.center.y - s.target.y,
      sphere.center.z - s.target.z,
    );
    return computeFitDistance(sphere.radius + offset, s.fov, aspect, s.framingMargin);
  }
}
