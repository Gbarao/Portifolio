import { Color, Mesh, PlaneGeometry, ShaderMaterial, Vector2 } from 'three';
import type { Disposable } from '../../core/Disposable';

const vertexShader = /* glsl */ `
varying vec2 vWorld;
void main() {
  vec4 world = modelMatrix * vec4(position, 1.0);
  vWorld = world.xz;
  gl_Position = projectionMatrix * viewMatrix * world;
}
`;

const fragmentShader = /* glsl */ `
uniform vec2 uHalf;
uniform float uRadius;
uniform float uSoftness;
uniform float uOpacity;
uniform vec3 uColor;
varying vec2 vWorld;
void main() {
  // Distância com sinal até o retângulo arredondado da base do objeto.
  vec2 q = abs(vWorld) - (uHalf - vec2(uRadius));
  float d = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - uRadius;
  float outside = max(d, 0.0);
  float core = exp(-outside / (uSoftness * 0.18));
  float wide = exp(-outside / uSoftness);
  float alpha = uOpacity * (0.6 * core + 0.4 * wide);
  gl_FragColor = vec4(uColor, alpha);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}
`;

/**
 * Sombra de contato analítica (oclusão ambiente do piso) com a forma da base do objeto.
 * Complementa o shadow map: elimina a sensação de objeto flutuando.
 */
export class ContactShadow implements Disposable {
  readonly mesh: Mesh<PlaneGeometry, ShaderMaterial>;
  private readonly half = new Vector2(1, 1);
  private readonly color = new Color();

  constructor() {
    const material = new ShaderMaterial({
      vertexShader,
      fragmentShader,
      transparent: true,
      depthWrite: false,
      uniforms: {
        uHalf: { value: this.half },
        uRadius: { value: 0.2 },
        uSoftness: { value: 0.5 },
        uOpacity: { value: 0.5 },
        uColor: { value: this.color },
      },
    });
    material.name = 'contact-shadow';
    const geometry = new PlaneGeometry(1, 1);
    geometry.rotateX(-Math.PI / 2);
    this.mesh = new Mesh(geometry, material);
    this.mesh.name = 'contact-shadow';
    this.mesh.position.y = 0.002;
    this.mesh.renderOrder = 1;
  }

  /** Cor da sombra: versão escura e saturada do piso (sombra colorida, nunca cinza). */
  setTint(floorColor: number): void {
    this.color.set(floorColor).multiplyScalar(0.28);
  }

  /** Atualiza a forma (inclui o bulging atual da base). Sem alocação. */
  update(
    halfWidth: number,
    halfDepth: number,
    radius: number,
    softness: number,
    opacity: number,
  ): void {
    this.half.set(halfWidth, halfDepth);
    const u = this.mesh.material.uniforms;
    (u.uRadius as { value: number }).value = Math.min(radius, halfWidth, halfDepth);
    (u.uSoftness as { value: number }).value = Math.max(0.01, softness);
    (u.uOpacity as { value: number }).value = opacity;
    const extent = Math.max(halfWidth, halfDepth) * 2 + softness * 8;
    this.mesh.scale.set(extent, 1, extent);
  }

  dispose(): void {
    this.mesh.removeFromParent();
    this.mesh.geometry.dispose();
    this.mesh.material.dispose();
  }
}
