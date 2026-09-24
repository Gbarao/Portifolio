import { TAU } from '../core/MathUtils';
import { BaseCameraRig, type CameraPose } from './CameraRig';

/** Órbita ao redor do alvo com número inteiro de voltas por ciclo. */
export class OrbitCameraRig extends BaseCameraRig {
  readonly mode = 'orbit' as const;

  protected evaluatePose(animationTime: number, out: CameraPose): void {
    const s = this.settings;
    const baseAzimuth = Math.atan2(s.position.x - s.target.x, s.position.z - s.target.z);
    let radius = s.distance;
    if (s.autoFrame) {
      const fit = this.fitDistance();
      radius = Math.sqrt(Math.max(fit * fit - s.height * s.height, (fit * 0.3) ** 2));
    }
    const angle = baseAzimuth + TAU * s.cycleCount * animationTime;
    out.target.set(s.target.x, s.target.y, s.target.z);
    out.position.set(
      s.target.x + radius * Math.sin(angle),
      s.target.y + s.height,
      s.target.z + radius * Math.cos(angle),
    );
    out.up.set(0, 1, 0);
  }
}
