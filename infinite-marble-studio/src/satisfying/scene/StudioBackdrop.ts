import { BufferGeometry, Color, Float32BufferAttribute, Mesh, MeshStandardMaterial } from 'three';
import type { Disposable } from '../../core/Disposable';

/**
 * Ciclorama de estúdio: piso que sobe em curva suave até a parede de fundo (sem linha
 * de horizonte). Gradiente por cor de vértice do piso para a parede.
 */
export function buildCycloramaGeometry(
  size: number,
  floorColor: number,
  wallColor: number,
): BufferGeometry {
  const width = size * 14;
  const front = size * 6;
  const back = size * 2.6;
  const radius = size * 2.4;
  const wall = size * 10;
  // Perfil (z, y) do piso da frente até o topo da parede.
  const profile: [number, number][] = [];
  const floorSteps = 24;
  for (let i = 0; i <= floorSteps; i++)
    profile.push([front - ((front + back) * i) / floorSteps, 0]);
  const arcSteps = 32;
  for (let i = 1; i <= arcSteps; i++) {
    const a = (Math.PI / 2) * (i / arcSteps);
    profile.push([-back - radius * Math.sin(a), radius * (1 - Math.cos(a))]);
  }
  const wallSteps = 12;
  for (let i = 1; i <= wallSteps; i++)
    profile.push([-back - radius, radius + (wall * i) / wallSteps]);

  const columns = 24;
  const positions: number[] = [];
  const colors: number[] = [];
  const floor = new Color(floorColor);
  const wallC = new Color(wallColor);
  const mixed = new Color();
  const totalHeight = radius + wall;
  for (const [z, y] of profile) {
    const blend = Math.min(1, y / (totalHeight * 0.55));
    mixed.copy(floor).lerp(wallC, blend * blend * (3 - 2 * blend));
    for (let c = 0; c <= columns; c++) {
      positions.push(-width / 2 + (width * c) / columns, y, z);
      colors.push(mixed.r, mixed.g, mixed.b);
    }
  }
  const indices: number[] = [];
  const row = columns + 1;
  for (let r = 0; r < profile.length - 1; r++) {
    for (let c = 0; c < columns; c++) {
      const a = r * row + c;
      const b = a + row;
      indices.push(a, a + 1, b, a + 1, b + 1, b);
    }
  }
  const geometry = new BufferGeometry();
  geometry.setAttribute('position', new Float32BufferAttribute(positions, 3));
  geometry.setAttribute('color', new Float32BufferAttribute(colors, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  geometry.computeBoundingSphere();
  return geometry;
}

export class StudioBackdrop implements Disposable {
  readonly mesh: Mesh<BufferGeometry, MeshStandardMaterial>;

  constructor(size: number, floorColor: number, wallColor: number) {
    const material = new MeshStandardMaterial({
      vertexColors: true,
      roughness: 0.92,
      metalness: 0,
    });
    material.name = 'studio-backdrop';
    material.envMapIntensity = 0.2;
    // Compensa a iluminação forte do produto: o fundo fica na cor escolhida, sem estourar.
    material.color.setScalar(0.72);
    this.mesh = new Mesh(buildCycloramaGeometry(size, floorColor, wallColor), material);
    this.mesh.name = 'studio-backdrop';
    this.mesh.receiveShadow = true;
  }

  dispose(): void {
    this.mesh.removeFromParent();
    this.mesh.geometry.dispose();
    this.mesh.material.dispose();
  }
}
