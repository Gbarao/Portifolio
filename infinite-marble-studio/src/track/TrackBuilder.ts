import { DoubleSide, FrontSide, MeshStandardMaterial, type Group } from 'three';
import type { PathModel } from '../path/PathModel';
import type { TrackSettings, TrackStyle } from '../presets/PresetSchema';
import { DualRailTrackBuilder } from './DualRailTrackBuilder';
import { TubeTrackBuilder } from './TubeTrackBuilder';

export interface TrackBuildContext {
  path: PathModel;
  settings: TrackSettings;
  material: MeshStandardMaterial;
}

/** Contrato dos construtores de trilho: geram geometria a partir do trajeto. */
export interface TrackBuilder {
  readonly style: TrackStyle;
  build(context: TrackBuildContext): Group;
}

// TODO FUTURE: Groove track builder

export function createTrackBuilder(style: TrackStyle): TrackBuilder {
  switch (style) {
    case 'tube':
      return new TubeTrackBuilder();
    case 'dualRail':
      return new DualRailTrackBuilder();
  }
}

export function createTrackMaterial(settings: TrackSettings): MeshStandardMaterial {
  const material = new MeshStandardMaterial();
  applyTrackMaterial(material, settings);
  return material;
}

export function applyTrackMaterial(material: MeshStandardMaterial, settings: TrackSettings): void {
  material.color.setHex(settings.color);
  material.metalness = settings.metalness;
  material.roughness = settings.roughness;
  material.emissive.setHex(settings.emissive);
  material.emissiveIntensity = settings.emissiveIntensity;
  const transparent = settings.opacity < 1;
  if (material.transparent !== transparent) material.needsUpdate = true;
  material.transparent = transparent;
  material.opacity = settings.opacity;
  material.depthWrite = !transparent;
  material.side = transparent ? DoubleSide : FrontSide;
}
