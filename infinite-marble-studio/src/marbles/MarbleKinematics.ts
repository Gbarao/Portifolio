import type { Color } from 'three';
import { Matrix4, Quaternion, Vector3 } from 'three';
import { TAU, modulo } from '../core/MathUtils';
import type { PathModel } from '../path/PathModel';
import { GROOVE_HALF_ANGLE_DEG } from '../track/GrooveTrackBuilder';
import type { MarbleSettings, TrackSettings } from '../presets/PresetSchema';
import { generateMarbleColors, generateMarbleScales } from './MarbleColorPalette';

/** Offset de fase da bolinha: uniforme (index / count) ou espaçamento fixo ao longo da curva. */
export function computePhaseOffset(index: number, count: number, spacing: number): number {
  if (count <= 0) return 0;
  return spacing > 0 ? modulo(index * spacing, 1) : index / count;
}

/** u = modulo(direção × t × ciclos + phaseOffset + fase global, 1). */
export function computeMarbleU(
  animationTime: number,
  phaseOffset: number,
  cycleCount: number,
  direction: number,
  globalPhase: number,
): number {
  return modulo(direction * animationTime * cycleCount + phaseOffset + globalPhase, 1);
}

/**
 * Altura do centro da bolinha acima da linha central do trilho.
 * Tubo: apoiada no topo. Dual rail: encaixada entre os trilhos (centralizada).
 * Canaleta: dentro do canal (altura negativa).
 */
export function computeRestHeight(
  track: Pick<TrackSettings, 'style' | 'radius' | 'railDistance' | 'railRadius'>,
  marbleRadius: number,
): number {
  if (track.style === 'tube') return track.radius + marbleRadius;
  if (track.style === 'groove') {
    // Dentro do canal: encosta no fundo. Maior que o canal: apoia nas duas bordas.
    const inner = track.radius;
    if (marbleRadius < inner) return marbleRadius - inner;
    const angle = (GROOVE_HALF_ANGLE_DEG * Math.PI) / 180;
    const rimX = inner * Math.sin(angle);
    const rimY = -inner * Math.cos(angle);
    return rimY + Math.sqrt(Math.max(0, marbleRadius * marbleRadius - rimX * rimX));
  }
  const half = track.railDistance / 2;
  const reach = track.railRadius + marbleRadius;
  return reach > half ? Math.sqrt(reach * reach - half * half) : 0;
}

/** Rotações inteiras aproximando rolagem sem deslizamento: ciclos × comprimento / circunferência. */
export function computeAutoSpinCycles(
  cycleCount: number,
  pathLength: number,
  radius: number,
): number {
  if (radius <= 0) return 0;
  return Math.max(1, Math.round((cycleCount * pathLength) / (TAU * radius)));
}

/**
 * Cinemática pura das bolinhas. Tudo é função direta do tempo de animação (sem acumulação)
 * e os objetos temporários são reutilizados (sem alocação por frame).
 */
export class MarbleKinematics {
  readonly count: number;
  readonly phaseOffsets: Float64Array;
  readonly baseScales: Float32Array;
  readonly baseColors: readonly number[];
  readonly spinCycles: number;
  readonly animatedColors: boolean;
  readonly animatedScale: boolean;

  private readonly settings: MarbleSettings;
  private readonly track: TrackSettings;

  private readonly tangent = new Vector3();
  private readonly up = new Vector3();
  private readonly side = new Vector3();
  private readonly basis = new Matrix4();
  private readonly spin = new Quaternion();
  private readonly spinAxis = new Vector3(1, 0, 0);

  constructor(
    readonly path: PathModel,
    marbles: MarbleSettings,
    track: TrackSettings,
    readonly seed: number,
  ) {
    this.settings = structuredClone(marbles);
    this.track = structuredClone(track);
    this.count = Math.max(1, Math.floor(marbles.count));
    this.phaseOffsets = new Float64Array(this.count);
    for (let i = 0; i < this.count; i++) {
      this.phaseOffsets[i] = computePhaseOffset(i, this.count, marbles.spacing);
    }
    this.baseScales = generateMarbleScales(this.count, marbles.scaleVariation, seed);
    this.baseColors = generateMarbleColors({ ...marbles, count: this.count }, seed);
    this.spinCycles = marbles.spinAuto
      ? computeAutoSpinCycles(marbles.cycleCount, path.length, marbles.radius)
      : Math.max(0, Math.round(marbles.spinCycles));
    this.animatedColors = marbles.hueShiftCycles > 0;
    this.animatedScale = marbles.pulseAmount > 0;
  }

  getU(index: number, animationTime: number): number {
    const s = this.settings;
    return computeMarbleU(
      animationTime,
      this.phaseOffsets[index] ?? 0,
      s.cycleCount,
      s.direction,
      s.phaseInitial,
    );
  }

  /** Escala relativa (1 = raio configurado) da bolinha no instante dado. */
  getScale(index: number, animationTime: number): number {
    const base = this.baseScales[index] ?? 1;
    if (!this.animatedScale) return base;
    const s = this.settings;
    const phase = this.phaseOffsets[index] ?? 0;
    return base * (1 + s.pulseAmount * Math.sin(TAU * (s.pulseCycles * animationTime + phase)));
  }

  /**
   * Escreve posição e orientação da bolinha. Retorna a escala relativa.
   */
  evaluate(
    index: number,
    animationTime: number,
    outPosition: Vector3,
    outQuaternion: Quaternion,
  ): number {
    const s = this.settings;
    const u = this.getU(index, animationTime);
    const scale = this.getScale(index, animationTime);
    this.path.getPointAt(u, outPosition);
    this.path.getFrameAt(u, this.tangent, this.up, this.side);

    const height = computeRestHeight(this.track, s.radius * scale) + s.offsetVertical;
    outPosition.addScaledVector(this.up, height).addScaledVector(this.side, s.offsetLateral);

    this.basis.makeBasis(this.side, this.up, this.tangent);
    outQuaternion.setFromRotationMatrix(this.basis);
    if (this.spinCycles > 0) {
      const phase = this.phaseOffsets[index] ?? 0;
      const angle = TAU * (this.spinCycles * animationTime * s.direction + phase);
      this.spin.setFromAxisAngle(this.spinAxis, angle);
      outQuaternion.multiply(this.spin);
    }
    return scale;
  }

  /** Cor da bolinha (com rotação periódica de matiz, se ativa). */
  evaluateColor(index: number, animationTime: number, outColor: Color): Color {
    outColor.setHex(this.baseColors[index] ?? 0xffffff);
    if (this.animatedColors) {
      outColor.offsetHSL(modulo(animationTime * this.settings.hueShiftCycles, 1), 0, 0);
    }
    return outColor;
  }
}
