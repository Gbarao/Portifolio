import {
  CylinderGeometry,
  InstancedMesh,
  Matrix4,
  MeshStandardMaterial,
  Quaternion,
  Vector3,
  type Object3D,
} from 'three';
import type { Disposable } from '../core/Disposable';
import type { PathModel } from '../path/PathModel';
import type { TrackSettings } from '../presets/PresetSchema';
import { trackOuterRadius } from './TrackBuilder';

export interface SupportPlacement {
  x: number;
  z: number;
  /** Altura do topo da haste (logo abaixo do trilho). */
  top: number;
  /** Altura da base (chão). */
  bottom: number;
}

export interface SupportLayout {
  placements: SupportPlacement[];
  poleRadius: number;
}

/**
 * Posições das hastes: amostras regulares ao longo do trilho, apenas onde o trilho está de pé
 * (frame "para cima" vertical) e sem outro trecho do trilho no caminho até o chão.
 * Determinístico: depende só do trajeto e das configurações.
 */
export function computeSupportLayout(
  path: PathModel,
  track: Pick<TrackSettings, 'style' | 'radius' | 'railRadius'>,
  groundY: number,
  spacing = 2.4,
): SupportLayout {
  const outer = trackOuterRadius(track);
  const poleRadius = Math.min(0.08, Math.max(0.03, outer * 0.2));
  const samples: Vector3[] = [];
  const sampleCount = 720;
  for (let i = 0; i < sampleCount; i++)
    samples.push(path.getPointAt(i / sampleCount, new Vector3()));

  const placements: SupportPlacement[] = [];
  const count = Math.max(3, Math.floor(path.length / spacing));
  const point = new Vector3();
  const tangent = new Vector3();
  const up = new Vector3();
  const side = new Vector3();
  const clearance = outer * 2 + poleRadius;
  for (let k = 0; k < count; k++) {
    const u = (k + 0.5) / count;
    path.getPointAt(u, point);
    path.getFrameAt(u, tangent, up, side);
    if (up.y < 0.6) continue;
    const top = point.y - outer;
    if (top - groundY < 0.3) continue;
    const blocked = samples.some(
      (q) =>
        q.y < top - outer && q.y > groundY && Math.hypot(q.x - point.x, q.z - point.z) < clearance,
    );
    if (blocked) continue;
    placements.push({ x: point.x, z: point.z, top, bottom: groundY });
  }
  return { placements, poleRadius };
}

/** Hastes (cilindros) + pés (discos) em dois InstancedMesh: 2 draw calls no total. */
export class SupportManager implements Disposable {
  private readonly material = new MeshStandardMaterial({ metalness: 0.55, roughness: 0.35 });
  private readonly poleGeometry = new CylinderGeometry(1, 1, 1, 14);
  private readonly footGeometry = new CylinderGeometry(1, 1, 1, 28);
  private poles: InstancedMesh | null = null;
  private feet: InstancedMesh | null = null;

  constructor(private readonly parent: Object3D) {}

  rebuild(path: PathModel, track: TrackSettings, groundY: number, visible: boolean): void {
    this.clear();
    this.material.color.setHex(track.supportColor);
    if (!visible) return;
    const { placements, poleRadius } = computeSupportLayout(path, track, groundY);
    if (placements.length === 0) return;
    this.poles = new InstancedMesh(this.poleGeometry, this.material, placements.length);
    this.feet = new InstancedMesh(this.footGeometry, this.material, placements.length);
    const matrix = new Matrix4();
    const position = new Vector3();
    const scale = new Vector3();
    const rotation = new Quaternion();
    placements.forEach((p, i) => {
      const height = p.top - p.bottom;
      position.set(p.x, p.bottom + height / 2, p.z);
      scale.set(poleRadius, height, poleRadius);
      this.poles?.setMatrixAt(i, matrix.compose(position, rotation, scale));
      position.set(p.x, p.bottom + 0.02, p.z);
      scale.set(poleRadius * 3.2, 0.04, poleRadius * 3.2);
      this.feet?.setMatrixAt(i, matrix.compose(position, rotation, scale));
    });
    for (const mesh of [this.poles, this.feet]) {
      mesh.name = mesh === this.poles ? 'support-poles' : 'support-feet';
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      mesh.computeBoundingSphere();
      this.parent.add(mesh);
    }
  }

  get count(): number {
    return this.poles?.count ?? 0;
  }

  private clear(): void {
    for (const mesh of [this.poles, this.feet]) {
      if (!mesh) continue;
      mesh.removeFromParent();
      mesh.dispose();
    }
    this.poles = null;
    this.feet = null;
  }

  dispose(): void {
    this.clear();
    this.poleGeometry.dispose();
    this.footGeometry.dispose();
    this.material.dispose();
  }
}
