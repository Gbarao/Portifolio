/**
 * Normais suaves por vértice (média das normais de face ponderada pela área), calculadas
 * in-place sobre arrays pré-alocados: nenhuma alocação por frame.
 */
export function computeVertexNormalsInto(
  positions: Float32Array,
  indices: Uint32Array,
  out: Float32Array,
): void {
  out.fill(0);
  for (let t = 0; t < indices.length; t += 3) {
    const a = (indices[t] as number) * 3;
    const b = (indices[t + 1] as number) * 3;
    const c = (indices[t + 2] as number) * 3;
    const ax = positions[a] as number;
    const ay = positions[a + 1] as number;
    const az = positions[a + 2] as number;
    const e1x = (positions[b] as number) - ax;
    const e1y = (positions[b + 1] as number) - ay;
    const e1z = (positions[b + 2] as number) - az;
    const e2x = (positions[c] as number) - ax;
    const e2y = (positions[c + 1] as number) - ay;
    const e2z = (positions[c + 2] as number) - az;
    // Produto vetorial (não normalizado = ponderação pela área).
    const nx = e1y * e2z - e1z * e2y;
    const ny = e1z * e2x - e1x * e2z;
    const nz = e1x * e2y - e1y * e2x;
    out[a] = (out[a] as number) + nx;
    out[a + 1] = (out[a + 1] as number) + ny;
    out[a + 2] = (out[a + 2] as number) + nz;
    out[b] = (out[b] as number) + nx;
    out[b + 1] = (out[b + 1] as number) + ny;
    out[b + 2] = (out[b + 2] as number) + nz;
    out[c] = (out[c] as number) + nx;
    out[c + 1] = (out[c + 1] as number) + ny;
    out[c + 2] = (out[c + 2] as number) + nz;
  }
  for (let i = 0; i < out.length; i += 3) {
    const x = out[i] as number;
    const y = out[i + 1] as number;
    const z = out[i + 2] as number;
    const len = Math.hypot(x, y, z);
    if (len > 1e-20) {
      out[i] = x / len;
      out[i + 1] = y / len;
      out[i + 2] = z / len;
    } else {
      out[i] = 0;
      out[i + 1] = 1;
      out[i + 2] = 0;
    }
  }
}

/** Volume fechado da malha (teorema da divergência). Positivo para malhas orientadas para fora. */
export function computeMeshVolume(positions: Float32Array, indices: Uint32Array): number {
  let volume = 0;
  for (let t = 0; t < indices.length; t += 3) {
    const a = (indices[t] as number) * 3;
    const b = (indices[t + 1] as number) * 3;
    const c = (indices[t + 2] as number) * 3;
    const ax = positions[a] as number;
    const ay = positions[a + 1] as number;
    const az = positions[a + 2] as number;
    const bx = positions[b] as number;
    const by = positions[b + 1] as number;
    const bz = positions[b + 2] as number;
    const cx = positions[c] as number;
    const cy = positions[c + 1] as number;
    const cz = positions[c + 2] as number;
    volume += ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx);
  }
  return volume / 6;
}

/** Área associada a cada vértice (1/3 da área dos triângulos vizinhos). */
export function computeVertexAreas(positions: Float32Array, indices: Uint32Array): Float32Array {
  const areas = new Float32Array(positions.length / 3);
  for (let t = 0; t < indices.length; t += 3) {
    const ia = indices[t] as number;
    const ib = indices[t + 1] as number;
    const ic = indices[t + 2] as number;
    const a = ia * 3;
    const b = ib * 3;
    const c = ic * 3;
    const e1x = (positions[b] as number) - (positions[a] as number);
    const e1y = (positions[b + 1] as number) - (positions[a + 1] as number);
    const e1z = (positions[b + 2] as number) - (positions[a + 2] as number);
    const e2x = (positions[c] as number) - (positions[a] as number);
    const e2y = (positions[c + 1] as number) - (positions[a + 1] as number);
    const e2z = (positions[c + 2] as number) - (positions[a + 2] as number);
    const third =
      Math.hypot(e1y * e2z - e1z * e2y, e1z * e2x - e1x * e2z, e1x * e2y - e1y * e2x) / 6;
    areas[ia] = (areas[ia] as number) + third;
    areas[ib] = (areas[ib] as number) + third;
    areas[ic] = (areas[ic] as number) + third;
  }
  return areas;
}
