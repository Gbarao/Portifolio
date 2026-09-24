import {
  CanvasTexture,
  Color,
  Fog,
  FogExp2,
  Mesh,
  MeshStandardMaterial,
  PlaneGeometry,
  SRGBColorSpace,
  type Scene,
  type Sphere,
} from 'three';
import type { Disposable } from '../core/Disposable';
import type { BackgroundSettings } from '../presets/PresetSchema';

const css = (hex: number): string => `#${hex.toString(16).padStart(6, '0')}`;

/** Gera a textura de fundo (gradiente/padrão) com a proporção da saída para evitar distorção. */
export function drawBackground(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  settings: BackgroundSettings,
): void {
  const main = css(settings.colorMain);
  const secondary = css(settings.colorSecondary);
  if (settings.gradientMode === 'radial') {
    const radius = Math.hypot(width, height) / 2;
    const g = ctx.createRadialGradient(width / 2, height / 2, 0, width / 2, height / 2, radius);
    g.addColorStop(0, main);
    g.addColorStop(1, secondary);
    ctx.fillStyle = g;
  } else {
    const g = ctx.createLinearGradient(0, 0, 0, height);
    g.addColorStop(0, main);
    g.addColorStop(1, secondary);
    ctx.fillStyle = g;
  }
  ctx.fillRect(0, 0, width, height);

  if (settings.type !== 'pattern' || settings.pattern === 'none') return;
  const cell = Math.max(8, (Math.max(width, height) / 22) * settings.patternScale);
  ctx.globalAlpha = 0.14;
  ctx.fillStyle = css(settings.patternColor);
  ctx.strokeStyle = css(settings.patternColor);
  ctx.lineWidth = Math.max(1, cell / 40);
  if (settings.pattern === 'grid') {
    ctx.beginPath();
    for (let x = (width % cell) / 2; x <= width; x += cell) {
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
    }
    for (let y = (height % cell) / 2; y <= height; y += cell) {
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
    }
    ctx.stroke();
  } else {
    const r = Math.max(1, cell / 14);
    for (let x = (width % cell) / 2; x <= width; x += cell) {
      for (let y = (height % cell) / 2; y <= height; y += cell) {
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }
  ctx.globalAlpha = 1;
}

/** Fundo (cor/gradiente/padrão), névoa e chão opcional. */
export class BackgroundManager implements Disposable {
  private texture: CanvasTexture | null = null;
  readonly ground: Mesh<PlaneGeometry, MeshStandardMaterial>;

  constructor(private readonly scene: Scene) {
    this.ground = new Mesh(new PlaneGeometry(1, 1), new MeshStandardMaterial());
    this.ground.name = 'ground';
    this.ground.rotation.x = -Math.PI / 2;
    this.ground.receiveShadow = true;
    scene.add(this.ground);
  }

  apply(settings: BackgroundSettings, _bounds: Sphere, aspect: number): void {
    this.texture?.dispose();
    this.texture = null;
    if (settings.type === 'solid' || typeof document === 'undefined') {
      this.scene.background = new Color(settings.colorMain);
    } else {
      const height = 1024;
      const width = Math.max(64, Math.round(height * aspect));
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        drawBackground(ctx, width, height, settings);
        this.texture = new CanvasTexture(canvas);
        this.texture.colorSpace = SRGBColorSpace;
        this.scene.background = this.texture;
      } else {
        this.scene.background = new Color(settings.colorMain);
      }
    }

    const fogColor = settings.fogMatchBackground
      ? settings.type === 'solid'
        ? settings.colorMain
        : settings.colorSecondary
      : settings.fogColor;
    if (!settings.fogEnabled) {
      this.scene.fog = null;
    } else if (settings.fogType === 'exponential') {
      this.scene.fog = new FogExp2(fogColor, settings.fogDensity);
    } else {
      this.scene.fog = new Fog(
        fogColor,
        settings.fogNear,
        Math.max(settings.fogNear + 1, settings.fogFar),
      );
    }

    const g = this.ground;
    g.visible = settings.groundEnabled;
    g.position.y = settings.groundHeight;
    g.scale.set(settings.groundSize, settings.groundSize, 1);
    g.material.color.setHex(settings.groundColor);
    g.material.roughness = settings.groundRoughness;
    g.material.metalness = settings.groundMetalness;
    const transparent = settings.groundOpacity < 1;
    if (g.material.transparent !== transparent) g.material.needsUpdate = true;
    g.material.transparent = transparent;
    g.material.opacity = settings.groundOpacity;
    g.material.depthWrite = !transparent;
  }

  dispose(): void {
    this.texture?.dispose();
    this.texture = null;
    this.ground.removeFromParent();
    this.ground.geometry.dispose();
    this.ground.material.dispose();
    this.scene.background = null;
    this.scene.fog = null;
  }
}
