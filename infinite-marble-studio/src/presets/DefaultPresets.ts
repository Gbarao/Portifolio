import { DEFAULT_CUSTOM_COLORS } from '../marbles/MarbleColorPalette';
import { createPresetPoints } from '../path/PathFactory';
import { PathModel } from '../path/PathModel';
import {
  PRESET_VERSION,
  type BackgroundSettings,
  type CameraSettings,
  type LightingPresetId,
  type LightingSettings,
  type LoopSettings,
  type MarbleSettings,
  type OutputSettings,
  type PathSettings,
  type ScenePreset,
  type TrackSettings,
} from './PresetSchema';

export const DEFAULT_SEED = 20240611;

export function createDefaultOutput(): OutputSettings {
  return {
    width: 1080,
    height: 1920,
    fps: 30,
    durationSeconds: 8,
    resolutionPreset: 'vertical',
    fileName: '',
    bitrateMbps: 5,
    codec: 'vp8',
    encoder: 'mediaRecorder',
    autoLoop: true,
  };
}

export function createDefaultLoop(): LoopSettings {
  return { durationSeconds: 8, fps: 60, cycleCount: 1 };
}

export function createDefaultPath(): PathSettings {
  return {
    preset: 'wave3d',
    points: createPresetPoints('wave3d'),
    closed: true,
    curveType: 'centripetal',
    tension: 0.5,
  };
}

export function createDefaultTrack(): TrackSettings {
  return {
    style: 'tube',
    radius: 0.3,
    railDistance: 1.0,
    railRadius: 0.15,
    color: 0x2a2f45,
    metalness: 0.6,
    roughness: 0.35,
    emissive: 0x000000,
    emissiveIntensity: 0,
    opacity: 1,
    segmentCount: 200,
    radialSegments: 16,
    castShadow: true,
    receiveShadow: true,
    visible: true,
    bankAngle: 0,
    finish: 'smooth',
    clearcoat: 0,
    supports: false,
    supportColor: 0x3b3f48,
  };
}

export function createDefaultMarbles(): MarbleSettings {
  return {
    count: 24,
    radius: 0.15,
    spacing: 0,
    cycleCount: 1,
    direction: 1,
    phaseInitial: 0,
    palette: 'rainbow',
    customColors: [...DEFAULT_CUSTOM_COLORS],
    metalness: 0.8,
    roughness: 0.2,
    emissive: 0x000000,
    emissiveIntensity: 0,
    castShadow: true,
    receiveShadow: false,
    offsetLateral: 0,
    offsetVertical: 0,
    scaleVariation: 0,
    pattern: 'solid',
    spinAuto: true,
    spinCycles: 1,
    hueShiftCycles: 0,
    pulseAmount: 0,
    pulseCycles: 1,
    segments: 32,
    clearcoat: 0,
  };
}

export function createDefaultCamera(): CameraSettings {
  return {
    mode: 'fixed',
    fov: 50,
    distance: 14,
    height: 3,
    offsetLateral: 0,
    target: { x: 0, y: 0, z: 0 },
    position: { x: 0, y: 7, z: 13 },
    cycleCount: 1,
    smoothing: 0.5,
    tilt: 0,
    autoFrame: true,
    framingMargin: 0.1,
    followMarbleIndex: 0,
    railLookAhead: 0.03,
    railPhaseOffset: -0.02,
    swayAmount: 0,
  };
}

/** Presets de iluminação armazenados como JSON estruturado. */
export const LIGHTING_PRESETS: Record<Exclude<LightingPresetId, 'custom'>, LightingSettings> = {
  darkNeon: {
    preset: 'darkNeon',
    ambientIntensity: 0.35,
    mainLightIntensity: 2.4,
    fillLightIntensity: 1.0,
    rimLightIntensity: 2.2,
    exposure: 1.1,
    shadowsEnabled: true,
    shadowResolution: 1024,
    shadowBias: -0.0005,
    shadowSoftness: 2,
    globalIntensity: 1,
    environmentIntensity: 0.35,
    toneMapping: 'linear',
    skyColor: 0x5b2a9e,
    groundColor: 0x05010d,
    mainColor: 0xff3fd8,
    mainPosition: { x: 6, y: 10, z: 7 },
    fillColor: 0x00e5ff,
    fillPosition: { x: -9, y: 4, z: 3 },
    rimColor: 0x8a5cff,
    rimPosition: { x: 0, y: 6, z: -11 },
    pulseAmount: 0,
    pulseCycles: 2,
  },
  cleanStudio: {
    preset: 'cleanStudio',
    ambientIntensity: 0.7,
    mainLightIntensity: 1.4,
    fillLightIntensity: 0.6,
    rimLightIntensity: 0.5,
    exposure: 1.0,
    shadowsEnabled: false,
    shadowResolution: 1024,
    shadowBias: -0.0005,
    shadowSoftness: 2,
    globalIntensity: 1,
    environmentIntensity: 0.55,
    toneMapping: 'linear',
    skyColor: 0xffffff,
    groundColor: 0xc9ced8,
    mainColor: 0xffffff,
    mainPosition: { x: 5, y: 10, z: 8 },
    fillColor: 0xeef3ff,
    fillPosition: { x: -7, y: 3, z: 5 },
    rimColor: 0xffffff,
    rimPosition: { x: 0, y: 5, z: -9 },
    pulseAmount: 0,
    pulseCycles: 1,
  },
  pastel: {
    preset: 'pastel',
    ambientIntensity: 0.55,
    mainLightIntensity: 1.2,
    fillLightIntensity: 0.5,
    rimLightIntensity: 0.45,
    exposure: 0.95,
    shadowsEnabled: true,
    shadowResolution: 1024,
    shadowBias: -0.0005,
    shadowSoftness: 2,
    globalIntensity: 1,
    environmentIntensity: 0.45,
    toneMapping: 'linear',
    skyColor: 0xffe4f2,
    groundColor: 0xd6f5ff,
    mainColor: 0xfff1e0,
    mainPosition: { x: 4, y: 10, z: 7 },
    fillColor: 0xd7c8ff,
    fillPosition: { x: -7, y: 3, z: 4 },
    rimColor: 0xc8fff0,
    rimPosition: { x: 0, y: 5, z: -9 },
    pulseAmount: 0,
    pulseCycles: 1,
  },
  metallicGold: {
    preset: 'metallicGold',
    ambientIntensity: 0.4,
    mainLightIntensity: 2.6,
    fillLightIntensity: 1.0,
    rimLightIntensity: 1.5,
    exposure: 1.1,
    shadowsEnabled: true,
    shadowResolution: 2048,
    shadowBias: -0.0004,
    shadowSoftness: 2,
    globalIntensity: 1,
    environmentIntensity: 0.9,
    toneMapping: 'linear',
    skyColor: 0xfff1c1,
    groundColor: 0x3b2a12,
    mainColor: 0xffd27a,
    mainPosition: { x: 6, y: 9, z: 6 },
    fillColor: 0xffb347,
    fillPosition: { x: -8, y: 3, z: 3 },
    rimColor: 0xfff4d6,
    rimPosition: { x: -2, y: 6, z: -10 },
    pulseAmount: 0,
    pulseCycles: 1,
  },
  woodenWarm: {
    preset: 'woodenWarm',
    ambientIntensity: 0.45,
    mainLightIntensity: 2.8,
    fillLightIntensity: 0.9,
    rimLightIntensity: 0.9,
    exposure: 1.0,
    shadowsEnabled: true,
    shadowResolution: 2048,
    shadowBias: -0.0004,
    shadowSoftness: 2,
    globalIntensity: 1,
    environmentIntensity: 0.6,
    toneMapping: 'linear',
    skyColor: 0xffe0b8,
    groundColor: 0x4a2a14,
    mainColor: 0xffb070,
    mainPosition: { x: 10, y: 6, z: 5 },
    fillColor: 0xffd6a0,
    fillPosition: { x: -7, y: 2, z: 4 },
    rimColor: 0xffc080,
    rimPosition: { x: 0, y: 5, z: -10 },
    pulseAmount: 0,
    pulseCycles: 1,
  },
  softStudio: {
    preset: 'softStudio',
    ambientIntensity: 0.6,
    mainLightIntensity: 2.7,
    fillLightIntensity: 0.85,
    rimLightIntensity: 0.7,
    exposure: 1.0,
    shadowsEnabled: true,
    shadowResolution: 2048,
    shadowBias: -0.0004,
    shadowSoftness: 5,
    globalIntensity: 1,
    environmentIntensity: 0.55,
    toneMapping: 'neutral',
    skyColor: 0xfff4ea,
    groundColor: 0xc9a58a,
    mainColor: 0xfff1e2,
    mainPosition: { x: 5, y: 12, z: 7 },
    fillColor: 0xffe6d2,
    fillPosition: { x: -8, y: 4, z: 5 },
    rimColor: 0xffffff,
    rimPosition: { x: 0, y: 6, z: -10 },
    pulseAmount: 0,
    pulseCycles: 1,
  },
};

export const LIGHTING_PRESET_LABELS: Record<LightingPresetId, string> = {
  darkNeon: 'Dark Neon',
  cleanStudio: 'Clean Studio',
  pastel: 'Pastel',
  metallicGold: 'Metallic Gold',
  woodenWarm: 'Wooden Warm',
  softStudio: 'Soft Studio',
  custom: 'Custom',
};

export function createLightingPreset(id: Exclude<LightingPresetId, 'custom'>): LightingSettings {
  return structuredClone(LIGHTING_PRESETS[id]);
}

export function createDefaultLighting(): LightingSettings {
  return createLightingPreset('darkNeon');
}

export function createDefaultBackground(): BackgroundSettings {
  return {
    type: 'gradient',
    colorMain: 0x1a1236,
    colorSecondary: 0x020206,
    gradientMode: 'vertical',
    pattern: 'none',
    patternColor: 0xffffff,
    patternScale: 1,
    fogEnabled: false,
    fogType: 'linear',
    fogColor: 0x0b0b18,
    fogMatchBackground: true,
    fogNear: 18,
    fogFar: 60,
    fogDensity: 0.03,
    groundEnabled: false,
    groundHeight: -6,
    groundColor: 0x141420,
    groundOpacity: 1,
    groundSize: 80,
    groundRoughness: 0.85,
    groundMetalness: 0,
    decorations: false,
  };
}

export function createDefaultProject(): ScenePreset {
  return {
    version: PRESET_VERSION,
    name: 'Infinite Marble',
    description: 'Projeto padrão: onda 3D com 24 bolinhas.',
    seed: DEFAULT_SEED,
    timestamp: 0,
    output: createDefaultOutput(),
    loop: createDefaultLoop(),
    path: createDefaultPath(),
    track: createDefaultTrack(),
    marbles: createDefaultMarbles(),
    camera: createDefaultCamera(),
    lighting: createDefaultLighting(),
    background: createDefaultBackground(),
  };
}

type PresetOverrides = {
  [K in keyof ScenePreset]?: ScenePreset[K] extends object
    ? Partial<ScenePreset[K]>
    : ScenePreset[K];
};

function buildPreset(overrides: PresetOverrides): ScenePreset {
  const base = createDefaultProject();
  return {
    ...base,
    ...overrides,
    output: { ...base.output, ...overrides.output },
    loop: { ...base.loop, ...overrides.loop },
    path: { ...base.path, ...overrides.path } as PathSettings,
    track: { ...base.track, ...overrides.track },
    marbles: { ...base.marbles, ...overrides.marbles },
    camera: { ...base.camera, ...overrides.camera },
    lighting: { ...base.lighting, ...overrides.lighting },
    background: { ...base.background, ...overrides.background },
  } as ScenePreset;
}

function pathFor(
  id:
    | 'circle'
    | 'figureEight'
    | 'wave3d'
    | 'toroidalSpiral'
    | 'torusKnot'
    | 'coilTower'
    | 'spiralTower',
): PathSettings {
  return {
    preset: id,
    points: createPresetPoints(id),
    closed: true,
    curveType: 'centripetal',
    tension: 0.5,
  };
}

/** Altura do chão logo abaixo do ponto mais baixo do trajeto (o trilho "encosta" no chão). */
function groundUnder(path: PathSettings, clearance: number): number {
  const model = new PathModel(path);
  return Number((model.boundingBox.min.y - clearance).toFixed(2));
}

const COIL_PATH = pathFor('coilTower');
const TOWER_PATH = pathFor('spiralTower');

/** Presets de cena prontos (built-in). */
export const BUILT_IN_PRESETS: readonly ScenePreset[] = [
  buildPreset({
    name: 'Wooden Coil',
    description: 'Canaleta de madeira em torre espiral, bolinhas brilhantes, estúdio suave.',
    seed: 7070,
    path: TOWER_PATH,
    track: {
      style: 'groove',
      radius: 0.46,
      color: 0xe0955a,
      finish: 'wood',
      metalness: 0,
      roughness: 0.42,
      clearcoat: 0.5,
      segmentCount: 400,
      radialSegments: 14,
      supports: true,
      supportColor: 0xdcc9a8,
    },
    marbles: {
      count: 10,
      radius: 0.33,
      palette: 'custom',
      customColors: [0x12857c, 0xe5531a],
      metalness: 0,
      roughness: 0.16,
      clearcoat: 1,
    },
    camera: { mode: 'fixed', position: { x: 3, y: 6.5, z: 12.5 }, framingMargin: 0.08 },
    lighting: createLightingPreset('softStudio'),
    background: {
      type: 'solid',
      colorMain: 0xe8c29e,
      fogEnabled: true,
      fogType: 'linear',
      fogMatchBackground: true,
      fogNear: 22,
      fogFar: 60,
      groundEnabled: true,
      groundHeight: groundUnder(TOWER_PATH, 0.56),
      groundColor: 0xe8c29e,
      groundRoughness: 0.95,
      decorations: true,
    },
  }),
  buildPreset({
    name: 'Blue Coaster',
    description: 'Canaleta azul com hastes metálicas, rampa ondulada e bolinhas de vidro.',
    seed: 8080,
    path: COIL_PATH,
    track: {
      style: 'groove',
      radius: 0.3,
      color: 0x1f6fe5,
      metalness: 0,
      roughness: 0.28,
      clearcoat: 0.8,
      segmentCount: 400,
      radialSegments: 14,
      supports: true,
      supportColor: 0x3a342f,
    },
    marbles: {
      count: 20,
      radius: 0.19,
      palette: 'custom',
      customColors: [0x1d2a44, 0xe9e3d8, 0x8a4a2c, 0x3b6d46, 0xb3262a, 0x6a6a6a],
      metalness: 0.05,
      roughness: 0.06,
      clearcoat: 1,
    },
    camera: { mode: 'fixed', position: { x: -6, y: 10, z: 9 }, framingMargin: 0.06 },
    lighting: { ...createLightingPreset('softStudio'), mainPosition: { x: -6, y: 12, z: 6 } },
    background: {
      type: 'solid',
      colorMain: 0xd8cfc2,
      fogEnabled: true,
      fogType: 'linear',
      fogMatchBackground: true,
      fogNear: 22,
      fogFar: 60,
      groundEnabled: true,
      groundHeight: groundUnder(COIL_PATH, 0.38),
      groundColor: 0xd8cfc2,
      groundRoughness: 0.95,
    },
  }),
  buildPreset({
    name: 'Mesmerizing Circle',
    description: 'Círculo simples, bolinhas neon, câmera fixa.',
    seed: 1111,
    path: pathFor('circle'),
    track: { radius: 0.14, color: 0x1c1c2e, metalness: 0.9, roughness: 0.25, bankAngle: -90 },
    marbles: {
      count: 24,
      radius: 0.32,
      palette: 'neon',
      metalness: 0.3,
      roughness: 0.2,
      emissive: 0x220033,
      emissiveIntensity: 0.4,
    },
    camera: { mode: 'fixed', position: { x: 0, y: 0, z: 16 }, framingMargin: 0.15 },
    lighting: createLightingPreset('darkNeon'),
    background: {
      type: 'gradient',
      gradientMode: 'radial',
      colorMain: 0x241046,
      colorSecondary: 0x030108,
    },
  }),
  buildPreset({
    name: 'Golden Spiral',
    description: 'Espiral toroidal, iluminação quente, câmera em órbita.',
    seed: 2222,
    path: pathFor('toroidalSpiral'),
    track: {
      radius: 0.09,
      color: 0x4a3418,
      metalness: 0.85,
      roughness: 0.3,
      segmentCount: 400,
      radialSegments: 10,
    },
    marbles: {
      count: 60,
      radius: 0.2,
      palette: 'metal',
      metalness: 1,
      roughness: 0.12,
      cycleCount: 1,
    },
    camera: { mode: 'orbit', height: 5, cycleCount: 1, position: { x: 0, y: 5, z: 14 } },
    lighting: createLightingPreset('metallicGold'),
    background: { type: 'gradient', colorMain: 0x3a2610, colorSecondary: 0x0b0704 },
  }),
  buildPreset({
    name: 'Twisted Figure',
    description: 'Figura de oito, câmera acompanhando, cores pastéis.',
    seed: 3333,
    path: pathFor('figureEight'),
    track: {
      style: 'dualRail',
      railDistance: 0.5,
      railRadius: 0.06,
      color: 0x8c7fc0,
      metalness: 0.3,
      roughness: 0.4,
      radialSegments: 10,
    },
    marbles: { count: 20, radius: 0.2, palette: 'pastels', metalness: 0.15, roughness: 0.3 },
    camera: { mode: 'follow', distance: 5, height: 2.2, smoothing: 0.6, fov: 55 },
    lighting: createLightingPreset('pastel'),
    background: {
      type: 'gradient',
      colorMain: 0xf2c4dc,
      colorSecondary: 0xaebfe8,
      groundEnabled: true,
      groundHeight: -3,
      groundColor: 0xd9c8e6,
    },
  }),
  buildPreset({
    name: 'Dark Loop',
    description: 'Torus knot, iluminação neon, fundo escuro.',
    seed: 4444,
    path: pathFor('torusKnot'),
    track: {
      radius: 0.11,
      color: 0x10101c,
      metalness: 0.9,
      roughness: 0.3,
      emissive: 0x2a0055,
      emissiveIntensity: 0.5,
      segmentCount: 400,
    },
    marbles: {
      count: 72,
      radius: 0.17,
      palette: 'neon',
      metalness: 0.4,
      roughness: 0.2,
      emissive: 0x1a0030,
      emissiveIntensity: 0.6,
    },
    camera: { mode: 'orbit', height: 6, cycleCount: 1, position: { x: 0, y: 6, z: 14 } },
    lighting: createLightingPreset('darkNeon'),
    background: {
      type: 'solid',
      colorMain: 0x05030c,
      fogEnabled: true,
      fogType: 'exponential',
      fogDensity: 0.02,
    },
  }),
  buildPreset({
    name: 'Minimalist',
    description: 'Circuito simples, iluminação de estúdio, monocromático.',
    seed: 5555,
    path: pathFor('wave3d'),
    track: { radius: 0.18, color: 0x3a3a3a, metalness: 0.2, roughness: 0.5 },
    marbles: {
      count: 24,
      radius: 0.2,
      palette: 'custom',
      customColors: [0x151515, 0xf4f4f4],
      metalness: 0.1,
      roughness: 0.35,
    },
    camera: { mode: 'fixed', position: { x: 0, y: 9, z: 11 } },
    lighting: createLightingPreset('cleanStudio'),
    background: {
      type: 'solid',
      colorMain: 0xd9d9d9,
      groundEnabled: true,
      groundHeight: -2.5,
      groundColor: 0xcfcfcf,
    },
  }),
];

export function findBuiltInPreset(name: string): ScenePreset | undefined {
  const preset = BUILT_IN_PRESETS.find((p) => p.name === name);
  return preset ? structuredClone(preset) : undefined;
}
