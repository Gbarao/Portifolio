import type { BufferAttribute } from 'three';
import {
  Color,
  Mesh,
  PerspectiveCamera,
  Scene,
  type BufferGeometry,
  type MeshPhysicalMaterial,
  type WebGLRenderer,
} from 'three';
import type { Disposable } from '../core/Disposable';
import { createSoftBlockGeometry } from './geometry/SoftBlockGeometry';
import { SatisfyingLighting } from './lighting/SatisfyingLighting';
import { createSoftMaterial, updateSoftMaterial } from './materials/SatisfyingMaterials';
import type { PressureTool } from './pressure/PressureTool';
import { SpherePressureTool } from './pressure/SpherePressureTool';
import type { SatisfyingSettings } from './SatisfyingSettings';
import { ContactShadow } from './scene/ContactShadow';
import { StudioBackdrop } from './scene/StudioBackdrop';
import {
  createSqueezeFrameState,
  SqueezeSimulation,
  type SqueezeFrameState,
} from './SqueezeSimulation';

/**
 * Cena WebGL do squeeze: objeto macio + ferramenta + estúdio. Todo o estado vem de
 * `SqueezeSimulation.evaluate(normalizedTime)`; a cena só copia buffers e poses.
 */
export class SqueezeScene implements Disposable {
  readonly scene = new Scene();
  readonly camera = new PerspectiveCamera(30, 9 / 16, 0.1, 200);
  readonly simulation: SqueezeSimulation;
  readonly state: SqueezeFrameState = createSqueezeFrameState();
  private readonly softMesh: Mesh<BufferGeometry, MeshPhysicalMaterial>;
  private readonly tool: PressureTool;
  private readonly lighting: SatisfyingLighting;
  private backdrop: StudioBackdrop;
  private renderer: WebGLRenderer | null = null;
  private settingsValue: SatisfyingSettings;
  private readonly contactShadow: ContactShadow;
  private readonly positionAttr: BufferAttribute;
  private readonly normalAttr: BufferAttribute;
  private readonly colorAttr: BufferAttribute;

  constructor(
    settings: SatisfyingSettings,
    readonly seed: number,
  ) {
    this.settingsValue = settings;
    this.simulation = new SqueezeSimulation(settings, seed);
    const size = Math.max(settings.object.width, settings.object.height, settings.object.depth);
    this.scene.name = 'satisfying-squeeze';
    this.scene.background = new Color(settings.background.color);

    const deformer = this.simulation.deformer;
    const geometry = createSoftBlockGeometry(
      this.simulation.mesh,
      deformer.positions,
      deformer.normals,
      deformer.occlusion,
    );
    this.positionAttr = geometry.getAttribute('position') as BufferAttribute;
    this.normalAttr = geometry.getAttribute('normal') as BufferAttribute;
    this.colorAttr = geometry.getAttribute('color') as BufferAttribute;
    const material = createSoftMaterial(settings.material);
    material.vertexColors = true;
    this.softMesh = new Mesh(geometry, material);
    this.softMesh.name = 'soft-object';
    this.softMesh.castShadow = true;
    this.softMesh.receiveShadow = true;
    this.softMesh.frustumCulled = false;

    this.tool = new SpherePressureTool(settings.pressure);
    this.backdrop = new StudioBackdrop(
      size,
      settings.background.floorColor,
      settings.background.color,
    );
    this.contactShadow = new ContactShadow();
    this.contactShadow.setTint(settings.background.floorColor);
    this.lighting = new SatisfyingLighting(this.scene, settings.lighting, settings.object);
    this.lighting.setStudioColors(0xffffff, settings.background.floorColor);
    this.scene.add(this.backdrop.mesh, this.contactShadow.mesh, this.softMesh, this.tool.object);
  }

  get settings(): SatisfyingSettings {
    return this.settingsValue;
  }

  attachRenderer(renderer: WebGLRenderer): void {
    this.renderer = renderer;
    this.lighting.attachRenderer(renderer);
  }

  /** Verdadeiro se `settings` pode ser aplicado sem reconstruir a malha. */
  canUpdateInPlace(settings: SatisfyingSettings, seed: number): boolean {
    return (
      seed === this.seed && JSON.stringify(settings.object) === JSON.stringify(this.settings.object)
    );
  }

  /**
   * Aplica material, luz, fundo, ferramenta, pressão, deformação e câmera sem recriar a
   * malha (sem alocação de geometria do objeto).
   */
  applySettings(settings: SatisfyingSettings): void {
    const previous = this.settingsValue;
    this.settingsValue = settings;
    this.simulation.updateSettings(settings);
    updateSoftMaterial(this.softMesh.material, settings.material);
    this.tool.configure(settings.pressure);
    this.lighting.apply(settings.lighting);
    if (this.renderer) this.lighting.attachRenderer(this.renderer);
    const bg = settings.background;
    if (
      bg.color !== previous.background.color ||
      bg.floorColor !== previous.background.floorColor
    ) {
      (this.scene.background as Color).set(bg.color);
      const size = Math.max(settings.object.width, settings.object.height, settings.object.depth);
      this.backdrop.dispose();
      this.backdrop = new StudioBackdrop(size, bg.floorColor, bg.color);
      this.scene.add(this.backdrop.mesh);
      this.contactShadow.setTint(bg.floorColor);
      this.lighting.setStudioColors(0xffffff, bg.floorColor);
    }
  }

  /** Atualiza toda a cena para o instante normalizado (determinístico, sem acúmulo). */
  update(normalizedTime: number, aspect: number): SqueezeFrameState {
    const state = this.simulation.evaluate(normalizedTime, aspect, this.state);
    this.simulation.deform(state);
    this.positionAttr.needsUpdate = true;
    this.normalAttr.needsUpdate = true;
    this.colorAttr.needsUpdate = true;
    this.tool.update(state.tool);

    const o = this.settings.object;
    const bulge = this.simulation.deformer.diagnostics.bulgeAmplitude;
    const baseGrow = Math.max(0, bulge) * 0.25;
    this.contactShadow.update(
      o.width / 2 + baseGrow,
      o.depth / 2 + baseGrow,
      this.simulation.mesh.radius,
      Math.max(o.width, o.depth) * 0.1,
      this.settings.background.contactShadow,
    );

    const c = state.camera;
    this.camera.fov = c.fov;
    this.camera.aspect = aspect;
    this.camera.position.set(c.px, c.py, c.pz);
    this.camera.lookAt(c.tx, c.ty, c.tz);
    this.camera.updateProjectionMatrix();
    return state;
  }

  dispose(): void {
    this.lighting.dispose();
    this.tool.dispose();
    this.backdrop.dispose();
    this.contactShadow.dispose();
    this.softMesh.removeFromParent();
    this.softMesh.geometry.dispose();
    this.softMesh.material.dispose();
  }
}
