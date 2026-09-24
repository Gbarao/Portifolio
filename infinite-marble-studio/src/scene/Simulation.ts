import { createCameraRig } from '../camera/CameraFactory';
import type { CameraPose, CameraRig } from '../camera/CameraRig';
import { computeAnimationTime } from '../core/LoopClock';
import { MarbleKinematics } from '../marbles/MarbleKinematics';
import { PathModel } from '../path/PathModel';
import { validatePathPoints } from '../path/PathValidator';
import type { ScenePreset } from '../presets/PresetSchema';

/**
 * Modelo matemático da cena (sem WebGL): trajeto, cinemática das bolinhas e câmera.
 * Usado igualmente pelo preview, pelo export e pelos testes — garantia de consistência.
 */
export class Simulation {
  path!: PathModel;
  kinematics!: MarbleKinematics;
  cameraRig!: CameraRig;
  /** Última validação do trajeto informado (pode ser inválido; o modelo mantém o último válido). */
  pathValid = true;
  private loopCycles = 1;

  constructor(project: ScenePreset) {
    this.rebuildAll(project);
  }

  rebuildAll(project: ScenePreset): void {
    this.rebuildPath(project);
  }

  /** Reconstrói trajeto, cinemática e câmera. Retorna false se o trajeto for inválido. */
  rebuildPath(project: ScenePreset): boolean {
    const validation = validatePathPoints(project.path.points, project.path.closed);
    this.pathValid = validation.valid;
    if (validation.valid || !this.path) {
      this.path = new PathModel(project.path, { bankAngleDeg: project.track.bankAngle });
    }
    this.rebuildMarbles(project);
    return validation.valid;
  }

  /** Reconstrói cinemática (quantidade, cores, fases) e câmera. */
  rebuildMarbles(project: ScenePreset): void {
    this.kinematics = new MarbleKinematics(this.path, project.marbles, project.track, project.seed);
    this.rebuildCamera(project);
  }

  rebuildCamera(project: ScenePreset): void {
    this.loopCycles = project.loop.cycleCount;
    this.cameraRig = createCameraRig({
      path: this.path,
      kinematics: this.kinematics,
      marbles: project.marbles,
      settings: project.camera,
      aspect: project.output.width / project.output.height,
      seed: project.seed,
    });
  }

  updateLoop(project: ScenePreset): void {
    this.loopCycles = project.loop.cycleCount;
  }

  animationTime(normalizedTime: number): number {
    return computeAnimationTime(normalizedTime, this.loopCycles);
  }

  evaluateCamera(animationTime: number, out: CameraPose): void {
    this.cameraRig.evaluate(animationTime, out);
  }
}
