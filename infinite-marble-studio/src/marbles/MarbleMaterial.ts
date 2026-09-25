import { CanvasTexture, MeshPhysicalMaterial, SRGBColorSpace } from 'three';
import type { MarbleSettings } from '../presets/PresetSchema';

/** Textura procedural com faixa no equador: torna a rolagem visível. */
function createStripeTexture(): CanvasTexture | null {
  if (typeof document === 'undefined') return null;
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 128;
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#1b1b1f';
  ctx.fillRect(0, 56, canvas.width, 16);
  ctx.fillRect(0, 22, canvas.width, 5);
  ctx.fillRect(0, 101, canvas.width, 5);
  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  texture.anisotropy = 4;
  return texture;
}

export function createMarbleMaterial(settings: MarbleSettings): MeshPhysicalMaterial {
  const material = new MeshPhysicalMaterial({ color: 0xffffff });
  applyMarbleMaterial(material, settings);
  return material;
}

/** Atualiza o material in-place (sem recriar shaders quando possível). */
export function applyMarbleMaterial(
  material: MeshPhysicalMaterial,
  settings: MarbleSettings,
): void {
  material.metalness = settings.metalness;
  material.roughness = settings.roughness;
  material.emissive.setHex(settings.emissive);
  material.emissiveIntensity = settings.emissiveIntensity;
  material.clearcoat = settings.clearcoat;
  material.clearcoatRoughness = 0.06;
  const wantsStripes = settings.pattern === 'striped';
  if (wantsStripes && !material.map) {
    material.map = createStripeTexture();
    material.needsUpdate = true;
  } else if (!wantsStripes && material.map) {
    material.map.dispose();
    material.map = null;
    material.needsUpdate = true;
  }
}
