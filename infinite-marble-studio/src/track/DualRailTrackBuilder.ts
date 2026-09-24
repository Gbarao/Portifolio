import { Curve, Group, Mesh, TubeGeometry, Vector3 } from 'three';
import type { PathModel } from '../path/PathModel';
import type { TrackBuildContext, TrackBuilder } from './TrackBuilder';

/**
 * Curva deslocada lateralmente usando os mesmos frames das bolinhas, garantindo que elas
 * permaneçam centralizadas entre os dois trilhos.
 */
export class OffsetCurve extends Curve<Vector3> {
  private readonly tangent = new Vector3();
  private readonly up = new Vector3();
  private readonly side = new Vector3();

  constructor(
    private readonly path: PathModel,
    private readonly lateralOffset: number,
  ) {
    super();
  }

  override getPoint(t: number, optionalTarget: Vector3 = new Vector3()): Vector3 {
    const u = this.path.wrapU(t);
    this.path.getPointAt(u, optionalTarget);
    this.path.getFrameAt(u, this.tangent, this.up, this.side);
    return optionalTarget.addScaledVector(this.side, this.lateralOffset);
  }
}

/** Dois tubos paralelos deslocados por ±railDistance/2 ao longo do vetor lateral do frame. */
export class DualRailTrackBuilder implements TrackBuilder {
  readonly style = 'dualRail' as const;

  build({ path, settings, material }: TrackBuildContext): Group {
    const group = new Group();
    group.name = 'track';
    const half = settings.railDistance / 2;
    for (const [name, offset] of [
      ['rail-left', -half],
      ['rail-right', half],
    ] as const) {
      const curve = new OffsetCurve(path, offset);
      curve.arcLengthDivisions = path.curve.arcLengthDivisions;
      const geometry = new TubeGeometry(
        curve,
        Math.round(settings.segmentCount),
        settings.railRadius,
        Math.round(settings.radialSegments),
        path.closed,
      );
      const mesh = new Mesh(geometry, material);
      mesh.name = name;
      mesh.castShadow = settings.castShadow;
      mesh.receiveShadow = settings.receiveShadow;
      group.add(mesh);
    }
    return group;
  }
}
