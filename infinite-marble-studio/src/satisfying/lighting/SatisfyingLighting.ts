import {
  ACESFilmicToneMapping,
  AgXToneMapping,
  DirectionalLight,
  HemisphereLight,
  NeutralToneMapping,
  Object3D,
  PMREMGenerator,
  RectAreaLight,
  type Scene,
  type Texture,
  type ToneMapping,
  VSMShadowMap,
  type WebGLRenderer,
} from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { RectAreaLightUniformsLib } from 'three/addons/lights/RectAreaLightUniformsLib.js';
import type { Disposable } from '../../core/Disposable';
import type {
  SatisfyingLightingId,
  SatisfyingLightingSettings,
  SatisfyingToneMapping,
} from '../SatisfyingSettings';

export const SATISFYING_TONE_MAPPINGS: Record<SatisfyingToneMapping, ToneMapping> = {
  neutral: NeutralToneMapping,
  agx: AgXToneMapping,
  aces: ACESFilmicToneMapping,
};

type LightingValues = Omit<SatisfyingLightingSettings, 'preset'>;

/** Presets de iluminação voltados a conteúdo satisfying (curvatura, brilho, contato). */
export const SATISFYING_LIGHTING_PRESETS: Readonly<Record<SatisfyingLightingId, LightingValues>> = {
  cleanStudio: {
    intensity: 1,
    exposure: 1,
    key: 2.6,
    fill: 0.8,
    rim: 1.2,
    top: 1.2,
    environment: 0.55,
    ambient: 0.4,
    shadowSoftness: 6,
    toneMapping: 'neutral',
    keyColor: 0xffffff,
    rimColor: 0xffffff,
  },
  softWhite: {
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
  pastel: {
    intensity: 1,
    exposure: 1.05,
    key: 2.1,
    fill: 0.9,
    rim: 1.3,
    top: 1.5,
    environment: 0.7,
    ambient: 0.5,
    shadowSoftness: 8,
    toneMapping: 'neutral',
    keyColor: 0xfff0f6,
    rimColor: 0xe6f0ff,
  },
  candy: {
    intensity: 1,
    exposure: 1,
    key: 2.8,
    fill: 0.8,
    rim: 2,
    top: 1.6,
    environment: 0.75,
    ambient: 0.35,
    shadowSoftness: 6,
    toneMapping: 'agx',
    keyColor: 0xfff6f0,
    rimColor: 0xffe0f0,
  },
  darkPremium: {
    intensity: 1,
    exposure: 1,
    key: 3.2,
    fill: 0.25,
    rim: 2.8,
    top: 1.1,
    environment: 0.3,
    ambient: 0.08,
    shadowSoftness: 5,
    toneMapping: 'agx',
    keyColor: 0xfff1e0,
    rimColor: 0xcfe0ff,
  },
  neon: {
    intensity: 1,
    exposure: 1,
    key: 2.2,
    fill: 0.5,
    rim: 3,
    top: 0.8,
    environment: 0.35,
    ambient: 0.12,
    shadowSoftness: 5,
    toneMapping: 'agx',
    keyColor: 0xf3e8ff,
    rimColor: 0x3ee6ff,
  },
  warmProduct: {
    intensity: 1,
    exposure: 1,
    key: 2.7,
    fill: 0.6,
    rim: 1.5,
    top: 1.2,
    environment: 0.55,
    ambient: 0.3,
    shadowSoftness: 7,
    toneMapping: 'neutral',
    keyColor: 0xffe2c2,
    rimColor: 0xfff0dc,
  },
  monochrome: {
    intensity: 1,
    exposure: 1,
    key: 2.6,
    fill: 0.45,
    rim: 1.8,
    top: 1.3,
    environment: 0.5,
    ambient: 0.25,
    shadowSoftness: 6,
    toneMapping: 'neutral',
    keyColor: 0xffffff,
    rimColor: 0xffffff,
  },
};

export function createSatisfyingLighting(id: SatisfyingLightingId): SatisfyingLightingSettings {
  return { preset: id, ...SATISFYING_LIGHTING_PRESETS[id] };
}

export interface SubjectBounds {
  width: number;
  height: number;
  depth: number;
}

let rectAreaInitialized = false;

/**
 * Key (com sombra suave) + Fill + Rim + Soft Top (RectAreaLight) + hemisfério + ambiente
 * procedural (RoomEnvironment → PMREM). Nenhum arquivo externo.
 */
export class SatisfyingLighting implements Disposable {
  readonly key = new DirectionalLight();
  readonly fill = new DirectionalLight();
  readonly rim = new DirectionalLight();
  readonly top = new RectAreaLight(0xffffff, 1, 4, 4);
  readonly ambient = new HemisphereLight(0xffffff, 0xf0e6e0, 0.3);
  private readonly target = new Object3D();
  private environment: Texture | null = null;
  private settings: SatisfyingLightingSettings;

  constructor(
    private readonly scene: Scene,
    settings: SatisfyingLightingSettings,
    subject: SubjectBounds,
  ) {
    if (!rectAreaInitialized) {
      RectAreaLightUniformsLib.init();
      rectAreaInitialized = true;
    }
    this.settings = structuredClone(settings);
    this.key.name = 'satisfying-key';
    this.fill.name = 'satisfying-fill';
    this.rim.name = 'satisfying-rim';
    this.top.name = 'satisfying-top';
    this.ambient.name = 'satisfying-ambient';
    this.target.name = 'satisfying-light-target';
    for (const light of [this.key, this.fill, this.rim]) light.target = this.target;
    this.key.castShadow = true;
    // VSM: penumbra larga e barata (blur separável), essencial para o visual de estúdio.
    this.key.shadow.mapSize.set(1024, 1024);
    this.key.shadow.bias = -0.0006;
    this.key.shadow.normalBias = 0.02;
    this.key.shadow.blurSamples = 16;
    // Sombra projetada translúcida: o piso mantém a cor (sem manchas cinzas).
    this.key.shadow.intensity = 0.62;
    scene.add(this.target, this.key, this.fill, this.rim, this.top, this.ambient);
    this.layout(subject);
    this.apply(settings);
  }

  /** Posiciona as luzes em função do tamanho do objeto. */
  layout(subject: SubjectBounds): void {
    const size = Math.max(subject.width, subject.height, subject.depth);
    const cy = subject.height * 0.5;
    this.target.position.set(0, cy, 0);
    const d = size * 4;
    this.key.position.set(d * 0.55, cy + d * 0.95, d * 0.6);
    this.fill.position.set(-d * 0.85, cy + d * 0.35, d * 0.55);
    this.rim.position.set(-d * 0.3, cy + d * 0.7, -d * 0.9);
    this.top.position.set(0, subject.height + size * 2.2, size * 0.4);
    this.top.width = size * 2.2;
    this.top.height = size * 2.2;
    this.top.lookAt(0, subject.height, 0);
    const extent = size * 1.4;
    const cam = this.key.shadow.camera;
    cam.left = -extent;
    cam.right = extent;
    cam.top = extent;
    cam.bottom = -extent;
    cam.near = d * 0.3;
    cam.far = d * 2.5;
    cam.updateProjectionMatrix();
  }

  apply(settings: SatisfyingLightingSettings): void {
    this.settings = structuredClone(settings);
    const g = settings.intensity;
    this.key.intensity = settings.key * g;
    this.key.color.set(settings.keyColor);
    this.fill.intensity = settings.fill * g;
    this.rim.intensity = settings.rim * g;
    this.rim.color.set(settings.rimColor);
    this.top.intensity = settings.top * g;
    this.ambient.intensity = settings.ambient * g;
    this.key.shadow.radius = Math.max(1, settings.shadowSoftness * 2.5);
    this.scene.environmentIntensity = settings.environment * g;
  }

  /** Tinge a luz ambiente com as cores do estúdio (sombras coloridas, não cinzas). */
  setStudioColors(sky: number, ground: number): void {
    this.ambient.color.set(sky);
    this.ambient.groundColor.set(ground);
  }

  /** Aplica tone mapping/exposição e cria (uma vez) o ambiente procedural. */
  attachRenderer(renderer: WebGLRenderer): void {
    renderer.toneMapping = SATISFYING_TONE_MAPPINGS[this.settings.toneMapping];
    renderer.toneMappingExposure = this.settings.exposure;
    renderer.shadowMap.enabled = true;
    if (renderer.shadowMap.type !== VSMShadowMap) {
      renderer.shadowMap.type = VSMShadowMap;
      renderer.shadowMap.needsUpdate = true;
    }
    if (!this.environment) {
      const pmrem = new PMREMGenerator(renderer);
      const room = new RoomEnvironment();
      this.environment = pmrem.fromScene(room, 0.04).texture;
      room.dispose();
      pmrem.dispose();
      this.scene.environment = this.environment;
    }
  }

  dispose(): void {
    this.key.shadow.dispose();
    for (const node of [this.key, this.fill, this.rim, this.top, this.ambient, this.target]) {
      node.removeFromParent();
    }
    this.environment?.dispose();
    this.environment = null;
    this.scene.environment = null;
  }
}
