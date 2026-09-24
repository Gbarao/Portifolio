import { Vector3, type Curve } from 'three';
import { modulo } from '../core/MathUtils';

const WORLD_UP = new Vector3(0, 1, 0);
const WORLD_FORWARD = new Vector3(0, 0, 1);

/**
 * Frames de transporte paralelo (rotation-minimizing, método da dupla reflexão) amostrados
 * ao longo do comprimento de arco. Diferente dos frames de Frenet-Serret puros, não invertem
 * em pontos de inflexão. Em curvas fechadas a torção residual é distribuída ao longo do
 * percurso, garantindo frame(0) === frame(1) — sem salto no fechamento.
 *
 * Convenção: side = up × tangent (base destra: side, up, tangent).
 */
export class PathFrames {
  readonly samples: number;
  readonly closed: boolean;
  private readonly tangents: Float64Array;
  private readonly ups: Float64Array;
  private readonly sides: Float64Array;

  constructor(curve: Curve<Vector3>, samples: number, closed: boolean, bankAngleRad = 0) {
    this.samples = Math.max(8, Math.floor(samples));
    this.closed = closed;
    const count = this.samples + 1;
    this.tangents = new Float64Array(count * 3);
    this.ups = new Float64Array(count * 3);
    this.sides = new Float64Array(count * 3);
    this.build(curve, bankAngleRad);
  }

  private build(curve: Curve<Vector3>, bankAngleRad: number): void {
    const n = this.samples;
    const positions: Vector3[] = [];
    const tangents: Vector3[] = [];
    const delta = 1e-4;
    const before = new Vector3();
    const after = new Vector3();

    for (let i = 0; i <= n; i++) {
      const u = i / n;
      positions.push(curve.getPointAt(this.closed ? modulo(u, 1) : u, new Vector3()));
      const u0 = this.closed ? modulo(u - delta, 1) : Math.max(0, u - delta);
      const u1 = this.closed ? modulo(u + delta, 1) : Math.min(1, u + delta);
      curve.getPointAt(u0, before);
      curve.getPointAt(u1, after);
      const tangent = after.clone().sub(before);
      if (tangent.lengthSq() < 1e-20)
        tangent.copy(i > 0 ? (tangents[i - 1] as Vector3) : WORLD_FORWARD);
      tangents.push(tangent.normalize());
    }
    if (this.closed) {
      (positions[n] as Vector3).copy(positions[0] as Vector3);
      (tangents[n] as Vector3).copy(tangents[0] as Vector3);
    }

    // Normal inicial: projeção do "para cima" global no plano normal à tangente.
    const t0 = tangents[0] as Vector3;
    const up0 = WORLD_UP.clone().addScaledVector(t0, -WORLD_UP.dot(t0));
    if (up0.lengthSq() < 0.01) {
      up0.copy(WORLD_FORWARD).addScaledVector(t0, -WORLD_FORWARD.dot(t0));
    }
    up0.normalize();

    const ups: Vector3[] = [up0];
    const v1 = new Vector3();
    const v2 = new Vector3();
    const rL = new Vector3();
    const tL = new Vector3();
    for (let i = 0; i < n; i++) {
      const r = ups[i] as Vector3;
      const ti = tangents[i] as Vector3;
      const tNext = tangents[i + 1] as Vector3;
      v1.subVectors(positions[i + 1] as Vector3, positions[i] as Vector3);
      const c1 = v1.dot(v1);
      if (c1 < 1e-14) {
        ups.push(r.clone());
        continue;
      }
      rL.copy(r).addScaledVector(v1, (-2 / c1) * v1.dot(r));
      tL.copy(ti).addScaledVector(v1, (-2 / c1) * v1.dot(ti));
      v2.subVectors(tNext, tL);
      const c2 = v2.dot(v2);
      const next = rL.clone();
      if (c2 > 1e-14) next.addScaledVector(v2, (-2 / c2) * v2.dot(rL));
      // Reortogonaliza para evitar deriva numérica.
      next.addScaledVector(tNext, -next.dot(tNext)).normalize();
      ups.push(next);
    }

    if (this.closed) {
      // Distribui a torção residual para que o frame final coincida com o inicial.
      const first = ups[0] as Vector3;
      const last = ups[n] as Vector3;
      const cross = new Vector3().crossVectors(first, last);
      const twist = Math.atan2(cross.dot(t0), first.dot(last));
      for (let i = 1; i <= n; i++) {
        rotateAroundAxis(ups[i] as Vector3, tangents[i] as Vector3, (-twist * i) / n);
      }
      (ups[n] as Vector3).copy(first);
    }

    // Rolagem global constante: alinha "up" ao eixo Y (ou Z em curvas verticais planas).
    const side = new Vector3();
    let sumUpY = 0;
    let sumSideY = 0;
    let sumUpZ = 0;
    let sumSideZ = 0;
    for (let i = 0; i < n; i++) {
      const u = ups[i] as Vector3;
      side.crossVectors(u, tangents[i] as Vector3);
      sumUpY += u.y;
      sumSideY += side.y;
      sumUpZ += u.z;
      sumSideZ += side.z;
    }
    const threshold = 1e-3 * n;
    let roll = 0;
    if (Math.hypot(sumUpY, sumSideY) > threshold) roll = Math.atan2(sumSideY, sumUpY);
    else if (Math.hypot(sumUpZ, sumSideZ) > threshold) roll = Math.atan2(sumSideZ, sumUpZ);
    roll += bankAngleRad;
    const cosR = Math.cos(roll);
    const sinR = Math.sin(roll);

    const rolled = new Vector3();
    for (let i = 0; i <= n; i++) {
      const t = tangents[i] as Vector3;
      const u = ups[i] as Vector3;
      side.crossVectors(u, t);
      rolled.copy(u).multiplyScalar(cosR).addScaledVector(side, sinR).normalize();
      side.crossVectors(rolled, t).normalize();
      const o = i * 3;
      this.tangents[o] = t.x;
      this.tangents[o + 1] = t.y;
      this.tangents[o + 2] = t.z;
      this.ups[o] = rolled.x;
      this.ups[o + 1] = rolled.y;
      this.ups[o + 2] = rolled.z;
      this.sides[o] = side.x;
      this.sides[o + 1] = side.y;
      this.sides[o + 2] = side.z;
    }
  }

  /** Frame interpolado em u ∈ [0, 1]. Não aloca objetos. */
  getFrame(u: number, outTangent: Vector3, outUp: Vector3, outSide: Vector3): void {
    const n = this.samples;
    const x = (u < 0 ? 0 : u > 1 ? 1 : u) * n;
    const i = Math.min(Math.floor(x), n - 1);
    const f = x - i;
    const a = i * 3;
    const b = a + 3;
    const g = 1 - f;
    const T = this.tangents;
    const U = this.ups;
    outTangent
      .set(T[a]! * g + T[b]! * f, T[a + 1]! * g + T[b + 1]! * f, T[a + 2]! * g + T[b + 2]! * f)
      .normalize();
    outUp.set(U[a]! * g + U[b]! * f, U[a + 1]! * g + U[b + 1]! * f, U[a + 2]! * g + U[b + 2]! * f);
    outUp.addScaledVector(outTangent, -outUp.dot(outTangent)).normalize();
    outSide.crossVectors(outUp, outTangent).normalize();
  }

  /** Acesso direto às amostras (usado por testes e pelo construtor do dual rail). */
  getSample(index: number, outTangent: Vector3, outUp: Vector3, outSide: Vector3): void {
    const o = Math.max(0, Math.min(this.samples, index)) * 3;
    outTangent.set(this.tangents[o]!, this.tangents[o + 1]!, this.tangents[o + 2]!);
    outUp.set(this.ups[o]!, this.ups[o + 1]!, this.ups[o + 2]!);
    outSide.set(this.sides[o]!, this.sides[o + 1]!, this.sides[o + 2]!);
  }
}

/** Rotaciona v (perpendicular a axis) em torno de axis unitário. */
function rotateAroundAxis(v: Vector3, axis: Vector3, angle: number): void {
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  const cx = axis.y * v.z - axis.z * v.y;
  const cy = axis.z * v.x - axis.x * v.z;
  const cz = axis.x * v.y - axis.y * v.x;
  const d = axis.dot(v);
  v.set(
    v.x * cos + cx * sin + axis.x * d * (1 - cos),
    v.y * cos + cy * sin + axis.y * d * (1 - cos),
    v.z * cos + cz * sin + axis.z * d * (1 - cos),
  );
}
