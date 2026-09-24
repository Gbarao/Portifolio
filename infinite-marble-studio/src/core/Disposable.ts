import type { Material, Object3D, Texture } from 'three';

export interface Disposable {
  dispose(): void;
}

function isTexture(value: unknown): value is Texture {
  return typeof value === 'object' && value !== null && (value as Texture).isTexture === true;
}

export function disposeMaterial(material: Material | Material[]): void {
  const list = Array.isArray(material) ? material : [material];
  for (const mat of list) {
    for (const value of Object.values(mat)) {
      if (isTexture(value)) value.dispose();
    }
    mat.dispose();
  }
}

/** Remove o objeto do pai e libera geometrias, materiais e texturas de toda a subárvore. */
export function disposeObject3D(root: Object3D): void {
  root.removeFromParent();
  root.traverse((node) => {
    const candidate = node as Object3D & {
      geometry?: { dispose(): void };
      material?: Material | Material[];
      dispose?: () => void;
    };
    candidate.geometry?.dispose();
    if (candidate.material) disposeMaterial(candidate.material);
    // InstancedMesh e outros objetos com buffers próprios.
    if (typeof candidate.dispose === 'function' && node !== root) candidate.dispose();
  });
  const rootDisposable = root as Object3D & { dispose?: () => void };
  if (typeof rootDisposable.dispose === 'function') rootDisposable.dispose();
}
