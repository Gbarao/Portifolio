import { PCFShadowMap, VSMShadowMap } from 'three';
import type { Disposable } from '../core/Disposable';
import type { RendererManager } from '../scene/RendererManager';
import type { SatisfyingSettings } from './SatisfyingSettings';
import { SqueezeScene } from './SqueezeScene';

export interface SatisfyingStats {
  vertices: number;
  triangles: number;
  deformMs: number;
}

/**
 * Ponte entre a aplicação e o gerador Satisfying Objects: mantém a SqueezeScene
 * sincronizada com as configurações (reconstruindo a malha só quando forma/seed mudam),
 * renderiza no RendererManager compartilhado e restaura o estado do renderer do Marble
 * Run ao ser desativado.
 */
export class SatisfyingController implements Disposable {
  private squeeze: SqueezeScene | null = null;
  private active = false;
  private lastDeformMs = 0;

  constructor(private readonly rendererManager: RendererManager) {}

  get isActive(): boolean {
    return this.active;
  }

  get scene(): SqueezeScene | null {
    return this.squeeze;
  }

  /** Sincroniza com as configurações. Retorna true se a malha foi reconstruída. */
  sync(settings: SatisfyingSettings, seed: number): boolean {
    const clone = structuredClone(settings);
    if (this.squeeze && this.squeeze.canUpdateInPlace(clone, seed)) {
      this.squeeze.applySettings(clone);
      return false;
    }
    this.squeeze?.dispose();
    this.squeeze = new SqueezeScene(clone, seed);
    if (this.active) this.squeeze.attachRenderer(this.rendererManager.renderer);
    return true;
  }

  activate(): void {
    this.active = true;
    const renderer = this.rendererManager.renderer;
    this.squeeze?.attachRenderer(renderer);
    if (renderer.shadowMap.type !== VSMShadowMap) {
      renderer.shadowMap.type = VSMShadowMap;
      renderer.shadowMap.needsUpdate = true;
    }
  }

  /** Devolve o renderer ao estado esperado pelo Marble Run (PCF). */
  deactivate(): void {
    this.active = false;
    const renderer = this.rendererManager.renderer;
    if (renderer.shadowMap.type !== PCFShadowMap) {
      renderer.shadowMap.type = PCFShadowMap;
      renderer.shadowMap.needsUpdate = true;
    }
  }

  renderAt(normalizedTime: number): void {
    const squeeze = this.squeeze;
    if (!squeeze) return;
    // Garante o estado do renderer (tone mapping, sombras VSM) mesmo que outro gerador
    // tenha alterado o renderer compartilhado: atribuições baratas, sem recompilação.
    squeeze.attachRenderer(this.rendererManager.renderer);
    const start = performance.now();
    squeeze.update(normalizedTime, this.rendererManager.aspect);
    this.lastDeformMs = performance.now() - start;
    const renderer = this.rendererManager.renderer;
    renderer.setRenderTarget(null);
    renderer.render(squeeze.scene, squeeze.camera);
  }

  getStats(): SatisfyingStats {
    const mesh = this.squeeze?.simulation.mesh;
    return {
      vertices: mesh?.vertexCount ?? 0,
      triangles: mesh ? mesh.indices.length / 3 : 0,
      deformMs: this.lastDeformMs,
    };
  }

  dispose(): void {
    this.squeeze?.dispose();
    this.squeeze = null;
  }
}
