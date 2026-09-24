import { Quaternion, Vector3 } from 'three';
import {
  BaseCameraRig,
  SmoothedFrameSampler,
  type CameraPose,
  type CameraRigContext,
} from './CameraRig';

/**
 * Persegue uma bolinha. A suavização é uma média em janela simétrica ao longo da curva
 * (determinística, sem acumulação entre frames).
 */
export class FollowCameraRig extends BaseCameraRig {
  readonly mode = 'follow' as const;
  private readonly sampler: SmoothedFrameSampler;
  private readonly marblePosition = new Vector3();
  private readonly marbleQuaternion = new Quaternion();
  private readonly center = new Vector3();
  private readonly tangent = new Vector3();
  private readonly up = new Vector3();
  private readonly side = new Vector3();
  private readonly smoothTarget = new Vector3();

  constructor(context: CameraRigContext) {
    super(context);
    this.sampler = new SmoothedFrameSampler(context.path);
  }

  protected evaluatePose(animationTime: number, out: CameraPose): void {
    const s = this.settings;
    const { kinematics, path } = this.context;
    const index = Math.min(Math.max(0, Math.round(s.followMarbleIndex)), kinematics.count - 1);
    const u = kinematics.getU(index, animationTime);
    kinematics.evaluate(index, animationTime, this.marblePosition, this.marbleQuaternion);

    this.sampler.sample(u, s.smoothing * 0.08, this.center, this.tangent, this.up, this.side);
    const backward = -this.marbles.direction;
    out.position
      .copy(this.center)
      .addScaledVector(this.tangent, backward * s.distance)
      .addScaledVector(this.up, s.height)
      .addScaledVector(this.side, s.offsetLateral);

    // Alvo suavizado: centro da janela deslocado pela mesma altura da bolinha.
    path.getPointAt(u, this.smoothTarget);
    this.smoothTarget.subVectors(this.marblePosition, this.smoothTarget).add(this.center);
    out.target.copy(this.marblePosition).lerp(this.smoothTarget, s.smoothing);
    out.up.copy(this.up);
  }
}
