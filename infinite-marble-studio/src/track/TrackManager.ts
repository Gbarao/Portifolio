import type { Group, MeshStandardMaterial, Object3D } from 'three';
import type { Disposable } from '../core/Disposable';
import type { PathModel } from '../path/PathModel';
import type { TrackSettings } from '../presets/PresetSchema';
import { applyTrackMaterial, createTrackBuilder, createTrackMaterial } from './TrackBuilder';

/** Mantém a geometria atual do trilho e descarta a anterior a cada reconstrução. */
export class TrackManager implements Disposable {
  private group: Group | null = null;
  private readonly material: MeshStandardMaterial;

  constructor(
    private readonly parent: Object3D,
    settings: TrackSettings,
  ) {
    this.material = createTrackMaterial(settings);
  }

  get object(): Group | null {
    return this.group;
  }

  rebuild(path: PathModel, settings: TrackSettings): void {
    this.disposeGeometry();
    applyTrackMaterial(this.material, settings);
    this.group = createTrackBuilder(settings.style).build({
      path,
      settings,
      material: this.material,
    });
    this.group.visible = settings.visible;
    this.parent.add(this.group);
  }

  /** Atualizações que não exigem nova geometria. */
  applySettings(settings: TrackSettings): void {
    applyTrackMaterial(this.material, settings);
    if (!this.group) return;
    this.group.visible = settings.visible;
    this.group.traverse((node) => {
      node.castShadow = settings.castShadow;
      node.receiveShadow = settings.receiveShadow;
    });
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
    this.material.dispose();
  }
}
