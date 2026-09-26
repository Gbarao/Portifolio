import { clamp, lerp } from '../../core/MathUtils';

/**
 * Coreografia de uma pressão, em frações do ciclo (0 → 1):
 *
 *   0 ─ repouso ─ approachStart ─ aproximação ─ contact ─ compressão ─ peak
 *     ─ hold ─ holdEnd ─ ferramenta sobe ─ toolReleaseEnd
 *     … bloco recupera (viscosidade + rebote elástico) … recoveryEnd ─ repouso ─ 1
 *
 * Tudo é função pura do tempo: nada é acumulado entre frames.
 */
export interface PressureTiming {
  approachStart: number;
  contact: number;
  peak: number;
  holdEnd: number;
  toolReleaseEnd: number;
  recoveryEnd: number;
}

export const DEFAULT_PRESSURE_TIMING: Readonly<PressureTiming> = {
  approachStart: 0.06,
  contact: 0.28,
  peak: 0.48,
  holdEnd: 0.6,
  toolReleaseEnd: 0.76,
  recoveryEnd: 0.95,
};

export interface PressureMotion {
  /** Folga entre a ferramenta e o topo do bloco em repouso (unidades de cena). */
  approachHeight: number;
  /** Profundidade de pressão no pico (unidades de cena). */
  maxDepth: number;
  /** Afundamento extra durante o hold (fração de maxDepth) — "fluência" do material. */
  creep: number;
  /** Parcela da pressão absorvida pela compressão global do bloco (0 = só local). */
  globalShare: number;
  /** 0 = recuperação rápida; 1 = lenta (memory foam). */
  viscosity: number;
  /** 0 = sem rebote; 1 = gelatina bem elástica. */
  bounce: number;
}

export interface PressureState {
  /** Quanto a ferramenta desceu desde a posição de repouso. */
  toolTravel: number;
  /** Penetração da ferramenta abaixo do topo em repouso (≥ 0). */
  toolDepth: number;
  /** Profundidade da indentação local no eixo da ferramenta (≥ 0). */
  indent: number;
  /** Compressão global no topo (positiva = achatado, negativa = esticado no rebote). */
  squash: number;
  /** Ferramenta tocando o bloco. */
  contact: boolean;
  /** Pressão normalizada em relação ao pico (0–1+). */
  pressure: number;
  /** Progresso da recuperação livre (0 durante a carga → 1 no repouso). */
  recovery: number;
}

export function createPressureState(): PressureState {
  return {
    toolTravel: 0,
    toolDepth: 0,
    indent: 0,
    squash: 0,
    contact: false,
    pressure: 0,
    recovery: 0,
  };
}

/** Rejeita cronogramas fora de ordem (retorna mensagens de erro; vazio = válido). */
export function validatePressureTiming(timing: PressureTiming): string[] {
  const keys: (keyof PressureTiming)[] = [
    'approachStart',
    'contact',
    'peak',
    'holdEnd',
    'toolReleaseEnd',
    'recoveryEnd',
  ];
  const errors: string[] = [];
  let previous = 0;
  for (const key of keys) {
    const value = timing[key];
    if (!Number.isFinite(value)) {
      errors.push(`timing.${key}: valor não finito.`);
      continue;
    }
    if (value < previous || value > 1) {
      errors.push(`timing.${key}: ${value} fora de ordem (esperado entre ${previous} e 1).`);
    }
    previous = Math.max(previous, value);
  }
  if (timing.contact - timing.approachStart < 0.02)
    errors.push('timing: aproximação curta demais.');
  if (timing.peak - timing.contact < 0.02) errors.push('timing: compressão curta demais.');
  if (timing.toolReleaseEnd - timing.holdEnd < 0.02) errors.push('timing: soltura curta demais.');
  if (timing.recoveryEnd - timing.holdEnd < 0.04) errors.push('timing: recuperação curta demais.');
  return errors;
}

/** Quíntica com derivadas 1ª e 2ª nulas nas bordas. */
export function smootherstep(edge0: number, edge1: number, x: number): number {
  if (edge1 === edge0) return x < edge0 ? 0 : 1;
  const t = clamp((x - edge0) / (edge1 - edge0), 0, 1);
  return t * t * t * (t * (t * 6 - 15) + 10);
}

/** Hermite cúbica: valores p0/p1 e derivadas m0/m1 (em unidades por fração do intervalo). */
function hermite(p0: number, m0: number, p1: number, m1: number, u: number): number {
  const u2 = u * u;
  const u3 = u2 * u;
  return (
    (2 * u3 - 3 * u2 + 1) * p0 + (u3 - 2 * u2 + u) * m0 + (-2 * u3 + 3 * u2) * p1 + (u3 - u2) * m1
  );
}

/**
 * Descida da ferramenta: acelera na aproximação, toca o bloco com velocidade não nula
 * e desacelera até parar no pico (resistência do material). Monotônica (Fritsch–Carlson).
 */
export function evaluateToolTravel(
  t: number,
  timing: PressureTiming,
  motion: PressureMotion,
): number {
  const approach = Math.max(0, motion.approachHeight);
  const depth = Math.max(0, motion.maxDepth);
  const full = approach + depth;
  const hold = full + depth * Math.max(0, motion.creep);
  const { approachStart, contact, peak, holdEnd, toolReleaseEnd } = timing;
  if (t <= approachStart || t >= toolReleaseEnd) return 0;
  if (t < peak) {
    const d1 = contact - approachStart;
    const d2 = peak - contact;
    const s1 = approach / d1;
    const s2 = depth / d2;
    const vc = s1 + s2 > 0 ? (2 * s1 * s2) / (s1 + s2) : 0;
    if (t < contact) return hermite(0, 0, approach, vc * d1, (t - approachStart) / d1);
    return hermite(approach, vc * d2, full, 0, (t - contact) / d2);
  }
  if (t < holdEnd) return lerp(full, hold, smootherstep(peak, holdEnd, t));
  return hold * (1 - smootherstep(holdEnd, toolReleaseEnd, t));
}

/** Decaimento viscoso monotônico 1 → 0 (derivada nula no fim). */
export function viscousDecay(tau: number, viscosity: number): number {
  const p = lerp(0.55, 1.6, clamp(viscosity, 0, 1));
  return 1 - smootherstep(0, 1, Math.pow(clamp(tau, 0, 1), p));
}

/** Oscilação elástica amortecida 1 → 0, com derivada nula em τ = 0 e τ = 1. */
export function elasticDecay(tau: number, bounce: number): number {
  const b = clamp(bounce, 0, 1);
  const x = clamp(tau, 0, 1);
  const omega = 2 * Math.PI * lerp(0.9, 2.6, b);
  const damping = lerp(10, 3.2, b);
  const envelope = (1 + damping * x) * Math.exp(-damping * x);
  return Math.cos(omega * x) * envelope * (1 - smootherstep(0.55, 1, x));
}

/** Estado completo da pressão em t ∈ [0, 1). Periódico: t = 0 e t = 1 dão o mesmo estado. */
export function evaluatePressure(
  t: number,
  timing: PressureTiming,
  motion: PressureMotion,
  out: PressureState = createPressureState(),
): PressureState {
  const time = t - Math.floor(t);
  const approach = Math.max(0, motion.approachHeight);
  const depth = Math.max(0, motion.maxDepth);
  const share = clamp(motion.globalShare, 0, 0.9);
  const travel = evaluateToolTravel(time, timing, motion);
  const toolDepth = Math.max(0, travel - approach);

  let total: number;
  let squash: number;
  let recovery = 0;
  if (time < timing.holdEnd) {
    total = toolDepth;
    squash = share * total;
  } else {
    const holdDepth = depth * (1 + Math.max(0, motion.creep));
    const tau = (time - timing.holdEnd) / Math.max(1e-6, timing.recoveryEnd - timing.holdEnd);
    recovery = smootherstep(0, 1, tau);
    squash = share * holdDepth * elasticDecay(tau, motion.bounce);
    const freeIndent = (1 - share) * holdDepth * viscousDecay(tau, motion.viscosity);
    // Restrição de contato: a superfície não pode ficar acima da ferramenta.
    total = Math.max(squash + freeIndent, toolDepth);
  }
  const indent = Math.max(0, total - squash);
  out.toolTravel = travel;
  out.toolDepth = toolDepth;
  out.indent = indent;
  out.squash = squash;
  out.contact = toolDepth > 0 && toolDepth >= squash + indent - 1e-9;
  out.pressure = depth > 0 ? (squash + indent) / depth : 0;
  out.recovery = recovery;
  return out;
}

/**
 * Instante (na fase de carga) em que a pressão atinge `fraction` do pico.
 * Usado para capturas de validação (0 %, 25 %, 50 %, 75 %, 100 %).
 */
export function timeForPressure(
  fraction: number,
  timing: PressureTiming,
  motion: PressureMotion,
): number {
  const target = clamp(fraction, 0, 1);
  if (target <= 0) return timing.contact;
  if (target >= 1) return timing.peak;
  let lo = timing.contact;
  let hi = timing.peak;
  const state = createPressureState();
  for (let i = 0; i < 60; i++) {
    const mid = (lo + hi) / 2;
    evaluatePressure(mid, timing, motion, state);
    if (state.pressure < target) lo = mid;
    else hi = mid;
  }
  return (lo + hi) / 2;
}
