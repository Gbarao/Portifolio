import { Mesh, MeshPhysicalMaterial, SphereGeometry } from 'three';
import type { SqueezeToolState } from '../deformation/SqueezeDeformer';
import type { PressureSettings, ToolFinishId } from '../SatisfyingSettings';
import type { PressureTool } from './PressureTool';

const FINISHES: Record<
  ToolFinishId,
  { metalness: number; roughness: number; clearcoat: number; transmission: number }
> = {
  chrome: { metalness: 1, roughness: 0.08, clearcoat: 0, transmission: 0 },
  satinMetal: { metalness: 1, roughness: 0.36, clearcoat: 0, transmission: 0 },
  ceramic: { metalness: 0, roughness: 0.25, clearcoat: 1, transmission: 0 },
  glass: { metalness: 0, roughness: 0.04, clearcoat: 1, transmission: 1 },
};

/** Esfera rígida que pressiona o objeto. */
export class SpherePressureTool implements PressureTool {
  readonly id = 'sphere' as const;
  readonly object: Mesh<SphereGeometry, MeshPhysicalMaterial>;

  constructor(settings: PressureSettings) {
    const geometry = new SphereGeometry(1, 96, 64);
    const material = new MeshPhysicalMaterial();
    material.name = 'pressure-tool';
    this.object = new Mesh(geometry, material);
    this.object.name = 'pressure-tool-sphere';
    this.object.castShadow = true;
    this.object.receiveShadow = true;
    this.configure(settings);
  }

  configure(settings: PressureSettings): void {
    const finish = FINISHES[settings.toolFinish];
    const material = this.object.material;
    material.color.set(settings.toolColor);
    material.metalness = finish.metalness;
    material.roughness = finish.roughness;
    material.clearcoat = finish.clearcoat;
    material.transmission = finish.transmission;
    material.thickness = finish.transmission > 0 ? 2 * settings.toolRadius : 0;
    material.ior = 1.5;
    this.object.scale.setScalar(settings.toolRadius);
  }

  update(state: SqueezeToolState): void {
    this.object.position.set(state.x, state.y, state.z);
    this.object.scale.setScalar(state.radius);
  }

  dispose(): void {
    this.object.removeFromParent();
    this.object.geometry.dispose();
    this.object.material.dispose();
  }
}
