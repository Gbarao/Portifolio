import { Group, Mesh, TubeGeometry } from 'three';
import type { TrackBuildContext, TrackBuilder } from './TrackBuilder';

/** Tubo contínuo seguindo a curva (THREE.TubeGeometry). */
export class TubeTrackBuilder implements TrackBuilder {
  readonly style = 'tube' as const;

  build({ path, settings, material }: TrackBuildContext): Group {
    const geometry = new TubeGeometry(
      path.curve,
      Math.round(settings.segmentCount),
      settings.radius,
      Math.round(settings.radialSegments),
      path.closed,
    );
    const mesh = new Mesh(geometry, material);
    mesh.name = 'track-tube';
    mesh.castShadow = settings.castShadow;
    mesh.receiveShadow = settings.receiveShadow;
    const group = new Group();
    group.name = 'track';
    group.add(mesh);
    return group;
  }
}
