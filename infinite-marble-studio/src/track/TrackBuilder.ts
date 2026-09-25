import { DoubleSide, FrontSide, MeshPhysicalMaterial, type Group } from 'three';
import type { PathModel } from '../path/PathModel';
import type { TrackSettings, TrackStyle } from '../presets/PresetSchema';
import { DualRailTrackBuilder } from './DualRailTrackBuilder';
import { GrooveTrackBuilder, grooveWallThickness } from './GrooveTrackBuilder';
import { TubeTrackBuilder } from './TubeTrackBuilder';

export interface TrackBuildContext {
  path: PathModel;
  settings: TrackSettings;
  material: MeshPhysicalMaterial;
}

/** Contrato dos construtores de trilho: geram geometria a partir do trajeto. */
export interface TrackBuilder {
  readonly style: TrackStyle;
  build(context: TrackBuildContext): Group;
}

export function createTrackBuilder(style: TrackStyle): TrackBuilder {
  switch (style) {
    case 'tube':
      return new TubeTrackBuilder();
    case 'dualRail':
      return new DualRailTrackBuilder();
    case 'groove':
      return new GrooveTrackBuilder();
  }
}

/** Raio externo do trilho (usado por hastes de suporte e enquadramento). */
export function trackOuterRadius(
  settings: Pick<TrackSettings, 'style' | 'radius' | 'railRadius'>,
): number {
  switch (settings.style) {
    case 'tube':
      return settings.radius;
    case 'dualRail':
      return settings.railRadius;
    case 'groove':
      return settings.radius + grooveWallThickness(settings.radius);
  }
}

export function createTrackMaterial(settings: TrackSettings): MeshPhysicalMaterial {
  const material = new MeshPhysicalMaterial();
  applyTrackMaterial(material, settings);
  return material;
}

export function applyTrackMaterial(material: MeshPhysicalMaterial, settings: TrackSettings): void {
  material.color.setHex(settings.color);
  material.metalness = settings.metalness;
  material.roughness = settings.roughness;
  material.emissive.setHex(settings.emissive);
  material.emissiveIntensity = settings.emissiveIntensity;
  material.clearcoat = settings.clearcoat;
  material.clearcoatRoughness = 0.15;
  const transparent = settings.opacity < 1;
  if (material.transparent !== transparent) material.needsUpdate = true;
  material.transparent = transparent;
  material.opacity = settings.opacity;
  material.depthWrite = !transparent;
  material.side = transparent ? DoubleSide : FrontSide;
}
