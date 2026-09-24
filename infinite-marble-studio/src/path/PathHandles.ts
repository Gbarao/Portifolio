import {
  BufferGeometry,
  Float32BufferAttribute,
  Group,
  Line,
  LineBasicMaterial,
  LineLoop,
  Mesh,
  MeshBasicMaterial,
  Raycaster,
  SphereGeometry,
  Vector2,
  type Camera,
  type Scene,
} from 'three';
import { TransformControls } from 'three/addons/controls/TransformControls.js';
import type { Disposable } from '../core/Disposable';
import type { Vec3Like } from '../presets/PresetSchema';

const HANDLE_RADIUS = 0.11;
const CLICK_TOLERANCE_PX = 5;

/**
 * Esferas de controle (handles) + TransformControls para edição dos pontos.
 * Visível apenas durante a edição; oculto em capturas.
 */
export class PathHandles implements Disposable {
  readonly group = new Group();
  private readonly meshes: Mesh[] = [];
  private readonly geometry = new SphereGeometry(HANDLE_RADIUS, 16, 12);
  private readonly material = new MeshBasicMaterial({
    color: 0x9fb4ff,
    depthTest: false,
    transparent: true,
    opacity: 0.55,
  });
  private readonly selectedMaterial = new MeshBasicMaterial({ color: 0xffc83d, depthTest: false });
  private readonly polylineMaterial = new LineBasicMaterial({
    color: 0x8a9bff,
    transparent: true,
    opacity: 0.45,
    depthTest: false,
  });
  private polyline: Line | null = null;
  private readonly transform: TransformControls;
  private readonly raycaster = new Raycaster();
  private readonly pointer = new Vector2();
  private pointerDown: { x: number; y: number } | null = null;
  private selected: number | null = null;
  private visible = true;

  onPointMoved: ((index: number, position: Vec3Like) => void) | null = null;
  onDragEnd: ((index: number) => void) | null = null;
  onSelect: ((index: number | null) => void) | null = null;
  onDraggingChanged: ((dragging: boolean) => void) | null = null;

  constructor(
    private readonly scene: Scene,
    private camera: Camera,
    private readonly domElement: HTMLElement,
  ) {
    this.group.name = 'path-handles';
    this.group.renderOrder = 10;
    scene.add(this.group);
    this.transform = new TransformControls(camera, domElement);
    this.transform.setSize(0.8);
    const helper = this.transform.getHelper();
    helper.name = 'transform-gizmo';
    scene.add(helper);

    this.transform.addEventListener('objectChange', () => {
      const obj = this.transform.object;
      if (this.selected === null || !obj) return;
      this.updatePolylineVertex(this.selected, obj.position.x, obj.position.y, obj.position.z);
      this.onPointMoved?.(this.selected, {
        x: obj.position.x,
        y: obj.position.y,
        z: obj.position.z,
      });
    });
    this.transform.addEventListener('dragging-changed', (event) => {
      const dragging = Boolean(event.value);
      this.onDraggingChanged?.(dragging);
      if (!dragging && this.selected !== null) this.onDragEnd?.(this.selected);
    });

    domElement.addEventListener('pointerdown', this.handlePointerDown);
    domElement.addEventListener('pointerup', this.handlePointerUp);
  }

  get selectedIndex(): number | null {
    return this.selected;
  }

  get isDragging(): boolean {
    return this.transform.dragging;
  }

  setCamera(camera: Camera): void {
    this.camera = camera;
    this.transform.camera = camera;
  }

  setVisible(visible: boolean): void {
    this.visible = visible;
    this.group.visible = visible;
    if (this.polyline) this.polyline.visible = visible;
    this.transform.enabled = visible;
    this.transform.getHelper().visible = visible && this.selected !== null;
  }

  setPoints(points: readonly Vec3Like[], closed: boolean): void {
    while (this.meshes.length > points.length) {
      const mesh = this.meshes.pop();
      mesh?.removeFromParent();
    }
    while (this.meshes.length < points.length) {
      const mesh = new Mesh(this.geometry, this.material);
      mesh.renderOrder = 10;
      this.meshes.push(mesh);
      this.group.add(mesh);
    }
    points.forEach((p, i) => {
      const mesh = this.meshes[i] as Mesh;
      mesh.userData.index = i;
      // Não sobrescreve o handle que está sendo arrastado.
      if (!(this.transform.dragging && i === this.selected)) mesh.position.set(p.x, p.y, p.z);
    });
    this.rebuildPolyline(points, closed);
    if (this.selected !== null && this.selected >= points.length) this.select(null);
    else this.select(this.selected, false);
  }

  private rebuildPolyline(points: readonly Vec3Like[], closed: boolean): void {
    if (this.polyline) {
      this.polyline.removeFromParent();
      this.polyline.geometry.dispose();
    }
    const geometry = new BufferGeometry();
    geometry.setAttribute(
      'position',
      new Float32BufferAttribute(
        points.flatMap((p) => [p.x, p.y, p.z]),
        3,
      ),
    );
    this.polyline = closed
      ? new LineLoop(geometry, this.polylineMaterial)
      : new Line(geometry, this.polylineMaterial);
    this.polyline.name = 'control-polygon';
    this.polyline.renderOrder = 9;
    this.polyline.visible = this.visible;
    this.scene.add(this.polyline);
  }

  private updatePolylineVertex(index: number, x: number, y: number, z: number): void {
    const attribute = this.polyline?.geometry.getAttribute('position');
    if (!attribute || index >= attribute.count) return;
    attribute.setXYZ(index, x, y, z);
    attribute.needsUpdate = true;
  }

  select(index: number | null, notify = true): void {
    this.selected = index;
    this.meshes.forEach((mesh, i) => {
      mesh.material = i === index ? this.selectedMaterial : this.material;
    });
    const mesh = index === null ? undefined : this.meshes[index];
    if (mesh) {
      if (this.transform.object !== mesh) this.transform.attach(mesh);
    } else {
      this.transform.detach();
    }
    this.transform.getHelper().visible = this.visible && mesh !== undefined;
    if (notify) this.onSelect?.(index);
  }

  private readonly handlePointerDown = (event: PointerEvent): void => {
    this.pointerDown = { x: event.clientX, y: event.clientY };
  };

  private readonly handlePointerUp = (event: PointerEvent): void => {
    const start = this.pointerDown;
    this.pointerDown = null;
    if (!start || !this.visible || this.transform.dragging || this.transform.axis !== null) return;
    if (Math.hypot(event.clientX - start.x, event.clientY - start.y) > CLICK_TOLERANCE_PX) return;
    const rect = this.domElement.getBoundingClientRect();
    this.pointer.set(
      ((event.clientX - rect.left) / rect.width) * 2 - 1,
      -((event.clientY - rect.top) / rect.height) * 2 + 1,
    );
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const hit = this.raycaster.intersectObjects(this.meshes, false)[0];
    if (hit) this.select(hit.object.userData.index as number);
  };

  dispose(): void {
    this.domElement.removeEventListener('pointerdown', this.handlePointerDown);
    this.domElement.removeEventListener('pointerup', this.handlePointerUp);
    this.transform.detach();
    this.transform.getHelper().removeFromParent();
    this.transform.dispose();
    this.group.removeFromParent();
    this.polyline?.removeFromParent();
    this.polyline?.geometry.dispose();
    this.geometry.dispose();
    this.material.dispose();
    this.selectedMaterial.dispose();
    this.polylineMaterial.dispose();
  }
}
