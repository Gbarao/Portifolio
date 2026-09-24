export const PRESET_VERSION = 1;

export interface Vec3Like {
  x: number;
  y: number;
  z: number;
}

export type Fps = 30 | 60;
export type ResolutionPresetId = 'vertical' | 'horizontal' | 'square' | 'custom';
export type VideoCodec = 'vp8' | 'vp9';
export type CurveType = 'centripetal' | 'chordal' | 'catmullrom';
export type PathPresetId =
  | 'circle'
  | 'figureEight'
  | 'wave3d'
  | 'toroidalSpiral'
  | 'torusKnot'
  | 'sTrack'
  | 'stackedCircuit'
  | 'custom';
export type TrackStyle = 'tube' | 'dualRail';
export type PaletteId = 'rainbow' | 'metal' | 'pastels' | 'neon' | 'custom';
export type MarblePattern = 'solid' | 'striped';
export type CameraMode = 'fixed' | 'orbit' | 'follow' | 'rail' | 'topView';
export type LightingPresetId =
  'darkNeon' | 'cleanStudio' | 'pastel' | 'metallicGold' | 'woodenWarm' | 'custom';
export type ToneMappingId = 'linear' | 'aces' | 'agx' | 'neutral' | 'none';
export type BackgroundType = 'solid' | 'gradient' | 'pattern';
export type GradientMode = 'vertical' | 'radial';
export type BackgroundPattern = 'grid' | 'dots' | 'none';
export type FogType = 'linear' | 'exponential';

export interface OutputSettings {
  width: number;
  height: number;
  fps: Fps;
  /** Duração do vídeo exportado. Com autoLoop, é ajustada para múltiplo inteiro do loop. */
  durationSeconds: number;
  resolutionPreset: ResolutionPresetId;
  /** Nome customizado (vazio = padrão infinite-marble-{preset}-{seed}-{w}x{h}). */
  fileName: string;
  bitrateMbps: number;
  codec: VideoCodec;
  autoLoop: boolean;
}

export interface LoopSettings {
  /** Período da animação em segundos. */
  durationSeconds: number;
  /** Grade de frames do preview. */
  fps: Fps;
  /** Repetições inteiras da coreografia completa dentro do loop. */
  cycleCount: number;
}

export interface PathSettings {
  preset: PathPresetId;
  points: Vec3Like[];
  closed: boolean;
  curveType: CurveType;
  /** Efetivo apenas com curveType "catmullrom" (comportamento do Three.js). */
  tension: number;
}

export interface TrackSettings {
  style: TrackStyle;
  /** Raio do tubo contínuo. */
  radius: number;
  /** Distância entre os trilhos paralelos (dual rail). */
  railDistance: number;
  /** Raio de cada trilho (dual rail). */
  railRadius: number;
  color: number;
  metalness: number;
  roughness: number;
  emissive: number;
  emissiveIntensity: number;
  opacity: number;
  segmentCount: number;
  radialSegments: number;
  castShadow: boolean;
  receiveShadow: boolean;
  visible: boolean;
  /** Rotação constante (graus) dos frames em torno da tangente. */
  bankAngle: number;
}

export interface MarbleSettings {
  count: number;
  radius: number;
  /** 0 = distribuição uniforme (index / count); >0 = fração da curva entre bolinhas. */
  spacing: number;
  /** Voltas completas por ciclo (inteiro). Define a velocidade. */
  cycleCount: number;
  direction: 1 | -1;
  phaseInitial: number;
  palette: PaletteId;
  customColors: number[];
  metalness: number;
  roughness: number;
  emissive: number;
  emissiveIntensity: number;
  castShadow: boolean;
  receiveShadow: boolean;
  offsetLateral: number;
  offsetVertical: number;
  /** Variação de escala por instância (0–0.1 = ±10%), derivada da seed. */
  scaleVariation: number;
  pattern: MarblePattern;
  /** Calcula spinCycles a partir do comprimento percorrido (rolagem aproximada). */
  spinAuto: boolean;
  spinCycles: number;
  hueShiftCycles: number;
  pulseAmount: number;
  pulseCycles: number;
  segments: number;
}

export interface CameraSettings {
  mode: CameraMode;
  fov: number;
  /** Orbit: raio. Follow: distância atrás. Top view: altitude. */
  distance: number;
  height: number;
  offsetLateral: number;
  target: Vec3Like;
  /** Posição da câmera fixa. */
  position: Vec3Like;
  cycleCount: number;
  smoothing: number;
  tilt: number;
  autoFrame: boolean;
  framingMargin: number;
  followMarbleIndex: number;
  railLookAhead: number;
  railPhaseOffset: number;
  swayAmount: number;
}

export interface LightingSettings {
  preset: LightingPresetId;
  ambientIntensity: number;
  mainLightIntensity: number;
  fillLightIntensity: number;
  rimLightIntensity: number;
  exposure: number;
  shadowsEnabled: boolean;
  shadowResolution: number;
  shadowBias: number;
  globalIntensity: number;
  /** Intensidade do ambiente procedural (RoomEnvironment). 0 = desativado. */
  environmentIntensity: number;
  toneMapping: ToneMappingId;
  skyColor: number;
  groundColor: number;
  mainColor: number;
  mainPosition: Vec3Like;
  fillColor: number;
  fillPosition: Vec3Like;
  rimColor: number;
  rimPosition: Vec3Like;
  pulseAmount: number;
  pulseCycles: number;
}

export interface BackgroundSettings {
  type: BackgroundType;
  colorMain: number;
  colorSecondary: number;
  gradientMode: GradientMode;
  pattern: BackgroundPattern;
  patternColor: number;
  patternScale: number;
  fogEnabled: boolean;
  fogType: FogType;
  fogColor: number;
  fogMatchBackground: boolean;
  fogNear: number;
  fogFar: number;
  fogDensity: number;
  groundEnabled: boolean;
  groundHeight: number;
  groundColor: number;
  groundOpacity: number;
  groundSize: number;
  groundRoughness: number;
  groundMetalness: number;
}

export interface ScenePreset {
  version: number;
  name: string;
  description?: string;
  seed: number;
  timestamp: number;
  output: OutputSettings;
  loop: LoopSettings;
  path: PathSettings;
  track: TrackSettings;
  marbles: MarbleSettings;
  camera: CameraSettings;
  lighting: LightingSettings;
  background: BackgroundSettings;
}

export type SectionKey =
  'output' | 'loop' | 'path' | 'track' | 'marbles' | 'camera' | 'lighting' | 'background';

// ---------------------------------------------------------------------------
// Especificação de campos: fonte única para validação e para os controles da UI.
// `required: true` marca campos do schema v1 original; os demais recebem o valor
// padrão quando ausentes (compatibilidade com JSON escrito à mão).
// ---------------------------------------------------------------------------

export type FieldSpec =
  | {
      kind: 'number';
      min: number;
      max: number;
      step?: number;
      integer?: boolean;
      required?: boolean;
    }
  | { kind: 'boolean'; required?: boolean }
  | { kind: 'enum'; values: readonly (string | number)[]; required?: boolean }
  | { kind: 'color'; required?: boolean }
  | { kind: 'vec3'; min: number; max: number; required?: boolean }
  | { kind: 'string'; maxLength: number; required?: boolean }
  | { kind: 'colorList'; minLength: number; maxLength: number; required?: boolean };

export const MAX_EXPORT_DIMENSION = 3840;
export const MAX_EXPORT_PIXELS = 3840 * 2160;
export const MIN_EXPORT_DIMENSION = 64;
export const SHADOW_RESOLUTIONS = [512, 1024, 2048] as const;

type SpecsFor<T> = { [K in keyof T]-?: FieldSpec };

export const OUTPUT_SPECS: SpecsFor<OutputSettings> = {
  width: {
    kind: 'number',
    min: MIN_EXPORT_DIMENSION,
    max: MAX_EXPORT_DIMENSION,
    step: 2,
    integer: true,
    required: true,
  },
  height: {
    kind: 'number',
    min: MIN_EXPORT_DIMENSION,
    max: MAX_EXPORT_DIMENSION,
    step: 2,
    integer: true,
    required: true,
  },
  fps: { kind: 'enum', values: [30, 60], required: true },
  durationSeconds: { kind: 'number', min: 1, max: 300, step: 0.5, required: true },
  resolutionPreset: { kind: 'enum', values: ['vertical', 'horizontal', 'square', 'custom'] },
  fileName: { kind: 'string', maxLength: 120 },
  bitrateMbps: { kind: 'number', min: 2, max: 15, step: 0.5 },
  codec: { kind: 'enum', values: ['vp8', 'vp9'] },
  autoLoop: { kind: 'boolean' },
};

export const LOOP_SPECS: SpecsFor<LoopSettings> = {
  durationSeconds: { kind: 'number', min: 1, max: 300, step: 0.5, required: true },
  fps: { kind: 'enum', values: [30, 60], required: true },
  cycleCount: { kind: 'number', min: 1, max: 16, step: 1, integer: true, required: true },
};

export const PATH_SPECS: SpecsFor<Omit<PathSettings, 'points'>> = {
  preset: {
    kind: 'enum',
    values: [
      'circle',
      'figureEight',
      'wave3d',
      'toroidalSpiral',
      'torusKnot',
      'sTrack',
      'stackedCircuit',
      'custom',
    ],
    required: true,
  },
  closed: { kind: 'boolean', required: true },
  curveType: { kind: 'enum', values: ['centripetal', 'chordal', 'catmullrom'], required: true },
  tension: { kind: 'number', min: 0, max: 1, step: 0.01, required: true },
};

export const POINT_COORD_LIMIT = 100;
export const MIN_PATH_POINTS = 4;
export const MAX_PATH_POINTS = 256;

export const TRACK_SPECS: SpecsFor<TrackSettings> = {
  style: { kind: 'enum', values: ['tube', 'dualRail'], required: true },
  radius: { kind: 'number', min: 0.02, max: 1.5, step: 0.01, required: true },
  railDistance: { kind: 'number', min: 0.1, max: 3, step: 0.01 },
  railRadius: { kind: 'number', min: 0.02, max: 0.6, step: 0.01 },
  color: { kind: 'color', required: true },
  metalness: { kind: 'number', min: 0, max: 1, step: 0.01, required: true },
  roughness: { kind: 'number', min: 0, max: 1, step: 0.01, required: true },
  emissive: { kind: 'color', required: true },
  emissiveIntensity: { kind: 'number', min: 0, max: 1, step: 0.01, required: true },
  opacity: { kind: 'number', min: 0, max: 1, step: 0.01, required: true },
  segmentCount: { kind: 'number', min: 32, max: 400, step: 1, integer: true, required: true },
  radialSegments: { kind: 'number', min: 3, max: 32, step: 1, integer: true },
  castShadow: { kind: 'boolean', required: true },
  receiveShadow: { kind: 'boolean' },
  visible: { kind: 'boolean' },
  bankAngle: { kind: 'number', min: -180, max: 180, step: 1 },
};

export const MARBLE_SPECS: SpecsFor<MarbleSettings> = {
  count: { kind: 'number', min: 1, max: 250, step: 1, integer: true, required: true },
  radius: { kind: 'number', min: 0.05, max: 1, step: 0.01, required: true },
  spacing: { kind: 'number', min: 0, max: 1, step: 0.001, required: true },
  cycleCount: { kind: 'number', min: 1, max: 32, step: 1, integer: true, required: true },
  direction: { kind: 'enum', values: [1, -1], required: true },
  phaseInitial: { kind: 'number', min: 0, max: 1, step: 0.001, required: true },
  palette: {
    kind: 'enum',
    values: ['rainbow', 'metal', 'pastels', 'neon', 'custom'],
    required: true,
  },
  customColors: { kind: 'colorList', minLength: 1, maxLength: 16 },
  metalness: { kind: 'number', min: 0, max: 1, step: 0.01, required: true },
  roughness: { kind: 'number', min: 0, max: 1, step: 0.01, required: true },
  emissive: { kind: 'color', required: true },
  emissiveIntensity: { kind: 'number', min: 0, max: 2, step: 0.01, required: true },
  castShadow: { kind: 'boolean', required: true },
  receiveShadow: { kind: 'boolean' },
  offsetLateral: { kind: 'number', min: -2, max: 2, step: 0.01, required: true },
  offsetVertical: { kind: 'number', min: -2, max: 2, step: 0.01 },
  scaleVariation: { kind: 'number', min: 0, max: 0.1, step: 0.005 },
  pattern: { kind: 'enum', values: ['solid', 'striped'] },
  spinAuto: { kind: 'boolean' },
  spinCycles: { kind: 'number', min: 0, max: 256, step: 1, integer: true },
  hueShiftCycles: { kind: 'number', min: 0, max: 8, step: 1, integer: true },
  pulseAmount: { kind: 'number', min: 0, max: 0.5, step: 0.01 },
  pulseCycles: { kind: 'number', min: 1, max: 16, step: 1, integer: true },
  segments: { kind: 'number', min: 8, max: 64, step: 1, integer: true },
};

export const CAMERA_SPECS: SpecsFor<CameraSettings> = {
  mode: { kind: 'enum', values: ['fixed', 'orbit', 'follow', 'rail', 'topView'], required: true },
  fov: { kind: 'number', min: 20, max: 100, step: 1, required: true },
  distance: { kind: 'number', min: 2, max: 50, step: 0.1, required: true },
  height: { kind: 'number', min: -10, max: 10, step: 0.1, required: true },
  offsetLateral: { kind: 'number', min: -5, max: 5, step: 0.05, required: true },
  target: { kind: 'vec3', min: -50, max: 50, required: true },
  position: { kind: 'vec3', min: -100, max: 100 },
  cycleCount: { kind: 'number', min: 1, max: 16, step: 1, integer: true, required: true },
  smoothing: { kind: 'number', min: 0, max: 1, step: 0.01, required: true },
  tilt: { kind: 'number', min: -90, max: 90, step: 1 },
  autoFrame: { kind: 'boolean' },
  framingMargin: { kind: 'number', min: 0, max: 0.3, step: 0.01 },
  followMarbleIndex: { kind: 'number', min: 0, max: 249, step: 1, integer: true },
  railLookAhead: { kind: 'number', min: 0.005, max: 0.2, step: 0.005 },
  railPhaseOffset: { kind: 'number', min: -0.5, max: 0.5, step: 0.005 },
  swayAmount: { kind: 'number', min: 0, max: 1, step: 0.01 },
};

export const LIGHTING_SPECS: SpecsFor<LightingSettings> = {
  preset: {
    kind: 'enum',
    values: ['darkNeon', 'cleanStudio', 'pastel', 'metallicGold', 'woodenWarm', 'custom'],
    required: true,
  },
  ambientIntensity: { kind: 'number', min: 0, max: 5, step: 0.01, required: true },
  mainLightIntensity: { kind: 'number', min: 0, max: 10, step: 0.01, required: true },
  fillLightIntensity: { kind: 'number', min: 0, max: 10, step: 0.01, required: true },
  rimLightIntensity: { kind: 'number', min: 0, max: 10, step: 0.01, required: true },
  exposure: { kind: 'number', min: 0.5, max: 3, step: 0.01, required: true },
  shadowsEnabled: { kind: 'boolean', required: true },
  shadowResolution: { kind: 'enum', values: SHADOW_RESOLUTIONS, required: true },
  shadowBias: { kind: 'number', min: -0.005, max: 0.005, step: 0.0001, required: true },
  globalIntensity: { kind: 'number', min: 0, max: 3, step: 0.01 },
  environmentIntensity: { kind: 'number', min: 0, max: 3, step: 0.01 },
  toneMapping: { kind: 'enum', values: ['linear', 'aces', 'agx', 'neutral', 'none'] },
  skyColor: { kind: 'color' },
  groundColor: { kind: 'color' },
  mainColor: { kind: 'color' },
  mainPosition: { kind: 'vec3', min: -50, max: 50 },
  fillColor: { kind: 'color' },
  fillPosition: { kind: 'vec3', min: -50, max: 50 },
  rimColor: { kind: 'color' },
  rimPosition: { kind: 'vec3', min: -50, max: 50 },
  pulseAmount: { kind: 'number', min: 0, max: 1, step: 0.01 },
  pulseCycles: { kind: 'number', min: 1, max: 16, step: 1, integer: true },
};

export const BACKGROUND_SPECS: SpecsFor<BackgroundSettings> = {
  type: { kind: 'enum', values: ['solid', 'gradient', 'pattern'], required: true },
  colorMain: { kind: 'color', required: true },
  colorSecondary: { kind: 'color' },
  gradientMode: { kind: 'enum', values: ['vertical', 'radial'] },
  pattern: { kind: 'enum', values: ['grid', 'dots', 'none'] },
  patternColor: { kind: 'color' },
  patternScale: { kind: 'number', min: 0.25, max: 4, step: 0.05 },
  fogEnabled: { kind: 'boolean', required: true },
  fogType: { kind: 'enum', values: ['linear', 'exponential'] },
  fogColor: { kind: 'color', required: true },
  fogMatchBackground: { kind: 'boolean' },
  fogNear: { kind: 'number', min: 0, max: 200, step: 0.5, required: true },
  fogFar: { kind: 'number', min: 1, max: 400, step: 0.5, required: true },
  fogDensity: { kind: 'number', min: 0, max: 0.2, step: 0.001 },
  groundEnabled: { kind: 'boolean', required: true },
  groundHeight: { kind: 'number', min: -30, max: 30, step: 0.1, required: true },
  groundColor: { kind: 'color', required: true },
  groundOpacity: { kind: 'number', min: 0, max: 1, step: 0.01 },
  groundSize: { kind: 'number', min: 5, max: 400, step: 1 },
  groundRoughness: { kind: 'number', min: 0, max: 1, step: 0.01 },
  groundMetalness: { kind: 'number', min: 0, max: 1, step: 0.01 },
};

export const SECTION_SPECS = {
  output: OUTPUT_SPECS,
  loop: LOOP_SPECS,
  track: TRACK_SPECS,
  marbles: MARBLE_SPECS,
  camera: CAMERA_SPECS,
  lighting: LIGHTING_SPECS,
  background: BACKGROUND_SPECS,
} as const;

export interface ResolutionPreset {
  id: ResolutionPresetId;
  label: string;
  width: number;
  height: number;
}

export const RESOLUTION_PRESETS: readonly ResolutionPreset[] = [
  { id: 'vertical', label: 'Vertical 9:16 (1080×1920)', width: 1080, height: 1920 },
  { id: 'horizontal', label: 'Horizontal 16:9 (1920×1080)', width: 1920, height: 1080 },
  { id: 'square', label: 'Quadrado 1:1 (1080×1080)', width: 1080, height: 1080 },
  { id: 'custom', label: 'Custom', width: 1080, height: 1920 },
];

/** Clona um preset (dados JSON puros). */
export function clonePreset(preset: ScenePreset): ScenePreset {
  return structuredClone(preset);
}
