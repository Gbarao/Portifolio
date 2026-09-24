import type { CameraMode, CameraSettings } from '../presets/PresetSchema';
import type { CameraRig, CameraRigContext } from './CameraRig';
import { FixedCameraRig } from './FixedCameraRig';
import { FollowCameraRig } from './FollowCameraRig';
import { OrbitCameraRig } from './OrbitCameraRig';
import { RailCameraRig } from './RailCameraRig';
import { TopViewCameraRig } from './TopViewCameraRig';

export const CAMERA_MODE_LABELS: Record<CameraMode, string> = {
  fixed: 'Fixa',
  orbit: 'Órbita',
  follow: 'Acompanhar bolinha',
  rail: 'Câmera na pista',
  topView: 'Visão superior',
};

/** Valores sugeridos ao trocar de modo pela interface. */
export const CAMERA_MODE_DEFAULTS: Record<CameraMode, Partial<CameraSettings>> = {
  fixed: { distance: 14, height: 3, tilt: 0 },
  orbit: { distance: 14, height: 4, tilt: 0 },
  follow: { distance: 4, height: 1.6, offsetLateral: 0, smoothing: 0.5, tilt: 0 },
  rail: { height: 0.9, offsetLateral: 0, smoothing: 0.4, tilt: 0 },
  topView: { distance: 16, tilt: 0 },
};

/** Modos cuja pose varia no tempo (exigem ciclos inteiros). */
export function isAnimatedCameraMode(mode: CameraMode): boolean {
  return mode === 'orbit' || mode === 'rail' || mode === 'follow';
}

export function createCameraRig(context: CameraRigContext): CameraRig {
  switch (context.settings.mode) {
    case 'fixed':
      return new FixedCameraRig(context);
    case 'orbit':
      return new OrbitCameraRig(context);
    case 'follow':
      return new FollowCameraRig(context);
    case 'rail':
      return new RailCameraRig(context);
    case 'topView':
      return new TopViewCameraRig(context);
  }
}
