import {
  Color,
  DynamicDrawUsage,
  InstancedBufferAttribute,
  InstancedMesh,
  Matrix4,
  Quaternion,
  SphereGeometry,
  Vector3,
  type MeshPhysicalMaterial,
} from 'three';
import type { Disposable } from '../core/Disposable';
import type { MarbleSettings } from '../presets/PresetSchema';
import type { MarbleKinematics } from './MarbleKinematics';
import { applyMarbleMaterial, createMarbleMaterial } from './MarbleMaterial';

/**
 * Renderiza todas as bolinhas com um único InstancedMesh (1 draw call).
 * O loop de atualização não aloca objetos: usa vetores/matrizes temporários fixos.
 */
export class MarbleSystem implements Disposable {
  readonly mesh: InstancedMesh<SphereGeometry, MeshPhysicalMaterial>;
  private readonly material: MeshPhysicalMaterial;
  private readonly geometry: SphereGeometry;
  private kinematics: MarbleKinematics;
  private radius: number;

  private readonly position = new Vector3();
  private readonly quaternion = new Quaternion();
  private readonly scale = new Vector3();
  private readonly matrix = new Matrix4();
  private readonly color = new Color();

  constructor(kinematics: MarbleKinematics, settings: MarbleSettings) {
    this.kinematics = kinematics;
    this.radius = settings.radius;
    const segments = Math.round(settings.segments);
    this.geometry = new SphereGeometry(1, segments, Math.max(6, Math.round(segments / 2)));
    this.material = createMarbleMaterial(settings);
    this.mesh = new InstancedMesh(this.geometry, this.material, kinematics.count);
    this.mesh.name = 'marbles';
    this.mesh.instanceMatrix.setUsage(DynamicDrawUsage);
    // As posições mudam a cada frame: o bounding sphere cacheado ficaria obsoleto.
    this.mesh.frustumCulled = false;
    this.mesh.castShadow = settings.castShadow;
    this.mesh.receiveShadow = settings.receiveShadow;
    this.mesh.instanceColor = new InstancedBufferAttribute(
      new Float32Array(kinematics.count * 3),
      3,
    );
    this.writeColors(0);
  }

  get count(): number {
    return this.kinematics.count;
  }

  get segments(): number {
    return this.geometry.parameters.widthSegments;
  }

  /** Scratch objects expostos para verificação de ausência de alocação nos testes. */
  get scratch(): readonly object[] {
    return [this.position, this.quaternion, this.scale, this.matrix, this.color];
  }

  /** Troca a cinemática mantendo o mesh (mesma quantidade de instâncias). */
  setKinematics(kinematics: MarbleKinematics, settings: MarbleSettings): void {
    if (kinematics.count !== this.kinematics.count) {
      throw new Error('MarbleSystem.setKinematics: quantidade diferente exige novo MarbleSystem');
    }
    this.kinematics = kinematics;
    this.applySettings(settings);
    this.writeColors(0);
  }

  applySettings(settings: MarbleSettings): void {
    this.radius = settings.radius;
    this.mesh.castShadow = settings.castShadow;
    this.mesh.receiveShadow = settings.receiveShadow;
    applyMarbleMaterial(this.material, settings);
  }

  /** Atualiza todas as instâncias para o tempo de animação dado (∈ [0, 1)). */
  update(animationTime: number): void {
    const k = this.kinematics;
    for (let i = 0; i < k.count; i++) {
      const s = k.evaluate(i, animationTime, this.position, this.quaternion);
      this.scale.setScalar(this.radius * s);
      this.matrix.compose(this.position, this.quaternion, this.scale);
      this.mesh.setMatrixAt(i, this.matrix);
    }
    this.mesh.instanceMatrix.needsUpdate = true;
    if (k.animatedColors) this.writeColors(animationTime);
  }

  private writeColors(animationTime: number): void {
    const k = this.kinematics;
    for (let i = 0; i < k.count; i++) {
      k.evaluateColor(i, animationTime, this.color);
      this.mesh.setColorAt(i, this.color);
    }
    if (this.mesh.instanceColor) this.mesh.instanceColor.needsUpdate = true;
  }

  dispose(): void {
    this.mesh.removeFromParent();
    this.geometry.dispose();
    this.material.map?.dispose();
    this.material.dispose();
    this.mesh.dispose();
  }
}
