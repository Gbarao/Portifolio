import {
  ACESFilmicToneMapping,
  AgXToneMapping,
  DirectionalLight,
  HemisphereLight,
  LinearToneMapping,
  NeutralToneMapping,
  NoToneMapping,
  Object3D,
  PMREMGenerator,
  Vector3,
  type Scene,
  type Sphere,
  type Texture,
  type ToneMapping,
  type WebGLRenderer,
} from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import type { Disposable } from '../core/Disposable';
import { TAU } from '../core/MathUtils';
import type { LightingSettings, ToneMappingId, Vec3Like } from '../presets/PresetSchema';

export interface LightIntensities {
  ambient: number;
  main: number;
  fill: number;
  rim: number;
}

export function createLightIntensities(): LightIntensities {
  return { ambient: 0, main: 0, fill: 0, rim: 0 };
}

/** Intensidades no instante t. A pulsação usa ciclos inteiros: periódica por construção. */
export function evaluateLightIntensities(
  settings: LightingSettings,
  animationTime: number,
  out: LightIntensities,
): LightIntensities {
  const g = settings.globalIntensity;
  const amount = settings.pulseAmount;
  const cycles = Math.max(1, Math.round(settings.pulseCycles));
  const pulse = amount > 0 ? 1 + amount * Math.sin(TAU * cycles * animationTime) : 1;
  const counter = amount > 0 ? 1 + amount * Math.sin(TAU * (cycles * animationTime + 0.5)) : 1;
  out.ambient = settings.ambientIntensity * g;
  out.main = settings.mainLightIntensity * g * pulse;
  out.fill = settings.fillLightIntensity * g;
  out.rim = settings.rimLightIntensity * g * counter;
  return out;
}

export const TONE_MAPPINGS: Record<ToneMappingId, ToneMapping> = {
  linear: LinearToneMapping,
  aces: ACESFilmicToneMapping,
  agx: AgXToneMapping,
  neutral: NeutralToneMapping,
  none: NoToneMapping,
};

/** Hemisphere + luz principal (com sombra) + preenchimento + recorte + ambiente procedural. */
export class LightingManager implements Disposable {
  readonly hemisphere = new HemisphereLight();
  readonly main = new DirectionalLight();
  readonly fill = new DirectionalLight();
  readonly rim = new DirectionalLight();
  private readonly target = new Object3D();
  private settings: LightingSettings;
  private readonly intensities = createLightIntensities();
  private environment: Texture | null = null;
  private readonly direction = new Vector3();

  constructor(
    private readonly scene: Scene,
    settings: LightingSettings,
  ) {
    this.settings = structuredClone(settings);
    this.hemisphere.name = 'ambient-light';
    this.main.name = 'main-light';
    this.fill.name = 'fill-light';
    this.rim.name = 'rim-light';
    this.target.name = 'light-target';
    for (const light of [this.main, this.fill, this.rim]) light.target = this.target;
    this.main.shadow.normalBias = 0.02;
    scene.add(this.hemisphere, this.main, this.fill, this.rim, this.target);
  }

  /** Cria (uma vez) o mapa de ambiente procedural RoomEnvironment — sem arquivos externos. */
  ensureEnvironment(renderer: WebGLRenderer): void {
    if (this.environment) return;
    const pmrem = new PMREMGenerator(renderer);
    const room = new RoomEnvironment();
    this.environment = pmrem.fromScene(room, 0.04).texture;
    room.dispose();
    pmrem.dispose();
    this.applyEnvironment();
  }

  private applyEnvironment(): void {
    const intensity = this.settings.environmentIntensity;
    this.scene.environment = intensity > 0 ? this.environment : null;
    this.scene.environmentIntensity = intensity;
  }

  private placeLight(light: DirectionalLight, position: Vec3Like, bounds: Sphere): void {
    this.direction.set(position.x, position.y, position.z);
    const length = this.direction.length();
    if (length < 1e-6) this.direction.set(0, 1, 0);
    this.direction.normalize();
    const distance = Math.max(length, bounds.radius * 2 + 5);
    light.position.copy(bounds.center).addScaledVector(this.direction, distance);
  }

  apply(settings: LightingSettings, bounds: Sphere, renderer: WebGLRenderer | null): void {
    const previousResolution = this.settings.shadowResolution;
    this.settings = structuredClone(settings);
    this.target.position.copy(bounds.center);
    this.hemisphere.color.setHex(settings.skyColor);
    this.hemisphere.groundColor.setHex(settings.groundColor);
    this.main.color.setHex(settings.mainColor);
    this.fill.color.setHex(settings.fillColor);
    this.rim.color.setHex(settings.rimColor);
    this.placeLight(this.main, settings.mainPosition, bounds);
    this.placeLight(this.fill, settings.fillPosition, bounds);
    this.placeLight(this.rim, settings.rimPosition, bounds);

    const shadow = this.main.shadow;
    this.main.castShadow = settings.shadowsEnabled;
    shadow.bias = settings.shadowBias;
    if (
      shadow.mapSize.x !== settings.shadowResolution ||
      previousResolution !== settings.shadowResolution
    ) {
      shadow.mapSize.set(settings.shadowResolution, settings.shadowResolution);
      shadow.map?.dispose();
      shadow.map = null;
    }
    const extent = bounds.radius + 2;
    const cam = shadow.camera;
    cam.left = -extent;
    cam.right = extent;
    cam.top = extent;
    cam.bottom = -extent;
    cam.near = 0.1;
    cam.far = this.main.position.distanceTo(bounds.center) + extent * 2;
    cam.updateProjectionMatrix();

    if (renderer) {
      renderer.toneMapping = TONE_MAPPINGS[settings.toneMapping];
      renderer.toneMappingExposure = settings.exposure;
      renderer.shadowMap.enabled = settings.shadowsEnabled;
    }
    this.applyEnvironment();
    this.update(0);
  }

  update(animationTime: number): void {
    const i = evaluateLightIntensities(this.settings, animationTime, this.intensities);
    this.hemisphere.intensity = i.ambient;
    this.main.intensity = i.main;
    this.fill.intensity = i.fill;
    this.rim.intensity = i.rim;
  }

  dispose(): void {
    this.main.shadow.map?.dispose();
    this.environment?.dispose();
    this.environment = null;
    this.scene.environment = null;
    for (const obj of [this.hemisphere, this.main, this.fill, this.rim, this.target]) {
      obj.removeFromParent();
    }
    this.main.dispose();
    this.fill.dispose();
    this.rim.dispose();
    this.hemisphere.dispose();
  }
}
