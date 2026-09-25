import type { CanvasTexture, Group, MeshPhysicalMaterial, Object3D } from 'three';
import type { Disposable } from '../core/Disposable';
import type { PathModel } from '../path/PathModel';
import type { TrackSettings } from '../presets/PresetSchema';
import { applyTrackMaterial, createTrackBuilder, createTrackMaterial } from './TrackBuilder';
import { createWoodTexture, woodRepeatsFor } from './WoodTexture';

/** Mantém a geometria atual do trilho e descarta a anterior a cada reconstrução. */
export class TrackManager implements Disposable {
  private group: Group | null = null;
  private readonly material: MeshPhysicalMaterial;
  private wood: { seed: number; texture: CanvasTexture } | null = null;
  private pathLength = 1;

  constructor(
    private readonly parent: Object3D,
    settings: TrackSettings,
  ) {
    this.material = createTrackMaterial(settings);
  }

  get object(): Group | null {
    return this.group;
  }

  rebuild(path: PathModel, settings: TrackSettings, seed: number): void {
    this.disposeGeometry();
    this.pathLength = path.length;
    this.applyMaterial(settings, seed);
    this.group = createTrackBuilder(settings.style).build({
      path,
      settings,
      material: this.material,
    });
    this.group.visible = settings.visible;
    this.parent.add(this.group);
  }

  /** Atualizações que não exigem nova geometria. */
  applySettings(settings: TrackSettings, seed: number): void {
    this.applyMaterial(settings, seed);
    if (!this.group) return;
    this.group.visible = settings.visible;
    this.group.traverse((node) => {
      node.castShadow = settings.castShadow;
      node.receiveShadow = settings.receiveShadow;
    });
  }

  private applyMaterial(settings: TrackSettings, seed: number): void {
    applyTrackMaterial(this.material, settings);
    const wantsWood = settings.finish === 'wood';
    if (wantsWood && this.wood?.seed !== seed) {
      this.wood?.texture.dispose();
      const texture = createWoodTexture(seed);
      this.wood = texture ? { seed, texture } : null;
    } else if (!wantsWood && this.wood) {
      this.wood.texture.dispose();
      this.wood = null;
    }
    const map = this.wood?.texture ?? null;
    if (map) map.repeat.set(woodRepeatsFor(this.pathLength), 1);
    if (this.material.map !== map) {
      this.material.map = map;
      this.material.needsUpdate = true;
    }
  }

  /** O material é compartilhado e reaproveitado: descarta apenas geometrias. */
  private disposeGeometry(): void {
    if (!this.group) return;
    this.group.removeFromParent();
    this.group.traverse((node) => {
      (node as Object3D & { geometry?: { dispose(): void } }).geometry?.dispose();
    });
    this.group = null;
  }

  dispose(): void {
    this.disposeGeometry();
    this.wood?.texture.dispose();
    this.wood = null;
    this.material.dispose();
  }
}
