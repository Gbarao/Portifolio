import { BaseCameraRig, type CameraPose } from './CameraRig';

/** Visão superior em perspectiva: altitude = distance (ou automática); zoom = FOV. */
export class TopViewCameraRig extends BaseCameraRig {
  readonly mode = 'topView' as const;

  protected evaluatePose(_animationTime: number, out: CameraPose): void {
    const s = this.settings;
    const altitude = s.autoFrame ? this.fitDistance() : s.distance;
    out.target.set(s.target.x, s.target.y, s.target.z);
    out.position.set(s.target.x, s.target.y + altitude, s.target.z);
    // Olhando para baixo, "para cima" na tela aponta para -Z (evita degenerar o lookAt).
    out.up.set(0, 0, -1);
  }
}
