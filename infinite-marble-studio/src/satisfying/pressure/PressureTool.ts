import type { Object3D } from 'three';
import type { Disposable } from '../../core/Disposable';
import type { SqueezeToolState } from '../deformation/SqueezeDeformer';
import type { PressureSettings, PressureToolId } from '../SatisfyingSettings';

/**
 * Ferramenta de pressão. Implementada no MVP: esfera. Arquitetura prevista:
 * Sphere, Plate, Cylinder, Roller, Wedge, Procedural Finger, MultiPoint.
 */
export interface PressureTool extends Disposable {
  readonly id: PressureToolId;
  readonly object: Object3D;
  /** Posiciona a ferramenta para o estado do frame (sem alocação). */
  update(state: SqueezeToolState): void;
  /** Atualiza aparência/dimensões a partir das configurações. */
  configure(settings: PressureSettings): void;
}
