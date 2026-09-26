import { DEFAULT_PRESSURE_TIMING, type PressureTiming } from './animation/PressureCurve';

/**
 * Configuração do gerador Satisfying Objects. Independente do ScenePreset do Marble Run:
 * saída (resolução, FPS, duração) continua vindo de `output`/`loop` do preset principal.
 */

/** Ações previstas na arquitetura. Implementada no MVP: somente 'squeeze'. */
export type SatisfyingActionId = 'squeeze';
export const FUTURE_ACTIONS = ['crush', 'stretch', 'push', 'pinch', 'roll'] as const;

export type SoftShapeId = 'softBlock';
export type PressureToolId = 'sphere';
export type ToolFinishId = 'chrome' | 'satinMetal' | 'ceramic' | 'glass';

export type SatisfyingMaterialId =
  | 'softRubber'
  | 'glossyGel'
  | 'slime'
  | 'foam'
  | 'silicone'
  | 'wax'
  | 'softPlastic'
  | 'butter'
  | 'candy';

export type SatisfyingLightingId =
  | 'cleanStudio'
  | 'softWhite'
  | 'pastel'
  | 'candy'
  | 'darkPremium'
  | 'neon'
  | 'warmProduct'
  | 'monochrome';

export type SatisfyingToneMapping = 'neutral' | 'agx' | 'aces';

export interface SoftObjectSettings {
  shape: SoftShapeId;
  width: number;
  height: number;
  depth: number;
  /** Raio das arestas arredondadas. */
  roundness: number;
  /** Subdivisões por unidade (malha). */
  subdivision: number;
}

export interface SatisfyingMaterialSettings {
  type: SatisfyingMaterialId;
  color: number;
  roughness: number;
  metalness: number;
  clearcoat: number;
  clearcoatRoughness: number;
  sheen: number;
  sheenColor: number;
  sheenRoughness: number;
  transmission: number;
  thickness: number;
  attenuationColor: number;
  specularIntensity: number;
  ior: number;
}

export interface PressureSettings {
  tool: PressureToolId;
  toolRadius: number;
  toolFinish: ToolFinishId;
  toolColor: number;
  /** Profundidade máxima como fração da altura do objeto. */
  strength: number;
  /** Folga acima do objeto em repouso (unidades). */
  approachHeight: number;
  /** Deslocamento horizontal do ponto de pressão (fração da meia-largura/profundidade). */
  offsetX: number;
  offsetZ: number;
  /** Pressões por loop (inteiro ≥ 1). */
  cycles: number;
  /** Fluência durante o hold (fração da profundidade). */
  creep: number;
  timing: PressureTiming;
}

export interface DeformationSettings {
  /** Parcela absorvida pela compressão do corpo inteiro (0–0.9). */
  softness: number;
  /** 0 = recupera rápido; 1 = memory foam. */
  viscosity: number;
  /** Rebote elástico (0–1). */
  elasticity: number;
  bulge: number;
  volumePreservation: number;
  /** Largura da saia da indentação (unidades). */
  falloff: number;
  /** 0 = compressão uniforme; 1 = localizada. */
  locality: number;
  /** Altura relativa do pico do bulging. */
  bulgeHeight: number;
}

export interface MacroCameraSettings {
  fov: number;
  /** Distância ao alvo (unidades). 0 = enquadramento automático. */
  distance: number;
  /** Elevação em graus (0 = na altura do alvo). */
  elevation: number;
  /** Azimute em graus (0 = de frente). */
  azimuth: number;
  /** Altura do alvo (fração da altura do objeto). */
  targetHeight: number;
  /** Amplitude da órbita sutil em graus. */
  orbitAmplitude: number;
  /** Amplitude do "respiro" de distância (fração). */
  dollyAmplitude: number;
  /** Ciclos inteiros por loop. */
  cycles: number;
  /** Margem de enquadramento (fração da largura da imagem). */
  framingMargin: number;
}

export interface SatisfyingLightingSettings {
  preset: SatisfyingLightingId;
  intensity: number;
  exposure: number;
  key: number;
  fill: number;
  rim: number;
  top: number;
  environment: number;
  ambient: number;
  shadowSoftness: number;
  toneMapping: SatisfyingToneMapping;
  keyColor: number;
  rimColor: number;
}

export interface SatisfyingBackgroundSettings {
  /** Cor da parede do ciclorama. */
  color: number;
  /** Cor do piso. */
  floorColor: number;
  /** Intensidade da sombra de contato (0–1). */
  contactShadow: number;
}

export interface SatisfyingSettings {
  action: SatisfyingActionId;
  object: SoftObjectSettings;
  material: SatisfyingMaterialSettings;
  pressure: PressureSettings;
  deformation: DeformationSettings;
  camera: MacroCameraSettings;
  lighting: SatisfyingLightingSettings;
  background: SatisfyingBackgroundSettings;
}

export function createDefaultSatisfyingSettings(): SatisfyingSettings {
  return {
    action: 'squeeze',
    object: {
      shape: 'softBlock',
      width: 2.2,
      height: 1.5,
      depth: 2.2,
      roundness: 0.42,
      subdivision: 36,
    },
    material: {
      type: 'glossyGel',
      color: 0xff5c9a,
      roughness: 0.32,
      metalness: 0,
      clearcoat: 1,
      clearcoatRoughness: 0.08,
      sheen: 0.35,
      sheenColor: 0xffd1e3,
      sheenRoughness: 0.45,
      transmission: 0,
      thickness: 1,
      attenuationColor: 0xff2f7d,
      specularIntensity: 0.6,
      ior: 1.45,
    },
    pressure: {
      tool: 'sphere',
      toolRadius: 0.72,
      toolFinish: 'ceramic',
      toolColor: 0xf7f5f2,
      strength: 0.42,
      approachHeight: 2.4,
      offsetX: 0,
      offsetZ: 0,
      cycles: 1,
      creep: 0.06,
      timing: { ...DEFAULT_PRESSURE_TIMING },
    },
    deformation: {
      softness: 0.4,
      viscosity: 0.35,
      elasticity: 0.55,
      bulge: 1,
      volumePreservation: 1,
      falloff: 0.55,
      locality: 0.55,
      bulgeHeight: 0.6,
    },
    camera: {
      fov: 30,
      distance: 0,
      elevation: 20,
      azimuth: 28,
      targetHeight: 0.9,
      orbitAmplitude: 3,
      dollyAmplitude: 0.015,
      cycles: 1,
      framingMargin: 0.05,
    },
    lighting: {
      preset: 'softWhite',
      intensity: 1,
      exposure: 1,
      key: 2.4,
      fill: 0.7,
      rim: 1.6,
      top: 1.4,
      environment: 0.6,
      ambient: 0.35,
      shadowSoftness: 7,
      toneMapping: 'neutral',
      keyColor: 0xfff4ea,
      rimColor: 0xffffff,
    },
    background: {
      color: 0xefc3d5,
      floorColor: 0xf9e3ec,
      contactShadow: 0.55,
    },
  };
}
