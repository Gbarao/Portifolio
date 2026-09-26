import { BufferAttribute, BufferGeometry, DynamicDrawUsage } from 'three';
import { clamp } from '../../core/MathUtils';

/** Dimensões do bloco macio (unidades de cena). O bloco repousa no chão: y ∈ [0, height]. */
export interface SoftBlockShape {
  width: number;
  height: number;
  depth: number;
  /** Raio do arredondamento das arestas (limitado a 48% da menor dimensão). */
  roundness: number;
  /** Subdivisões por unidade de comprimento (densidade da malha). */
  subdivision: number;
}

/** Malha em arrays tipados: a mesma estrutura é usada no navegador e nos testes. */
export interface SoftBlockMesh {
  /** Posições de repouso (x, y, z por vértice). */
  positions: Float32Array;
  /** Normais analíticas de repouso (unitárias). */
  normals: Float32Array;
  /** Triângulos (índices, orientação anti-horária vista de fora). */
  indices: Uint32Array;
  vertexCount: number;
  /** Raio efetivo do arredondamento. */
  radius: number;
}

export const MIN_BLOCK_SEGMENTS = 4;
export const MAX_BLOCK_SEGMENTS = 160;

/** Raio de arredondamento efetivo (evita caixas degeneradas). */
export function effectiveRoundness(shape: SoftBlockShape): number {
  const limit = 0.48 * Math.min(shape.width, shape.height, shape.depth);
  return clamp(shape.roundness, 0.001, limit);
}

/** Segmentos por eixo a partir da densidade. */
export function blockSegments(shape: SoftBlockShape): [number, number, number] {
  const seg = (size: number): number =>
    clamp(Math.round(size * shape.subdivision), MIN_BLOCK_SEGMENTS, MAX_BLOCK_SEGMENTS);
  return [seg(shape.width), seg(shape.height), seg(shape.depth)];
}

/**
 * Caixa arredondada soldada: cubo subdividido cujos vértices de aresta são compartilhados
 * entre faces (malha contínua, sem costura), projetado sobre a caixa arredondada:
 * ponto → ponto mais próximo da caixa interna + direção × raio.
 */
export function buildSoftBlockMesh(shape: SoftBlockShape): SoftBlockMesh {
  const [nx, ny, nz] = blockSegments(shape);
  const radius = effectiveRoundness(shape);
  const hw = shape.width / 2;
  const hh = shape.height / 2;
  const hd = shape.depth / 2;
  const inner = [hw - radius, hh - radius, hd - radius] as const;

  // Mapa (i, j, k) da grade → índice do vértice (apenas pontos da superfície).
  const stride = (nx + 1) * (ny + 1);
  const lookup = new Int32Array((nx + 1) * (ny + 1) * (nz + 1)).fill(-1);
  const positions: number[] = [];
  const normals: number[] = [];

  const vertex = (i: number, j: number, k: number): number => {
    const key = i + j * (nx + 1) + k * stride;
    const existing = lookup[key] as number;
    if (existing >= 0) return existing;
    // Ponto no cubo [-hw, hw] × [-hh, hh] × [-hd, hd].
    const px = -hw + (2 * hw * i) / nx;
    const py = -hh + (2 * hh * j) / ny;
    const pz = -hd + (2 * hd * k) / nz;
    const cx = clamp(px, -inner[0], inner[0]);
    const cy = clamp(py, -inner[1], inner[1]);
    const cz = clamp(pz, -inner[2], inner[2]);
    let dx = px - cx;
    let dy = py - cy;
    let dz = pz - cz;
    const len = Math.hypot(dx, dy, dz);
    if (len > 1e-12) {
      dx /= len;
      dy /= len;
      dz /= len;
    } else {
      // Nunca ocorre para pontos da superfície (len = raio nas faces), mas mantém finito.
      dy = 1;
    }
    const index = positions.length / 3;
    positions.push(cx + dx * radius, cy + dy * radius + hh, cz + dz * radius);
    normals.push(dx, dy, dz);
    lookup[key] = index;
    return index;
  };

  const indices: number[] = [];
  /** Quad (a, b, c, d) em ordem anti-horária vista de fora. */
  const quad = (a: number, b: number, c: number, d: number): void => {
    indices.push(a, b, c, a, c, d);
  };

  // +X / -X
  for (let j = 0; j < ny; j++) {
    for (let k = 0; k < nz; k++) {
      quad(vertex(nx, j, k), vertex(nx, j + 1, k), vertex(nx, j + 1, k + 1), vertex(nx, j, k + 1));
      quad(vertex(0, j, k), vertex(0, j, k + 1), vertex(0, j + 1, k + 1), vertex(0, j + 1, k));
    }
  }
  // +Y / -Y
  for (let i = 0; i < nx; i++) {
    for (let k = 0; k < nz; k++) {
      quad(vertex(i, ny, k), vertex(i, ny, k + 1), vertex(i + 1, ny, k + 1), vertex(i + 1, ny, k));
      quad(vertex(i, 0, k), vertex(i + 1, 0, k), vertex(i + 1, 0, k + 1), vertex(i, 0, k + 1));
    }
  }
  // +Z / -Z
  for (let i = 0; i < nx; i++) {
    for (let j = 0; j < ny; j++) {
      quad(vertex(i, j, nz), vertex(i + 1, j, nz), vertex(i + 1, j + 1, nz), vertex(i, j + 1, nz));
      quad(vertex(i, j, 0), vertex(i, j + 1, 0), vertex(i + 1, j + 1, 0), vertex(i + 1, j, 0));
    }
  }

  return {
    positions: new Float32Array(positions),
    normals: new Float32Array(normals),
    indices: new Uint32Array(indices),
    vertexCount: positions.length / 3,
    radius,
  };
}

/**
 * BufferGeometry dinâmica. Se `positions`/`normals` forem fornecidos, eles passam a ser
 * os próprios buffers dos atributos (o deformador escreve direto neles, sem cópia).
 */
export function createSoftBlockGeometry(
  mesh: SoftBlockMesh,
  positions: Float32Array = new Float32Array(mesh.positions),
  normals: Float32Array = new Float32Array(mesh.normals),
  colors?: Float32Array,
): BufferGeometry {
  const geometry = new BufferGeometry();
  const position = new BufferAttribute(positions, 3);
  const normal = new BufferAttribute(normals, 3);
  position.setUsage(DynamicDrawUsage);
  normal.setUsage(DynamicDrawUsage);
  geometry.setAttribute('position', position);
  geometry.setAttribute('normal', normal);
  if (colors) {
    const color = new BufferAttribute(colors, 3);
    color.setUsage(DynamicDrawUsage);
    geometry.setAttribute('color', color);
  }
  geometry.setIndex(new BufferAttribute(mesh.indices, 1));
  geometry.computeBoundingSphere();
  return geometry;
}
