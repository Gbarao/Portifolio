import {
  Color,
  InstancedBufferAttribute,
  InstancedMesh,
  Matrix4,
  MeshPhysicalMaterial,
  Quaternion,
  SphereGeometry,
  Vector3,
  type Object3D,
  type Sphere,
} from 'three';
import { TAU } from '../core/MathUtils';
import type { Disposable } from '../core/Disposable';
import { SeededRandom } from '../core/SeededRandom';

export interface DecorationPlacement {
  x: number;
  z: number;
  radius: number;
  /** Índice na lista de cores das bolinhas. */
  colorIndex: number;
}

/**
 * Cúpulas espalhadas no chão ao redor do trajeto, fora da área ocupada por ele.
 * Determinístico: depende só da seed e do bounding sphere do trajeto.
 */
export function computeDecorationLayout(
  seed: number,
  bounds: Pick<Sphere, 'center' | 'radius'>,
  count = 6,
): DecorationPlacement[] {
  const rng = SeededRandom.derived(seed, 'decorations');
  const base = rng.nextFloat(0, TAU);
  const scale = bounds.radius / 5;
  const placements: DecorationPlacement[] = [];
  for (let i = 0; i < count; i++) {
    const angle = base + (TAU * i) / count + rng.nextFloat(-0.35, 0.35);
    const distance = bounds.radius * rng.nextFloat(0.95, 1.3);
    placements.push({
      x: bounds.center.x + Math.cos(angle) * distance,
      z: bounds.center.z + Math.sin(angle) * distance,
      radius: rng.nextFloat(0.3, 0.95) * scale,
      colorIndex: i,
    });
  }
  return placements;
}

/** Cúpulas (meias-esferas) brilhantes num único InstancedMesh. */
export class DecorationManager implements Disposable {
  private readonly geometry = new SphereGeometry(1, 40, 20, 0, TAU, 0, Math.PI / 2);
  private readonly material = new MeshPhysicalMaterial({
    color: 0xffffff,
    roughness: 0.28,
    metalness: 0,
    clearcoat: 1,
    clearcoatRoughness: 0.08,
  });
  private mesh: InstancedMesh | null = null;

  constructor(private readonly parent: Object3D) {}

  rebuild(
    seed: number,
    bounds: Pick<Sphere, 'center' | 'radius'>,
    groundY: number,
    colors: readonly number[],
    visible: boolean,
  ): void {
    this.clear();
    if (!visible || colors.length === 0) return;
    const placements = computeDecorationLayout(seed, bounds);
    const mesh = new InstancedMesh(this.geometry, this.material, placements.length);
    mesh.instanceColor = new InstancedBufferAttribute(new Float32Array(placements.length * 3), 3);
    const matrix = new Matrix4();
    const rotation = new Quaternion();
    const position = new Vector3();
    const scale = new Vector3();
    const color = new Color();
    placements.forEach((p, i) => {
      position.set(p.x, groundY, p.z);
      scale.setScalar(p.radius);
      mesh.setMatrixAt(i, matrix.compose(position, rotation, scale));
      mesh.setColorAt(i, color.setHex(colors[p.colorIndex % colors.length] as number));
    });
    mesh.name = 'decorations';
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.computeBoundingSphere();
    this.mesh = mesh;
    this.parent.add(mesh);
  }

  private clear(): void {
    if (!this.mesh) return;
    this.mesh.removeFromParent();
    this.mesh.dispose();
    this.mesh = null;
  }

  dispose(): void {
    this.clear();
    this.geometry.dispose();
    this.material.dispose();
  }
}
