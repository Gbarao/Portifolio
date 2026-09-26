import { computeAnimationTime } from '../core/LoopClock';
import { clamp, TAU } from '../core/MathUtils';
import { SeededRandom } from '../core/SeededRandom';
import {
  createPressureState,
  evaluatePressure,
  type PressureMotion,
  type PressureState,
} from './animation/PressureCurve';
import {
  createMacroCameraPose,
  evaluateMacroCamera,
  type MacroCameraPose,
} from './camera/MacroCameraRig';
import {
  SqueezeDeformer,
  type SqueezeDeformationParams,
  type SqueezeToolState,
} from './deformation/SqueezeDeformer';
import { buildSoftBlockMesh, type SoftBlockMesh } from './geometry/SoftBlockGeometry';
import type { SatisfyingSettings } from './SatisfyingSettings';

/** Estado completo de um instante (sem WebGL). */
export interface SqueezeFrameState {
  normalizedTime: number;
  pressureTime: number;
  pressure: PressureState;
  tool: SqueezeToolState;
  camera: MacroCameraPose;
}

export function createSqueezeFrameState(): SqueezeFrameState {
  return {
    normalizedTime: 0,
    pressureTime: 0,
    pressure: createPressureState(),
    tool: { x: 0, y: 0, z: 0, radius: 1, indent: 0, squash: 0, profileRadius: 1 },
    camera: createMacroCameraPose(),
  };
}

/** Converte settings em parâmetros de movimento da curva de pressão. */
export function pressureMotionFrom(settings: SatisfyingSettings): PressureMotion {
  return {
    approachHeight: Math.max(0, settings.pressure.approachHeight),
    maxDepth: clamp(settings.pressure.strength, 0, 0.7) * settings.object.height,
    creep: clamp(settings.pressure.creep, 0, 0.3),
    globalShare: clamp(settings.deformation.softness, 0, 0.9),
    viscosity: clamp(settings.deformation.viscosity, 0, 1),
    bounce: clamp(settings.deformation.elasticity, 0, 1),
  };
}

export function deformationParamsFrom(settings: SatisfyingSettings): SqueezeDeformationParams {
  const d = settings.deformation;
  return {
    falloff: Math.max(0.01, d.falloff),
    locality: clamp(d.locality, 0, 1),
    bulge: clamp(d.bulge, 0, 3),
    volumePreservation: clamp(d.volumePreservation, 0, 1.5),
    bulgeHeight: clamp(d.bulgeHeight, 0.2, 0.85),
  };
}

/**
 * Pequenas imperfeições determinísticas (seed): ondulações suaves de baixa frequência
 * ao longo da normal, com amplitude ~0,4 % do tamanho. O objeto parece "feito à mão".
 */
export function applyImperfections(mesh: SoftBlockMesh, seed: number, amount: number): void {
  if (amount <= 0) return;
  const rng = SeededRandom.derived(seed, 'softObjectImperfections');
  const waves: { kx: number; ky: number; kz: number; phase: number; amp: number }[] = [];
  for (let i = 0; i < 5; i++) {
    const theta = rng.nextFloat(0, TAU);
    const phi = rng.nextFloat(-1, 1);
    const k = rng.nextFloat(1.2, 3.2);
    const r = Math.sqrt(1 - phi * phi);
    waves.push({
      kx: k * r * Math.cos(theta),
      ky: k * phi,
      kz: k * r * Math.sin(theta),
      phase: rng.nextFloat(0, TAU),
      amp: rng.nextFloat(0.4, 1),
    });
  }
  const p = mesh.positions;
  const n = mesh.normals;
  for (let v = 0; v < p.length; v += 3) {
    const x = p[v] as number;
    const y = p[v + 1] as number;
    const z = p[v + 2] as number;
    let d = 0;
    for (const w of waves) d += w.amp * Math.sin(w.kx * x + w.ky * y + w.kz * z + w.phase);
    // O fundo permanece plano (apoio no chão).
    const grounded = clamp(y / 0.08, 0, 1);
    const offset = (amount * d * grounded) / waves.length;
    p[v] = x + (n[v] as number) * offset;
    p[v + 1] = y + (n[v + 1] as number) * offset;
    p[v + 2] = z + (n[v + 2] as number) * offset;
  }
}

/**
 * Simulação determinística do squeeze: normalizedTime + settings + seed → estado.
 * É a fonte de verdade usada pela cena WebGL e pelos testes.
 */
export class SqueezeSimulation {
  readonly mesh: SoftBlockMesh;
  readonly deformer: SqueezeDeformer;
  private readonly motion: PressureMotion;
  private readonly params: SqueezeDeformationParams;

  constructor(
    readonly settings: SatisfyingSettings,
    readonly seed: number,
  ) {
    this.mesh = buildSoftBlockMesh(settings.object);
    const size = Math.min(settings.object.width, settings.object.height, settings.object.depth);
    applyImperfections(this.mesh, seed, size * 0.004);
    this.deformer = new SqueezeDeformer(this.mesh, {
      width: settings.object.width,
      height: settings.object.height,
      depth: settings.object.depth,
      radius: this.mesh.radius,
    });
    this.motion = pressureMotionFrom(settings);
    this.params = deformationParamsFrom(settings);
  }

  /** Posição de repouso (centro) da ferramenta: tocando o topo + folga. */
  get toolRestY(): number {
    return (
      this.settings.object.height + this.settings.pressure.toolRadius + this.motion.approachHeight
    );
  }

  evaluate(
    normalizedTime: number,
    aspect: number,
    out: SqueezeFrameState = createSqueezeFrameState(),
  ): SqueezeFrameState {
    const s = this.settings;
    const t = normalizedTime - Math.floor(normalizedTime);
    const pressureTime = computeAnimationTime(t, s.pressure.cycles);
    evaluatePressure(pressureTime, s.pressure.timing, this.motion, out.pressure);
    out.normalizedTime = t;
    out.pressureTime = pressureTime;
    out.tool.radius = s.pressure.toolRadius;
    out.tool.x = clamp(s.pressure.offsetX, -0.6, 0.6) * (s.object.width / 2);
    out.tool.z = clamp(s.pressure.offsetZ, -0.6, 0.6) * (s.object.depth / 2);
    out.tool.y = this.toolRestY - out.pressure.toolTravel;
    out.tool.indent = out.pressure.indent;
    out.tool.squash = out.pressure.squash;
    // A cavidade se alarga enquanto recupera (fica rasa e suave, sem borda marcada).
    out.tool.profileRadius = s.pressure.toolRadius * (1 + 2.5 * out.pressure.recovery);
    evaluateMacroCamera(s.camera, s.object, aspect, t, out.camera);
    return out;
  }

  /** Deforma a malha para o estado (buffers do deformer). */
  deform(state: SqueezeFrameState): void {
    this.deformer.apply(state.tool, this.params);
  }
}
