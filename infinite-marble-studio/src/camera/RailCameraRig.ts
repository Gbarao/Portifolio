import { Vector3 } from 'three';
import { modulo } from '../core/MathUtils';
import {
  BaseCameraRig,
  SmoothedFrameSampler,
  type CameraPose,
  type CameraRigContext,
} from './CameraRig';

/** Câmera que percorre o próprio trilho usando a mesma parametrização u das bolinhas. */
export class RailCameraRig extends BaseCameraRig {
  readonly mode = 'rail' as const;
  private readonly sampler: SmoothedFrameSampler;
  private readonly center = new Vector3();
  private readonly tangent = new Vector3();
  private readonly up = new Vector3();
  private readonly side = new Vector3();
  private readonly ahead = new Vector3();

  constructor(context: CameraRigContext) {
    super(context);
    this.sampler = new SmoothedFrameSampler(context.path);
  }

  /** u da câmera: mesmo avanço das bolinhas com offset adiantado/atrasado. */
  getU(animationTime: number): number {
    const s = this.settings;
    const m = this.marbles;
    return modulo(
      m.direction * animationTime * s.cycleCount + m.phaseInitial + s.railPhaseOffset,
      1,
    );
  }

  protected evaluatePose(animationTime: number, out: CameraPose): void {
    const s = this.settings;
    const direction = this.marbles.direction;
    const u = this.getU(animationTime);
    this.sampler.sample(u, s.smoothing * 0.05, this.center, this.tangent, this.up, this.side);
    out.position
      .copy(this.center)
      .addScaledVector(this.up, s.height)
      .addScaledVector(this.side, s.offsetLateral);

    this.context.path.getPointAt(u + direction * s.railLookAhead, this.ahead);
    out.target.copy(this.ahead).addScaledVector(this.up, s.height * 0.6);
    out.up.copy(this.up);
  }
}
