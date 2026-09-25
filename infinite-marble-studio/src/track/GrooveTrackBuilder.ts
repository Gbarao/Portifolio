import { BufferGeometry, Float32BufferAttribute, Group, Mesh, Vector3 } from 'three';
import type { PathModel } from '../path/PathModel';
import type { TrackBuildContext, TrackBuilder } from './TrackBuilder';

/** Meia-abertura da canaleta, medida a partir do fundo (graus). 105° = paredes levemente curvadas para dentro. */
export const GROOVE_HALF_ANGLE_DEG = 105;
const HALF_ANGLE = (GROOVE_HALF_ANGLE_DEG * Math.PI) / 180;

/** Espessura da parede em função do raio interno. */
export function grooveWallThickness(innerRadius: number): number {
  return Math.min(0.2, Math.max(0.025, innerRadius * 0.22));
}

/** Um trecho do perfil 2D (x = lateral, y = "para cima" do frame) com normais próprias. */
interface ProfileStrip {
  points: [number, number][];
  normals: [number, number][];
}

/** Perfil em U: superfície interna, externa e as duas bordas (vértices separados = arestas nítidas). */
export function buildGrooveProfile(innerRadius: number, arcSegments: number): ProfileStrip[] {
  const outer = innerRadius + grooveWallThickness(innerRadius);
  const steps = Math.max(6, Math.round(arcSegments));
  const arc = (radius: number, from: number, to: number, inward: boolean): ProfileStrip => {
    const points: [number, number][] = [];
    const normals: [number, number][] = [];
    for (let j = 0; j <= steps; j++) {
      const a = from + ((to - from) * j) / steps;
      const sx = Math.sin(a);
      const cy = Math.cos(a);
      points.push([radius * sx, -radius * cy]);
      normals.push(inward ? [-sx, cy] : [sx, -cy]);
    }
    return { points, normals };
  };
  const cos = Math.cos(HALF_ANGLE);
  const sin = Math.sin(HALF_ANGLE);
  const at = (radius: number, a: number): [number, number] => [
    radius * Math.sin(a),
    -radius * Math.cos(a),
  ];
  return [
    arc(innerRadius, -HALF_ANGLE, HALF_ANGLE, true),
    arc(outer, HALF_ANGLE, -HALF_ANGLE, false),
    {
      points: [at(innerRadius, HALF_ANGLE), at(outer, HALF_ANGLE)],
      normals: [
        [cos, sin],
        [cos, sin],
      ],
    },
    {
      points: [at(outer, -HALF_ANGLE), at(innerRadius, -HALF_ANGLE)],
      normals: [
        [-cos, sin],
        [-cos, sin],
      ],
    },
  ];
}

/**
 * Extruda o perfil ao longo do trajeto usando os frames do PathModel (os mesmos das bolinhas).
 * UV: u ∈ [0, 1] ao longo do comprimento, v ∈ [0, 1] ao longo de cada trecho do perfil.
 */
export function buildGrooveGeometry(
  path: PathModel,
  innerRadius: number,
  segments: number,
  arcSegments: number,
): BufferGeometry {
  const strips = buildGrooveProfile(innerRadius, arcSegments);
  const rings = Math.max(8, Math.round(segments));
  const positions: number[] = [];
  const normals: number[] = [];
  const uvs: number[] = [];
  const indices: number[] = [];
  const point = new Vector3();
  const tangent = new Vector3();
  const up = new Vector3();
  const side = new Vector3();

  // Frames por anel, compartilhados por todos os trechos.
  const frames: { p: Vector3; u: Vector3; s: Vector3 }[] = [];
  for (let i = 0; i <= rings; i++) {
    const u = path.closed ? (i % rings) / rings : i / rings;
    path.getPointAt(u, point);
    path.getFrameAt(u, tangent, up, side);
    frames.push({ p: point.clone(), u: up.clone(), s: side.clone() });
  }

  for (const strip of strips) {
    const base = positions.length / 3;
    const count = strip.points.length;
    for (let i = 0; i <= rings; i++) {
      const f = frames[i] as { p: Vector3; u: Vector3; s: Vector3 };
      for (let j = 0; j < count; j++) {
        const [px, py] = strip.points[j] as [number, number];
        const [nx, ny] = strip.normals[j] as [number, number];
        positions.push(
          f.p.x + f.s.x * px + f.u.x * py,
          f.p.y + f.s.y * px + f.u.y * py,
          f.p.z + f.s.z * px + f.u.z * py,
        );
        normals.push(f.s.x * nx + f.u.x * ny, f.s.y * nx + f.u.y * ny, f.s.z * nx + f.u.z * ny);
        uvs.push(i / rings, j / (count - 1));
      }
    }
    for (let i = 0; i < rings; i++) {
      for (let j = 0; j < count - 1; j++) {
        const a = base + i * count + j;
        const b = base + (i + 1) * count + j;
        indices.push(a, b, a + 1, b, b + 1, a + 1);
      }
    }
  }

  const geometry = new BufferGeometry();
  geometry.setAttribute('position', new Float32BufferAttribute(positions, 3));
  geometry.setAttribute('normal', new Float32BufferAttribute(normals, 3));
  geometry.setAttribute('uv', new Float32BufferAttribute(uvs, 2));
  geometry.setIndex(indices);
  geometry.computeBoundingSphere();
  return geometry;
}

/** Canaleta em U (as bolinhas correm dentro do canal). */
export class GrooveTrackBuilder implements TrackBuilder {
  readonly style = 'groove' as const;

  build({ path, settings, material }: TrackBuildContext): Group {
    const geometry = buildGrooveGeometry(
      path,
      settings.radius,
      settings.segmentCount,
      settings.radialSegments,
    );
    const mesh = new Mesh(geometry, material);
    mesh.name = 'track-groove';
    mesh.castShadow = settings.castShadow;
    mesh.receiveShadow = settings.receiveShadow;
    const group = new Group();
    group.name = 'track';
    group.add(mesh);
    return group;
  }
}
