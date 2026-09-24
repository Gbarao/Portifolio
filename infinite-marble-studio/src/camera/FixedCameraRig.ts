import { Vector3 } from 'three';
import { BaseCameraRig, type CameraPose } from './CameraRig';

/** Câmera parada. Com autoFrame, mantém a direção configurada e ajusta a distância. */
export class FixedCameraRig extends BaseCameraRig {
  readonly mode = 'fixed' as const;
  private readonly direction = new Vector3();

  protected evaluatePose(_animationTime: number, out: CameraPose): void {
    const s = this.settings;
    out.target.set(s.target.x, s.target.y, s.target.z);
    out.position.set(s.position.x, s.position.y, s.position.z);
    out.up.set(0, 1, 0);
    if (s.autoFrame) {
      this.direction.subVectors(out.position, out.target);
      if (this.direction.lengthSq() < 1e-8) this.direction.set(0, 0.25, 1);
      this.direction.normalize();
      out.position.copy(out.target).addScaledVector(this.direction, this.fitDistance());
    }
  }
}
