import { clamp } from '../../core/MathUtils';
import type { SoftBlockMesh } from '../geometry/SoftBlockGeometry';
import { computeVertexAreas, computeVertexNormalsInto } from './MeshNormals';

/**
 * Parâmetros do material "macio" (independentes do tempo).
 * Unidades de comprimento em unidades de cena.
 */
export interface SqueezeDeformationParams {
  /** Largura extra da "saia" da indentação fora do contato (unidades de cena). */
  falloff: number;
  /** 0 = compressão global uniforme; 1 = concentrada sob a ferramenta. */
  locality: number;
  /** Intensidade relativa do bulging lateral (1 = compensação exata). */
  bulge: number;
  /** Fração do volume deslocado que reaparece como bulging (0–1.2). */
  volumePreservation: number;
  /** Altura relativa (0–1) do pico do bulging lateral. */
  bulgeHeight: number;
}

/** Estado da ferramenta esférica + profundidades da pressão (vindas da PressureCurve). */
export interface SqueezeToolState {
  x: number;
  y: number;
  z: number;
  radius: number;
  /** Indentação local no eixo (≥ 0). */
  indent: number;
  /** Compressão global no topo (pode ser negativa = esticado). */
  squash: number;
  /**
   * Raio da esfera usado para o formato da indentação (≥ radius). Durante a recuperação
   * livre ele cresce: a cavidade fica mais rasa e mais suave, como espuma voltando.
   */
  profileRadius: number;
}

/** Dimensões usadas pelo campo de deformação. */
export interface SqueezeBody {
  width: number;
  height: number;
  depth: number;
  radius: number;
}

/** Diagnóstico do último frame (útil para testes e UI de depuração). */
export interface SqueezeDiagnostics {
  contactRadius: number;
  bulgeAmplitude: number;
  displacedVolume: number;
  clampedVertices: number;
}

/**
 * Raio de contato `a` para uma indentação `indent` de uma esfera de raio R, tal que a
 * superfície conformada à esfera (dentro do contato) encontre o perfil de Hertz (fora) com
 * continuidade: indent = R − √(R² − a²) + a² / (2R). Monotônica em a ∈ [0, R).
 */
export function solveContactRadius(indent: number, sphereRadius: number): number {
  const R = sphereRadius;
  if (indent <= 0 || R <= 0) return 0;
  const f = (a: number): number => R - Math.sqrt(Math.max(0, R * R - a * a)) + (a * a) / (2 * R);
  const maxA = R * 0.985;
  if (indent >= f(maxA)) return maxA;
  let lo = 0;
  let hi = maxA;
  for (let i = 0; i < 48; i++) {
    const mid = (lo + hi) / 2;
    if (f(mid) < indent) lo = mid;
    else hi = mid;
  }
  return (lo + hi) / 2;
}

/**
 * Deslocamento vertical (para baixo) da superfície a uma distância horizontal ρ do eixo.
 * Dentro do contato: superfície da esfera. Fora: perfil de Hertz (semi-espaço elástico),
 * atenuado por uma janela gaussiana que preserva C¹ em ρ = a.
 */
export function indentationProfile(
  rho: number,
  indent: number,
  contactRadius: number,
  sphereRadius: number,
  falloff: number,
): number {
  if (indent <= 0) return 0;
  const a = contactRadius;
  const R = sphereRadius;
  if (rho <= a) return indent - (R - Math.sqrt(Math.max(0, R * R - rho * rho)));
  const hertz =
    ((2 * a * a - rho * rho) * Math.asin(a / rho) + a * Math.sqrt(rho * rho - a * a)) /
    (Math.PI * R);
  const width = Math.max(1e-4, falloff);
  const u = (rho - a) / width;
  return Math.max(0, hertz) * Math.exp(-u * u);
}

/** Perfil vertical do bulging (0 no chão, pico em `peak`, reduzido no topo). */
export function bulgeProfile(s: number, peak: number): number {
  const x = clamp(s, 0, 1);
  const p = clamp(peak, 0.2, 0.85);
  // sin(π · x^γ) tem pico em x = p quando p^γ = 0.5.
  const gamma = Math.log(0.5) / Math.log(p);
  const barrel = Math.sin(Math.PI * Math.pow(x, gamma));
  // O topo arredondado também "rola" para fora quando é esmagado.
  const roll = 0.35 * x * x * x;
  return Math.max(0, barrel) + roll;
}

/** Intensidade da oclusão de contato (ferramenta) e de apoio (chão). */
const CONTACT_OCCLUSION = 0.5;
const GROUND_OCCLUSION = 0.35;

/**
 * Deformador de squeeze: campo de deslocamento contínuo aplicado às posições de repouso.
 *
 *   ρ = distância horizontal ao eixo da ferramenta
 *   1. compressão global:  Δy = −squash · (y/H) · g(ρ)        (g plana dentro do contato)
 *   2. indentação local:   Δy = −L(ρ) · v(y)                  (Hertz + conformação à esfera)
 *   3. bulging:            Δxz = B · P(y/H) · w(ρ) · n_xz     (normal de repouso horizontal)
 *   4. B calculado para repor `volumePreservation` × volume deslocado (medido na malha)
 *   5. contato: nenhum vértice dentro da esfera
 *
 * Buffers pré-alocados: `apply` não aloca memória.
 */
export class SqueezeDeformer {
  readonly positions: Float32Array;
  readonly normals: Float32Array;
  /** Oclusão de contato por vértice (RGB, multiplicada na cor do material). */
  readonly occlusion: Float32Array;
  private readonly vertexAreas: Float32Array;
  private readonly scratchDy: Float32Array;
  private readonly scratchBulge: Float32Array;
  readonly diagnostics: SqueezeDiagnostics = {
    contactRadius: 0,
    bulgeAmplitude: 0,
    displacedVolume: 0,
    clampedVertices: 0,
  };

  constructor(
    private readonly mesh: SoftBlockMesh,
    private readonly body: SqueezeBody,
  ) {
    this.positions = new Float32Array(mesh.positions);
    this.normals = new Float32Array(mesh.normals);
    this.occlusion = new Float32Array(mesh.positions.length).fill(1);
    this.vertexAreas = computeVertexAreas(mesh.positions, mesh.indices);
    this.scratchDy = new Float32Array(mesh.vertexCount);
    this.scratchBulge = new Float32Array(mesh.vertexCount);
  }

  get rest(): SoftBlockMesh {
    return this.mesh;
  }

  /** Largura (desvio) da compressão global. */
  private globalSigma(params: SqueezeDeformationParams): number {
    const half = Math.max(this.body.width, this.body.depth) / 2;
    // locality 0 → muito largo (uniforme); 1 → ~40 % da meia-largura.
    return half * (0.4 + 6 * Math.pow(1 - clamp(params.locality, 0, 1), 2));
  }

  private bulgeSigma(): number {
    return 0.75 * Math.max(this.body.width, this.body.depth);
  }

  /** Peso da compressão global: 1 dentro do contato, gaussiano fora. */
  private globalWeight(rho: number, contactRadius: number, sigma: number): number {
    const d = Math.max(0, rho - contactRadius);
    return Math.exp(-(d * d) / (2 * sigma * sigma));
  }

  /** Atenuação vertical da indentação (material profundo se move menos). */
  private depthWeight(y: number, lambda: number): number {
    const H = this.body.height;
    const s = y / H;
    return Math.exp(-Math.max(0, H - y) / lambda) * smooth01(s / 0.2);
  }

  /** Deforma a malha para o estado dado. Não aloca memória. */
  apply(tool: SqueezeToolState, params: SqueezeDeformationParams): void {
    const rest = this.mesh.positions;
    const restNormals = this.mesh.normals;
    const areas = this.vertexAreas;
    const out = this.positions;
    const H = this.body.height;
    const R = Math.max(1e-4, tool.radius);
    const shapeR = Math.max(R, tool.profileRadius);
    const indent = Math.max(0, tool.indent);
    const contactRadius = solveContactRadius(indent, shapeR);
    const sigmaG = this.globalSigma(params);
    const sigmaB = this.bulgeSigma();
    const lambda = Math.max(shapeR * 0.9, contactRadius * 1.6, 0.15 * H);
    // Além deste raio a saia gaussiana é desprezível (< 1e-5): pula o cálculo de Hertz.
    const localReach = contactRadius + 3.5 * Math.max(1e-4, params.falloff);

    // Passada 1: deslocamento vertical + peso do bulging, acumulando volumes na própria
    // malha (ΔV ≈ Σ Aᵢ · nᵢ · dᵢ, com Aᵢ = área associada ao vértice).
    let verticalVolume = 0;
    let bulgePerUnit = 0;
    for (let v = 0, i = 0; v < rest.length; v += 3, i++) {
      const x0 = rest[v] as number;
      const y0 = rest[v + 1] as number;
      const z0 = rest[v + 2] as number;
      const s = clamp(y0 / H, 0, 1);
      const dxT = x0 - tool.x;
      const dzT = z0 - tool.z;
      const rho = Math.sqrt(dxT * dxT + dzT * dzT);
      const global = tool.squash * s * this.globalWeight(rho, contactRadius, sigmaG);
      const local =
        indent > 0 && rho < localReach
          ? indentationProfile(rho, indent, contactRadius, shapeR, params.falloff) *
            this.depthWeight(y0, lambda)
          : 0;
      const dy = -global - local;
      const nx = restNormals[v] as number;
      const ny = restNormals[v + 1] as number;
      const nz = restNormals[v + 2] as number;
      const weight =
        bulgeProfile(s, params.bulgeHeight) * Math.exp(-(rho * rho) / (2 * sigmaB * sigmaB));
      const area = areas[i] as number;
      // Estiramento vertical local (∂y/∂y₀): a lateral comprimida tem menos área para
      // receber o bulging, então cada unidade de amplitude rende menos volume.
      const stretch = Math.max(0.05, 1 - global / Math.max(1e-6, y0) - local / lambda);
      verticalVolume += area * ny * dy;
      bulgePerUnit += area * (nx * nx + nz * nz) * weight * stretch;
      this.scratchDy[i] = dy;
      this.scratchBulge[i] = weight;
    }
    const displaced = -verticalVolume;
    const bulgeAmplitude =
      bulgePerUnit > 0
        ? (displaced * clamp(params.volumePreservation, 0, 1.5) * clamp(params.bulge, 0, 3)) /
          bulgePerUnit
        : 0;

    // Passada 2: posições finais, restrição de contato e oclusão.
    let clamped = 0;
    const R2 = R * R;
    for (let v = 0, i = 0; v < rest.length; v += 3, i++) {
      const bulge = bulgeAmplitude * (this.scratchBulge[i] as number);
      const x = (rest[v] as number) + (restNormals[v] as number) * bulge;
      const z = (rest[v + 2] as number) + (restNormals[v + 2] as number) * bulge;
      let y = (rest[v + 1] as number) + (this.scratchDy[i] as number);

      // Contato: projeção vertical para a calota inferior da esfera.
      const ddx = x - tool.x;
      const ddz = z - tool.z;
      const r2 = ddx * ddx + ddz * ddz;
      if (r2 < R2 && y < tool.y) {
        const surface = tool.y - Math.sqrt(R2 - r2);
        if (y > surface) {
          y = surface;
          clamped++;
        }
      }
      // O chão é rígido.
      if (y < 0) y = 0;

      out[v] = x;
      out[v + 1] = y;
      out[v + 2] = z;

      // Oclusão: escurece perto da ferramenta (contato) e rente ao chão (apoio).
      const ddy = y - tool.y;
      const gap = Math.max(0, Math.sqrt(r2 + ddy * ddy) - R);
      const ao =
        (1 - CONTACT_OCCLUSION * Math.exp(-gap / (0.22 * R))) *
        (1 - GROUND_OCCLUSION * Math.exp(-y / (0.06 * H)));
      this.occlusion[v] = ao;
      this.occlusion[v + 1] = ao;
      this.occlusion[v + 2] = ao;
    }

    computeVertexNormalsInto(out, this.mesh.indices, this.normals);
    this.diagnostics.contactRadius = contactRadius;
    this.diagnostics.bulgeAmplitude = bulgeAmplitude;
    this.diagnostics.displacedVolume = displaced;
    this.diagnostics.clampedVertices = clamped;
  }
}

function smooth01(x: number): number {
  const t = clamp(x, 0, 1);
  return t * t * (3 - 2 * t);
}
