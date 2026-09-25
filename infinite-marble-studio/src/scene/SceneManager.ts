import {
  GridHelper,
  PerspectiveCamera,
  Scene,
  type BufferGeometry,
  type Material,
  type Object3D,
  type Texture,
  type WebGLRenderTarget,
} from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { createCameraPose, type CameraPose } from '../camera/CameraRig';
import type { Disposable } from '../core/Disposable';
import { MarbleSystem } from '../marbles/MarbleSystem';
import { PathHandles } from '../path/PathHandles';
import type { ScenePreset, SectionKey, TrackSettings, Vec3Like } from '../presets/PresetSchema';
import { SupportManager } from '../track/SupportBuilder';
import { TrackManager } from '../track/TrackManager';
import { BackgroundManager } from './BackgroundManager';
import { DecorationManager } from './DecorationManager';
import { LightingManager } from './LightingManager';
import type { RendererManager } from './RendererManager';
import { Simulation } from './Simulation';

export type DirtySection = SectionKey | 'seed' | 'all';

export interface RenderStats {
  drawCalls: number;
  triangles: number;
  geometries: number;
  textures: number;
  memoryBytes: number;
}

const TRACK_GEOMETRY_KEYS: readonly (keyof TrackSettings)[] = [
  'style',
  'radius',
  'railDistance',
  'railRadius',
  'segmentCount',
  'radialSegments',
];

/** Aplica uma pose calculada a uma câmera Three.js. */
export function applyCameraPose(camera: PerspectiveCamera, pose: CameraPose, aspect: number): void {
  camera.position.copy(pose.position);
  camera.up.copy(pose.up);
  camera.lookAt(pose.target);
  if (pose.tilt !== 0) camera.rotateX(pose.tilt);
  if (camera.fov !== pose.fov || camera.aspect !== aspect) {
    camera.fov = pose.fov;
    camera.aspect = aspect;
    camera.updateProjectionMatrix();
  }
  camera.updateMatrixWorld();
}

/** Estimativa aproximada de memória de GPU (geometrias, texturas, sombras). */
export function estimateMemoryBytes(
  scene: Scene,
  shadowResolution: number,
  shadows: boolean,
): number {
  const geometries = new Set<BufferGeometry>();
  const textures = new Set<Texture>();
  let bytes = 0;
  scene.traverse((node: Object3D) => {
    const candidate = node as Object3D & {
      geometry?: BufferGeometry;
      material?: Material | Material[];
      instanceMatrix?: { array: ArrayLike<number> & { byteLength: number } };
      instanceColor?: { array: { byteLength: number } } | null;
    };
    if (candidate.geometry && !geometries.has(candidate.geometry)) {
      geometries.add(candidate.geometry);
      for (const attribute of Object.values(candidate.geometry.attributes)) {
        bytes += (attribute.array as { byteLength: number }).byteLength;
      }
      const index = candidate.geometry.index;
      if (index) bytes += (index.array as { byteLength: number }).byteLength;
    }
    if (candidate.instanceMatrix) bytes += candidate.instanceMatrix.array.byteLength;
    if (candidate.instanceColor) bytes += candidate.instanceColor.array.byteLength;
    const materials = candidate.material ? ([] as Material[]).concat(candidate.material) : [];
    for (const material of materials) {
      for (const value of Object.values(material)) {
        if ((value as Texture | null)?.isTexture) textures.add(value as Texture);
      }
    }
  });
  const background = scene.background as Texture | null;
  if (background?.isTexture) textures.add(background);
  for (const texture of textures) {
    const image = texture.image as { width?: number; height?: number } | null;
    if (image?.width && image.height) bytes += image.width * image.height * 4 * 1.33;
  }
  if (scene.environment) bytes += 256 * 256 * 6 * 8 * 1.5;
  if (shadows) bytes += shadowResolution * shadowResolution * 4;
  return bytes;
}

/**
 * Orquestra a cena Three.js: trilho, bolinhas, luzes, fundo, câmeras e helpers de edição.
 * Toda animação é derivada de `renderAt(normalizedTime)`.
 */
export class SceneManager implements Disposable {
  readonly scene = new Scene();
  readonly rigCamera = new PerspectiveCamera(50, 9 / 16, 0.05, 500);
  readonly editorCamera = new PerspectiveCamera(50, 9 / 16, 0.05, 500);
  readonly simulation: Simulation;
  readonly handles: PathHandles;
  private readonly lighting: LightingManager;
  private readonly background: BackgroundManager;
  private readonly track: TrackManager;
  private readonly supports: SupportManager;
  private readonly decorations: DecorationManager;
  private marbles: MarbleSystem;
  private readonly grid = new GridHelper(24, 24, 0x5566aa, 0x2a3050);
  private readonly rigControls: OrbitControls;
  private readonly editorControls: OrbitControls;
  private readonly pose = createCameraPose();
  private project: ScenePreset;
  private lastTrack: TrackSettings;
  private helpersVisible = true;
  private editorView = false;
  private capturing = false;
  private suppressControlEvents = false;

  /** Chamado quando o usuário move a câmera fixa com OrbitControls. */
  onFixedCameraEdited: ((position: Vec3Like, target: Vec3Like) => void) | null = null;
  /** Fim da interação com a câmera fixa (para registrar no histórico). */
  onFixedCameraEditEnd: (() => void) | null = null;

  constructor(
    private readonly rendererManager: RendererManager,
    project: ScenePreset,
  ) {
    this.project = project;
    this.lastTrack = structuredClone(project.track);
    this.simulation = new Simulation(project);
    const renderer = rendererManager.renderer;

    this.lighting = new LightingManager(this.scene, project.lighting);
    this.lighting.ensureEnvironment(renderer);
    this.background = new BackgroundManager(this.scene);
    this.track = new TrackManager(this.scene, project.track);
    this.supports = new SupportManager(this.scene);
    this.decorations = new DecorationManager(this.scene);
    this.marbles = new MarbleSystem(this.simulation.kinematics, project.marbles);
    this.scene.add(this.marbles.mesh);

    this.grid.name = 'editor-grid';
    const gridMaterial = this.grid.material as Material;
    gridMaterial.transparent = true;
    gridMaterial.opacity = 0.35;
    this.scene.add(this.grid);

    this.handles = new PathHandles(this.scene, this.rigCamera, rendererManager.canvas);

    this.rigControls = new OrbitControls(this.rigCamera, rendererManager.canvas);
    this.rigControls.enableDamping = false;
    this.rigControls.addEventListener('change', () => {
      if (this.suppressControlEvents) return;
      const p = this.rigCamera.position;
      const t = this.rigControls.target;
      this.onFixedCameraEdited?.({ x: p.x, y: p.y, z: p.z }, { x: t.x, y: t.y, z: t.z });
    });
    this.rigControls.addEventListener('end', () => this.onFixedCameraEditEnd?.());
    this.editorControls = new OrbitControls(this.editorCamera, rendererManager.canvas);
    this.editorControls.enableDamping = false;
    this.handles.onDraggingChanged = (dragging) => {
      this.rigControls.enabled = !dragging && this.isRigControlAllowed();
      this.editorControls.enabled = !dragging && this.editorView && !this.capturing;
    };

    this.applyChanges(project, new Set<DirtySection>(['all']));
    this.syncEditorCamera();
  }

  get activeCamera(): PerspectiveCamera {
    return this.editorView && !this.capturing ? this.editorCamera : this.rigCamera;
  }

  get isEditorView(): boolean {
    return this.editorView;
  }

  get marbleSystem(): MarbleSystem {
    return this.marbles;
  }

  private isRigControlAllowed(): boolean {
    return this.project.camera.mode === 'fixed' && !this.editorView && !this.capturing;
  }

  private updateControlState(): void {
    this.rigControls.enabled = this.isRigControlAllowed();
    this.editorControls.enabled = this.editorView && !this.capturing;
    this.handles.setCamera(this.activeCamera);
    this.suppressControlEvents = true;
    const target = this.project.camera.target;
    this.rigControls.target.set(target.x, target.y, target.z);
    this.suppressControlEvents = false;
  }

  /** Aplica as seções alteradas do projeto (reconstruindo apenas o necessário). */
  applyChanges(project: ScenePreset, dirty: ReadonlySet<DirtySection>): void {
    this.project = project;
    const all = dirty.has('all');
    const renderer = this.rendererManager.renderer;
    const trackGeometryChanged = TRACK_GEOMETRY_KEYS.some(
      (key) => this.lastTrack[key] !== project.track[key],
    );
    const bankChanged = this.lastTrack.bankAngle !== project.track.bankAngle;
    const pathDirty = all || dirty.has('path') || bankChanged;
    const trackDirty = pathDirty || (dirty.has('track') && trackGeometryChanged);

    if (all || dirty.has('output')) {
      this.rendererManager.setOutputSize(project.output.width, project.output.height);
    }
    if (pathDirty) {
      this.simulation.rebuildPath(project);
    } else if (dirty.has('marbles') || dirty.has('seed') || trackDirty) {
      this.simulation.rebuildMarbles(project);
    } else if (dirty.has('camera') || dirty.has('output')) {
      this.simulation.rebuildCamera(project);
    }
    if (all || dirty.has('loop')) this.simulation.updateLoop(project);

    const bounds = this.simulation.path.boundingSphere;
    if (trackDirty) {
      this.track.rebuild(this.simulation.path, project.track, project.seed);
    } else if (dirty.has('track') || dirty.has('seed')) {
      this.track.applySettings(project.track, project.seed);
    }
    const background = project.background;
    if (trackDirty || dirty.has('track') || dirty.has('background')) {
      this.supports.rebuild(
        this.simulation.path,
        project.track,
        background.groundHeight,
        project.track.supports && background.groundEnabled,
      );
    }
    if (pathDirty || dirty.has('background') || dirty.has('marbles') || dirty.has('seed')) {
      this.decorations.rebuild(
        project.seed,
        bounds,
        background.groundHeight,
        this.simulation.kinematics.baseColors,
        background.decorations && background.groundEnabled,
      );
    }

    if (pathDirty || trackDirty || dirty.has('marbles') || dirty.has('seed')) {
      const needsNewMesh =
        this.marbles.count !== this.simulation.kinematics.count ||
        this.marbles.segments !== Math.round(project.marbles.segments);
      if (needsNewMesh) {
        this.marbles.dispose();
        this.marbles = new MarbleSystem(this.simulation.kinematics, project.marbles);
        this.scene.add(this.marbles.mesh);
      } else {
        this.marbles.setKinematics(this.simulation.kinematics, project.marbles);
      }
    }

    if (all || pathDirty || dirty.has('lighting')) {
      const shadowToggled = renderer.shadowMap.enabled !== project.lighting.shadowsEnabled;
      this.lighting.apply(project.lighting, bounds, renderer);
      if (shadowToggled) this.markMaterialsForUpdate();
    }
    if (all || pathDirty || dirty.has('background') || dirty.has('output')) {
      this.background.apply(
        project.background,
        bounds,
        project.output.width / project.output.height,
      );
    }
    if (pathDirty) {
      this.handles.setPoints(project.path.points, project.path.closed);
      const box = this.simulation.path.boundingBox;
      this.grid.position.set(bounds.center.x, box.min.y - 0.6, bounds.center.z);
    }
    this.lastTrack = structuredClone(project.track);
    this.updateControlState();
  }

  private markMaterialsForUpdate(): void {
    this.scene.traverse((node) => {
      const material = (node as Object3D & { material?: Material | Material[] }).material;
      if (!material) return;
      for (const m of ([] as Material[]).concat(material)) m.needsUpdate = true;
    });
  }

  /** Atualiza a cena para o tempo normalizado (sem renderizar). */
  update(normalizedTime: number): void {
    const t = this.simulation.animationTime(normalizedTime);
    this.marbles.update(t);
    this.lighting.update(t);
    this.simulation.evaluateCamera(t, this.pose);
    this.suppressControlEvents = true;
    applyCameraPose(this.rigCamera, this.pose, this.rendererManager.aspect);
    if (this.rigControls.enabled) this.rigControls.target.copy(this.pose.target);
    this.suppressControlEvents = false;
    if (this.editorCamera.aspect !== this.rendererManager.aspect) {
      this.editorCamera.aspect = this.rendererManager.aspect;
      this.editorCamera.updateProjectionMatrix();
    }
  }

  renderAt(normalizedTime: number, target: WebGLRenderTarget | null = null): void {
    this.update(normalizedTime);
    const renderer = this.rendererManager.renderer;
    renderer.setRenderTarget(target);
    renderer.render(this.scene, this.activeCamera);
    renderer.setRenderTarget(null);
  }

  setHelpersVisible(visible: boolean): void {
    this.helpersVisible = visible;
    this.refreshHelperVisibility();
  }

  get areHelpersVisible(): boolean {
    return this.helpersVisible;
  }

  private refreshHelperVisibility(): void {
    const show = this.helpersVisible && !this.capturing;
    this.grid.visible = show;
    this.handles.setVisible(show);
  }

  /** Vista de edição livre (câmera independente do rig). */
  setEditorView(enabled: boolean): void {
    if (enabled && !this.editorView) this.syncEditorCamera();
    this.editorView = enabled;
    this.updateControlState();
  }

  private syncEditorCamera(): void {
    this.update(0);
    this.editorCamera.position.copy(this.rigCamera.position);
    this.editorCamera.quaternion.copy(this.rigCamera.quaternion);
    this.editorCamera.fov = this.rigCamera.fov;
    this.editorCamera.aspect = this.rigCamera.aspect;
    this.editorCamera.updateProjectionMatrix();
    this.editorControls.target.copy(this.pose.target);
    this.editorControls.update();
  }

  /** Modo captura: sem helpers, sem controles, sempre com a câmera do rig. */
  setCaptureMode(capturing: boolean): void {
    this.capturing = capturing;
    this.refreshHelperVisibility();
    this.updateControlState();
  }

  get helpersHidden(): boolean {
    return !this.grid.visible && !this.handles.group.visible;
  }

  getStats(): RenderStats {
    const info = this.rendererManager.renderer.info;
    return {
      drawCalls: info.render.calls,
      triangles: info.render.triangles,
      geometries: info.memory.geometries,
      textures: info.memory.textures,
      memoryBytes: estimateMemoryBytes(
        this.scene,
        this.project.lighting.shadowResolution,
        this.project.lighting.shadowsEnabled,
      ),
    };
  }

  dispose(): void {
    this.rigControls.dispose();
    this.editorControls.dispose();
    this.handles.dispose();
    this.marbles.dispose();
    this.track.dispose();
    this.supports.dispose();
    this.decorations.dispose();
    this.background.dispose();
    this.lighting.dispose();
    this.grid.removeFromParent();
    this.grid.geometry.dispose();
    (this.grid.material as Material).dispose();
  }
}
